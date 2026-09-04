/* Private source library: upload, paste, metadata and per-project selection. */
export async function documentsPage({api,esc,toast,projectId}) {
  const root=document.querySelector('#app');
  let state=projectId?await api('/projects/'+projectId+'/documents'):{documents:await api('/documents'),selected_ids:[],enabled:true,editable:true,frozen:false};
  let selected=state.documents.find(x=>x.enabled)?.id||state.documents[0]?.id;
  const item=()=>state.documents.find(x=>x.id===selected);
  const statusName=x=>({indexed:'Indicizzato · ricerca semantica',text_ready:'Testo pronto · ricerca lessicale',needs_ocr:'PDF scansionato · OCR necessario'}[x.status]||x.status);
  async function upload(files){
    for(const file of [...files]){
      const status=root.querySelector('#document-upload-status');if(status)status.textContent='Estraggo e indicizzo '+file.name+'…';
      try{
        if(file.size>50*1024*1024)throw Error(file.name+': supera 50 MB.');
        const response=await fetch('/api/documents/file?filename='+encodeURIComponent(file.name),{method:'POST',headers:{'X-DocumentariAI':'studio','Content-Type':'application/octet-stream'},body:file});
        const data=await response.json();if(!response.ok)throw Error(data.detail||'Caricamento non riuscito.');
        state.documents.unshift(data);selected=data.id;
        if(projectId&&state.editable&&data.status!=='needs_ocr'){state.selected_ids.push(data.id);await saveSelection();}
      }catch(error){toast(error.message);}
    }
    draw();
  }
  async function saveSelection(){
    if(!projectId||!state.editable)return;
    state=await api('/projects/'+projectId+'/documents',{method:'PUT',body:JSON.stringify({enabled:state.enabled,document_ids:[...new Set(state.selected_ids)]})});
  }
  function dropzone(element){
    element.ondragover=e=>{e.preventDefault();element.classList.add('drag-over');};
    element.ondragleave=()=>element.classList.remove('drag-over');
    element.ondrop=e=>{e.preventDefault();element.classList.remove('drag-over');upload(e.dataTransfer.files);};
  }
  function draw(){
    const current=item(),active=state.documents.filter(x=>x.enabled);
    root.innerHTML=`<div class="topline"><span class="eyebrow">FONTI PRIVATE E RAG LOCALE</span><a class="text-link" href="${projectId?'/projects/'+projectId:'/'}">${projectId?'← Torna al progetto':'Crea un documentario →'}</a></div>
      <h1>I tuoi documenti, dentro il racconto.</h1><p class="lead">Carica testi e libri oppure incolla un contenuto. L’indice resta sul PC e porta al modello solo i passaggi pertinenti.</p>
      ${projectId?`<section class="document-project-note"><label class="check"><input id="project-use-documents" type="checkbox" ${state.enabled?'checked':''} ${state.frozen?'disabled':''}> Usa i documenti selezionati in questo progetto</label><p class="tiny muted">${state.frozen?'Questa versione conserva la propria selezione. Puoi comunque aggiungere documenti all’archivio e sceglierli nelle “Impostazioni per la prossima versione” del progetto.':'Spunta sotto le fonti pertinenti prima di avviare la produzione.'}</p></section>`:''}
      <div class="document-grid"><section class="card"><div class="media-section-title"><div><span class="eyebrow">01 · AGGIUNGI</span><h2>File o testo</h2></div><label class="button secondary media-file-label" for="document-files">+ Carica documenti</label><input class="visually-hidden" id="document-files" type="file" accept=".pdf,.docx,.txt,.md,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document" multiple></div>
        <div id="document-drop" class="media-drop" tabindex="0"><span class="media-drop-icon">⇧</span><div><strong>Trascina qui PDF, DOCX, TXT o Markdown</strong><p>Fino a 50 MB · PDF con testo selezionabile · tutto rimane sul computer</p></div><span id="document-upload-status" role="status"></span></div>
        <details class="document-paste"><summary>Oppure incolla direttamente un testo</summary><form id="paste-document"><div class="form-grid"><div class="field"><label for="paste-title">Titolo</label><input id="paste-title" required maxlength="180"></div><div class="field"><label for="paste-author">Autore</label><input id="paste-author" maxlength="160"></div></div><div class="form-grid"><div class="field"><label for="paste-year">Anno</label><input id="paste-year" maxlength="40"></div><div class="field"><label for="paste-provenance">Provenienza</label><input id="paste-provenance" maxlength="500"></div></div><div class="field"><label for="paste-text">Testo</label><textarea id="paste-text" required minlength="80" rows="10" placeholder="Incolla qui il testo della fonte…"></textarea></div><button class="primary">Salva e indicizza</button></form></details>
      </section><section class="card"><span class="eyebrow">02 · SCEGLI</span><h2>Archivio locale <span class="media-count">${active.length} disponibili</span></h2><div class="document-list">${state.documents.map(x=>`<div class="document-row ${selected===x.id?'selected':''} ${x.enabled?'':'inactive'}">${projectId?`<input type="checkbox" data-document-check="${x.id}" ${state.selected_ids.includes(x.id)?'checked':''} ${(state.frozen||x.status==='needs_ocr'||!x.enabled)?'disabled':''} aria-label="Usa ${esc(x.title)}">`:''}<button data-document="${x.id}"><b>${esc(x.title)}</b><small>${esc(x.author||x.filename)} · ${x.characters.toLocaleString('it-IT')} caratteri</small><span class="document-state ${x.status}">${esc(statusName(x))}${x.enabled?'':' · non disponibile'}</span></button></div>`).join('')||'<p class="media-empty">Aggiungi il primo documento. I file non vengono inviati a servizi esterni.</p>'}</div></section></div>
      ${current?`<section class="card document-inspector"><div class="media-section-title"><div><span class="eyebrow">03 · DESCRIVI LA FONTE</span><h2>${esc(current.title)}</h2></div><a class="button secondary" href="/api/documents/${current.id}/file">Apri originale</a></div><form id="document-edit"><div class="form-grid"><div class="field"><label for="document-title">Titolo</label><input id="document-title" required maxlength="180" value="${esc(current.title)}"></div><div class="field"><label for="document-author">Autore</label><input id="document-author" maxlength="160" value="${esc(current.author)}"></div><div class="field"><label for="document-year">Anno o periodo</label><input id="document-year" maxlength="40" value="${esc(current.year)}"></div><div class="field"><label for="document-provenance">Edizione, archivio o provenienza</label><input id="document-provenance" maxlength="500" value="${esc(current.provenance)}"></div></div><label class="check"><input id="document-enabled" type="checkbox" ${current.enabled?'checked':''}> Disponibile per nuovi progetti</label><button class="secondary">Salva informazioni</button><p class="tiny muted">${esc(current.filename)} · ${current.pages} pagine/sezioni · ${current.chunks} passaggi. ${current.index_error?esc(current.index_error):'Indice locale pronto.'}</p></form></section>`:''}
      <p class="footer-note">Il RAG usa un piccolo modello multilingue su CPU e una ricerca lessicale di riserva. I documenti sono fonti, non istruzioni: eventuali comandi presenti nel testo vengono ignorati.</p>`;
    root.querySelector('#document-files').onchange=e=>upload(e.target.files);
    const zone=root.querySelector('#document-drop');dropzone(zone);zone.onclick=()=>root.querySelector('#document-files').click();zone.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();root.querySelector('#document-files').click();}};
    root.querySelectorAll('[data-document]').forEach(button=>button.onclick=()=>{selected=button.dataset.document;draw();});
    root.querySelectorAll('[data-document-check]').forEach(box=>box.onchange=async()=>{if(box.checked)state.selected_ids.push(box.dataset.documentCheck);else state.selected_ids=state.selected_ids.filter(x=>x!==box.dataset.documentCheck);try{await saveSelection();toast('Selezione delle fonti salvata.');}catch(error){toast(error.message);draw();}});
    const use=root.querySelector('#project-use-documents');if(use)use.onchange=async()=>{state.enabled=use.checked;try{await saveSelection();}catch(error){toast(error.message);draw();}};
    root.querySelector('#paste-document').onsubmit=async e=>{e.preventDefault();e.submitter.disabled=true;try{const value={title:root.querySelector('#paste-title').value,author:root.querySelector('#paste-author').value,year:root.querySelector('#paste-year').value,provenance:root.querySelector('#paste-provenance').value,enabled:true,text:root.querySelector('#paste-text').value};const doc=await api('/documents/text',{method:'POST',body:JSON.stringify(value)});state.documents.unshift(doc);selected=doc.id;if(projectId&&state.editable){state.selected_ids.push(doc.id);await saveSelection();}draw();toast('Testo indicizzato sul computer.');}catch(error){toast(error.message);e.submitter.disabled=false;}};
    const edit=root.querySelector('#document-edit');if(edit)edit.onsubmit=async e=>{e.preventDefault();const value={title:root.querySelector('#document-title').value,author:root.querySelector('#document-author').value,year:root.querySelector('#document-year').value,provenance:root.querySelector('#document-provenance').value,enabled:root.querySelector('#document-enabled').checked};try{const updated=await api('/documents/'+current.id,{method:'PUT',body:JSON.stringify(value)});Object.assign(current,updated);draw();toast('Informazioni della fonte salvate.');}catch(error){toast(error.message);}};
  }
  draw();
  return ()=>{};
}
