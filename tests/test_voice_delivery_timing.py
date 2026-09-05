import array,hashlib,json,math,subprocess,sys,wave
from pathlib import Path

CORE=Path(__file__).resolve().parents[1]/'pipeline'


def test_delivery_timing_uses_measured_audio_and_keeps_clean_cues(tmp_path):
    voice=tmp_path/'build/test/voice';voice.mkdir(parents=True)
    lines=['Il viaggio inizia dal porto.','La nave raggiunge la nuova città.']
    manifest={'backend':'tts_api','items':{}}
    for i,line in enumerate(lines):
        name=f'{i}.wav'
        with wave.open(str(voice/name),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
            f.writeframes(array.array('h',(round(math.sin(n*2*math.pi*220/24000)*4000) for n in range(48000))))
        manifest['items'][f'01:{i}']={'file':name,'spoken_sha256':hashlib.sha256(line.encode()).hexdigest()}
    (voice/'external-voice-cache.json').write_text(json.dumps(manifest),encoding='utf-8')
    pack={'slug':'test','voice':'test','voice_engine':'tts_api','target_minutes':10,'fps':24,
          'voice_delivery':{'style':'calm','speed':.9,'pause_seconds':.5},
          'scenes':[{'id':'01','title':'Prova','lines':lines}]}
    (tmp_path/'pack.json').write_text(json.dumps(pack),encoding='utf-8')
    code='''
import json,sys,wave
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from engine import narration
from engine.voice_delivery import delivery_options
narration.ROOT=Path(sys.argv[2])
pack=json.loads((narration.ROOT/'pack.json').read_text())
t=narration.synthesize(pack)
assert t['voice_tempo']==.9
s=t['scenes'][0];a,b=s['cues']
assert abs(b['start']-a['end']-.5)<.00001
assert 2.15<a['end']-a['start']<2.3
assert [c['text'] for c in s['cues']]==pack['scenes'][0]['lines']
assert t['duration']<10 and 'user delivery' in t['voice_tempo_mode']
with wave.open(str(narration.ROOT/s['audio'])) as f:
 assert abs(f.getnframes()/f.getframerate()-s['duration'])<.0001
old={'target_minutes':5,'max_voice_tempo':1.22}
default={**old,'voice_delivery':{'style':'original','speed':1.,'pause_seconds':.18}}
assert narration.select_voice_tempo(old,'kokoro',438.8,18.6)==narration.select_voice_tempo(default,'kokoro',438.8,18.6)
for value in [float('nan'),True,0,2]:
 try:delivery_options({'voice_delivery':{'speed':value}})
 except ValueError:pass
 else:raise AssertionError('Bad speed accepted')
'''
    result=subprocess.run([sys.executable,'-X','utf8','-c',code,str(CORE),str(tmp_path)],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stdout+'\n'+result.stderr
