/* Local image library, semantic bindings and a faithful 16:9 inset position editor. */
const kinds={person:'Persona',place:'Luogo',topic:'Argomento',event:'Evento',entity:'Popolo / organizzazione',scene:'Scena'};
const icons={person:'♙',place:'⌖',topic:'◈',event:'◷',entity:'⚑',scene:'▣'};
export async function mediaPage({api,esc,toast,projectId}) {
  let items=await api('/media'), selected=items.find(x=>x.enabled)?.id, project=null;
  let selectedSlot='',linkTarget=-1,extra=[], filter='', saving=Promise.resolve(), disposed=false;
  const requestedSlot=new URLSearchParams(location.search).get('slot')||'';
  let revealRequestedSlot=!!requestedSlot;
  const columnWidthKey='h3-media-target-width';
  const rememberedWidth=Number(localStorage.getItem(columnWidthKey));
  let targetColumnWidth=Number.isFinite(rememberedWidth)&&rememberedWidth>=320?Math.min(640,rememberedWidth):380;
  if(projectId){project=await api('/projects/'+projectId+'/media');if(project.visual?.slots?.some(x=>x.id===requestedSlot))selectedSlot=requestedSlot;}
  const root=document.querySelector('#app');
  const item=()=>items.find(x=>x.id===selected);
  const visualItem=()=>project?.visual?.slots?.find(x=>x.id===selectedSlot);
  const defaultLayout=()=>({x:.71,y:.21,width:.25,fit:'contain'});
  const activeItem=()=>{const v=visualItem();return v?{...v,title:v.title||v.label,layout:v.layout||defaultLayout(),visual:true}:item();};
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
    const all=project?[...(project.targets||[]),...extra]:[...extra,...items.flatMap(x=>x.bindings)];
    const seen=new Set();return all.filter(b=>{const key=b.kind+':'+b.label.toLocaleLowerCase();if(seen.has(key))return false;seen.add(key);return true;});
  }
  const sameBinding=(a,b)=>a.kind===b.kind&&a.label.toLowerCase()===b.label.toLowerCase();
  const linkedItems=b=>items.filter(x=>x.enabled&&x.bindings.some(binding=>sameBinding(binding,b)));
  async function activateTarget(binding){
    if(projectId&&binding?.visual_slot_id&&binding.visual_editable&&!binding.enabled)await api('/projects/'+projectId+'/visual-slots/'+encodeURIComponent(binding.visual_slot_id),{method:'PUT',body:JSON.stringify({enabled:true})});
  }
  async function bind(mid,b){const m=items.find(x=>x.id===mid);if(!m)return;
    selected=mid;selectedSlot='';linkTarget=-1;m.enabled=true;items=[m,...items.filter(x=>x.id!==mid)];
    if(!m.bindings.some(x=>sameBinding(x,b)))m.bindings.push({kind:b.kind,label:b.label,aliases:b.aliases||[]});
    await persist(m);await activateTarget(b);if(projectId)project=await api('/projects/'+projectId+'/media');draw();toast('Immagine collegata a '+b.label+'.');
  }
  async function unbindTarget(b){
    const linked=linkedItems(b);if(!linked.length)return;
    for(const m of linked){m.bindings=m.bindings.filter(x=>!sameBinding(x,b));await persist(m);}
    linkTarget=-1;if(projectId)project=await api('/projects/'+projectId+'/media');draw();toast('Collegamento rimosso da '+b.label+'.');
  }
  async function upload(files,binding){
    const list=[...files];if(!list.length)return;
    const status=root.querySelector(binding?'#link-upload-status':'#upload-status');
    for(let i=0;i<list.length;i++){
      if(status)status.textContent='Caricamento '+(i+1)+' di '+list.length+'…';
      try{
        if(list[i].size>20*1024*1024)throw Error(list[i].name+': supera 20 MB.');
        const r=await fetch('/api/media?filename='+encodeURIComponent(list[i].name),{method:'POST',headers:{'X-DocumentariAI':'studio','Content-Type':'application/octet-stream'},body:list[i]});
        if(!r.ok){const e=await r.json();throw Error(e.detail||'Caricamento non riuscito.');}
        const m=await r.json();items.unshift(m);selected=m.id;selectedSlot='';
        if(binding){m.bindings=[{kind:binding.kind,label:binding.label,aliases:binding.aliases||[]}];await persist(m);await activateTarget(binding);linkTarget=-1;}
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
  function position(){const m=activeItem(),box=root.querySelector('#inset-box');if(!m||!box)return;
    const {w,h}=geometry(m);Object.assign(box.style,{left:m.layout.x*100+'%',top:m.layout.y*100+'%',width:w*100+'%',height:h*100+'%'});
    box.querySelector('img').style.objectFit=m.layout.fit;box.querySelector('span').textContent=m.title;
    const heading=root.querySelector('.media-inspector h2');if(heading)heading.textContent=m.title;
    const sizeLabel=root.querySelector('#inset-size-value');if(sizeLabel)sizeLabel.textContent=Math.round(w*100)+'%';
  }
  function draw(){
    if(disposed)return;
    const m=item(),v=visualItem(),shown=activeItem(),ts=targets(),linkBinding=ts[linkTarget];
    root.innerHTML=`<div class="topline"><span class="eyebrow">IL TUO ARCHIVIO VISIVO</span><a class="text-link" href="${projectId?'/projects/'+projectId:'/'}">${projectId?'← Torna al progetto':'Crea un documentario →'}</a></div>
      <h1>Un’immagine. Il suo posto nella storia.</h1>
      <p class="lead">Collega ritratti, luoghi e materiali ai soggetti del racconto. Compariranno in un riquadro, insieme alle mappe e alle altre scene.</p>
      ${project?`<section class="media-project-note"><label class="check"><input id="project-use-media" type="checkbox" ${project.enabled?'checked':''} ${project.frozen?'disabled':''}> Usa le immagini associate in questo progetto</label><p class="tiny muted">${project.visual?.awaiting_review?'La produzione è ferma prima della voce e del rendering. Collega ciò che vuoi usare, poi continua: ricerca, testo e mappe non verranno rifatti.':project.visual?.completed?'Puoi sostituire qualsiasi immagine del film. L’aggiornamento crea una nuova versione e renderizza soltanto le scene interessate.':project.frozen?'Le immagini di questa produzione sono fissate; gli slot restano disponibili per un aggiornamento dopo il completamento.':'Le associazioni sono riutilizzabili anche negli altri documentari. Salvale prima di avviare la produzione.'}</p></section>`:''}
      ${project?.visual?.ready?`<section class="visual-refresh-bar"><div><b>${project.visual.required_count} obbligatori · ${project.visual.suggested_count} suggeriti</b><span>${project.visual.available_count} trovati · ${project.visual.blank_count} placeholder · ${project.visual.disabled_count} esclusi · ${project.visual.change_count} modifiche pronte</span></div>${project.visual.awaiting_review?`<button id="visual-approve" class="primary">Continua produzione</button>`:project.visual.completed?`<button id="visual-refresh" class="primary" ${project.visual.change_count?'':'disabled'}>Aggiorna solo le scene interessate</button>`:''}</section>`:''}
      <section class="card media-library"><div class="media-section-title"><div><span class="eyebrow">01 · CARICA</span><h2>Le tue immagini <span class="media-count">${items.filter(x=>x.enabled).length}</span></h2></div><label class="button secondary media-file-label" for="media-files">+ Aggiungi immagini</label><input class="visually-hidden" id="media-files" type="file" accept="image/jpeg,image/png,image/webp" multiple></div>
        <div id="media-drop" class="media-drop" tabindex="0" role="button" aria-label="Carica immagini trascinandole o scegliendo un file"><span class="media-drop-icon">↥</span><div><strong>Trascina qui le immagini</strong><p>JPG, PNG o WebP · fino a 20 MB · puoi anche trascinarle direttamente su un collegamento</p></div><span id="upload-status" role="status"></span></div>
        <div class="media-library-tools"><label class="visually-hidden" for="media-search">Cerca un’immagine</label><input id="media-search" placeholder="Cerca nelle tue immagini…" value="${esc(filter)}"><span class="tiny muted">La libreria è condivisa. Trascina una scheda sul soggetto oppure usa il pulsante Collega.</span></div>
        <div id="media-cards" class="media-cards">${items.filter(x=>x.enabled&&(!filter||x.title.toLowerCase().includes(filter.toLowerCase()))).map(x=>`<button class="media-card ${selected===x.id&&!selectedSlot?'selected':''}" draggable="true" data-mid="${x.id}" aria-pressed="${selected===x.id&&!selectedSlot}" aria-label="Seleziona ${esc(x.title)}"><img draggable="false" src="/api/media/${x.id}/thumb" alt=""><strong>${esc(x.title)}</strong><small>${x.bindings.length?x.bindings.length+' collegamenti':'Da collegare'} <span>⠿</span></small></button>`).join('')||'<p class="media-empty">Il tuo archivio comincia con la prima immagine.</p>'}</div>
        ${items.some(x=>!x.enabled)?`<details><summary>Immagini archiviate</summary><div class="media-archived">${items.filter(x=>!x.enabled).map(x=>`<button class="secondary" data-restore="${x.id}">Ripristina ${esc(x.title)}</button>`).join('')}</div></details>`:''}
      </section>
      <div class="media-workspace" style="--media-target-width:${targetColumnWidth}px"><section class="card media-targets"><span class="eyebrow">02 · COLLEGA</span><h2>A chi o a cosa?</h2><p class="tiny muted">Un’immagine può avere più collegamenti. Aggiungi un nome, poi trascinaci sopra l’immagine.</p>
        ${m&&!selectedSlot?`<button class="media-selected-drag" draggable="true" data-mid="${m.id}" aria-label="Trascina immagine selezionata"><img draggable="false" src="/api/media/${m.id}/thumb" alt=""><span><small>IMMAGINE SELEZIONATA</small><b>${esc(m.title)}</b><i>Trascinami su un soggetto ↓</i></span></button>`:v?`<div class="media-selected-drag visual-selected">${v.has_preview?`<img src="/api/projects/${projectId}/visual-slots/${encodeURIComponent(v.id)}/image" alt="">`:`<span class="visual-blank">＋</span>`}<span><small>ELEMENTO DEL PROGETTO</small><b>${esc(v.label)}</b><i>Le modifiche compaiono a destra →</i></span></div>`:''}
        <div class="media-target-list">${ts.map((b,i)=>{const attached=linkedItems(b),featured=attached[0];return `<div class="media-target-row"><button class="media-target ${attached.length?'linked':''} ${selectedSlot===b.visual_slot_id?'selected-slot':''} ${b.visual_state?'visual-'+b.visual_state:''}" data-target="${i}" aria-label="${b.visual_slot_id?'Apri':'Seleziona'} ${esc(b.label)}">${featured?`<img loading="lazy" src="/api/media/${featured.id}/thumb" alt="">`:b.visual_slot_id&&b.visual_has_preview?`<img loading="lazy" src="/api/projects/${projectId}/visual-slots/${encodeURIComponent(b.visual_slot_id)}/image" alt="">`:`<span>${icons[b.kind]||'◈'}</span>`}<div><small>${b.visual_slot_id?(b.optional?'SUGGERITA':'OBBLIGATORIA')+' · ':''}${esc(kinds[b.kind]||b.kind)}${b.visual_state?' · '+({blank:'PLACEHOLDER',missing:'DA COMPLETARE',empty:'SFONDO FACOLTATIVO',disabled:'ESCLUSA',available:'TROVATA',user:'PERSONALIZZATA'}[b.visual_state]||'NEL FILM'):''}</small><strong>${esc(b.label)}</strong>${attached.length?`<em>${attached.length} ${attached.length===1?'immagine collegata':'immagini collegate'}</em>`:b.scene_ids?.length?`<em>${b.scene_ids.length} ${b.scene_ids.length===1?'scena':'scene'}</em>`:''}</div></button><div class="media-target-actions"><button class="media-binding-toggle ${attached.length?'linked':''}" data-binding-modal="${i}">${attached.length?'Cambia':'Collega'}</button>${attached.length?`<button data-target-unbind="${i}">Scollega</button>`:''}${b.visual_slot_id?`<button class="visual-slot-toggle ${b.enabled?'enabled':''}" data-visual-toggle="${esc(b.visual_slot_id)}" data-visual-enabled="${b.enabled?'true':'false'}" ${b.visual_editable?'':'disabled title="Disponibile al termine della produzione"'}>${b.visual_editable?(b.enabled?'Escludi':b.optional?'Attiva':'Ripristina'):'Dopo il film'}</button>`:''}</div></div>`}).join('')||'<div class="media-empty">Crea il primo collegamento qui sopra.</div>'}</div>
        <details ${!ts.length?'open':''}><summary>+ Nuovo collegamento</summary><form id="target-form"><label for="target-kind">Tipo di collegamento</label><select id="target-kind">${Object.entries(kinds).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select><label for="target-label">Nome del soggetto</label><input id="target-label" required minlength="2" maxlength="120" placeholder="Es. Annibale, Roma, commercio"><button class="secondary" type="submit">+ Crea collegamento</button></form></details>
        <p class="tiny muted">La comparsa segue i nomi e le varianti presenti nelle frasi narrate. Un collegamento “Scena” segue il titolo della scena.</p>
      </section><button id="media-column-resizer" class="media-column-resizer" type="button" role="separator" aria-orientation="vertical" aria-valuemin="320" aria-valuemax="640" aria-valuenow="${targetColumnWidth}" aria-label="Ridimensiona la colonna dei collegamenti" title="Trascina per allargare o restringere la colonna"><span aria-hidden="true">↔</span></button><section class="media-editor"><div class="media-section-title"><div><span class="eyebrow">03 · COMPONI</span><h2>Il riquadro nel video</h2></div><span id="media-save-state" class="tiny muted" role="status">Salvato sul PC</span></div>
        <div id="inset-stage" class="inset-stage"><div class="inset-stage-heading"><span>ATLANTE STORICO</span><b>Una finestra sul racconto</b></div><div class="inset-stage-timeline"><span>●</span><i></i><span>◷</span><i></i><span>●</span></div>
        ${shown&&(!shown.visual||shown.has_preview)?`<div id="inset-box" class="inset-box" tabindex="0" role="group" aria-label="Riquadro immagine: trascina o usa i tasti freccia"><img draggable="false" src="${shown.visual?`/api/projects/${projectId}/visual-slots/${encodeURIComponent(shown.id)}/image`:`/api/media/${shown.id}/image`}" alt="${esc(shown.title)}"><span>${esc(shown.title)}</span></div>`:`<div class="inset-stage-placeholder">${v?'Nessuna immagine recuperata per '+esc(v.label)+'. Caricane una dal pannello qui sotto.':'Seleziona un’immagine per posizionare il riquadro.'}</div>`}</div>
        <p class="tiny muted">Anteprima di posizione su una mappa dimostrativa · 16:9. Trascina il riquadro; i tasti freccia permettono piccoli spostamenti.</p>
        ${v?`<div class="card media-inspector visual-inspector"><div class="media-section-title"><div><small class="eyebrow">${v.optional?'SUGGERITA':'OBBLIGATORIA'} · ${esc(kinds[v.kind]||v.kind)}</small><h2>${esc(v.label)}</h2></div><button class="text-link" data-visual-toggle="${esc(v.id)}" data-visual-enabled="${v.enabled?'true':'false'}" ${project.visual.editable?'':'disabled'}>${v.enabled?'Escludi dal film':'Ripristina nel film'}</button></div>
          <div class="visual-editor-actions"><label class="button secondary media-file-label" for="visual-replace">Sostituisci immagine</label><input class="visually-hidden" id="visual-replace" type="file" accept="image/jpeg,image/png,image/webp"><span class="tiny muted">Puoi caricare una nuova immagine anche durante la produzione; verrà preparata per la revisione o per la versione successiva.</span></div>
          ${project.visual.editable?`<div class="media-presets" role="group" aria-label="Posizione del riquadro">${[['tl','↖ Alto a sinistra'],['tr','↗ Alto a destra'],['bl','↙ Basso a sinistra'],['br','↘ Basso a destra']].map(([k,l])=>`<button class="secondary" data-corner="${k}">${l}</button>`).join('')}</div><div class="form-grid"><div class="field"><label for="inset-size">Dimensione <span id="inset-size-value"></span></label><input type="range" id="inset-size" min="16" max="36" step="1" value="${Math.round(shown.layout.width*100)}"></div><div class="field"><label for="inset-fit">Inquadratura</label><select id="inset-fit"><option value="contain" ${shown.layout.fit==='contain'?'selected':''}>Immagine intera</option><option value="cover" ${shown.layout.fit==='cover'?'selected':''}>Riempi il riquadro</option></select></div></div>`:`<p class="media-locked">La produzione è in corso. Puoi già preparare una sostituzione; posizione, dimensione ed esclusione saranno modificabili appena il film sarà terminato.</p>`}
          <details><summary>Provenienza e crediti dell’immagine trovata</summary><dl class="visual-source"><dt>Titolo</dt><dd>${esc(v.title||v.label)}</dd><dt>Autore</dt><dd>${esc(v.credit||'Non indicato')}</dd><dt>Licenza</dt><dd>${esc(v.rights||'Non indicata')}</dd><dt>Fonte</dt><dd>${esc(v.source||'Non indicata')}</dd></dl></details>
        </div>`:m?`<div class="card media-inspector"><div class="media-section-title"><h2>${esc(m.title)}</h2><div class="media-inspector-actions"><button class="text-link" id="archive-image">Archivia</button><button class="text-link danger" id="delete-image">Elimina</button></div></div>
          <div class="media-presets" role="group" aria-label="Posizione del riquadro">${[['tl','↖ Alto a sinistra'],['tr','↗ Alto a destra'],['bl','↙ Basso a sinistra'],['br','↘ Basso a destra']].map(([k,l])=>`<button class="secondary" data-corner="${k}">${l}</button>`).join('')}</div>
          <div class="form-grid"><div class="field"><label for="inset-size">Dimensione <span id="inset-size-value"></span></label><input type="range" id="inset-size" min="16" max="36" step="1" value="${Math.round(m.layout.width*100)}"></div><div class="field"><label for="inset-fit">Inquadratura</label><select id="inset-fit"><option value="contain" ${m.layout.fit==='contain'?'selected':''}>Immagine intera</option><option value="cover" ${m.layout.fit==='cover'?'selected':''}>Riempi il riquadro</option></select></div></div>
          <div class="field"><label for="image-title">Titolo nel video</label><input id="image-title" maxlength="120" value="${esc(m.title)}"></div>
          <div class="media-bindings">${m.bindings.map((b,i)=>`<div class="media-binding"><div><span>${esc(kinds[b.kind])} · <b>${esc(b.label)}</b></span><button data-unbind="${i}" aria-label="Rimuovi collegamento ${esc(b.label)}">×</button></div><label for="aliases-${i}">Altri nomi o varianti, separati da virgole</label><input id="aliases-${i}" data-alias="${i}" maxlength="1000" value="${esc((b.aliases||[]).join(', '))}" placeholder="Es. Annibale Barca, generale cartaginese"></div>`).join('')||'<p class="media-unlinked">Aggiungi un collegamento per far comparire questa immagine nel racconto.</p>'}</div>
          <details><summary>Provenienza e crediti</summary>${[['credit','Autore / attribuzione'],['source','Provenienza o URL'],['rights','Licenza o diritti dichiarati']].map(([k,l])=>`<div class="field"><label for="image-${k}">${l}</label><input id="image-${k}" maxlength="${k==='source'?500:300}" value="${esc(m[k])}"></div>`).join('')}<p class="tiny muted">Conserviamo l’originale e riportiamo queste informazioni nei crediti del progetto. Non viene assegnata automaticamente una licenza alle tue immagini.</p></details><button class="secondary" id="media-save">Salva riquadro</button>
        </div>`:''}
      </section></div><p class="footer-note">Le immagini personali rimangono sul PC. Ogni produzione conserva la propria copia; modificare la libreria non cambia i video già creati. Più immagini collegate alla stessa frase si alternano.</p>
      ${linkBinding?`<div class="media-link-modal" role="dialog" aria-modal="true" aria-labelledby="link-modal-title" tabindex="-1"><button class="media-modal-backdrop" data-link-close aria-label="Chiudi"></button><section class="media-link-dialog"><div class="media-section-title"><div><span class="eyebrow">COLLEGA IMMAGINE</span><h2 id="link-modal-title">${esc(linkBinding.label)}</h2></div><button class="media-modal-close" data-link-close aria-label="Chiudi">×</button></div><div id="link-drop" class="media-link-drop"><span class="media-drop-icon">↥</span><div><strong>Trascina qui un’immagine dal PC</strong><p>JPG, PNG o WebP · fino a 20 MB</p></div><label class="button primary media-file-label" for="link-file">Scegli dal computer</label><input class="visually-hidden" id="link-file" type="file" accept="image/jpeg,image/png,image/webp"><span id="link-upload-status" role="status"></span></div>${items.some(x=>x.enabled)?`<div class="media-modal-library"><h3>Oppure scegli dalla libreria</h3><div>${items.filter(x=>x.enabled).map(x=>`<button data-link-mid="${x.id}"><img src="/api/media/${x.id}/thumb" alt=""><span>${esc(x.title)}</span>${x.bindings.some(binding=>sameBinding(binding,linkBinding))?'<small>Già collegata</small>':'<small>Usa questa</small>'}</button>`).join('')}</div></div>`:''}</section></div>`:''}`;
    root.querySelector('#media-files').onchange=e=>upload(e.target.files);
    const zone=root.querySelector('#media-drop');dropzone(zone,e=>upload(e.dataTransfer.files));zone.onclick=()=>root.querySelector('#media-files').click();zone.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();root.querySelector('#media-files').click();}};
    root.querySelector('#media-search').oninput=e=>{filter=e.target.value;const pos=e.target.selectionStart;draw();const input=root.querySelector('#media-search');input.focus();input.setSelectionRange(pos,pos);};
    root.querySelectorAll('[data-mid]').forEach(el=>{el.onclick=()=>{selected=el.dataset.mid;selectedSlot='';draw();};el.ondragstart=e=>{e.dataTransfer.setData('application/x-h3-media',el.dataset.mid);e.dataTransfer.effectAllowed='copy';};});
    root.querySelectorAll('[data-restore]').forEach(el=>el.onclick=()=>{const m=items.find(x=>x.id===el.dataset.restore);m.enabled=true;selected=m.id;persist(m,true);});
    root.querySelector('#target-form').onsubmit=e=>{e.preventDefault();const b={kind:root.querySelector('#target-kind').value,label:root.querySelector('#target-label').value.trim(),aliases:[]};if(b.label.length<2)return;extra.push(b);draw();toast('Collegamento creato. Trascina un’immagine su '+b.label+'.');};
    root.querySelectorAll('[data-target]').forEach(el=>{const b=ts[+el.dataset.target];el.onclick=()=>{linkTarget=-1;if(b.visual_slot_id){selectedSlot=b.visual_slot_id;draw();}else toast('Usa Collega per scegliere o caricare un’immagine.');};dropzone(el,e=>e.dataTransfer.files.length?upload(e.dataTransfer.files,b):bind(e.dataTransfer.getData('application/x-h3-media'),b));});
    root.querySelectorAll('[data-binding-modal]').forEach(el=>el.onclick=()=>{linkTarget=+el.dataset.bindingModal;draw();});
    root.querySelectorAll('[data-target-unbind]').forEach(el=>{const b=ts[+el.dataset.targetUnbind];el.onclick=()=>unbindTarget(b);});
    root.querySelectorAll('[data-link-close]').forEach(el=>el.onclick=()=>{linkTarget=-1;draw();});
    root.querySelectorAll('[data-link-mid]').forEach(el=>el.onclick=()=>bind(el.dataset.linkMid,linkBinding));
    const linkFile=root.querySelector('#link-file');if(linkFile)linkFile.onchange=()=>upload(linkFile.files,linkBinding);
    const linkDrop=root.querySelector('#link-drop');if(linkDrop){dropzone(linkDrop,e=>upload(e.dataTransfer.files,linkBinding));}
    const modal=root.querySelector('.media-link-modal');if(modal){modal.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();linkTarget=-1;draw();}};modal.focus();}
    root.querySelectorAll('[data-visual-toggle]').forEach(el=>el.onclick=async()=>{el.disabled=true;const enabled=el.dataset.visualEnabled!=='true';try{await api('/projects/'+projectId+'/visual-slots/'+encodeURIComponent(el.dataset.visualToggle),{method:'PUT',body:JSON.stringify({enabled})});project=await api('/projects/'+projectId+'/media');draw();toast(enabled?'Riferimento attivato.':'Riferimento escluso dal film.');}catch(e){toast(e.message);el.disabled=false;}});
    const use=root.querySelector('#project-use-media');if(use)use.onchange=async()=>{try{project=await api('/projects/'+projectId+'/media',{method:'PUT',body:JSON.stringify({enabled:use.checked})});}catch(e){toast(e.message);use.checked=project.enabled;}};
    const refresh=root.querySelector('#visual-refresh');if(refresh)refresh.onclick=async()=>{refresh.disabled=true;refresh.textContent='Creo la nuova versione…';try{const data=await api('/projects/'+projectId+'/visual-refresh',{method:'POST'});toast('Nuova versione V'+data.project.version+' creata.');location.href='/projects/'+data.project.id;}catch(e){toast(e.message);refresh.disabled=false;refresh.textContent='Aggiorna solo le scene interessate';}};
    const approve=root.querySelector('#visual-approve');if(approve)approve.onclick=async()=>{approve.disabled=true;approve.textContent='Ripresa in corso…';try{await api('/projects/'+projectId+'/visual-approve',{method:'POST'});toast('Revisione approvata. La produzione riparte dalla voce.');location.href='/projects/'+projectId;}catch(e){toast(e.message);approve.disabled=false;approve.textContent='Continua produzione';}};
    const visualReplace=root.querySelector('#visual-replace');if(visualReplace)visualReplace.onchange=()=>upload(visualReplace.files,{kind:v.kind,label:v.label,aliases:[],visual_slot_id:v.id,visual_editable:project.visual.editable,enabled:v.enabled});
    const workspace=root.querySelector('.media-workspace'),resizer=root.querySelector('#media-column-resizer');
    const columnLimit=()=>Math.max(320,Math.min(640,workspace.getBoundingClientRect().width-540));
    const applyColumnWidth=(value,remember=false)=>{targetColumnWidth=Math.round(Math.max(320,Math.min(columnLimit(),value)));workspace.style.setProperty('--media-target-width',targetColumnWidth+'px');resizer.setAttribute('aria-valuenow',targetColumnWidth);if(remember)localStorage.setItem(columnWidthKey,String(targetColumnWidth));};
    let resizing=null;
    resizer.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();resizer.setPointerCapture(e.pointerId);resizing={x:e.clientX,width:workspace.querySelector('.media-targets').getBoundingClientRect().width};resizer.classList.add('dragging');};
    resizer.onpointermove=e=>{if(resizing)applyColumnWidth(resizing.width+e.clientX-resizing.x);};
    resizer.onpointerup=()=>{if(!resizing)return;resizing=null;resizer.classList.remove('dragging');localStorage.setItem(columnWidthKey,String(targetColumnWidth));};
    resizer.onpointercancel=resizer.onpointerup;
    resizer.ondblclick=()=>applyColumnWidth(380,true);
    resizer.onkeydown=e=>{let value=null;if(e.key==='ArrowLeft')value=targetColumnWidth-20;if(e.key==='ArrowRight')value=targetColumnWidth+20;if(e.key==='Home')value=320;if(e.key==='End')value=columnLimit();if(value!==null){e.preventDefault();applyColumnWidth(value,true);}};
    if(revealRequestedSlot){revealRequestedSlot=false;requestAnimationFrame(()=>root.querySelector('.media-target.selected-slot')?.scrollIntoView({block:'center',behavior:'smooth'}));}
    if(!shown)return;
    position();
    if(m&&!v){
      root.querySelector('#archive-image').onclick=()=>{m.enabled=false;selected=items.find(x=>x.enabled)?.id;persist(m,true);toast('Immagine archiviata. Puoi ripristinarla dalla libreria.');};
      root.querySelector('#delete-image').onclick=async()=>{if(!confirm('Eliminare definitivamente “'+m.title+'” dalla libreria? Le copie già conservate nei progetti non verranno cancellate.'))return;try{await api('/media/'+m.id,{method:'DELETE'});items=items.filter(x=>x.id!==m.id);selected=items.find(x=>x.enabled)?.id;draw();toast('Immagine eliminata dalla libreria.');}catch(e){toast(e.message);}};
      root.querySelector('#media-save').onclick=()=>persist(m);
      root.querySelectorAll('[data-unbind]').forEach(el=>el.onclick=()=>{m.bindings.splice(+el.dataset.unbind,1);persist(m,true);});
      root.querySelectorAll('[data-alias]').forEach(el=>el.onchange=()=>{m.bindings[+el.dataset.alias].aliases=el.value.split(',').map(x=>x.trim()).filter(Boolean).slice(0,12);persist(m);});
      for(const k of ['title','credit','source','rights']){const input=root.querySelector('#image-'+k);input.onchange=()=>{m[k]=input.value.trim()||(k==='title'?'Immagine':'');position();persist(m);};if(k==='title')input.oninput=()=>{m.title=input.value.trim()||'Immagine';position();};}
    }
    const saveLayout=async()=>{if(v){try{await api('/projects/'+projectId+'/visual-slots/'+encodeURIComponent(v.id),{method:'PUT',body:JSON.stringify({layout:shown.layout})});project=await api('/projects/'+projectId+'/media');toast('Inquadratura salvata.');}catch(e){toast(e.message);}}else await persist(m);};
    const fit=root.querySelector('#inset-fit');if(fit)fit.onchange=e=>{shown.layout.fit=e.target.value;position();saveLayout();};
    const range=root.querySelector('#inset-size');if(range){range.oninput=()=>{shown.layout.width=+range.value/100;position();};range.onchange=saveLayout;}
    root.querySelectorAll('[data-corner]').forEach(el=>el.onclick=()=>{const {w,h}=geometry(shown);shown.layout.x=el.dataset.corner[1]==='l'?.02:.98-w;shown.layout.y=el.dataset.corner[0]==='t'?.19:.80-h;position();saveLayout();});
    const box=root.querySelector('#inset-box'),stage=root.querySelector('#inset-stage');let dragging=null;
    if(!box||v&&!project.visual.editable)return;
    box.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();box.focus();box.setPointerCapture(e.pointerId);dragging={x:e.clientX,y:e.clientY,l:shown.layout.x,t:shown.layout.y,rect:stage.getBoundingClientRect()};box.classList.add('dragging');};
    box.onpointermove=e=>{if(!dragging)return;shown.layout.x=dragging.l+(e.clientX-dragging.x)/dragging.rect.width;shown.layout.y=dragging.t+(e.clientY-dragging.y)/dragging.rect.height;position();};
    box.onpointerup=()=>{if(dragging){dragging=null;box.classList.remove('dragging');saveLayout();}};box.onpointercancel=box.onpointerup;
    box.onkeydown=e=>{const delta={ArrowLeft:[-.005,0],ArrowRight:[.005,0],ArrowUp:[0,-.005],ArrowDown:[0,.005]}[e.key];if(delta){e.preventDefault();shown.layout.x+=delta[0];shown.layout.y+=delta[1];position();saveLayout();}};
  }
  draw();return ()=>{disposed=true;};
}
