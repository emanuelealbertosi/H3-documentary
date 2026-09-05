import {normalizeDelivery,previewText} from './voice-delivery.js?v=1.17.1';
const providers={
 openai:{name:'OpenAI compatibile',base_url:'http://localhost:8000/v1',model:'tts-1',voice:'',format:'mp3',timeout:180,hint:'Per server locali che espongono POST /v1/audio/speech.'},
 higgs:{name:'Higgs TTS remoto',base_url:'http://localhost:8095/v1',model:'',voice:'',format:'wav',timeout:900,hint:'Contratto Higgs Audio v3: H3 carica il modello prima della sintesi e lo scarica al termine. Il server HTTP resta attivo.'},
 elevenlabs:{name:'ElevenLabs',base_url:'https://api.elevenlabs.io/v1',model:'eleven_multilingual_v2',voice:'',format:'mp3',timeout:180,hint:'Inserisci il voice ID già disponibile nel tuo account.'},
 google:{name:'Google Cloud TTS',base_url:'https://texttospeech.googleapis.com/v1',model:'',voice:'it-IT-Standard-A',format:'wav',timeout:180,hint:'Usa token OAuth, JSON service account o credenziali Google predefinite sul PC.'}
};
const q=s=>document.querySelector(s);
const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export function ttsSelection(value){
 value=String(value||'kokoro');
 return value.startsWith('api:')?{tts_engine:'api',tts_profile_id:value.slice(4)}:{tts_engine:value,tts_profile_id:''};
}
export function projectTtsSelection(project){
 return project.tts_engine==='api'&&project.tts_profile_id?'api:'+project.tts_profile_id:(project.tts_engine||'kokoro');
}
export function bindReference(engineId,referenceId,tts){
 const engine=q('#'+engineId),reference=q('#'+referenceId);if(!engine||!reference)return;
 const update=()=>{
  const item=(tts.engines||[]).find(x=>x.id===engine.value);
  reference.disabled=!item?.supports_reference;
  if(reference.disabled)reference.value='';
  reference.title=reference.disabled?'Questa voce non usa un campione one-shot.':'';
 };
 engine.addEventListener('change',update);update();
}

function number(id,fallback){const value=+q('#'+id).value;return Number.isFinite(value)?value:fallback}
function generationSeed(provider){
 if(provider!=='higgs'||!q('#tts-api-keep-seed').checked)return -1;
 const input=q('#tts-api-seed'),value=Number(input.value);
 if(!String(input.value).trim()||!Number.isInteger(value)||value<0||value>2147483647)throw Error('Il seed deve essere un numero intero tra 0 e 2147483647.');
 return value;
}
function formValue(){
 const provider=q('#tts-api-provider').value;
 return {
  id:q('#tts-api-profile').value,name:q('#tts-api-name').value.trim()||providers[provider]?.name||'Server TTS',provider,
  base_url:q('#tts-api-url').value.trim(),model:q('#tts-api-model').value.trim(),voice:q('#tts-api-voice').value.trim(),
  language:q('#tts-api-language').value.trim(),response_format:q('#tts-api-format').value,timeout:number('tts-api-timeout',180),
  temperature:number('tts-api-temperature',1),top_p:number('tts-api-top-p',.95),top_k:number('tts-api-top-k',50),
  seed:generationSeed(provider),max_new_tokens:number('tts-api-max-tokens',2048),style_protocol:provider==='higgs'&&q('#tts-api-style-protocol').checked?'higgs_tags':'none',
  api_key:q('#tts-api-key').value,clear_api_key:q('#tts-api-clear').checked
 };
}
async function errorOf(response){
 try{const body=await response.json();return typeof body.detail==='string'?body.detail:JSON.stringify(body.detail)}
 catch{return 'Il server TTS non ha risposto correttamente.'}
}
function referenceOptions(voices){
 return '<option value="">Nessun campione · usa la voce configurata</option>'+voices.map(v=>'<option value="'+safe(v.id)+'">'+safe(v.name)+' · '+safe(v.duration_seconds)+' s'+(v.reference_text?' · trascritto':'')+'</option>').join('');
}

export function mountTtsAdmin(target,initial,{toast,reload,voices=[],selectedProfileId='',getDelivery=()=>normalizeDelivery()}){
 let profiles=initial||[];
 target.innerHTML=`<section class="card tts-api-card">
  <div class="card-head"><span class="step-no">TTS</span><h2>Server per la voce</h2></div>
  <p class="tiny muted">Salva più server e più voci. Ogni nuovo progetto conserverà la configurazione scelta.</p>
  <div class="form-grid">
   <div class="field"><label for="tts-api-profile">Profili salvati</label><select id="tts-api-profile"><option value="">Nuovo profilo</option>${profiles.map(x=>'<option value="'+safe(x.id)+'">'+safe(x.name)+' · '+safe(providers[x.provider]?.name||x.provider)+'</option>').join('')}</select></div>
   <div class="field"><label for="tts-api-provider">Tipo di server</label><select id="tts-api-provider">${Object.entries(providers).map(([id,p])=>'<option value="'+id+'">'+p.name+'</option>').join('')}</select></div>
  </div>
  <div class="form-grid">
   <div class="field"><label for="tts-api-name">Nome riconoscibile</label><input id="tts-api-name" placeholder="Per esempio: Higgs sul PC con GPU"></div>
   <div class="field"><label for="tts-api-url">Indirizzo del server</label><input id="tts-api-url" type="url"></div>
  </div>
  <div class="form-grid">
   <div class="field"><label for="tts-api-model">Modello</label><input id="tts-api-model"><span class="hint">Facoltativo per il server Higgs descritto nella specifica.</span></div>
   <div class="field"><label for="tts-api-voice">Voce / voice ID persistente</label><input id="tts-api-voice"><span class="hint">Lascia vuoto per la voce predefinita o per usare un campione one-shot.</span></div>
  </div>
  <div id="tts-higgs-seed" class="hidden">
   <label class="check"><input id="tts-api-keep-seed" type="checkbox" aria-describedby="tts-api-seed-hint"> Mantieni lo stesso seed tra le frasi</label>
   <p id="tts-api-seed-hint" class="tiny muted">Riduce la casualità tra le frasi. Per un narratore coerente scegli anche una voce salvata o lo stesso campione one-shot: il seed da solo non garantisce lo stesso timbro.</p>
   <div class="field"><label for="tts-api-seed">Seed conservato</label><input id="tts-api-seed" type="number" min="0" max="2147483647" step="1" aria-describedby="tts-api-seed-state"><span id="tts-api-seed-state" class="hint" role="status"></span></div>
  </div>
  <div class="form-grid">
   <div class="field"><label for="tts-api-language">Lingua</label><input id="tts-api-language" value="it-IT"></div>
   <div class="field"><label for="tts-api-format">Formato restituito</label><select id="tts-api-format"><option value="wav">WAV</option><option value="mp3">MP3</option><option value="flac">FLAC</option><option value="ogg">OGG</option></select></div>
  </div>
  <div class="form-grid">
   <div class="field"><label for="tts-api-timeout">Tempo massimo per frase (s)</label><input id="tts-api-timeout" type="number" min="10" max="1800" value="180"><span class="hint">Per Higgs remoto sono consigliati 900 secondi.</span></div>
   <div class="field"><label for="tts-api-key">Chiave o credenziale · se richiesta</label><input id="tts-api-key" type="password" autocomplete="new-password"><span class="hint" id="tts-api-key-hint">Lascia vuoto sulla LAN privata se il server non richiede autenticazione.</span></div>
  </div>
  <details id="tts-higgs-options"><summary>Parametri di generazione Higgs</summary>
   <label class="check"><input id="tts-api-style-protocol" type="checkbox"> Indicazioni espressive Higgs 3</label><p class="tiny muted">Attiva solo se il tuo server riconosce le indicazioni espressive. Verifica con la prova d’ascolto. Il testo del documentario resta invariato.</p>
   <div class="form-grid"><div class="field"><label for="tts-api-temperature">Temperature</label><input id="tts-api-temperature" type="number" min="0" max="2" step="0.05"></div><div class="field"><label for="tts-api-top-p">Top P</label><input id="tts-api-top-p" type="number" min="0" max="1" step="0.01"></div></div>
   <div class="field"><label for="tts-api-top-k">Top K</label><input id="tts-api-top-k" type="number" min="0" max="1000"></div>
   <div class="field"><label for="tts-api-max-tokens">Token audio massimi</label><input id="tts-api-max-tokens" type="number" min="64" max="32768"></div>
  </details>
  <label class="check"><input id="tts-api-clear" type="checkbox"> Rimuovi la credenziale salvata</label>
  <p id="tts-api-hint" class="tiny muted"></p>
  <details class="tts-profile-preview"><summary>Testo e impostazioni della prova</summary><div class="field"><label for="tts-api-preview-text">Testo della prova</label><textarea id="tts-api-preview-text" rows="3" maxlength="500">${safe(previewText)}</textarea><span class="hint">La prova usa ritmo e interpretazione scelti in «Voce e cloning one-shot» qui sopra, insieme ai parametri di questo server. Non avvia un documentario.</span></div></details>
  <div class="actions"><button type="button" class="primary" id="tts-api-save">Salva server TTS</button><button type="button" class="secondary" id="tts-api-test">Ascolta una prova</button><button type="button" class="danger hidden" id="tts-api-delete">Elimina profilo</button></div>
  <p id="tts-api-result" class="connection-result" role="status"></p><audio id="tts-api-player" class="hidden" controls></audio>
  <div id="tts-higgs-controls" class="higgs-panel hidden">
   <div class="divider"></div><h3>Controllo del PC Higgs</h3>
   <p class="tiny muted">Questi comandi lasciano acceso il server HTTP. Durante una produzione H3 carica automaticamente il modello una sola volta e lo scarica sempre al termine dell’attività.</p>
   <div class="actions"><button type="button" class="secondary" id="tts-higgs-status">Controlla stato</button><button type="button" class="secondary" id="tts-higgs-load">Carica modello</button><button type="button" class="secondary" id="tts-higgs-unload">Scarica modello</button></div>
   <p id="tts-higgs-result" class="connection-result" role="status"></p>
   <div class="divider"></div><h3>Cloning e voce persistente</h3>
   <div class="field"><label for="tts-api-reference">Campione vocale salvato in H3</label><select id="tts-api-reference">${referenceOptions(voices)}</select><span class="hint">Higgs: usa un parlato pulito; 10–20 secondi sono spesso sufficienti, ma H3 accetta campioni da 4 a 60 secondi. La trascrizione esatta viene inviata insieme all’audio.</span></div>
   <div class="form-grid"><div class="field"><label for="tts-higgs-voice-id">Nome della voce sul server</label><input id="tts-higgs-voice-id" pattern="[A-Za-z0-9_-]+" placeholder="emanuele_it"></div><label class="check"><input id="tts-higgs-overwrite" type="checkbox"> Sostituisci la voce se esiste già</label></div>
   <button type="button" class="secondary" id="tts-higgs-upload">Registra questa voce sul server</button>
  </div>
  <div class="banner space-top"><b>Dati inviati</b><br>Il testo narrato viene trasmesso al server scelto. Con Higgs, il campione one-shot e la sua trascrizione vengono inviati solo per i progetti che lo selezionano. Kokoro e Chatterbox locali restano disponibili.</div>
 </section>`;

 const selected=()=>profiles.find(x=>x.id===q('#tts-api-profile').value);
 const updateSeed=()=>{
  const fixed=q('#tts-api-provider').value==='higgs'&&q('#tts-api-keep-seed').checked;
  q('#tts-api-seed').disabled=!fixed;
  q('#tts-api-seed-state').textContent=fixed?'Lo stesso valore viene inviato per ogni frase, anche nella prova d’ascolto.':'Casualità del server attiva (seed -1). Riattivando la spunta ritrovi il numero scelto.';
 };
 const showHiggs=()=>{
  const higgs=q('#tts-api-provider').value==='higgs';
  q('#tts-higgs-seed').classList.toggle('hidden',!higgs);
  q('#tts-higgs-options').classList.toggle('hidden',!higgs);
  q('#tts-higgs-controls').classList.toggle('hidden',!(higgs&&q('#tts-api-profile').value));
 };
 const apply=profile=>{
  const preset=profile||providers[q('#tts-api-provider').value];
  q('#tts-api-name').value=profile?.name||'';q('#tts-api-url').value=preset.base_url;q('#tts-api-model').value=preset.model||'';q('#tts-api-voice').value=preset.voice||'';
  q('#tts-api-language').value=profile?.language||'it-IT';q('#tts-api-format').value=profile?.response_format||preset.format||'mp3';q('#tts-api-timeout').value=profile?.timeout||preset.timeout||180;
  q('#tts-api-temperature').value=profile?.temperature??1;q('#tts-api-top-p').value=profile?.top_p??.95;q('#tts-api-top-k').value=profile?.top_k??50;q('#tts-api-max-tokens').value=profile?.max_new_tokens??2048;
  const seed=profile?(profile.seed??-1):(q('#tts-api-provider').value==='higgs'?42:-1);
  q('#tts-api-keep-seed').checked=seed>=0;q('#tts-api-seed').value=seed>=0?seed:42;updateSeed();
  q('#tts-api-style-protocol').checked=profile?.style_protocol==='higgs_tags';
  q('#tts-api-key').value='';q('#tts-api-clear').checked=false;
  q('#tts-api-key-hint').textContent=profile?.has_api_key?'Credenziale salvata e cifrata. Lascia vuoto per conservarla.':'Lascia vuoto sulla LAN privata se il server non richiede autenticazione.';
  q('#tts-api-hint').textContent=providers[q('#tts-api-provider').value].hint;q('#tts-api-delete').classList.toggle('hidden',!profile);showHiggs();
 };
 q('#tts-api-keep-seed').onchange=updateSeed;
 q('#tts-api-profile').onchange=e=>{const p=profiles.find(x=>x.id===e.target.value);if(p){q('#tts-api-provider').value=p.provider;apply(p)}else apply(null)};
 q('#tts-api-provider').onchange=()=>{q('#tts-api-profile').value='';apply(null)};
 const initialProfile=profiles.find(x=>x.id===selectedProfileId)||profiles[0];
 if(initialProfile){q('#tts-api-profile').value=initialProfile.id;q('#tts-api-provider').value=initialProfile.provider;apply(initialProfile)}else apply(null);

 q('#tts-api-save').onclick=async e=>{e.target.disabled=true;try{
  const response=await fetch('/api/tts/profiles',{method:'POST',headers:{'Content-Type':'application/json','X-DocumentariAI':'studio'},body:JSON.stringify(formValue())});
  if(!response.ok)throw Error(await errorOf(response));const saved=await response.json();toast('Server TTS salvato. Ora compare nella scelta della voce.');await reload(saved.id);
 }catch(error){q('#tts-api-result').textContent=error.message;q('#tts-api-result').className='connection-result bad'}finally{e.target.disabled=false}};

 q('#tts-api-test').onclick=async e=>{e.target.disabled=true;const result=q('#tts-api-result');result.className='connection-result';result.textContent='Carico il modello e genero una breve prova…';try{
  const text=q('#tts-api-preview-text').value.trim();if(!text||text.length>500)throw Error('Scrivi una breve prova, fino a 500 caratteri.');
  const payload={...formValue(),reference_id:q('#tts-api-provider').value==='higgs'?q('#tts-api-reference').value:'',text,tts_delivery:getDelivery()};
  const response=await fetch('/api/tts/profiles/test',{method:'POST',headers:{'Content-Type':'application/json','X-DocumentariAI':'studio'},body:JSON.stringify(payload)});
  if(!response.ok)throw Error(await errorOf(response));const blob=await response.blob(),player=q('#tts-api-player');if(player.dataset.url)URL.revokeObjectURL(player.dataset.url);
  const styleFallback=response.headers?.get('X-Voice-Style-Fallback')==='true';
  player.dataset.url=URL.createObjectURL(blob);player.src=player.dataset.url;player.classList.remove('hidden');result.textContent=styleFallback?'Il server non ha accettato le indicazioni espressive: la prova usa l’interpretazione originale, con velocità e pause scelte. Il modello Higgs è stato scaricato.':q('#tts-api-provider').value==='higgs'?'Prova ricevuta; il modello Higgs è stato scaricato.':'Prova ricevuta. Riproduzione in corso.';result.className='connection-result'+(styleFallback?'':' good');await player.play();
 }catch(error){result.textContent=error.message;result.className='connection-result bad'}finally{e.target.disabled=false}};

 q('#tts-api-delete').onclick=async e=>{const id=q('#tts-api-profile').value;if(!id)return;e.target.disabled=true;try{
  const response=await fetch('/api/tts/profiles/'+id,{method:'DELETE',headers:{'X-DocumentariAI':'studio'}});if(!response.ok)throw Error(await errorOf(response));toast('Profilo TTS eliminato.');await reload();
 }catch(error){q('#tts-api-result').textContent=error.message;q('#tts-api-result').className='connection-result bad'}finally{e.target.disabled=false}};

 const higgsCall=async(path,method='POST')=>{
  const p=selected();if(!p||p.provider!=='higgs')throw Error('Salva e seleziona prima un profilo Higgs.');
  const response=await fetch('/api/tts/profiles/'+p.id+path,{method,headers:{'X-DocumentariAI':'studio'}});if(!response.ok)throw Error(await errorOf(response));return response.json();
 };
 const runHiggs=async(button,path,verb)=>{button.disabled=true;const result=q('#tts-higgs-result');result.textContent=verb+'…';result.className='connection-result';try{
  const data=await higgsCall(path);const state=data.model_state||'sconosciuto';result.textContent='Stato dichiarato dal server Higgs: '+state+(data.device?' · '+data.device:'')+(path==='/model/unload'?' · La VRAM effettiva è gestita dal processo remoto.':'');result.className='connection-result good';
 }catch(error){result.textContent=error.message;result.className='connection-result bad'}finally{button.disabled=false}};
 q('#tts-higgs-status').onclick=e=>runHiggs(e.target,'/status','Controllo lo stato');
 q('#tts-higgs-load').onclick=e=>runHiggs(e.target,'/model/load','Carico il modello');
 q('#tts-higgs-unload').onclick=e=>runHiggs(e.target,'/model/unload','Scarico il modello');
 q('#tts-higgs-upload').onclick=async e=>{e.target.disabled=true;const result=q('#tts-higgs-result');try{
  const p=selected(),reference_id=q('#tts-api-reference').value,voice_id=q('#tts-higgs-voice-id').value.trim();
  if(!p||p.provider!=='higgs')throw Error('Salva e seleziona prima un profilo Higgs.');if(!reference_id)throw Error('Seleziona un campione vocale.');if(!/^[A-Za-z0-9_-]+$/.test(voice_id))throw Error('Il nome voce può usare lettere, numeri, trattino e trattino basso.');
  const response=await fetch('/api/tts/profiles/'+p.id+'/voices/upload',{method:'POST',headers:{'Content-Type':'application/json','X-DocumentariAI':'studio'},body:JSON.stringify({reference_id,voice_id,overwrite:q('#tts-higgs-overwrite').checked})});
  if(!response.ok)throw Error(await errorOf(response));const data=await response.json();q('#tts-api-voice').value=data.voice;result.textContent='Voce registrata come '+data.voice+'. Salva il profilo per usarla senza riallegare il campione.';result.className='connection-result good';
 }catch(error){result.textContent=error.message;result.className='connection-result bad'}finally{e.target.disabled=false}};
}
