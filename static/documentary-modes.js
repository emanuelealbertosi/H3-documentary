// Stable project IDs, grouped only for a clearer choice in the interface.
export const modeGroups = [
  ['Conflitti', [
    ['battle', 'Battaglia', 'Un singolo scontro: terreno, schieramenti, attacchi e ritirate.'],
    ['war', 'Guerra e campagne militari', 'Un conflitto più ampio: fronti, campagne, svolte e conseguenze.'],
    ['revolution', 'Rivoluzioni', 'Cause, protagonisti, mobilitazione e cambiamenti del potere.'],
  ]],
  ['Territori e potere', [
    ['territorial_expansion', 'Imperi, espansioni e confini', 'Territori colorati nel tempo, conquiste e perdite. I contorni sono schematici quando mancano dati geografici storici verificati.'],
    ['political_history', 'Geopolitica, alleanze e influenze', 'Stati, alleanze, crisi e zone d’influenza. Influenza e controllo territoriale hanno segni visivi differenti.'],
  ]],
  ['Viaggi e scambi', [
    ['exploration', 'Viaggi ed esplorazioni', 'Partenza, tappe e arrivo: itinerari animati e mappe di orientamento.'],
    ['migration', 'Migrazioni e popoli', 'Origini, flussi, incontri e insediamenti, distinguendo migrazioni e invasioni.'],
    ['trade_network', 'Commercio e rotte', 'Reti di città, porti, merci e collegamenti terrestri o marittimi.'],
  ]],
  ['Società e idee', [
    ['cultural_movement', 'Arte e movimenti culturali', 'Città, persone, opere e circolazione delle idee.'],
    ['religious_expansion', 'Religioni e diffusione', 'Comunità, credenze e aree religiose, distinte dalle conquiste politiche.'],
    ['economic_history', 'Economia e industria', 'Produzione, scambi e trasformazioni sociali; grafici solo con dati disponibili.'],
    ['technology_history', 'Scienza e tecnologia', 'Scoperte, invenzioni, adozione e conseguenze nella società.'],
  ]],
  ['Vite ed epoche', [
    ['biography', 'Biografia', 'Una vita: luoghi, persone, svolte ed eredità. Mappe quando aiutano il racconto.'],
    ['general_history', 'Epoche e storia generale', 'Un racconto trasversale con mappe, cronologia, immagini e confronti.'],
  ]],
];
const auto = ['auto', 'Automatico · consigliato', 'Descrivi argomento, periodo e area: lo studio sceglie il tipo di racconto e combina i componenti adatti.'];
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function modeHint(value) { return [auto, ...modeGroups.flatMap(([, rows]) => rows)].find(row => row[0] === value)?.[2] || auto[2]; }
export function documentaryModeSelect(id, value='auto') {
  const option = row => `<option value="${row[0]}"${row[0]===value?' selected':''}>${esc(row[1])}</option>`;
  return `<div class="field documentary-mode"><label for="${id}">Tipo di racconto</label><select id="${id}" aria-describedby="${id}-hint">${option(auto)}${modeGroups.map(([group, rows])=>`<optgroup label="${esc(group)}">${rows.map(option).join('')}</optgroup>`).join('')}</select><span class="hint" id="${id}-hint" aria-live="polite">${esc(modeHint(value))}</span></div>`;
}
export function bindDocumentaryMode(id) {
  const select=document.getElementById(id),hint=document.getElementById(id+'-hint');
  if(select&&hint) { select.onchange=()=>{hint.textContent=modeHint(select.value)};select.onchange(); }
}
