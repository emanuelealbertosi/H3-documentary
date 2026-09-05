"""Selectable-text PDF presentations using frozen scenes and their existing assets."""
import hashlib,json,re
from pathlib import Path
from xml.sax.saxutils import escape

from .presentation_plan import load_timeline,plan_pages
from .still_render import StillRenderer,output_path,workspace_context


def _progress(done,total,message):
    print('PDF_PROGRESS '+json.dumps({'done':done,'total':total,'message':message},ensure_ascii=False),flush=True)


def editorial_sections(timeline,workspace):
    """Read provenance without invoking exporters that rewrite production files."""
    root=Path(workspace).resolve();sections=[]
    for name,title in [('sources.md','Fonti e metodo'),('credits.md','Crediti e licenze')]:
        candidates=[root/name]
        slug=timeline.get('slug','')
        candidates.extend(root/folder/slug/name for folder in ('documentaries','battles'))
        path=next((p for p in candidates if p.is_file() and p.resolve().is_relative_to(root)),None)
        if path:
            if path.stat().st_size>5*1024*1024:raise ValueError('Documento dei crediti troppo grande per una presentazione.')
            sections.append((title,path.read_text(encoding='utf-8')))
    if not any(title=='Fonti e metodo' for title,_ in sections):
        text='\n\n'.join(f"{s.get('id','')} · {s.get('title','')}\n{s.get('url','')}\n{s.get('use','')}" for s in timeline.get('sources',[]))
        sections.append(('Fonti e metodo',text or 'Il progetto non contiene riferimenti bibliografici.'))
    # The current timeline is authoritative if old text exports predate image updates.
    details=[]
    for asset in timeline.get('user_media',[])+timeline.get('visual_assets',[]):
        details.append(f"{asset.get('title',asset.get('id','Immagine'))}. {asset.get('credit') or asset.get('creator','')}\n"
            f"{asset.get('rights') or asset.get('license','Diritti non specificati')} {asset.get('license_url','')}\n{asset.get('source','')}")
    from .image_rights import image_license_credits
    known={(a.get('source',''),a.get('title',a.get('id',''))) for a in timeline.get('user_media',[])+timeline.get('visual_assets',[])}
    for credit in image_license_credits(timeline,root=root):
        if (credit['source'],credit['title']) not in known:
            details.append(f"{credit['title']}. {credit['credit']}\n{credit['id']} {credit['license_url']}\n{credit['source']}")
    if timeline.get('video_license'):details.append(timeline['video_license'])
    if timeline.get('extra_credits'):details.append(timeline['extra_credits'])
    if details:sections.append(('Materiali della versione esportata','\n\n'.join(details)))
    return sections


def export_presentation(workspace,output,variant='compact',narration='full',manifest=None,*,timeline=None,renderer_factory=StillRenderer):
    workspace=Path(workspace).resolve();output=output_path(workspace,output,'.pdf')
    manifest=output_path(workspace,manifest or output.with_suffix('.json'),'.json')
    if output.exists() or manifest.exists():raise ValueError('Questo nome di esportazione esiste già: scegli un nuovo nome per conservare il PDF precedente.')
    if timeline is None:timeline,timeline_path=load_timeline(workspace)
    else:timeline_path=None
    pages=plan_pages(timeline,variant,narration)
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from reportlab.lib.colors import HexColor

    font=workspace/'assets/fonts/Manrope[wght].ttf'
    if not font.is_file():raise ValueError('Il carattere locale Manrope non è disponibile nel progetto.')
    pdfmetrics.registerFont(TTFont('H3Presentation',str(font)))
    body=ParagraphStyle('H3Body',fontName='H3Presentation',fontSize=15,leading=22,textColor=HexColor('#26363A'),spaceAfter=9,splitLongWords=True)
    heading=ParagraphStyle('H3Heading',parent=body,fontSize=23,leading=30,spaceAfter=14)
    output.parent.mkdir(parents=True,exist_ok=True)
    cache=output.parent/'.frames'/output.stem;cache.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.rendering.pdf')
    if temp.exists():raise ValueError('Un’esportazione con questo nome è già in lavorazione.')
    pdf=canvas.Canvas(str(temp),pagesize=(960,780),pageCompression=1)
    pdf.setTitle(timeline.get('title','Presentazione storica'))
    pdf.setAuthor('H3-documentary');pdf.setSubject('Presentazione derivata dalle scene approvate; nessuna nuova generazione narrativa.')
    page_count=0;frames=[]

    def new_page(title,sub=''):
        nonlocal page_count
        if page_count:pdf.showPage()
        page_count+=1
        if page_count>2000:raise ValueError('Il testo richiede oltre 2000 pagine: esportazione interrotta senza troncamenti.')
        pdf.setFillColor(HexColor('#F8F6F0'));pdf.rect(0,0,960,780,fill=1,stroke=0)
        pdf.setFillColor(HexColor('#213D44'));pdf.setFont('H3Presentation',17)
        label=str(title)
        while pdfmetrics.stringWidth(label,'H3Presentation',17)>865 and len(label)>1:label=label[:-2]+'…'
        pdf.drawString(32,750,label)
        pdf.setFont('H3Presentation',10);pdf.setFillColor(HexColor('#597177'))
        pdf.drawString(32,731,str(sub));pdf.drawRightString(928,18,str(page_count))
        pdf.setStrokeColor(HexColor('#D5B878'));pdf.line(32,34,928,34)

    def flow(items,top,bottom=52):
        items=list(items);y=top
        while items:
            paragraph=items.pop(0);width,height=paragraph.wrap(896,max(0,y-bottom))
            if height<=y-bottom:
                paragraph.drawOn(pdf,32,y-height);y-=height+9;continue
            parts=paragraph.split(896,max(0,y-bottom))
            if parts:
                head=parts.pop(0);_,h=head.wrap(896,y-bottom);head.drawOn(pdf,32,y-h)
                return parts+items
            return [paragraph]+items
        return []

    def paragraphs(text,style=body):
        result=[]
        for part in re.split(r'\n\s*\n',str(text)):
            if not part.strip():continue
            is_heading=bool(re.fullmatch(r'#{1,6} [^\n]+',part.strip()))
            if is_heading:part=re.sub(r'^#{1,6} ','',part.strip())
            result.append(Paragraph(escape(part).replace('\n','<br/>'),heading if is_heading else style))
        return result

    try:
        _progress(0,len(pages)+1,'Preparo la presentazione')
        with workspace_context(workspace):
            renderer=renderer_factory(timeline,workspace,cache)
            for number,page in enumerate(pages,1):
                frame=renderer.frame(page).convert('RGB');frame_path=cache/f'{number:04}.jpg'
                frame.save(frame_path,quality=94,subsampling=0)
                detail='Sintesi della scena' if variant=='compact' else f"Passaggio {page['cue_index']+1} · "+('Partenza' if page['phase']=='start' else 'Sviluppo / arrivo')
                new_page(page['title'],f"Scena {page['scene_id']} · {detail} · {page['historical_date']}")
                pdf.drawImage(str(frame_path),16,198,width=928,height=522,preserveAspectRatio=True,anchor='c')
                sources=', '.join(map(str,page['source_ids'])) or 'Riferimenti nel progetto'
                pdf.setFillColor(HexColor('#597177'));pdf.setFont('H3Presentation',10)
                pdf.drawString(32,181,('Fonti: '+sources)[:165])
                remainder=flow(paragraphs(page['text']),160)
                while remainder:
                    new_page(page['title'],'Testo narrato · continuazione')
                    remainder=flow(remainder,701)
                frames.append({k:page[k] for k in ('scene_id','cue_index','phase','time','inset_asset_id')}
                    |{'path':str(frame_path.relative_to(workspace)),'sha256':hashlib.sha256(frame_path.read_bytes()).hexdigest()})
                _progress(number,len(pages)+1,f'Immagine {number}/{len(pages)}')
        for title,text in editorial_sections(timeline,workspace):
            new_page(title,'Fonti e attribuzioni della versione esportata')
            remainder=flow(paragraphs(text),701)
            while remainder:
                new_page(title,'Continuazione');remainder=flow(remainder,701)
        pdf.save();temp.replace(output)
        result={'schema_version':1,'variant':variant,'narration':narration,'pages':page_count,'visual_pages':len(pages),
            'output':str(output.relative_to(workspace)),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'timeline':str(timeline_path.relative_to(workspace)) if timeline_path else 'explicit_fixture',
            'timeline_sha256':hashlib.sha256(json.dumps(timeline,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'timing_status':timeline.get('timing_status','existing_timeline'),'frames':frames,
            'narration_characters':sum(len(p['text']) for p in pages),'network_requests':0}
        pending=manifest.with_suffix('.json.tmp');pending.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');pending.replace(manifest)
        _progress(len(pages)+1,len(pages)+1,f'PDF pronto · {page_count} pagine')
        return result
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
