import array,hashlib,json,subprocess,wave
from pathlib import Path

CORE=Path(__file__).resolve().parents[1]/'pipeline'


def test_external_voice_never_uses_an_unnatural_emergency_speedup():
    code="""
import sys
sys.path.insert(0,sys.argv[1])
from engine.narration import select_voice_tempo
pack={'target_minutes':5,'max_voice_tempo':1.22}
assert select_voice_tempo(pack,'tts_api',438.8,18.6)==1.15
pack={'target_minutes':5,'max_voice_tempo':1.22,'external_max_voice_tempo':1.15}
assert select_voice_tempo(pack,'tts_api',438.8,18.6)==1.15
assert select_voice_tempo(pack,'kokoro',438.8,18.6)==1.22
"""
    subprocess.run([str(CORE/'.venv/Scripts/python.exe'),'-c',code,str(CORE)],check=True,capture_output=True,text=True)


def test_external_voice_manifest_feeds_timeline_without_piper(tmp_path):
    spoken='Questa frase arriva dalla sintesi esterna.'
    voice=tmp_path/'build/prova/voice';voice.mkdir(parents=True)
    with wave.open(str(voice/'external.wav'),'wb') as target:
        target.setnchannels(1);target.setsampwidth(2);target.setframerate(24000)
        target.writeframes(array.array('h',[0])*24000)
    manifest={'version':1,'backend':'chatterbox','items':{'01:0':{
        'file':'external.wav','spoken_sha256':hashlib.sha256(spoken.encode('utf-8')).hexdigest()}}}
    (voice/'external-voice-cache.json').write_text(json.dumps(manifest),encoding='utf-8')
    pack={'slug':'prova','voice':'chatterbox-marker','voice_engine':'chatterbox','target_minutes':.05,
          'min_minutes':0,'max_minutes':1,'fps':30,'scenes':[{'id':'01','title':'Prova','lines':[spoken]}]}
    (tmp_path/'pack.json').write_text(json.dumps(pack),encoding='utf-8')
    code="""
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from engine import narration
narration.ROOT=Path(sys.argv[2])
narration.PiperVoice.load=lambda *_: (_ for _ in ()).throw(AssertionError('Piper must not load'))
timeline=narration.synthesize(json.loads((narration.ROOT/'pack.json').read_text(encoding='utf-8')))
assert timeline['voice_engine']=='chatterbox'
assert timeline['scenes'][0]['cues'][0]['text']=='Questa frase arriva dalla sintesi esterna.'
assert (narration.ROOT/timeline['scenes'][0]['audio']).is_file()
"""
    subprocess.run([str(CORE/'.venv/Scripts/python.exe'),'-c',code,str(CORE),str(tmp_path)],check=True,capture_output=True,text=True)
