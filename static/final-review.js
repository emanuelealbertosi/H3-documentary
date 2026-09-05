const safe=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const panels=new WeakMap();

export function finalReviewHtml(projectId,state={}){
 const busy=!!state.busy,editing=!!state.editing,revision=Number(state.revision_number)||0;
 const scenes=state.changed_scene_ids||state.changed_scenes||[];
 const count=Array.isArray(scenes)?scenes.length:Number(scenes)||0;
 if(!state.available&&!editing&&!busy)return '';
 const message=state.error||(!busy&&state.can_open===false?'Attendi il termine dell’attività in corso prima di modificare questo video.':state.message)||(busy?'L’aggiornamento è in corso. Il film precedente resta disponibile qui sotto.':editing?'Correggi ciò che vuoi, salva la revisione e aggiorna questo video.':'Puoi tornare sul testo, sui luoghi e sulle immagini del film completato.');
 return '<div class="card-head"><h2>'+ (busy?'Aggiornamento del video':editing?'Revisione del video completato':'Rivedi il video completato')+'</h2>'+(revision?'<span class="status">Revisione '+revision+'</span>':'')+'</div>'+
  '<p class="'+(state.error?'connection-result bad':'tiny muted')+'" role="status" aria-live="polite">'+safe(message)+'</p>'+
  (busy?'<p class="tiny muted">Il video già pronto rimane consultabile durante il lavoro. Le modifiche saranno pubblicate in questo progetto al termine della verifica.</p>':
   editing?'<p class="tiny muted">Tutto facoltativo: testi e luoghi nei pannelli qui sotto, immagini nella galleria. Vengono aggiornate le scene coinvolte, riutilizzando l’audio invariato. Se cambia la durata, possono essere aggiornate anche altre scene per mantenere corretta la timeline.</p><div class="actions"><button type="button" class="primary" data-final-action="render">Aggiorna questo video</button><button type="button" class="secondary" data-final-focus>Testi e luoghi ↓</button><a class="button secondary" href="/projects/'+encodeURIComponent(projectId)+'/media">Immagini e riquadri</a><button type="button" class="secondary" data-final-action="discard">Annulla revisione</button></div><p class="tiny muted">Il progetto resta lo stesso. La ricerca non viene ripetuta. Annulla revisione ripristina le modifiche preparate per questo aggiornamento; le immagini caricate rimangono nella libreria.</p>':
   '<div class="actions"><button type="button" class="primary" data-final-action="open">Riapri revisione</button></div><p class="tiny muted">Correggi questo film nello stesso progetto. Usa Prepara nuova versione se vuoi ripartire dalla ricerca con un’altra versione.</p>')+
  (count?'<p class="tiny muted">'+count+' '+(count===1?'scena coinvolta':'scene coinvolte')+' nell’ultimo aggiornamento.</p>':'');
}

// Keep all routes on the same project. A failed draft save must never queue a
// render with older text, and an open/discard action must never start the engine.
export async function performFinalReviewAction(action,projectId,{api,save=async()=>{}}){
 const path='/projects/'+encodeURIComponent(projectId)+'/final-review';
 if(action==='open')return api(path,{method:'POST'});
 if(action==='discard')return api(path,{method:'DELETE'});
 if(action==='render'){await save();return api(path+'/render',{method:'POST'})}
 throw Error('Azione di revisione non disponibile.');
}

export function updateFinalReview(target,projectId,state,options){
 if(!target)return;
 let panel=panels.get(target);
 if(!panel||panel.projectId!==projectId){panel={projectId,inflight:false,state:{},html:''};panels.set(target,panel)}
 panel.options=options;
 // Mutation responses are newer than a poll that began before the button click.
 if(!panel.inflight&&(!state?.updated||!panel.state.updated||state.updated>=panel.state.updated))panel.state=state||{};
 renderPanel(target,panel);
}

function renderPanel(target,panel){
 const html=finalReviewHtml(panel.projectId,{...panel.state,error:panel.requestError||panel.state.error});
 target.hidden=!html;
 if(panel.html!==html){target.innerHTML=html;panel.html=html}
 for(const button of target.querySelectorAll('[data-final-action]')){
  button.disabled=panel.inflight||panel.state.busy||panel.state.can_open===false;
  button.onclick=async()=>{
   if(panel.inflight||panel.state.busy||panel.state.can_open===false)return;
   const action=button.dataset.finalAction,options=panel.options;
   if(action==='discard'&&!confirm('Annullare le modifiche di questa revisione e conservare il film già pronto? Le immagini caricate rimarranno nella libreria.'))return;
   panel.inflight=true;panel.requestError='';renderPanel(target,panel);
   try{
    const next=await performFinalReviewAction(action,panel.projectId,{api:options.api,save:options.save});
    if(!target.isConnected)return;
    panel.state=next||panel.state;
    if(action==='discard')options.discard?.();
    options.toast?.(action==='open'?'Revisione aperta nello stesso progetto.':action==='discard'?'Revisione annullata. Il film già pronto è conservato.':'Aggiornamento avviato nello stesso progetto.');
    await options.refresh?.();
   }catch(error){if(target.isConnected){panel.requestError=error.message;options.toast?.(error.message)}}
   finally{panel.inflight=false;if(target.isConnected)renderPanel(target,panel)}
  };
 }
 const focus=target.querySelector('[data-final-focus]');if(focus){focus.disabled=panel.inflight;focus.onclick=()=>panel.options.focus?.()}
}
