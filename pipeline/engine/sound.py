"""Procedural score and discreet effects; no external recordings or music licences."""
import math
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter,sosfilt
from scipy.ndimage import maximum_filter1d,gaussian_filter1d
from .common import ROOT,write_json

SR=48000
def lowpass(y,freq):return sosfilt(butter(2,freq,fs=SR,output='sos'),y)

def effect(kind,seed):
    rng=np.random.default_rng(seed)
    duration={'cannon':2.3,'musket':1.5,'cavalry':6.,'march':5.,'rain':9.,'transition':1.2}[kind]
    t=np.arange(round(duration*SR),dtype=float)/SR
    if kind=='cannon':
        noise=rng.normal(size=len(t))
        y=.45*lowpass(noise,1900)*np.exp(-t*5)+.34*np.sin(2*np.pi*(63*t-8*t*t))*np.exp(-t*2.7)
        y+=.1*lowpass(noise,200)*np.exp(-t*1.8)
    elif kind=='musket':
        y=np.zeros_like(t)
        for start in [0,.13,.28,.51,.73]:
            age=np.maximum(0,t-start); mask=t>=start
            y+=rng.normal(size=len(t))*.12*np.exp(-age*35)*mask
        y=lowpass(y,3200)
    elif kind in ('cavalry','march'):
        y=np.zeros_like(t); interval=.34 if kind=='cavalry' else .57
        pulse_times=np.arange(0,duration-.15,interval)
        for k,start in enumerate(pulse_times):
            starts=[start,start+.13] if kind=='cavalry' else [start]
            for at in starts:
                age=np.maximum(0,t-at); mask=(t>=at)&(t<at+.18)
                impact=np.sin(2*np.pi*(145 if kind=='cavalry' else 95)*age)*np.exp(-age*35)
                impact+=.25*rng.normal(size=len(t))*np.exp(-age*70)
                y+=.12*impact*mask
        y=lowpass(y,2000)*np.sin(np.pi*np.clip(t/duration,0,1))
    elif kind=='rain':
        y=lowpass(rng.normal(size=len(t)),4200)*.06*np.minimum(1,t)*np.minimum(1,duration-t)
    else:
        y=lowpass(rng.normal(size=len(t)),1000)*.065*np.sin(np.pi*t/duration)**2
    y*=np.minimum(1,t/.006)*np.minimum(1,(duration-t)/.18)
    return y.astype(np.float32)

def score(t):
    # Original slowly crossfaded minor-mode harmonies. Deliberately quiet under the narrator.
    chords=[[73.416,110,146.832,174.614],[58.27,87.307,116.54,146.832],
            [65.406,98,130.812,164.814],[65.406,97.999,146.832,195.998]]
    period=28.
    sound=np.zeros((len(t),2),dtype=np.float32)
    for n in range(int(t[0]//period)-1,int(t[-1]//period)+2):
        middle=(n+.5)*period
        env=np.clip(1-np.abs(t-middle)/period,0,1)
        env=np.sin(env*np.pi/2)**2
        for j,f in enumerate(chords[n%4]):
            tone=(np.sin(2*np.pi*f*t+.15*np.sin(2*np.pi*.18*t))+
                  .16*np.sin(2*np.pi*f*2*t)+.05*np.sin(2*np.pi*f*3*t))*.0055
            sound[:,0]+=tone*env*(1.0 if j%2 else .73)
            sound[:,1]+=tone*env*(.73 if j%2 else 1.0)
    return sound

def mix_scene(scene,out_dir):
    sr,y=wavfile.read(ROOT/scene['audio']); assert sr==SR
    voice=y.astype(np.float32)/32768
    t=scene['start']+np.arange(len(voice),dtype=np.float64)/sr
    bed=score(t)
    rng=np.random.default_rng(int(scene['id'])+1815)
    wind=lowpass(rng.normal(0,.003,len(t)),650)
    bed+=wind[:,None]
    fx_assets=ROOT/'assets/audio/procedural'/out_dir.parent.name; fx_assets.mkdir(parents=True,exist_ok=True)
    events=[dict(type='transition',cue=0),*scene['sfx']]
    for index,event in enumerate(events):
        fx=effect(event['type'],1815+int(scene['id'])*10+index)
        wavfile.write(fx_assets/f'{scene["id"]}-{index}-{event["type"]}.wav',sr,(fx*26000).astype(np.int16))
        start=0 if event['type']=='transition' else scene['cues'][event['cue']]['start']
        offset=int(start*sr); length=min(len(fx),len(voice)-offset)
        pan=[-.40,.32,.10][index%3]; l=math.sqrt((1-pan)/2); r=math.sqrt((1+pan)/2)
        gain={'cannon':.15,'musket':.21,'cavalry':.42,'march':.42,'rain':.24,'transition':.30}[event['type']]
        bed[offset:offset+length,0]+=fx[:length]*l*gain
        bed[offset:offset+length,1]+=fx[:length]*r*gain
    # Envelope computed at 100 Hz: anticipates speech and releases gently.
    block=480; pad=(-len(voice))%block
    rms=np.sqrt(np.mean(np.pad(voice,(0,pad)).reshape(-1,block)**2,axis=1))
    envelope=gaussian_filter1d(maximum_filter1d(rms,size=25),sigma=12)
    envelope=np.interp(np.arange(len(voice)),np.arange(len(envelope))*block,envelope)
    duck=1-.72*np.clip(envelope/.035,0,1)
    bed*=duck[:,None]
    fade=np.minimum(1,np.arange(len(voice))/(sr*.28))*np.minimum(1,(len(voice)-np.arange(len(voice)))/(sr*.38))
    bed*=fade[:,None]
    output=voice[:,None]*np.ones((1,2))+bed
    peak=float(np.max(np.abs(output)))
    assert peak<.99,peak
    out=out_dir/f'{scene["id"]}-mix.wav'
    wavfile.write(out,sr,(output*32767).astype(np.int16))
    speech=voice**2>.0004
    bed_rms=float(np.sqrt(np.mean(bed[speech]**2)))
    speech_rms=float(np.sqrt(np.mean(voice[speech]**2)))
    return out,dict(scene=scene['id'],peak_dbfs=20*math.log10(max(peak,1e-8)),
                    voice_to_bed_db=20*math.log10(speech_rms/max(bed_rms,1e-8)))

def mix_all(timeline):
    out_dir=ROOT/'build'/timeline['slug']/'sound'; out_dir.mkdir(parents=True,exist_ok=True)
    reports=[]; chunks=[]
    for s in timeline['scenes']:
        out,report=mix_scene(s,out_dir); reports.append(report)
        _,chunk=wavfile.read(out); chunks.append(chunk)
        print('Audio mixed',s['id'],f'voice/bed +{report["voice_to_bed_db"]:.1f}dB',flush=True)
    full=out_dir/'full-mix.wav'; wavfile.write(full,SR,np.concatenate(chunks))
    write_json(out_dir/'mix-report.json',reports)
    return full
