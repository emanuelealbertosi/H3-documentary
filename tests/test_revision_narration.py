"""Same-project revisions retain unchanged audio and use real measured cue grids."""
import array
import copy
import hashlib
import json
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from pipeline.engine.revision_narration import prepare_revision_pack, merge_timeline, revise_narration

ROOT = Path(__file__).resolve().parents[1]


def pack_fixture():
    return {
        'schema_version': 1, 'slug': 'test', 'width': 1920, 'height': 1080,
        'fps': 24, 'target_minutes': 10, 'voice': 'original-voice', 'voice_engine': 'tts_api',
        'voice_reference': 'assets/voices/narratore.wav', 'voice_reference_text': 'Campione del narratore.',
        'voice_api': {'provider': 'higgs', 'voice': 'original', 'seed': 42},
        'metadata': {'manual_narration': True}, 'sources': [{'id': 'S1'}],
        'maps': {'campaign': {}}, 'commanders': {},
        'scenes': [
            {'id': f'{i:02}', 'title': f'Scena {i}', 'map': 'campaign', 'sources': ['S1'],
             'lines': [f'Prima frase della scena {i}.', f'Seconda frase della scena {i}.'],
             'camera_start': [11, 43, 8], 'camera_end': [12, 44, 8],
             'arrows': [], 'commanders': [], 'sfx': [], 'focus': []}
            for i in range(1, 4)
        ],
    }


def measured(pack):
    timeline = copy.deepcopy(pack)
    for index, scene in enumerate(timeline['scenes']):
        cues = [{'index': i, 'text': line, 'spoken': line, 'start': .65 + i, 'end': 1.25 + i}
                for i, line in enumerate(scene['lines'])]
        scene.update(duration=3.5, frames=84, start=index * 3.5, end=(index + 1) * 3.5,
                     audio=f'build/test/voice/{scene["id"]}-narration.wav', cues=cues)
    timeline.update(duration=len(timeline['scenes']) * 3.5, voice_tempo=.96, timing_status='measured_tts')
    return timeline


def wav(path, seconds=.3):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        pcm = array.array('h', (round(4000 * math.sin(n * 2 * math.pi * 220 / 24000))
                               for n in range(round(seconds * 24000))))
        stream.writeframes(pcm)


def hashes(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.wav')}


def test_merge_retains_measured_audio_and_grid_while_moving_later_scenes():
    authored = pack_fixture()
    old = measured(authored)
    edited = copy.deepcopy(authored)
    edited['scenes'][0]['camera_end'] = [15, 43, 6]
    edited['scenes'][1]['lines'][0] = 'La frase è stata corretta.'
    edited['scenes'][2]['insets'] = [{'asset_id': 'new-image'}]
    replacement = copy.deepcopy(old['scenes'][1])
    replacement.update(duration=4.5, frames=108)
    replacement['cues'][0]['text'] = replacement['cues'][0]['spoken'] = edited['scenes'][1]['lines'][0]
    before = copy.deepcopy((old, edited, replacement))
    result = merge_timeline(old, edited, {'02': replacement})
    assert (old, edited, replacement) == before
    assert result['duration'] == 11.5
    assert [(s['start'], s['end']) for s in result['scenes']] == [(0, 3.5), (3.5, 8), (8, 11.5)]
    for index in (0, 2):
        for field in ('audio', 'cues', 'duration', 'frames'):
            assert result['scenes'][index][field] == old['scenes'][index][field]
    assert result['scenes'][0]['camera_end'] == [15, 43, 6]
    assert result['scenes'][2]['insets'] == [{'asset_id': 'new-image'}]


def test_preserves_original_voice_configuration_after_current_defaults_change():
    old = measured(pack_fixture())
    old['voice_delivery'] = {'style': 'calm', 'speed': .9, 'pause_seconds': .4}
    edited = pack_fixture()
    edited.update(voice='current-other-voice', voice_engine='kokoro', voice_reference='wrong.wav',
                  voice_reference_text='Wrong text', voice_api={'seed': -1}, voice_delivery={'speed': 1.1})
    revised = prepare_revision_pack(edited, old)
    for key in ('voice', 'voice_engine', 'voice_reference', 'voice_reference_text', 'voice_api', 'voice_delivery'):
        assert revised[key] == old[key]
    assert edited['voice'] == 'current-other-voice'


@pytest.mark.parametrize('reason', ['unselected_text', 'unknown_scene', 'bad_cue', 'reorder'])
def test_rejects_mismatched_partial_revision_before_accepting_timing(reason):
    authored = pack_fixture()
    old = measured(authored)
    replacements = {}
    if reason == 'unselected_text':
        authored['scenes'][0]['lines'][0] = 'Testo privo di audio nuovo.'
    elif reason == 'unknown_scene':
        replacements = {'99': copy.deepcopy(old['scenes'][0])}
    elif reason == 'bad_cue':
        old['scenes'][0]['cues'][0]['end'] = 900
    else:
        authored['scenes'].reverse()
    with pytest.raises(ValueError):
        merge_timeline(old, authored, replacements)


def test_general_history_events_are_enriched_after_full_timeline_merge():
    from pipeline.engine.common import validate_pack
    raw = json.loads((ROOT / 'pipeline/documentaries/rinascimento/documentary.json').read_text(encoding='utf-8'))
    adapted = validate_pack(raw)
    old = measured(adapted)
    first, last = old['scenes'][0], old['scenes'][-1]
    old['events'] = adapted['events'] = [
        {'id': 'test-event', 'year': 1500, 'scene_id': last['id'], 'cue': 0, 'type': 'cultural_event'},
    ]
    replacement = copy.deepcopy(first)
    replacement.update(duration=4.5, frames=108)
    result = merge_timeline(old, adapted, {first['id']: replacement})
    assert result['events'][0]['timestamp_video'] == result['scenes'][-1]['start'] + .65
    assert len(result['narration']) == len(old['scenes'])
    assert result['timing_status'] == 'measured_tts'


@pytest.mark.parametrize('explicit_delivery', [False, True])
def test_selective_synthesis_reuses_raw_clips_and_unchanged_wavs_with_real_ffmpeg(tmp_path, monkeypatch, explicit_delivery):
    from pipeline.engine import narration
    monkeypatch.setattr(narration, 'ROOT', tmp_path)
    original = pack_fixture()
    if explicit_delivery:
        original['voice_delivery'] = {'style': 'calm', 'speed': .9, 'pause_seconds': .4}
    folder = tmp_path / 'build/test/voice'
    manifest = {'backend': 'tts_api', 'items': {}}
    for scene in original['scenes']:
        for index, line in enumerate(scene['lines']):
            name = f'{scene["id"]}-{index}-raw.wav'
            wav(folder / name, .3 + index * .1)
            manifest['items'][f'{scene["id"]}:{index}'] = {
                'file': name, 'spoken_sha256': hashlib.sha256(line.encode()).hexdigest(),
            }
    (folder / 'external-voice-cache.json').write_text(json.dumps(manifest), encoding='utf-8')
    old = narration.synthesize(original)
    # A prior automatic tempo is reused for newly edited narration as well.
    if not explicit_delivery:
        old['voice_tempo'] = .96
        (tmp_path / 'build/test/timeline.json').write_text(json.dumps(old), encoding='utf-8')
    before = hashes(folder)
    edited = copy.deepcopy(original)
    edited['scenes'][1]['lines'][0] = 'Questo passaggio ora contiene la correzione.'
    new_line = edited['scenes'][1]['lines'][0]
    wav(folder / 'corrected-raw.wav', .95)
    manifest['items']['02:0'] = {'file': 'corrected-raw.wav', 'spoken_sha256': hashlib.sha256(new_line.encode()).hexdigest()}
    (folder / 'external-voice-cache.json').write_text(json.dumps(manifest), encoding='utf-8')
    calls = []

    def synthesize_subset(pack):
        calls.append(copy.deepcopy(pack))
        return narration.synthesize(pack)

    result = revise_narration(edited, ['02'], workspace=tmp_path, synthesizer=synthesize_subset)
    assert len(calls) == 1 and [s['id'] for s in calls[0]['scenes']] == ['02']
    assert calls[0]['voice_api'] == original['voice_api']
    assert calls[0]['voice_reference'] == original['voice_reference']
    assert calls[0]['voice_delivery']['speed'] == (.9 if explicit_delivery else .96)
    after = hashes(folder)
    for name, digest in before.items():
        if name != '02-narration.wav':
            assert after[name] == digest, name
    assert after['02-narration.wav'] != before['02-narration.wav']
    assert result['scenes'][0]['cues'] == old['scenes'][0]['cues']
    assert result['scenes'][2]['cues'] == old['scenes'][2]['cues']
    assert result['scenes'][2]['start'] > old['scenes'][2]['start']
    assert result['duration'] < 15  # The old 10-minute target never compresses this subset.
    assert json.loads((tmp_path / 'timeline.json').read_text(encoding='utf-8')) == result
    assert result['scenes'][1]['cues'][0]['text'] == new_line


def test_visual_only_cli_works_from_unrelated_current_directory_without_tts(tmp_path):
    candidate = tmp_path / 'candidate'
    for relative in ('engine/__init__.py', 'engine/common.py', 'engine/revision_narration.py', 'tools/revise_narration.py'):
        dest = candidate / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'pipeline' / relative, dest)
    authored = pack_fixture()
    old = measured(authored)
    for scene in old['scenes']:
        wav(candidate / scene['audio'])
    folder = candidate / 'build/test'
    (folder / 'timeline.json').write_text(json.dumps(old), encoding='utf-8')
    before = hashes(folder / 'voice')
    authored['scenes'][1]['camera_end'] = [15, 43, 4]
    (candidate / 'pack.json').write_text(json.dumps(authored), encoding='utf-8')
    response = subprocess.run([sys.executable, '-X', 'utf8', str(candidate / 'tools/revise_narration.py'),
                               '--battle', 'pack.json'], cwd=tmp_path, capture_output=True, text=True, encoding='utf-8')
    assert response.returncode == 0, response.stdout + response.stderr
    result = json.loads((folder / 'timeline.json').read_text(encoding='utf-8'))
    assert hashes(folder / 'voice') == before
    assert result['scenes'][1]['camera_end'] == [15, 43, 4]
    assert result['duration'] == old['duration']
