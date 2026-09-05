const safe=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const panels=new WeakMap();
const elementNames={movement:'Movimento',movements:'Movimenti',route:'Percorso',routes:'Percorsi',territory:'Territorio',territories:'Territori',territory_ids:'Area',asset_ids:'Immagine',scene_type:'Tipo scena',region:'Regione',regions:'Regioni',network:'Rete',networks:'Reti',data:'Dati',data_visualization:'Grafico',map:'Mappa',camera:'Inquadratura',visual:'Elemento visuale'};
const elementLabel=value=>[...new Set(value.split(',').map(item=>item.trim()).map(item=>/^movements\[\d+\]$/.test(item)?'Percorso':elementNames[item]||item))].join(', ');
function reasonLabel(value){
 return value.replace(/movements\[\d+\]\s+termina a (['"])(.*?)\1, ma titolo\/event della scena non nominano questa destinazione\.\s*La stessa scena deve raccontare esplicitamente la partenza o l[’']arrivo;\s*altrimenti sposta o rimuovi il movimento\./gs,(_,quote,name)=>'Il percorso verso '+name+' non è descritto in questa scena; è stato escluso per evitare una freccia incoerente.')
  .replace(/Riferimenti visuali non disponibili:[^.]*\./g,'Un’area o un’immagine prevista non è disponibile.');
}

// Only public descriptions reach the UI. Raw model data stays in the checkpoint.
export function visualRecoveryRows(project={},visual={}){
 const warnings=Array.isArray(visual.visual_warnings)&&visual.visual_warnings.length?visual.visual_warnings:(Array.isArray(project.result?.visual_warnings)?project.result.visual_warnings:[]);
 const slots=Array.isArray(visual.slots)?visual.slots:[];
 const groups=new Map();
 for(const warning of warnings){
  if(!warning||typeof warning!=='object')continue;
  const sceneId=typeof warning.scene_id==='string'?warning.scene_id:'';
  const sceneIndex=Number.isInteger(warning.scene_index)&&warning.scene_index>=0?warning.scene_index:null;
  const title=typeof warning.scene_title==='string'&&warning.scene_title.trim()?warning.scene_title:(sceneId||'Scena da controllare');
  const key=sceneId||title+'|'+sceneIndex;
  let group=groups.get(key);
  if(!group){group={sceneId,sceneIndex,title,placeholder:false,slotId:'',issues:[]};groups.set(key,group)}
  group.placeholder=group.placeholder||warning.placeholder===true;
  if(typeof warning.slot_id==='string')group.slotId=warning.slot_id;
  const element=elementLabel(typeof warning.element==='string'?warning.element:'visual');
  const reason=reasonLabel(typeof warning.reason==='string'&&warning.reason.trim()?warning.reason:'L’elemento non è utilizzabile e non è stato disegnato.');
  if(!group.issues.some(issue=>issue.element===element&&issue.reason===reason))group.issues.push({element,reason});
 }
 return [...groups.values()].map(group=>{
  const slot=slots.find(item=>item.id===group.slotId)||(group.placeholder?slots.find(item=>item.source_type==='scene_background'&&(item.scene_ids||[]).includes(group.sceneId)):null);
  group.slotId=slot?.id||group.slotId;
  group.canManage=Boolean(visual.ready&&(!group.placeholder||group.slotId));
  const excluded=slot&&(slot.enabled===false||slot.state==='disabled');
  const filled=slot&&(slot.replacement_ready||['user','available'].includes(slot.state));
  group.state=!group.placeholder?'omitted':excluded?'excluded':filled?'filled':'pending';
  return group;
 });
}

export function visualRecoveryHtml(projectId,project={},visual={}){
 const rows=visualRecoveryRows(project,visual);
 if(!rows.length)return '';
 const pending=rows.filter(row=>row.state==='pending').length;
 const hasCards=rows.some(row=>row.placeholder);
 const awaiting=project.status==='review'&&visual.awaiting_review;
 const title=pending?'Scene da completare a mano':'Elementi visuali da controllare';
 const introduction=awaiting&&hasCards?'La produzione è ferma per la revisione. Per le scene indicate puoi collegare una mappa preparata da te o un’immagine alla scheda.':hasCards?'Per le scene indicate è prevista una scheda da completare con una mappa preparata da te o un’immagine.':'Alcuni elementi grafici non utilizzabili sono stati esclusi. Le scene conservano gli altri elementi validi.';
 const ready=(visual.ready?(hasCards?'Apri Gestisci per collegare il materiale. La sostituzione aggiunge l’immagine alla scena; non ricostruisce l’elemento omesso.':'Controlla le anteprime. Da Gestisci puoi aprire i materiali del progetto.'):'I collegamenti per controllare i materiali saranno disponibili dopo la loro preparazione.')+(awaiting&&hasCards?' Puoi anche premere Continua produzione lasciando la scheda vuota, oppure escluderla da Gestisci.':'');
 const labels={pending:'Da completare',filled:'Immagine collegata',excluded:'Scheda esclusa',omitted:'Elemento omesso'};
 const base='/projects/'+encodeURIComponent(projectId)+'/media';
 return '<section class="banner space-bottom" aria-label="Elementi visuali da controllare"><b>'+title+'</b><p>'+introduction+'</p><p>'+ready+'</p>'+
  '<details data-visual-recovery-details'+(pending?' open':'')+'><summary>'+rows.length+' '+(rows.length===1?'scena da controllare':'scene da controllare')+(pending?' · '+pending+' da completare':'')+'</summary><div class="info-list">'+rows.map(row=>{
   const href=base+(row.slotId?'?slot='+encodeURIComponent(row.slotId):'');
   const stateClass=row.state==='filled'?'':'warn';
   return '<div data-recovery-scene="'+safe(row.sceneId)+'"><b>'+safe(row.title)+'</b> <span class="status '+stateClass+'">'+labels[row.state]+'</span>'+
    row.issues.map(issue=>'<p><strong>'+safe(issue.element)+'</strong> · '+safe(issue.reason)+'</p>').join('')+
    (row.canManage?'<a class="text-link" href="'+href+'" aria-label="Gestisci '+safe(row.title)+'">Gestisci →</a>':'<span class="tiny muted">Preparazione dei materiali in corso.</span>')+'</div>';
  }).join('')+'</div></details><p class="tiny">Il motivo dell’esclusione resta nel progetto anche dopo aver collegato un’immagine.</p></section>';
}

export function updateVisualRecovery(target,projectId,project={},visual={}){
 if(!target)return;
 const html=visualRecoveryHtml(projectId,project,visual);
 const old=panels.get(target);
 if(old?.projectId===projectId&&old.html===html)return;
 const details=target.querySelector('[data-visual-recovery-details]');
 const expanded=old?.projectId===projectId&&details?details.open:null;
 target.innerHTML=html;panels.set(target,{projectId,html});
 if(expanded!==null){const next=target.querySelector('[data-visual-recovery-details]');if(next)next.open=expanded}
}
