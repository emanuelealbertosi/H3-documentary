/* Local image library, semantic bindings and a faithful 16:9 inset position editor. */
const kinds={person:'Persona',place:'Luogo',topic:'Argomento',event:'Evento',entity:'Popolo / organizzazione',scene:'Scena'};
const icons={person:'♙',place:'⌖',topic:'◈',event:'◷',entity:'⚑',scene:'▣'};
export async function mediaPage({api,esc,toast,projectId}) {
  let items=await api('/media'), selected=items.find(x=>x.enabled)?.id, project=null;
  let extra=[], filter='', saving=Promise.resolve(), disposed=false;
  if(projectId)project=await api('/projects/'+projectId+'/media');
  const root=document.querySelector('#app');
  const item=()=>items.find(x=>x.id===selected);
  function persist(m,redraw=false){
    const value=Object.fromEntries(['title','credit','source','rights','enabled','bindings','layout'].map(k=>[k,structuredClone(m[k])]));
    const label=root.querySelector('#media-save-state');if(label)label.textContent='Salvataggio…';
    saving=saving.catch(()=>{}).then(()=>api('/media/'+m.id,{method:'PUT',body:JSON.stringify(value)})).then(()=>{
      if(disposed)return;
      const state=root.querySelector('#media-save-state');if(state)state.textContent='Salvato sul PC';
      if(redraw)draw();
    }).catch(e=>{if(!disposed){toast(e.message);const state=root.querySelector('#media-save-state');if(state)state.textContent='Errore: riprova con Salva';}});
    return saving;
  }
  function targets(){
    const all=[...(project?.targets||[]),...extra,...items.flatMap(x=>x.bindings)];
    const seen=new Set();return all.filter(b=>{const key=b.kind+':'+b.label.toLocaleLowerCase();if(seen.has(key))return false;seen.add(key);return true;});
  }
  async function bind(mid,b){const m=items.find(x=>x.id===mid);if(!m)return;
    selected=mid;m.enabled=true;
    if(!m.bindings.some(x=>x.kind===b.kind&&x.label.toLowerCase()===b.label.toLowerCase()))m.bindings.push({kind:b.kind,label:b.label,aliases:b.aliases||[]});
    await persist(m);if(projectId)project=await api('/projects/'+projectId+'/media');draw();toast('Immagine collegata a '+b.label+'.');
  }
  async function upload(files,binding){
    const list=[...files];if(!list.length)return;
    const status=root.querySelector('#upload-status');
    for(let i=0;i<list.length;i++){
      if(status)status.textContent='Caricamento '+(i+1)+' di '+list.length+'…';
      try{
        if(list[i].size>20*1024*1024)throw Error(list[i].name+': supera 20 MB.');
        const r=await fetch('/api/media?filename='+encodeURIComponent(list[i].name),{method:'POST',headers:{'X-DocumentariAI':'studio','Content-Type':'application/octet-stream'},body:list[i]});
        if(!r.ok){const e=await r.json();throw Error(e.detail||'Caricamento non riuscito.');}
        const m=await r.json();items.unshift(m);selected=m.id;
        if(binding){m.bindings=[{...binding,aliases:binding.aliases||[]}];await persist(m);}
      }catch(e){toast(e.message);}
    }
    if(projectId)project=await api('/projects/'+projectId+'/media');if(!disposed)draw();
  }
  function dropzone(el,onDrop){
    el.ondragover=e=>{e.preventDefault();el.classList.add('drag-over');e.dataTransfer.dropEffect='copy';};
    el.ondragleave=e=>{if(!el.contains(e.relatedTarget))el.classList.remove('drag-over');};
    el.ondrop=e=>{e.preventDefault();e.stopPropagation();el.classList.remove('drag-over');onDrop(e);};
  }
  function geometry(m){const w=m.layout.width,h=w*1920*.75/1080+72/1080;
    m.layout.x=Math.max(.02,Math.min(.98-w,m.layout.x));m.layout.y=Math.max(.19,Math.min(.80-h,m.layout.y));
    return {w,h};
  }
  function position(){const m=item(),box=root.querySelector('#inset-box');if(!m||!box)return;
    const {w,h}=geometry(m);Object.assign(box.style,{left:m.layout.x*100+'%',top:m.layout.y*100+'%',width:w*100+'%',height:h*100+'%'});
    box.querySelector('img').style.objectFit=m.layout.fit;box.querySelector('span').textContent=m.title;
    const heading=root.querySelector('.media-inspector h2');if(heading)heading.textContent=m.title;
    root.querySelector('#inset-size-value').textContent=Math.round(w*100)+'%';
  }
  function draw(){
    if(disposed)return;
    const m=item(), ts=targets();
    root.innerHTML=`<div class="topline"><span class="eyebrow">IL TUO ARCHIVIO VISIVO</span><a class="text-link" href="${projectId?'/projects/'+projectId:'/'}">${projectId?'← Torna al progetto':'Crea un documentario →'}</a></div>
      <h1>Un’immagine. Il suo posto nella storia.</h1>
      <p class="lead">Collega ritratti, luoghi e materiali ai soggetti del racconto. Compariranno in un riquadro, insieme alle mappe e alle altre scene.</p>
      ${project?`<section class="media-project-note"><label class="check"><input id="project-use-media" type="checkbox" ${project.enabled?'checked':''} ${project.frozen?'disabled':''}> Usa le immagini associate in questo progetto</label><p class="tiny muted">${project.visual?.completed?'Puoi sostituire qualsiasi immagine del film. L’aggiornamento crea una nuova versione e renderizza soltanto le scene interessate.':project.frozen?'Le immagini di questa produzione sono fissate; gli slot restano disponibili per un aggiornamento dopo il completamento.':'Le associazioni sono riutilizzabili anche negli altri documentari. Salvale prima di avviare la produzione.'}</p></section>`:''}
      ${project?.visual?.ready?`<section class="visual-refresh-bar"><div><b>${project.visual.blank_count?project.visual.blank_count+' immagini da completare':'Tutte le immagini hanno un contenuto'}</b><span>${project.visual.slots.length} elementi visuali modificabili · ${project.visual.replacement_count} sostituzioni pronte</span></div>${project.visual.completed?`<button id="visual-refresh" class="primary" ${project.visual.replacement_count?'':'disabled'}>Aggiorna solo le scene interessate</button>`:''}</section>`:''}
      <section class="card media-library"><div class="media-section-title"><div><span class="eyebrow">01 · CARICA</span><h2>Le tue immagini <span class="media-count">${items.filter(x=>x.enabled).length}</span></h2></div><label class="button secondary media-file-label" for="media-files">+ Aggiungi immagini</label><input class="visually-hidden" id="media-files" type="file" accept="image/jpeg,image/png,image/webp" multiple></div>
        <div id="media-drop" class="media-drop" tabindex="0" role="button" aria-label="Carica immagini trascinandole o scegliendo un file"><span class="media-drop-icon">↥</span><div><strong>Trascina qui le immagini</strong><p>JPG, PNG o WebP · fino a 20 MB · puoi anche trascinarle direttamente su un collegamento</p></div><span id="upload-status" role="status"></span></div>
        <div class="media-library-tools"><label class="visually-hidden" for="media-search">Cerca un’immagine</label><input id="media-search" placeholder="Cerca nelle tue immagini…" value="${esc(filter)}"><span class="tiny muted">Trascina una scheda su un soggetto, oppure selezionala e fai clic sul collegamento.</span></div>
        <div id="media-cards" class="media-cards">${items.filter(x=>x.enabled&&(!filter||x.title.toLowerCase().includes(filter.toLowerCase()))).map(x=>`<button class="media-card ${selected===x.id?'selected':''}" draggable="true" data-mid="${x.id}" aria-pressed="${selected===x.id}" aria-label="Seleziona ${esc(x.title)}"><img draggable="false" src="/api/media/${x.id}/thumb" alt=""><strong>${esc(x.title)}</strong><small>${x.bindings.length?x.bindings.length+' collegamenti':'Da collegare'} <span>⠿</span></small></button>`).join('')||'<p class="media-empty">Il tuo archivio comincia con la prima immagine.</p>'}</div>
        ${items.some(x=>!x.enabled)?`<details><summary>Immagini archiviate</summary><div class="media-archived">${items.filter(x=>!x.enabled).map(x=>`<button class="secondary" data-restore="${x.id}">Ripristina ${esc(x.title)}</button>`).join('')}</div></details>`:''}
      </section>
      <div class="media-workspace"><section class="card media-targets"><span class="eyebrow">02 · COLLEGA</span><h2>A chi o a cosa?</h2><p class="tiny muted">Un’immagine può avere più collegamenti. Aggiungi un nome, poi trascinaci sopra l’immagine.</p>
        ${m?`<button class="media-selected-drag" draggable="true" data-mid="${m.id}" aria-label="Trascina immagine selezionata"><img draggable="false" src="/api/media/${m.id}/thumb" alt=""><span><small>IMMAGINE SELEZIONATA</small><b>${esc(m.title)}</b><i>Trascinami su un soggetto ↓</i></span></button>`:''}
        <div class="media-target-list">${ts.map((b,i)=>`<button class="media-target ${m?.bindings.some(x=>x.kind===b.kind&&x.label===b.label)?'linked':''} ${b.visual_state?'visual-'+b.visual_state:''}" data-target="${i}" aria-label="Collega a ${esc(b.label)}"><span>${icons[b.kind]||'◈'}</span><div><small>${esc(kinds[b.kind]||b.kind)}${b.visual_state?' · '+({blank:'SCHEDA NEUTRA',missing:'DA COMPLETARE',available:'TROVATA',user:'PERSONALIZZATA'}[b.visual_state]||'NEL FILM'):''}</small><strong>${esc(b.label)}</strong>${b.scene_ids?.length?`<em>${b.scene_ids.length} ${b.scene_ids.length===1?'scena':'scene'}</em>`:''}</div><i>+</i></button>`).join('')||'<div class="media-empty">Crea il primo collegamento qui sopra.</div>'}</div>
        <details ${!ts.length?'open':''}><summary>+ Nuovo collegamento</summary><form id="target-form"><label for="target-kind">Tipo di collegamento</label><select id="target-kind">${Object.entries(kinds).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select><label for="target-label">Nome del soggetto</label><input id="target-label" required minlength="2" maxlength="120" placeholder="Es. Annibale, Roma, commercio"><button class="secondary" type="submit">+ Crea collegamento</button></form></details>
        <p class="tiny muted">La comparsa segue i nomi e le varianti presenti nelle frasi narrate. Un collegamento “Scena” segue il titolo della scena.</p>
      </section><section class="media-editor"><div class="media-section-title"><div><span class="eyebrow">03 · COMPONI</span><h2>Il riquadro nel video</h2></div><span id="media-save-state" class="tiny muted" role="status">Salvato sul PC</span></div>
        <div id="inset-stage" class="inset-stage"><div class="inset-stage-heading"><span>ATLANTE STORICO</span><b>Una finestra sul racconto</b></div><div class="inset-stage-timeline"><span>●</span><i></i><span>◷</span><i></i><span>●</span></div>
        ${m?`<div id="inset-box" class="inset-box" tabindex="0" role="group" aria-label="Riquadro immagine: trascina o usa i tasti freccia"><img draggable="false" src="/api/media/${m.id}/image" alt="${esc(m.title)}"><span>${esc(m.title)}</span></div>`:'<div class="inset-stage-placeholder">Seleziona un’immagine per posizionare il riquadro.</div>'}</div>
        <p class="tiny muted">Anteprima di posizione su una mappa dimostrativa · 16:9. Trascina il riquadro; i tasti freccia permettono piccoli spostamenti.</p>
        ${m?`<div class="card media-inspector"><div class="media-section-title"><h2>${esc(m.title)}</h2><button class="text-link" id="archive-image">Archivia</button></div>
          <div class="media-presets" role="group" aria-label="Posizione del riquadro">${[['tl','↖ Alto a sinistra'],['tr','↗ Alto a destra'],['bl','↙ Basso a sinistra'],['br','↘ Basso a destra']].map(([k,l])=>`<button class="secondary" data-corner="${k}">${l}</button>`).join('')}</div>
          <div class="form-grid"><div class="field"><label for="inset-size">Dimensione <span id="inset-size-value"></span></label><input type="range" id="inset-size" min="16" max="36" step="1" value="${Math.round(m.layout.width*100)}"></div><div class="field"><label for="inset-fit">Inquadratura</label><select id="inset-fit"><option value="contain" ${m.layout.fit==='contain'?'selected':''}>Immagine intera</option><option value="cover" ${m.layout.fit==='cover'?'selected':''}>Riempi il riquadro</option></select></div></div>
          <div class="field"><label for="image-title">Titolo nel video</label><input id="image-title" maxlength="120" value="${esc(m.title)}"></div>
          <div class="media-bindings">${m.bindings.map((b,i)=>`<div class="media-binding"><div><span>${esc(kinds[b.kind])} · <b>${esc(b.label)}</b></span><button data-unbind="${i}" aria-label="Rimuovi collegamento ${esc(b.label)}">×</button></div><label for="aliases-${i}">Altri nomi o varianti, separati da virgole</label><input id="aliases-${i}" data-alias="${i}" maxlength="1000" value="${esc((b.aliases||[]).join(', '))}" placeholder="Es. Annibale Barca, generale cartaginese"></div>`).join('')||'<p class="media-unlinked">Aggiungi un collegamento per far comparire questa immagine nel racconto.</p>'}</div>
          <details><summary>Provenienza e crediti</summary>${[['credit','Autore / attribuzione'],['source','Provenienza o URL'],['rights','Licenza o diritti dichiarati']].map(([k,l])=>`<div class="field"><label for="image-${k}">${l}</label><input id="image-${k}" maxlength="${k==='source'?500:300}" value="${esc(m[k])}"></div>`).join('')}<p class="tiny muted">Conserviamo l’originale e riportiamo queste informazioni nei crediti del progetto. Non viene assegnata automaticamente una licenza alle tue immagini.</p></details><button class="secondary" id="media-save">Salva riquadro</button>
        </div>`:''}
      </section></div><p class="footer-note">Le immagini personali rimangono sul PC. Ogni produzione conserva la propria copia; modificare la libreria non cambia i video già creati. Più immagini collegate alla stessa frase si alternano.</p>`;
    root.querySelector('#media-files').onchange=e=>upload(e.target.files);
    const zone=root.querySelector('#media-drop');dropzone(zone,e=>upload(e.dataTransfer.files));zone.onclick=()=>root.querySelector('#media-files').click();zone.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();root.querySelector('#media-files').click();}};
    root.querySelector('#media-search').oninput=e=>{filter=e.target.value;const pos=e.target.selectionStart;draw();const input=root.querySelector('#media-search');input.focus();input.setSelectionRange(pos,pos);};
    root.querySelectorAll('[data-mid]').forEach(el=>{el.onclick=()=>{selected=el.dataset.mid;draw();};el.ondragstart=e=>{e.dataTransfer.setData('application/x-h3-media',el.dataset.mid);e.dataTransfer.effectAllowed='copy';};});
    root.querySelectorAll('[data-restore]').forEach(el=>el.onclick=()=>{const m=items.find(x=>x.id===el.dataset.restore);m.enabled=true;selected=m.id;persist(m,true);});
    root.querySelector('#target-form').onsubmit=e=>{e.preventDefault();const b={kind:root.querySelector('#target-kind').value,label:root.querySelector('#target-label').value.trim(),aliases:[]};if(b.label.length<2)return;extra.push(b);draw();toast('Collegamento creato. Trascina un’immagine su '+b.label+'.');};
    root.querySelectorAll('[data-target]').forEach(el=>{const b=ts[+el.dataset.target];el.onclick=()=>selected?bind(selected,b):toast('Seleziona prima un’immagine.');dropzone(el,e=>e.dataTransfer.files.length?upload(e.dataTransfer.files,b):bind(e.dataTransfer.getData('application/x-h3-media'),b));});
    const use=root.querySelector('#project-use-media');if(use)use.onchange=async()=>{try{project=await api('/projects/'+projectId+'/media',{method:'PUT',body:JSON.stringify({enabled:use.checked})});}catch(e){toast(e.message);use.checked=project.enabled;}};
    const refresh=root.querySelector('#visual-refresh');if(refresh)refresh.onclick=async()=>{refresh.disabled=true;refresh.textContent='Creo la nuova versione…';try{const data=await api('/projects/'+projectId+'/visual-refresh',{method:'POST'});toast('Nuova versione V'+data.project.version+' creata.');location.href='/projects/'+data.project.id;}catch(e){toast(e.message);refresh.disabled=false;refresh.textContent='Aggiorna solo le scene interessate';}};
    if(!m)return;
    position();
    root.querySelector('#archive-image').onclick=()=>{m.enabled=false;selected=items.find(x=>x.enabled)?.id;persist(m,true);toast('Immagine archiviata. Puoi ripristinarla dalla libreria.');};
    root.querySelector('#media-save').onclick=()=>persist(m);
    root.querySelectorAll('[data-unbind]').forEach(el=>el.onclick=()=>{m.bindings.splice(+el.dataset.unbind,1);persist(m,true);});
    root.querySelectorAll('[data-alias]').forEach(el=>el.onchange=()=>{m.bindings[+el.dataset.alias].aliases=el.value.split(',').map(x=>x.trim()).filter(Boolean).slice(0,12);persist(m);});
    for(const k of ['title','credit','source','rights']){const input=root.querySelector('#image-'+k);input.onchange=()=>{m[k]=input.value.trim()||(k==='title'?'Immagine':'');position();persist(m);};if(k==='title')input.oninput=()=>{m.title=input.value.trim()||'Immagine';position();};}
    root.querySelector('#inset-fit').onchange=e=>{m.layout.fit=e.target.value;position();persist(m);};
    const range=root.querySelector('#inset-size');range.oninput=()=>{m.layout.width=+range.value/100;position();};range.onchange=()=>persist(m);
    root.querySelectorAll('[data-corner]').forEach(el=>el.onclick=()=>{const {w,h}=geometry(m);m.layout.x=el.dataset.corner[1]==='l'?.02:.98-w;m.layout.y=el.dataset.corner[0]==='t'?.19:.80-h;position();persist(m);});
    const box=root.querySelector('#inset-box'),stage=root.querySelector('#inset-stage');let dragging=null;
    box.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();box.focus();box.setPointerCapture(e.pointerId);dragging={x:e.clientX,y:e.clientY,l:m.layout.x,t:m.layout.y,rect:stage.getBoundingClientRect()};box.classList.add('dragging');};
    box.onpointermove=e=>{if(!dragging)return;m.layout.x=dragging.l+(e.clientX-dragging.x)/dragging.rect.width;m.layout.y=dragging.t+(e.clientY-dragging.y)/dragging.rect.height;position();};
    box.onpointerup=()=>{if(dragging){dragging=null;box.classList.remove('dragging');persist(m);}};box.onpointercancel=box.onpointerup;
    box.onkeydown=e=>{const delta={ArrowLeft:[-.005,0],ArrowRight:[.005,0],ArrowUp:[0,-.005],ArrowDown:[0,.005]}[e.key];if(delta){e.preventDefault();m.layout.x+=delta[0];m.layout.y+=delta[1];position();persist(m);}};
  }
  draw();return ()=>{disposed=true;};
}
