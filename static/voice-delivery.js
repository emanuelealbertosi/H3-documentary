const safe=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const styles=[['original','Voce del modello'],['documentary','Documentario'],['calm','Calmo'],['engaging','Coinvolgente'],['solemn','Solenne']];
const bindings=new Map();
export const previewText='Il viaggio comincia qui. Fra città, incontri e nuove scoperte, seguiamo le tracce di una storia che ha cambiato il mondo.';

export function normalizeDelivery(value={}){
 const bounded=(input,fallback,min,max)=>Number.isFinite(Number(input))?Math.max(min,Math.min(max,Number(input))):fallback;
 return {style:styles.some(([id])=>id===value?.style)?value.style:'original',speed:bounded(value?.speed??1,1,.85,1.15),pause_seconds:bounded(value?.pause_seconds??.18,.18,0,.8)};
}
const percent=value=>Math.round(value*100)+'%';
const seconds=value=>Number(value).toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2})+' s';

export function voiceDeliveryFields(prefix,value={},options={}){
 const delivery=normalizeDelivery(value);
 return `<details class="voice-delivery" id="${prefix}"${options.open?' open':''}><summary>Ritmo e interpretazione della voce</summary>
  <div class="field"><label for="${prefix}-style">Stile della lettura</label><select id="${prefix}-style">${styles.map(([id,label])=>`<option value="${id}"${id===delivery.style?' selected':''}>${label}</option>`).join('')}</select></div>
  <div class="form-grid voice-delivery-sliders">
   <div class="field"><label for="${prefix}-speed">Velocità <output id="${prefix}-speed-value" for="${prefix}-speed">${percent(delivery.speed)}</output></label><input id="${prefix}-speed" type="range" min="0.85" max="1.15" step="0.01" value="${delivery.speed}" aria-describedby="${prefix}-speed-hint"><span class="hint" id="${prefix}-speed-hint">85% più lenta · 100% normale · 115% più rapida</span></div>
   <div class="field"><label for="${prefix}-pause">Pausa fra le frasi <output id="${prefix}-pause-value" for="${prefix}-pause">${seconds(delivery.pause_seconds)}</output></label><input id="${prefix}-pause" type="range" min="0" max="0.8" step="0.01" value="${delivery.pause_seconds}" aria-describedby="${prefix}-pause-hint"><span class="hint" id="${prefix}-pause-hint">Da una lettura continua a pause più ampie.</span></div>
  </div>
  <p id="${prefix}-capabilities" class="tiny muted" role="status"></p>
  <p class="tiny muted">Personalizzando la lettura, la durata segue la voce. Il testo del racconto rimane invariato.</p>
  ${options.preview===false?'':`<details class="voice-preview"><summary>Ascolta prima di produrre il video</summary><div class="field"><label for="${prefix}-text">Testo della prova</label><textarea id="${prefix}-text" rows="3" maxlength="500">${safe(options.text||previewText)}</textarea><span class="hint">Una breve prova usa soltanto la voce scelta; non avvia un documentario.</span></div><div class="actions"><button type="button" class="secondary" id="${prefix}-preview">Ascolta questa lettura</button><button type="button" class="text-link" id="${prefix}-original">Confronta con la voce normale</button></div><p id="${prefix}-result" class="connection-result" role="status" aria-live="polite"></p><audio id="${prefix}-player" controls class="hidden" preload="none" aria-label="Prova della voce"></audio></details>`}
 </details>`;
}

export function readVoiceDelivery(prefix){
 const value=suffix=>document.getElementById(prefix+'-'+suffix)?.value;
 return normalizeDelivery({style:value('style'),speed:value('speed'),pause_seconds:value('pause')});
}

export function deliveryCapabilityNote(engine,delivery){
 const capabilities=engine?.delivery_capabilities;
 if(capabilities?.note){const unsupported=delivery.style!=='original'&&Array.isArray(capabilities.styles)&&!capabilities.styles.includes(delivery.style);return (unsupported?'Questa voce non applica lo stile espressivo selezionato; velocità e pause restano disponibili. ':'')+capabilities.note}
 return delivery.style==='original'?'La voce mantiene l’interpretazione del modello. Puoi regolare velocità e pause.':'Il tono espressivo dipende dalla voce scelta. Se non è supportato, vengono applicati soltanto velocità e pause.';
}

export async function requestVoicePreview(payload,signal){
 const response=await fetch('/api/tts/preview',{method:'POST',headers:{'Content-Type':'application/json','X-DocumentariAI':'studio'},body:JSON.stringify(payload),signal});
 if(!response.ok){let message='La prova della voce non è riuscita.';try{const result=await response.json();message=typeof result.detail==='string'?result.detail:message}catch{}throw Error(message)}
 const blob=await response.blob();blob.h3StyleFallback=response.headers?.get('X-Voice-Style-Fallback')==='true';return blob;
}

function stylesheet(){
 if(document.getElementById('voice-delivery-css'))return;
 const link=document.createElement('link');link.id='voice-delivery-css';link.rel='stylesheet';link.href='/static/voice-delivery.css'+new URL(import.meta.url).search;document.head.append(link);
}

export function bindVoiceDelivery(prefix,{tts,engineId,referenceId,getSelection,requestPreview=requestVoicePreview}={}){
 const element=document.getElementById(prefix);
 if(!element)return;
 if(bindings.get(prefix)?.element===element)return;
 bindings.get(prefix)?.dispose();stylesheet();
 const node=suffix=>element.querySelector('[id="'+prefix+'-'+suffix+'"]'),engine=document.getElementById(engineId);
 const listeners=[];let objectUrl='',controller;
 const on=(target,event,callback)=>{target?.addEventListener(event,callback);listeners.push(()=>target?.removeEventListener(event,callback))};
 const update=()=>{
  const delivery=readVoiceDelivery(prefix);
  node('speed-value').textContent=percent(delivery.speed);node('pause-value').textContent=seconds(delivery.pause_seconds);
  node('capabilities').textContent=deliveryCapabilityNote((tts?.engines||[]).find(x=>x.id===engine?.value),delivery);
 };
 const selection=()=>{
  if(getSelection)return getSelection();
  const value=engine?.value||'kokoro';
  return {...(value.startsWith('api:')?{tts_engine:'api',tts_profile_id:value.slice(4)}:{tts_engine:value,tts_profile_id:''}),tts_reference_id:document.getElementById(referenceId)?.value||''};
 };
 const play=async original=>{
  const text=node('text').value.trim(),result=node('result'),buttons=[node('preview'),node('original')];
  if(!text){result.textContent='Scrivi una breve frase da ascoltare.';result.className='connection-result bad';return}
  if(text.length>500){result.textContent='La prova può contenere al massimo 500 caratteri.';result.className='connection-result bad';return}
  const delivery=original?normalizeDelivery():readVoiceDelivery(prefix);
  buttons.forEach(b=>b.disabled=true);result.textContent='Preparo una breve prova con la voce scelta…';result.className='connection-result';
  controller?.abort();controller=new AbortController();
  try{
   const blob=await requestPreview({...selection(),text,tts_delivery:delivery},controller.signal);
   if(!element.isConnected)return;
   const player=node('player');player.pause();if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=URL.createObjectURL(blob);player.src=objectUrl;player.classList.remove('hidden');
   result.textContent=blob.h3StyleFallback?'Il server non ha accettato le indicazioni espressive: la prova usa l’interpretazione originale, con velocità e pause scelte.':original?'Prova della voce normale pronta.':'Prova con le impostazioni scelte pronta.';result.className='connection-result'+(blob.h3StyleFallback?'':' good');
   try{await player.play()}catch{result.textContent+=' Premi Riproduci per ascoltarla.'}
  }catch(error){if(error.name!=='AbortError'&&element.isConnected){result.textContent=error.message;result.className='connection-result bad'}}
  finally{if(element.isConnected)buttons.forEach(b=>b.disabled=false)}
 };
 on(node('style'),'change',update);on(node('speed'),'input',update);on(node('pause'),'input',update);on(engine,'change',update);
 on(node('preview'),'click',()=>play(false));on(node('original'),'click',()=>play(true));update();
 const dispose=()=>{controller?.abort();listeners.forEach(remove=>remove());node('player')?.pause();if(objectUrl)URL.revokeObjectURL(objectUrl)};
 bindings.set(prefix,{element,dispose});
}

export function disposeVoiceDelivery(){for(const binding of bindings.values())binding.dispose();bindings.clear()}
