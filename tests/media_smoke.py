"""Real local TTS/render/verification; scripted demo, not a historical production.

Run with the app Python. --base-work is a previously rendered atlas project;
--portrait is an optional locally licensed sample. No remote model or paid API.
"""
import argparse,copy,io,json,os,shutil,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['DOCUMENTARIAI_DATA']=str(ROOT/'tests/output/media-smoke')
from app import store,media,pipeline
from app.models import ProjectRequest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-work',type=Path,required=True);parser.add_argument('--portrait',type=Path)
    args=parser.parse_args();store.init()
    p=store.create(ProjectRequest(topic='Immagini e mappe: prova tecnica',minutes=2,start=False));pid=p['id']
    store.write_json(store.DATA/'latest.json',{'id':pid})
    work,python=pipeline.isolate(pid,ROOT/'pipeline')
    source=args.base_work.resolve();old=store.read_json(source/'timeline.json')
    for f in (source/'assets/geography').glob('*'):
        if f.is_file() and f.suffix in ('.json','.geojson','.md'):
            dest=work/f.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():os.link(f,dest)
    # Same immutable raster inputs, independent engine, narration and outputs.
    atlas_dir=(source/old['atlas']).parent
    for f in atlas_dir.rglob('*'):
        if not f.is_file():continue
        dest=work/f.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():os.link(f,dest)
    if args.portrait:
        raw=args.portrait.read_bytes();m=media.upload(raw,args.portrait.name)
        value=media.MediaEdit(title='Annibale · ritratto tradizionale',credit='Fratelli Alinari, circa 1900',source='https://commons.wikimedia.org/wiki/File:Hannibal_Barca_bust_from_Capua_photo.jpg',rights='Pubblico dominio',bindings=[{'kind':'person','label':'Annibale'}])
    else:
        im=Image.new('RGB',(800,600),'#204e55');d=ImageDraw.Draw(im);d.text((60,80),'PERSONA / IMMAGINE DI PROVA',fill='white',font=ImageFont.truetype(str(ROOT/'pipeline/assets/fonts/Manrope[wght].ttf'),30));buf=io.BytesIO();im.save(buf,format='PNG');m=media.upload(buf.getvalue(),'persona-demo.png')
        value=media.MediaEdit(title='Persona · immagine di prova',rights='Grafica originale di test',bindings=[{'kind':'person','label':'Annibale'}])
    records=[media.save(m['id'],value)]
    for label,kind,color in [('Capua','place','#b9975e'),('Commercio','topic','#477b72')]:
        im=Image.new('RGB',(800,600),'#19383f');d=ImageDraw.Draw(im)
        for x,y in [(120,390),(400,180),(680,340)]:d.ellipse((x-24,y-24,x+24,y+24),fill=color)
        d.line([(120,390),(400,180),(680,340)],fill=color,width=8)
        f=ImageFont.truetype(str(ROOT/'pipeline/assets/fonts/Manrope[wght].ttf'),42)
        d.text((45,40),label,fill='#f1e7cf',font=f);d.text((45,520),'GRAFICA DIMOSTRATIVA',fill='#f1e7cf',font=f.font_variant(size=23))
        b=io.BytesIO();im.save(b,format='PNG');m=media.upload(b.getvalue(),label+'.png')
        records.append(media.save(m['id'],media.MediaEdit(title=label+' · esempio',rights='Grafica originale di test',bindings=[{'kind':kind,'label':label}],layout={'x':.71,'y':.21,'width':.25})))
    pack=copy.deepcopy(old)
    scene=copy.deepcopy(old['scenes'][1])
    for key in ('cues','audio','start','end','frames','duration'):scene.pop(key,None)
    scene.update(id='01',title='Immagini, mappe e racconto',mode='map',commanders=[],routes=[],facts=['Persone, luoghi e argomenti · riquadri sincronizzati alla voce'],kicker='Esempio del nuovo editor',lines=[
        'La mappa continua a muoversi mentre il racconto introduce immagini e dettagli.',
        'Quando viene nominato Annibale, il suo ritratto compare nel riquadro accanto alla carta.',
        'Un luogo come Capua può avere una propria immagine, collegata al suo nome.',
        'Anche un argomento, come il commercio, può richiamare un materiale visivo.',
        'Il riquadro scompare alla fine della frase. Posizione e dimensione si scelgono con il mouse, mentre la voce rimane sempre sincronizzata.'
    ])
    slug='demo-riquadri'
    pack.update(slug=slug,title='Immagini e mappe · prova del generatore',short_title='Immagini e mappe',subtitle='Riquadri sincronizzati',description='Prova tecnica con testo preparato; nessun modello remoto.',display_date='Esempio editor',scenes=[scene],target_minutes=.55,min_minutes=.2,max_minutes=1.2,output='output/demo_riquadri_1080p.mp4',verification_dir='demo_riquadri_verification',voice_sentence_chunks=[f'01:{i}' for i in range(5)],sources=[{'id':'S1','title':'Documentazione tecnica del progetto','url':'https://github.com/emanuelealbertosi/H3-documentary','use':'Testo dimostrativo del software, non ricerca storica.'}])
    scene['sources']=['S1'];assert media.attach(pack,records,work)==3
    path=work/'battles'/slug/'battle.json';store.write_json(path,pack)
    shutil.copy2(ROOT/'tests/check_image_insets.py',work/'tools/check_image_insets.py')
    def run(*cmd):subprocess.run([str(python),*map(str,cmd)],cwd=work,check=True)
    run('documentary.py','voice','--battle',path.relative_to(work))
    run('tools/check_image_insets.py')
    for cmd in ('preview','render','finalize','verify'):run('documentary.py',cmd,'--battle',path.relative_to(work),'--jobs','2')
    run('tools/check_atlas_final.py',slug)
    result={'workspace':str(work),'video':str(work/pack['output']),'report':str(work/'output'/pack['verification_dir']/'report.json'),'scope':'Local image upload/association, immutable snapshots, real Kokoro TTS, rendering, FFmpeg finalization and full decode. No LLM used.'}
    store.write_json(store.DATA/'result.json',result);print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
