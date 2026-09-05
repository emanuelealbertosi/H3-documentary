const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function boundaryUsageField(value='commercial') {
  return `<details open><summary>Uso di mappe e immagini</summary><div class="field"><label for="boundary_usage">Destinazione d’uso di mappe e immagini</label><select id="boundary_usage"><option value="commercial"${value==='commercial'?' selected':''}>Anche commerciale · fonti compatibili</option><option value="education_nc"${value==='education_nc'?' selected':''}>Didattico non commerciale · più fonti ammesse</option></select><span class="hint">Per le immagini: Wikimedia Commons, poi Openverse quando serve. L’uso non commerciale ammette anche CC BY-NC e CC BY-NC-SA; restano escluse le licenze senza modifiche (ND) o non riconosciute. Più fonti possono offrire più risultati pertinenti, senza garantirli.</span><span class="hint">Per i confini: Cliopatria e, in modalità non commerciale, CShapes. Le ricostruzioni possono essere approssimative; i periodi mancanti non vengono colmati con confini moderni. Fonti, attribuzioni e condizioni restano nei crediti. La scelta vale per nuove produzioni e rigenerazioni.</span></div></details>`;
}
export function showBoundaryReport(report,anchor) {
  let panel=document.getElementById('project-boundaries');
  if(!report?.layers?.length){panel?.remove();return}
  if(!panel){panel=document.createElement('section');panel.id='project-boundaries';panel.className='card space-top';anchor.before(panel)}
  const opened=[...panel.querySelectorAll('details')].map(d=>d.open);
  const names={sourced:'Da archivio datato',partial:'Copertura parziale',schematic:'Area indicativa'};
  panel.innerHTML='<h2>Confini e provenienza</h2><p>'+report.sourced+' aree da archivio · '+report.partial+' parziali · '+report.schematic+' indicative</p>'+report.layers.map(r=>'<details><summary>'+esc(r.label)+' · '+esc(names[r.status]||r.status)+'</summary><ul>'+r.notes.map(n=>'<li>'+esc(n)+'</li>').join('')+'</ul></details>').join('')+'<p class="tiny muted">Geometrie e manifest sono disponibili nei Materiali. '+(report.usage==='education_nc'?'Uso didattico non commerciale: verifica le attribuzioni e le condizioni riportate nei crediti.':'La selezione esclude gli archivi limitati agli usi non commerciali.')+'</p>';
  panel.querySelectorAll('details').forEach((d,i)=>{d.open=opened[i]||false});
}
