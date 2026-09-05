const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const copy=value=>JSON.parse(JSON.stringify(value));
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
let active=null,leafletReady=null;

export function validPosition(pos){return Array.isArray(pos)&&pos.length===2&&pos.every(Number.isFinite)&&Math.abs(pos[0])<=179&&Math.abs(pos[1])<=78}
export function wordCount(lines){return lines.join(' ').trim().split(/\s+/u).filter(Boolean).length}

// The saved server draft is distinct from the unsaved browser draft. A late save
// acknowledges only the submitted values, never text entered while it was open.
export class ReviewDraft {
 constructor(value){this.replace(value);this.saving=null}
 replace(value){this.saved=copy(value);this.scenes=copy(value.scenes||[]);this.places=copy(value.places||[])}
 get dirty(){const patch=this.patch();return !!(patch.scenes.length||patch.places.length)}
 patch(){return {revision:this.saved.revision,scenes:this.scenes.filter(s=>!equal(s.lines,this.saved.scenes?.find(x=>x.id===s.id)?.lines)).map(s=>({id:s.id,lines:[...s.lines]})),places:this.places.filter(p=>!equal(p.pos,this.saved.places?.find(x=>x.id===p.id)?.pos)).map(p=>({id:p.id,pos:[...p.pos]}))}}
 setLine(id,index,value){const s=this.scenes.find(x=>x.id===id);if(!s||!Number.isInteger(index)||index<0||index>=s.lines.length)throw Error('Frase non disponibile.');s.lines[index]=String(value)}
 setPosition(id,pos){if(!validPosition(pos))throw Error('Controlla le coordinate: latitudine da −78 a 78 e longitudine da −179 a 179.');const p=this.places.find(x=>x.id===id);if(!p)throw Error('Luogo non disponibile.');p.pos=[...pos]}
 resetScene(id){const old=this.saved.scenes.find(x=>x.id===id),scene=this.scenes.find(x=>x.id===id);if(old&&scene)scene.lines=[...old.lines]}
 resetPlace(id){const old=this.saved.places.find(x=>x.id===id),place=this.places.find(x=>x.id===id);if(old&&place)place.pos=copy(old.pos)}
 restoreScene(id){const scene=this.scenes.find(x=>x.id===id);if(scene?.base_lines)scene.lines=[...scene.base_lines]}
 restorePlace(id){const place=this.places.find(x=>x.id===id);if(place?.base_pos)this.setPosition(id,place.base_pos)}
 async save(write){
  if(this.saving)return this.saving;
  if(!this.dirty)return this.saved;
  if(!this.saved.editable)throw Error(this.saved.reason||'Il progetto non è disponibile per le modifiche.');
  if(this.scenes.some(s=>s.lines.some(line=>!line.trim())))throw Error('Ogni frase deve contenere il testo da leggere. Puoi riscriverla senza lasciarla vuota.');
  const patch=this.patch(),submitted={scenes:copy(this.scenes),places:copy(this.places)};
  this.saving=(async()=>{
   const next=await write(patch);
   const newerScenes=this.scenes.filter(s=>!equal(s.lines,submitted.scenes.find(x=>x.id===s.id)?.lines));
   const newerPlaces=this.places.filter(p=>!equal(p.pos,submitted.places.find(x=>x.id===p.id)?.pos));
   this.replace(next);
   for(const s of newerScenes){const target=this.scenes.find(x=>x.id===s.id);if(target)target.lines=[...s.lines]}
   for(const p of newerPlaces){const target=this.places.find(x=>x.id===p.id);if(target)target.pos=[...p.pos]}
   return next;
  })();
  try{return await this.saving}finally{this.saving=null}
 }
}

export function editorHtml(){return `<div class="review-editor-heading"><div><h2>Rivedi il racconto e i luoghi</h2><p class="tiny muted">Tutto facoltativo. Puoi correggere il testo narrato o spostare un luogo prima di produrre la voce e il video.</p></div><span data-review-badge class="status"></span></div>
 <p data-review-reason class="tiny muted" role="status"></p><div data-review-content hidden>
 <details class="review-section" data-review-text><summary>Testo narrato <span data-review-scene-total></span></summary><div class="review-scene-toolbar"><div class="field"><label for="review-scene">Scena da rivedere</label><select id="review-scene" data-review-scenes></select></div><div class="actions"><button type="button" class="secondary" data-review-reset-text>Annulla modifiche non salvate</button><button type="button" class="secondary" data-review-original-text>Ripristina testo originale</button></div></div><p class="tiny muted" data-review-scene-caption></p><div data-review-lines></div><p class="tiny muted">Ogni casella corrisponde a un passaggio già associato alle animazioni. Puoi riscriverlo; la durata e la sincronizzazione verranno ricalcolate quando continui.</p></details>
 <details class="review-section" data-review-geography><summary>Luoghi sulla mappa <span data-review-place-total></span></summary><p class="tiny muted">Questa mappa serve a posizionare i luoghi. Le coste sono uno sfondo geografico di orientamento, non confini storici. Le correzioni spostano i riferimenti collegati al luogo nelle scene.</p><div class="review-geography-grid"><div class="review-place-sidebar"><div class="field"><label for="review-place-search">Cerca tra i luoghi del progetto</label><input id="review-place-search" data-review-search type="search" placeholder="Nome del luogo"></div><div class="review-place-list" data-review-places role="group" aria-label="Luoghi del progetto"></div></div><div class="review-map-column"><div class="review-map-toolbar"><button type="button" class="secondary" data-review-all>Mostra tutti i luoghi</button><button type="button" class="secondary" data-review-detail aria-pressed="false">Mappa dettagliata online</button></div><p class="tiny muted" data-review-map-note>La mappa iniziale funziona anche senza connessione. I dettagli online richiedono le mappe di OpenStreetMap; viene condivisa soltanto l’area visualizzata.</p><div class="review-map" data-review-map aria-label="Mappa dei luoghi del progetto"></div><p data-review-map-status class="tiny muted" role="status"></p><div class="review-place-controls"><h3 data-review-place-name></h3><p class="tiny muted" data-review-place-scenes></p><div class="actions"><button type="button" class="secondary" data-review-position aria-pressed="false">Posiziona sulla mappa</button><button type="button" class="secondary" data-review-reset-place>Annulla spostamento non salvato</button><button type="button" class="secondary" data-review-original-place>Ripristina posizione originale</button></div><p class="tiny muted">Trascina il segnaposto oppure premi Posiziona sulla mappa e indica il punto. Puoi anche inserire le coordinate qui sotto.</p><details><summary>Coordinate del luogo</summary><div class="form-grid"><div class="field"><label for="review-lat">Latitudine</label><input id="review-lat" data-review-lat type="number" min="-78" max="78" step="any"></div><div class="field"><label for="review-lon">Longitudine</label><input id="review-lon" data-review-lon type="number" min="-179" max="179" step="any"></div></div></details></div></div></div></details>
 <div class="review-save-row"><div><b data-review-save-status role="status" aria-live="polite"></b><p class="tiny muted">Salvare prepara le modifiche. Premi <b>Continua produzione</b> per applicarle al film insieme alle immagini.</p></div><button type="button" class="primary" data-review-save>Salva la revisione</button></div></div><button type="button" data-review-retry class="secondary" hidden>Riprova ad aprire la revisione</button>`}

function loadLeaflet(){
 if(globalThis.L)return Promise.resolve(globalThis.L);
 if(!leafletReady)leafletReady=new Promise((resolve,reject)=>{
  const style=document.createElement('link');style.rel='stylesheet';style.href='/static/vendor/leaflet/leaflet.css';document.head.append(style);
  const script=document.createElement('script');script.src='/static/vendor/leaflet/leaflet.js';script.onload=()=>resolve(globalThis.L);script.onerror=()=>{leafletReady=null;script.remove();reject(Error('Non riesco ad aprire la mappa. Puoi comunque correggere le coordinate o riprovare.'))};document.head.append(script);
 });return leafletReady;
}

function mount(target,id,{api,toast}){
 target.innerHTML=editorHtml();
 const ui={target,id,api,toast,model:null,stateKey:'',sceneId:null,placeId:null,map:null,markers:new Map(),dead:false,loading:null,placing:false};
 ui.node=name=>target.querySelector('[data-review-'+name+']');
 const n=ui.node;
 ui.beforeUnload=event=>{if(ui.model?.dirty){event.preventDefault();event.returnValue=''}};window.addEventListener('beforeunload',ui.beforeUnload);
 n('scenes').onchange=()=>{ui.sceneId=n('scenes').value;renderScene(ui)};
 n('reset-text').onclick=()=>{ui.model.resetScene(ui.sceneId);renderScene(ui);renderStatus(ui)};
 n('original-text').onclick=()=>{ui.model.restoreScene(ui.sceneId);renderScene(ui);renderStatus(ui)};
 n('search').oninput=()=>renderPlaces(ui);
 n('geography').addEventListener('toggle',()=>{if(n('geography').open)ensureMap(ui).catch(error=>{n('map-status').textContent=error.message})});
 n('all').onclick=()=>{if(ui.map)fitPlaces(ui)};
 n('position').onclick=()=>{ui.placing=!ui.placing;renderPlacement(ui)};
 n('reset-place').onclick=()=>{ui.model.resetPlace(ui.placeId);syncMarker(ui,ui.placeId);renderPlace(ui);renderStatus(ui)};
 n('original-place').onclick=()=>{ui.model.restorePlace(ui.placeId);syncMarker(ui,ui.placeId);renderPlace(ui);renderStatus(ui)};
 for(const name of ['lat','lon'])n(name).onchange=()=>{
  const lat=n('lat'),lon=n('lon');
  if(!lat.value.trim()||!lon.value.trim()||!lat.checkValidity()||!lon.checkValidity()){toast('Controlla entrambe le coordinate prima di salvare.');renderPlace(ui);return}
  try{ui.model.setPosition(ui.placeId,[Number(lon.value),Number(lat.value)]);syncMarker(ui,ui.placeId);renderStatus(ui);if(ui.map)ui.map.panTo([Number(lat.value),Number(lon.value)])}catch(error){toast(error.message);renderPlace(ui)}
 };
 n('detail').onclick=()=>toggleDetails(ui).catch(error=>{n('map-status').textContent=error.message});
 n('save').onclick=()=>save(ui).catch(error=>toast(error.message));
 n('retry').onclick=()=>load(ui,true);
 return ui;
}

async function load(ui,force=false){
 if(ui.loading&&!force){ui.loadAgain=true;return ui.loading}
 ui.lastLoad=Date.now();
 const ticket=Symbol();ui.ticket=ticket;ui.node('retry').hidden=true;
 if(!ui.model)ui.node('reason').textContent='Apertura del testo e dei luoghi…';
 ui.loading=(async()=>{
  try{
   const value=await ui.api('/projects/'+encodeURIComponent(ui.id)+'/editorial-review');
   if(ui.dead||ui.ticket!==ticket)return;
   if(ui.model?.dirty){ui.model.saved.editable=value.editable;ui.model.saved.reason=value.reason;renderStatus(ui);return}
   const same=ui.model&&equal(ui.model.saved.scenes,value.scenes)&&equal(ui.model.saved.places,value.places);
   if(ui.model)ui.model.replace(value);else ui.model=new ReviewDraft(value);
   ui.node('content').hidden=!value.available;
   if(!same&&value.available){
    ui.sceneId=ui.model.scenes.some(x=>x.id===ui.sceneId)?ui.sceneId:ui.model.scenes[0]?.id;
    ui.placeId=ui.model.places.some(x=>x.id===ui.placeId)?ui.placeId:ui.model.places[0]?.id;
    ui.node('scenes').innerHTML=ui.model.scenes.map((s,i)=>`<option value="${escape(s.id)}">${i+1}. ${escape(s.title||s.id)}</option>`).join('');
    ui.node('scenes').value=ui.sceneId||'';renderScene(ui);renderPlaces(ui);renderPlace(ui);
    if(ui.map)rebuildMarkers(ui);
   }
   ui.node('scene-total').textContent='· '+ui.model.scenes.length+' scene';ui.node('place-total').textContent='· '+ui.model.places.length+' luoghi';
   renderStatus(ui);
  }catch(error){if(!ui.dead){ui.node('reason').textContent=error.message;ui.node('retry').hidden=false}}
 })();try{await ui.loading}finally{if(ui.ticket===ticket){ui.loading=null;if(ui.loadAgain&&!ui.dead){ui.loadAgain=false;load(ui)}}}
}

function renderScene(ui){
 const s=ui.model.scenes.find(x=>x.id===ui.sceneId),n=ui.node;
 if(!s){n('lines').innerHTML='<p class="tiny muted">Il testo non è ancora disponibile.</p>';return}
 n('lines').innerHTML=s.lines.map((line,i)=>`<div class="field"><label for="review-line-${i}">Passaggio ${i+1}</label><textarea id="review-line-${i}" rows="3" data-review-line="${i}" ${ui.model.saved.editable?'':'disabled'}>${escape(line)}</textarea></div>`).join('');
 for(const field of n('lines').querySelectorAll('textarea'))field.oninput=()=>{ui.model.setLine(s.id,Number(field.dataset.reviewLine),field.value);sceneCaption(ui,s);renderStatus(ui)};
 sceneCaption(ui,s);
}
function sceneCaption(ui,s){ui.node('scene-caption').textContent=[s.date,s.lines.length+' passaggi',wordCount(s.lines)+' parole'].filter(Boolean).join(' · ')}
function renderPlaces(ui){
 const query=ui.node('search').value.trim().toLocaleLowerCase('it'),places=ui.model.places.filter(p=>String(p.name||p.id).toLocaleLowerCase('it').includes(query));
 ui.node('places').innerHTML=places.map(p=>`<button class="review-place ${p.id===ui.placeId?'selected':''}" type="button" data-place-id="${escape(p.id)}" aria-pressed="${p.id===ui.placeId}"><span class="review-place-dot" aria-hidden="true"></span><span>${escape(p.name)}<small>${p.scene_ids.length} ${p.scene_ids.length===1?'scena':'scene'}</small></span></button>`).join('')||'<p class="tiny muted">Nessun luogo corrisponde al nome cercato.</p>';
 for(const button of ui.node('places').querySelectorAll('[data-place-id]'))button.onclick=()=>selectPlace(ui,button.dataset.placeId,true);
}
function selectPlace(ui,id,pan=false){ui.placeId=id;ui.placing=false;renderPlaces(ui);renderPlace(ui);for(const pid of ui.markers.keys())syncMarker(ui,pid);if(pan&&ui.map){const p=ui.model.places.find(x=>x.id===id);if(p&&validPosition(p.pos))ui.map.setView([p.pos[1],p.pos[0]],Math.max(5,ui.map.getZoom()))}}
function renderPlace(ui){
 const p=ui.model.places.find(x=>x.id===ui.placeId),n=ui.node;
 n('place-name').textContent=p?.name||'Nessun luogo nella scena';n('place-scenes').textContent=p?'Collegato a '+p.scene_ids.length+' '+(p.scene_ids.length===1?'scena.':'scene.'):'';
 n('lat').value=validPosition(p?.pos)?String(p.pos[1]):'';n('lon').value=validPosition(p?.pos)?String(p.pos[0]):'';
 renderPlacement(ui);renderStatus(ui);
}
function renderPlacement(ui){const n=ui.node;n('position').setAttribute('aria-pressed',String(ui.placing));n('position').textContent=ui.placing?'Annulla posizionamento':'Posiziona sulla mappa';n('map').classList.toggle('is-placing',ui.placing);if(ui.placing)n('map-status').textContent='Indica sulla mappa la nuova posizione di '+(ui.model.places.find(x=>x.id===ui.placeId)?.name||'questo luogo')+'.';else if(!ui.online)n('map-status').textContent='Puoi ingrandire con + e − e spostare la mappa trascinandola.'}

function renderStatus(ui){
 const n=ui.node,m=ui.model;if(!m)return;
 const editable=m.saved.editable&&!m.saving,dirty=m.dirty;
 n('reason').textContent=m.saved.reason||(!m.saved.editable?'Questa revisione è consultabile. Per correggerla, apri il progetto durante la pausa di revisione.':'Le modifiche sono facoltative: puoi continuare anche senza aprire questi pannelli.');
 n('badge').textContent=m.saved.editable?'Revisione aperta':'Consultazione';
 n('save').disabled=!editable||!dirty;n('save').textContent=m.saving?'Salvataggio…':'Salva la revisione';
 n('save-status').textContent=m.saving?'Salvataggio in corso…':dirty?'Modifiche non ancora salvate':m.saved.dirty?'Revisione salvata · pronta per la produzione':'Nessuna modifica in sospeso';
 for(const field of n('lines').querySelectorAll('textarea'))field.disabled=!editable;
 for(const name of ['reset-text','original-text','reset-place','original-place','position','lat','lon'])n(name).disabled=!editable||(!['reset-text','original-text'].includes(name)&&!ui.placeId);
 n('original-text').disabled=!editable||!ui.model.scenes.find(x=>x.id===ui.sceneId)?.base_lines;
 n('original-place').disabled=!editable||!ui.model.places.find(x=>x.id===ui.placeId)?.base_pos;
 n('geography').hidden=!m.places.length;n('text').hidden=!m.scenes.length;
 for(const marker of ui.markers.values()){if(editable)marker.dragging?.enable();else marker.dragging?.disable()}
 if(!editable&&ui.placing){ui.placing=false;renderPlacement(ui)}
}

async function save(ui){
 if(ui.loading)await ui.loading;
 if(!ui.model)throw Error('Attendi il caricamento della revisione prima di continuare.');
 if(!ui.model.dirty)return;
 const request=ui.model.save(patch=>ui.api('/projects/'+encodeURIComponent(ui.id)+'/editorial-review',{method:'PUT',body:JSON.stringify(patch)}));
 renderStatus(ui);
 try{await request;if(!ui.dead)ui.toast('Revisione salvata. Verrà applicata quando continui la produzione.')}finally{if(!ui.dead)renderStatus(ui)}
}

async function ensureMap(ui){
 if(ui.map){ui.map.invalidateSize();return}
 if(ui.mapLoading)return ui.mapLoading;
 ui.mapLoading=(async()=>{
  const L=await loadLeaflet();if(ui.dead)return;
  const response=await fetch('/static/maps/world-land.geojson');if(!response.ok)throw Error('La mappa di orientamento non è disponibile. Puoi ancora usare le coordinate.');
  const land=await response.json();if(ui.dead)return;
  ui.map=L.map(ui.node('map'),{minZoom:1,maxZoom:18,worldCopyJump:true,scrollWheelZoom:false,maxBounds:[[-78,-179],[78,179]],maxBoundsViscosity:1}).setView([30,15],2);
  // Keep the offline coastline below the optional raster tiles; it remains a
  // backdrop for missing tiles without hiding roads and labels that did load.
  ui.map.createPane('reviewLand').style.zIndex='190';
  ui.land=globalThis.L.geoJSON(land,{pane:'reviewLand',style:{color:'#a4b7a5',weight:.7,fillColor:'#e4ead3',fillOpacity:1},interactive:false,attribution:'<a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener">Natural Earth</a> · pubblico dominio'}).addTo(ui.map);
  ui.map.on('click',event=>{if(!ui.placing||!ui.model.saved.editable||ui.model.saving)return;const point=event.latlng.wrap();try{ui.model.setPosition(ui.placeId,[Number(point.lng.toFixed(6)),Number(point.lat.toFixed(6))]);ui.placing=false;syncMarker(ui,ui.placeId);renderPlace(ui)}catch(error){ui.toast(error.message);syncMarker(ui,ui.placeId)}});
  rebuildMarkers(ui);fitPlaces(ui);ui.map.invalidateSize();
 })();try{await ui.mapLoading}finally{ui.mapLoading=null}
}
function markerIcon(ui,id){return globalThis.L.divIcon({className:'review-pin-container',html:`<span class="review-map-pin ${id===ui.placeId?'selected':''}" aria-hidden="true"></span>`,iconSize:[28,36],iconAnchor:[14,33],tooltipAnchor:[0,-30]})}
function syncMarker(ui,id){const marker=ui.markers.get(id),p=ui.model.places.find(x=>x.id===id);if(!validPosition(p?.pos)){marker?.remove();ui.markers.delete(id);return}if(!marker){if(ui.map)rebuildMarkers(ui);return}marker.setLatLng([p.pos[1],p.pos[0]]);marker.setIcon(markerIcon(ui,id));marker.setZIndexOffset(id===ui.placeId?500:0)}
function rebuildMarkers(ui){
 for(const marker of ui.markers.values())marker.remove();ui.markers.clear();
 for(const p of ui.model.places){
  if(!validPosition(p.pos))continue;
  const marker=globalThis.L.marker([p.pos[1],p.pos[0]],{icon:markerIcon(ui,p.id),draggable:!!ui.model.saved.editable,title:p.name,alt:p.name,keyboard:true}).addTo(ui.map).bindTooltip(escape(p.name),{direction:'top'});
  marker.on('click',()=>selectPlace(ui,p.id));marker.on('dragstart',()=>{ui.placeId=p.id;renderPlaces(ui);renderPlace(ui)});
  marker.on('dragend',()=>{if(!ui.model.saved.editable||ui.model.saving){syncMarker(ui,p.id);return}const point=marker.getLatLng().wrap();try{ui.model.setPosition(p.id,[Number(point.lng.toFixed(6)),Number(point.lat.toFixed(6))])}catch(error){ui.toast(error.message)}syncMarker(ui,p.id);renderPlace(ui)});
  ui.markers.set(p.id,marker);
 }
 renderStatus(ui);
}
function fitPlaces(ui){const points=ui.model.places.filter(p=>validPosition(p.pos)).map(p=>[p.pos[1],p.pos[0]]);if(points.length)ui.map.fitBounds(points,{padding:[45,45],maxZoom:6})}
async function toggleDetails(ui){
 await ensureMap(ui);if(ui.dead||!ui.map)return;
 if(ui.online){ui.online.remove();ui.online=null;ui.node('detail').textContent='Mappa dettagliata online';ui.node('detail').setAttribute('aria-pressed','false');renderPlacement(ui);return}
 ui.online=globalThis.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>',referrerPolicy:'strict-origin-when-cross-origin'}).addTo(ui.map);
 ui.online.on('tileerror',()=>{ui.node('map-status').textContent='Alcuni dettagli online non sono disponibili. La mappa di orientamento e le modifiche restano utilizzabili.'});
 ui.node('detail').textContent='Torna alla mappa offline';ui.node('detail').setAttribute('aria-pressed','true');ui.node('map-status').textContent='Dettagli attuali di OpenStreetMap, utili per orientarsi. Non rappresentano i confini dell’epoca.';
}

export function updateReviewEditor(target,id,project,options){
 if(!target)return;
 if(!active||active.target!==target||active.id!==id){disposeReviewEditor();active=mount(target,id,options)}
 const ui=active,key=project.status+'|'+project.stage+'|'+!!options.presentationBusy;
 if(key!==ui.stateKey){ui.stateKey=key;
  if(ui.model&&['running','queued','cancelling'].includes(project.status)){ui.model.saved.editable=false;ui.model.saved.reason='La produzione è in corso: le modifiche saranno disponibili alla pausa di revisione.';renderStatus(ui)}
  load(ui);
 }else if(project.status==='review'&&ui.model?.saved.available&&!ui.model.saved.editable&&!ui.model.dirty&&!ui.loading&&Date.now()-ui.lastLoad>=7000&&/^Attendi/.test(ui.model.saved.reason||'')){
  // A review can be published just before the worker releases its lock.
  // Retry only this transient state; an ordinary project poll never reloads text.
  load(ui);
 }
}
export async function saveReviewEditor(){if(active?.loading)await active.loading;if(active?.model?.dirty)await save(active)}
export function canLeaveReview(){return !active?.model?.dirty||confirm('Ci sono modifiche alla revisione non salvate. Vuoi uscire e perderle?')}
export function disposeReviewEditor(){if(!active)return;active.dead=true;window.removeEventListener('beforeunload',active.beforeUnload);active.map?.remove();active=null}
