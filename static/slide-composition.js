/* Shared black-canvas editor. Effects mirror engine/slide_visuals.py. */
export function slideSpec(layout,background=false){
  return layout.slide ||= {mode:background?'fullscreen':'inset',x:.1,y:.22,width:.8,height:.62,fit:layout.fit||'contain',effect:'fixed',fade:false,show_text:true};
}
export function slideGeometry(layout){
  const s=layout.slide;
  if(s.mode==='fullscreen')return {x:0,y:0,w:1,h:1};
  if(s.mode==='inset'){
    const w=layout.width,h=w*1920*.75/1080+72/1080;
    layout.x=Math.max(.02,Math.min(.98-w,layout.x));layout.y=Math.max(.19,Math.min(.80-h,layout.y));
    return {x:layout.x,y:layout.y,w,h};
  }
  s.x=Math.max(0,Math.min(1-s.width,s.x));s.y=Math.max(0,Math.min(1-s.height,s.y));
  return {x:s.x,y:s.y,w:s.width,h:s.height};
}
export function prepareSlideStage(root,shown){
  const stage=root.querySelector('#inset-stage');if(!stage)return;
  stage.classList.add('slide-stage');stage.style.background='#000';
  const heading=stage.querySelector('.inset-stage-heading');heading.querySelector('span').textContent='SLIDE SENZA MAPPA';
  heading.querySelector('b').textContent=shown?.source_type==='scene_background'?shown.label.replace(/^Sfondo · /,''):'Titolo della scena';
  stage.querySelector('.inset-stage-timeline').hidden=true;
  stage.nextElementSibling.textContent='Composizione 16:9 · Trascina il riquadro o usa i tasti freccia. L’anteprima dell’effetto è indicativa; le anteprime del progetto mostrano la scena completa.';
}
export function mountSlideEditor(root,shown,{editable,save,onError}){
  const background=shown.source_type==='scene_background',s=slideSpec(shown.layout,background);
  const inspector=root.querySelector('.media-inspector'),box=root.querySelector('#inset-box'),stage=root.querySelector('#inset-stage');
  if(!inspector)return;
  if(background)inspector.querySelector('h2').textContent=shown.label;
  inspector.querySelectorAll('.media-presets,.form-grid').forEach(el=>el.remove());
  const el=document.createElement('div');el.className='slide-composition-controls';
  const select=(id,label,options,value)=>`<div class="field"><label for="slide-${id}">${label}</label><select id="slide-${id}">${options.map(([k,v])=>`<option value="${k}" ${value===k?'selected':''}>${v}</option>`).join('')}</select></div>`;
  el.innerHTML=`<fieldset ${editable?'':'disabled'}><legend>Composizione della slide</legend><div class="form-grid">${select('mode','Formato',[...(!background?[['inset','Miniatura con didascalia']]:[]),['box','Riquadro libero'],['fullscreen','Tutto schermo']],s.mode)}${select('fit','Adattamento',[['contain','Immagine intera'],['cover','Riempi e ritaglia']],s.fit)}</div><div class="form-grid" id="slide-dimensions"><div class="field"><label for="slide-width">Larghezza <output id="slide-width-label"></output></label><input id="slide-width" type="range" min="10" max="100" step="1"></div><div class="field" id="slide-height-field"><label for="slide-height">Altezza <output id="slide-height-label"></output></label><input id="slide-height" type="range" min="10" max="100" step="1"></div></div><div class="form-grid">${select('effect','Movimento',[['fixed','Fissa'],['zoom_in','Zoom in lento'],['zoom_out','Zoom out lento'],['scroll_left','Scorri a sinistra'],['scroll_right','Scorri a destra'],['scroll_up','Scorri in alto'],['scroll_down','Scorri in basso']],s.effect)}<label class="check"><input id="slide-fade" type="checkbox" ${s.fade?'checked':''}> Dissolvenza in entrata e uscita</label></div>${background?`<label class="check"><input id="slide-text" type="checkbox" ${s.show_text?'checked':''}> Mostra titolo e testo della scena</label>`:''}<div class="field"><label for="slide-preview">Anteprima dell’effetto · scorri per vedere il movimento</label><input id="slide-preview" type="range" min="0" max="100" value="50"><p class="tiny muted">Movimenti lenti e contenuti. La durata segue la voce narrante; la dissolvenza dura al massimo 0,75 secondi per lato.</p></div></fieldset>`;
  inspector.querySelector('.visual-editor-actions')?.after(el);
  if(!el.isConnected)inspector.querySelector('.media-section-title').after(el);
  const q=id=>el.querySelector('#slide-'+id);
  function position(){
    const g=slideGeometry(shown.layout),inset=s.mode==='inset';
    q('dimensions').hidden=s.mode==='fullscreen';q('height-field').hidden=inset;
    q('width').min=inset?'16':'10';q('width').max=inset?'36':'100';
    q('width').value=Math.round(g.w*100);q('height').value=Math.round(g.h*100);
    q('width-label').textContent=Math.round(g.w*100)+'%';q('height-label').textContent=Math.round(g.h*100)+'%';
    stage.querySelector('.inset-stage-heading').hidden=background&&!s.show_text;
    if(!box)return;
    box.classList.toggle('slide-unframed',!inset);
    Object.assign(box.style,{left:g.x*100+'%',top:g.y*100+'%',width:g.w*100+'%',height:g.h*100+'%',cursor:s.mode==='fullscreen'?'default':'move'});
    const img=box.querySelector('img');img.style.objectFit=s.fit;
    const raw=+q('preview').value/100,p=raw*raw*(3-2*raw);let z=1,x=0,y=0;
    if(s.effect==='zoom_in')z=1+.1*p;
    if(s.effect==='zoom_out')z=1.1-.1*p;
    if(s.effect.startsWith('scroll_')){z=1.12;const d=6*(2*p-1);if(s.effect==='scroll_left')x=-d;if(s.effect==='scroll_right')x=d;if(s.effect==='scroll_up')y=-d;if(s.effect==='scroll_down')y=d;}
    img.style.transform=`translate(${x}%,${y}%) scale(${z})`;
    box.style.opacity=s.fade?Math.min(1,raw*8,(1-raw)*8):1;
    // A background with no replacement remains genuinely black, never a dummy photograph.
    img.style.visibility=background&&!shown.replacement_ready&&['blank','empty','missing'].includes(shown.state)?'hidden':'visible';
  }
  const persist=()=>Promise.resolve(save()).catch(onError);
  for(const key of ['mode','fit','effect'])q(key).onchange=()=>{s[key]=q(key).value;position();persist();};
  q('fade').onchange=()=>{s.fade=q('fade').checked;position();persist();};
  if(q('text'))q('text').onchange=()=>{s.show_text=q('text').checked;position();persist();};
  q('width').oninput=()=>{if(s.mode==='inset')shown.layout.width=+q('width').value/100;else s.width=+q('width').value/100;position();};
  q('height').oninput=()=>{s.height=+q('height').value/100;position();};
  q('width').onchange=persist;q('height').onchange=persist;q('preview').oninput=position;
  let drag=null;
  if(box&&editable){
    const target=()=>s.mode==='inset'?shown.layout:s;
    box.onpointerdown=e=>{if(e.button!==0||s.mode==='fullscreen')return;e.preventDefault();box.focus();box.setPointerCapture(e.pointerId);const a=target();drag={x:e.clientX,y:e.clientY,left:a.x,top:a.y,rect:stage.getBoundingClientRect()};};
    box.onpointermove=e=>{if(!drag)return;const a=target();a.x=drag.left+(e.clientX-drag.x)/drag.rect.width;a.y=drag.top+(e.clientY-drag.y)/drag.rect.height;position();};
    box.onpointerup=()=>{if(drag){drag=null;persist();}};box.onpointercancel=box.onpointerup;
    box.onkeydown=e=>{if(s.mode==='fullscreen')return;const d={ArrowLeft:[-.005,0],ArrowRight:[.005,0],ArrowUp:[0,-.005],ArrowDown:[0,.005]}[e.key];if(d){e.preventDefault();const a=target();a.x+=d[0];a.y+=d[1];position();persist();}};
  }
  position();
}
