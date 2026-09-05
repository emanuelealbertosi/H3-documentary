const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function boundaryUsageField(value='commercial') {
  return `<details open><summary>Confini storici e destinazione d’uso</summary><div class="field"><label for="boundary_usage">Uso delle mappe</label><select id="boundary_usage"><option value="commercial"${value==='commercial'?' selected':''}>Anche commerciale · archivi compatibili</option><option value="education_nc"${value==='education_nc'?' selected':''}>Didattico non commerciale · include CShapes</option></select><span class="hint">Recupero automatico da archivi datati: Cliopatria e, per uso non commerciale, CShapes. Le fonti e le condizioni di riuso restano nei crediti del progetto. Le ricostruzioni storiche possono essere approssimative; gli intervalli mancanti non vengono colmati con confini moderni.</span></div></details>`;
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
