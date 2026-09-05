const safe=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const panels=new WeakMap();
const size=bytes=>bytes>=1e6?(bytes/1e6).toLocaleString('it-IT',{maximumFractionDigits:1})+' MB':Math.ceil((Number(bytes)||0)/1000)+' KB';
const variantName=variant=>variant==='teaching'?'Didattica':'Compatta';
const date=value=>{const parsed=new Date(value);return Number.isNaN(parsed.getTime())?'':parsed.toLocaleString('it-IT',{dateStyle:'short',timeStyle:'short'})};

export function presentationHtml(){
 return `<h2>Presentazione PDF</h2><p class="tiny muted">Le immagini e le mappe del documentario diventano una presentazione da usare a lezione. È un’esportazione separata dal video.</p>
  <form data-pdf-form><fieldset style="border:0;padding:0;margin:0;min-width:0" data-pdf-fields>
   <div class="field"><label for="presentation-variant">Formato delle pagine</label><select id="presentation-variant" data-pdf-variant><option value="compact">Compatta · un’immagine per scena</option><option value="teaching">Didattica · passaggi significativi delle scene</option></select></div>
   <label class="check"><input type="checkbox" data-pdf-narration checked> Includi il testo narrato originale</label><p class="tiny muted">Il testo può aggiungere pagine. Fonti e crediti sono sempre inclusi.</p>
   <button type="submit" class="secondary" data-pdf-create>Crea PDF</button>
  </fieldset></form>
  <p class="connection-result" data-pdf-message role="status" aria-live="polite"></p>
  <div class="hidden" data-pdf-progress><div class="progress-meta"><span>Preparazione della presentazione</span><span data-pdf-percent></span></div><div class="progress-track" role="progressbar" aria-label="Avanzamento della presentazione PDF" aria-valuemin="0" aria-valuemax="100" data-pdf-bar><i data-pdf-fill></i></div></div>
  <div class="space-top" data-pdf-exports></div>`;
}

export function presentationLinks(projectId,exports=[]){
 const files=[...new Map((Array.isArray(exports)?exports:[]).filter(file=>typeof file?.path==='string'&&file.path.toLowerCase().endsWith('.pdf')).map(file=>[file.path,file])).values()].reverse();
 if(!files.length)return '<p class="tiny muted">Le presentazioni pronte compariranno qui. Le esportazioni precedenti vengono conservate.</p>';
 return '<h3>Presentazioni da scaricare</h3><div class="file-list">'+files.map(file=>{
  const label=variantName(file.variant)+' · '+(file.narration==='none'?'senza testo narrato':'con testo narrato');
  return '<a href="/api/projects/'+encodeURIComponent(projectId)+'/file?download=true&amp;path='+encodeURIComponent(file.path)+'" download="'+safe(file.name||'presentazione.pdf')+'"><span>'+safe(label)+'<br><small>'+safe(date(file.created))+'</small></span><span>'+safe(file.pages)+' pagine · '+size(file.bytes)+' ↓</span></a>';
 }).join('')+'</div>';
}

export function updatePresentation(target,projectId,value,{api,toast=()=>{}}={}){
 if(!target)return;
 let panel=panels.get(target);
 if(!panel||panel.projectId!==projectId){
  target.innerHTML=presentationHtml();panel={projectId,state:{},inflight:false,exportSignature:''};panels.set(target,panel);
  const node=name=>target.querySelector('[data-pdf-'+name+']');panel.node=node;
  node('form').onsubmit=async event=>{
   event.preventDefault();if(panel.inflight||panel.state.busy||!panel.state.available)return;
   const options={variant:node('variant').value==='teaching'?'teaching':'compact',narration:node('narration').checked?'full':'none'};
   panel.inflight=true;render(target,panel);node('message').textContent='Avvio della presentazione PDF…';
   try{
    const state=await api('/projects/'+encodeURIComponent(projectId)+'/presentation',{method:'POST',body:JSON.stringify(options)});
    if(!target.isConnected)return;
    panel.state=state;toast('Presentazione PDF avviata. Puoi seguire qui la preparazione.');
   }catch(error){if(target.isConnected)panel.state={...panel.state,status:'failed',error:error.message}}
   finally{panel.inflight=false;if(target.isConnected)render(target,panel)}
  };
 }
 // A slow older polling response must not overwrite a newer export state.
 if(!value?.updated||!panel.state.updated||value.updated>=panel.state.updated)panel.state=value||{};
 render(target,panel);
}

function render(target,panel){
 const {node,state}=panel;
 const busy=panel.inflight||state.busy||['queued','running'].includes(state.status);
 const blocked=busy||!state.available;
 node('fields').disabled=blocked;node('create').disabled=blocked;node('create').textContent=busy?'Preparazione in corso…':'Crea PDF';
 const message=state.error||(!state.available&&state.reason?state.reason:state.message)||state.reason||'Scegli le pagine e crea la presentazione.';
 node('message').textContent=message;node('message').className='connection-result'+(state.error?' bad':state.status==='completed'?' good':'');
 node('progress').classList.toggle('hidden',!busy);
 const progress=Math.min(100,Math.max(0,Number(state.progress)||0));
 node('percent').textContent=Math.round(progress)+'%';node('bar').setAttribute('aria-valuenow',String(progress));node('fill').style.width=progress+'%';
 const signature=JSON.stringify(state.exports||[]);
 if(signature!==panel.exportSignature){node('exports').innerHTML=presentationLinks(panel.projectId,state.exports);panel.exportSignature=signature}
}
