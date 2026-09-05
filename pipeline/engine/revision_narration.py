"""Revise selected narration scenes while retaining every other measured cue grid.

This runs in a disposable candidate workspace.  It never performs research,
selects a new voice, or changes the ordinary full-production narration path.
"""
import copy
import math
from pathlib import Path


VOICE_IDENTITY = (
    'voice', 'voice_engine', 'voice_styles', 'voice_speaker', 'voice_credit',
    'voice_reference', 'voice_reference_text', 'voice_language', 'voice_api',
    'voice_delivery', 'pronunciation', 'chatterbox_exaggeration',
    'chatterbox_cfg_weight', 'chatterbox_temperature', 'chatterbox_repetition_penalty',
)
MEASURED_FIELDS = ('duration', 'cues', 'audio', 'frames')


def prepare_revision_pack(pack, previous):
    """Adapt edited visuals and retain the completed production's voice identity."""
    from .common import validate_pack
    edited = copy.deepcopy(pack)
    for key in VOICE_IDENTITY:
        if key in previous:
            edited[key] = copy.deepcopy(previous[key])
        else:
            edited.pop(key, None)
    edited = validate_pack(edited)
    # The adapter may supply current defaults absent from a legacy timeline.
    for key in VOICE_IDENTITY:
        if key in previous:
            edited[key] = copy.deepcopy(previous[key])
        elif key not in ('voice', 'voice_engine'):
            edited.pop(key, None)
    for field in ('slug', 'fps', 'width', 'height'):
        if edited.get(field) != previous.get(field):
            raise ValueError('La revisione deve conservare il formato originale: ' + field)
    old_ids = [s['id'] for s in previous['scenes']]
    if [s['id'] for s in edited['scenes']] != old_ids or len(set(old_ids)) != len(old_ids):
        raise ValueError('La revisione deve conservare le scene e il loro ordine.')
    return edited


def _measured_scene(scene, lines, fps):
    """Reject provisional or inconsistent timing before any synthesis work."""
    duration = scene.get('duration')
    if (isinstance(duration, bool) or not isinstance(duration, (int, float))
            or not math.isfinite(duration) or duration <= 0):
        raise ValueError('Durata misurata mancante per la scena ' + scene['id'])
    if scene.get('frames') != round(duration * fps) or not scene.get('audio'):
        raise ValueError('Audio o fotogrammi mancanti per la scena ' + scene['id'])
    cues = scene.get('cues', [])
    if len(cues) != len(lines) or [c.get('text') for c in cues] != lines:
        raise ValueError('La voce non corrisponde al testo della scena ' + scene['id'])
    end = 0
    for index, cue in enumerate(cues):
        start, stop = cue.get('start'), cue.get('end')
        valid = all(not isinstance(n, bool) and isinstance(n, (int, float)) and math.isfinite(n)
                    for n in (start, stop))
        if not valid or not end <= start < stop <= duration or cue.get('index') != index:
            raise ValueError('Tempi vocali non validi per la scena ' + scene['id'])
        end = stop


def merge_timeline(previous, pack, replacements=None):
    """Merge authored visuals with measured replacements; inputs remain untouched.

    ``replacements`` is a mapping of scene IDs to newly measured scene objects,
    or the complete temporary timeline returned by ``narration.synthesize``.
    Empty replacements also support map/image-only revisions without any TTS.
    """
    edited = prepare_revision_pack(pack, previous)
    replacements = replacements or {}
    if isinstance(replacements.get('scenes'), list):
        items = replacements['scenes']
        replacements = {s['id']: s for s in items}
        if len(replacements) != len(items):
            raise ValueError('Scene vocali duplicate nella revisione.')
    old = {s['id']: s for s in previous['scenes']}
    if not set(replacements) <= set(old):
        raise ValueError('La revisione contiene una scena vocale sconosciuta.')
    result = copy.deepcopy(previous)
    result.update({k: copy.deepcopy(v) for k, v in edited.items() if k != 'scenes'})
    result['scenes'] = []
    cursor = 0.0
    for authored in edited['scenes']:
        sid = authored['id']
        measured = replacements.get(sid, old[sid])
        if sid not in replacements and authored['lines'] != old[sid]['lines']:
            raise ValueError('Il testo è cambiato senza rigenerare la voce della scena ' + sid)
        _measured_scene(measured, authored['lines'], edited['fps'])
        scene = copy.deepcopy(authored)
        scene.update({key: copy.deepcopy(measured[key]) for key in MEASURED_FIELDS})
        scene['start'] = round(cursor, 6)
        cursor += measured['duration']
        scene['end'] = round(cursor, 6)
        result['scenes'].append(scene)
    result['duration'] = cursor
    result['timing_status'] = 'measured_tts'
    if replacements:
        result.setdefault('metadata', {})['manual_narration'] = True
        result['voice_tempo_mode'] = 'selective revision; unchanged scenes retain their measured narration'
    if result.get('documentary_schema_version') == 2:
        from .history_schema import enrich_timeline
        enrich_timeline(result)
    return result


def revise_narration(pack, scenes, *, workspace=None, synthesizer=None):
    """Synthesize only selected scenes, then publish the complete measured timeline.

    External TTS caches must already have been prepared by the app, using the
    same subset and original voice configuration.  Raw clips retain the normal
    synthesis cache key, so unchanged phrases inside an edited scene are reused.
    """
    from .common import ROOT, read_json, write_json
    root = Path(workspace) if workspace is not None else ROOT
    path = root / 'build' / pack['slug'] / 'timeline.json'
    previous = read_json(path)
    if previous.get('timing_status') == 'estimated':
        raise ValueError('La revisione richiede la timeline vocale del film concluso.')
    edited = prepare_revision_pack(pack, previous)
    selected = list(scenes)
    known = {s['id'] for s in edited['scenes']}
    if len(set(selected)) != len(selected) or not set(selected) <= known:
        raise ValueError('Elenco delle scene da rileggere non valido.')
    selected = set(selected)
    old_by_id = {s['id']: s for s in previous['scenes']}
    # Preflight the entire original film and every unchanged text before touching
    # a WAV.  Candidate outputs may be discarded if a later TTS request fails.
    for scene in edited['scenes']:
        old_scene = old_by_id[scene['id']]
        _measured_scene(old_scene, old_scene['lines'], edited['fps'])
        audio = (root / old_scene['audio']).resolve()
        if not audio.is_relative_to(root.resolve()) or not audio.is_file():
            raise ValueError('Audio originale non disponibile per la scena ' + scene['id'])
        if scene['id'] not in selected and scene['lines'] != old_scene['lines']:
            raise ValueError('Selezionare anche la voce della scena modificata ' + scene['id'])
    replacements = {}
    if selected:
        subset = copy.deepcopy(edited)
        subset['scenes'] = [s for s in subset['scenes'] if s['id'] in selected]
        subset.setdefault('metadata', {})['manual_narration'] = True
        from .voice_delivery import delivery_options
        if delivery_options(subset) is None:
            tempo = previous.get('voice_tempo', 1.0)
            if (not isinstance(tempo, bool) and isinstance(tempo, (int, float))
                    and math.isfinite(tempo) and .85 <= tempo <= 1.15):
                subset['voice_delivery'] = {'style': 'original', 'speed': tempo, 'pause_seconds': .18}
            elif tempo != 1.0:
                print('La velocità automatica precedente supera i controlli di lettura: '
                      'le frasi corrette manterranno il ritmo naturale.', flush=True)
        # Global events can refer to scenes omitted from this temporary subset.
        # Enrich only after merging, using the complete scene list.
        subset.pop('documentary_schema_version', None)
        if synthesizer is None:
            from . import narration
            if narration.ROOT.resolve() != root.resolve():
                raise ValueError('Eseguire la revisione dal motore dello spazio di lavoro candidato.')
            synthesizer = narration.synthesize
        generated = synthesizer(subset)
        new_ids = [s['id'] for s in generated['scenes']]
        if len(new_ids) != len(selected) or set(new_ids) != selected:
            raise ValueError('La sintesi non ha restituito tutte le scene richieste.')
        replacements = {s['id']: s for s in generated['scenes']}
    merged = merge_timeline(previous, edited, replacements)
    write_json(path, merged)
    write_json(root / 'timeline.json', merged)
    print(f'Revisione voce: {len(selected)} scene aggiornate; '
          f'{len(merged["scenes"]) - len(selected)} conservate. '
          f'Durata: {merged["duration"]:.2f} secondi.', flush=True)
    return merged
