const safe=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const projectName=p=>(p.display_title||p.topic)+(Number(p.version)>1?' · V'+p.version:'');
export function titleControl(p){
 return '<span class="project-title" data-project-title="'+safe(p.id)+'" data-value="'+safe(p.display_title||p.topic)+'" data-version="'+(Number(p.version)||1)+'" data-updated="'+safe(p.updated||'')+'">'+titleButton(p)+'</span>';
}
function titleButton(p){return '<button type="button" class="project-title-button" title="Clicca per modificare il titolo" aria-label="Modifica titolo: '+safe(projectName(p))+'">'+safe(projectName(p))+'<span class="title-pencil" aria-hidden="true">✎</span></button>'}
export function updateProjectTitle(root,p){
 for(const node of root.querySelectorAll('[data-project-title]')){
  if(node.dataset.projectTitle!==p.id||node.dataset.editing||node.dataset.updated>(p.updated||''))continue;
  node.dataset.value=p.display_title||p.topic;node.dataset.updated=p.updated||'';
  const html=titleButton(p);if(node.innerHTML!==html)node.innerHTML=html;
 }
}
export function bindProjectTitles(root,{api,toast}){
 for(const node of root.querySelectorAll('[data-project-title]')){
  if(node.dataset.bound)continue;node.dataset.bound='true';
  node.addEventListener('click',event=>{
   event.stopPropagation();
   if(node.dataset.editing)return;
   const original=node.dataset.value;node.dataset.editing='true';
   node.innerHTML='<span class="project-title-edit"><input type="text" aria-label="Titolo del progetto" maxlength="200" value="'+safe(original)+'"><span class="title-controls"><button type="button" data-save-title aria-label="Salva titolo" title="Salva · Invio">✓</button><button type="button" data-cancel-title aria-label="Annulla modifica titolo" title="Annulla · Esc">×</button></span></span><span class="title-error" role="alert"></span>';
   const input=node.querySelector('input'),error=node.querySelector('[role="alert"]');let saving=false,closed=false;
   const close=value=>{closed=true;delete node.dataset.editing;node.dataset.value=value;node.innerHTML=titleButton({topic:value,version:node.dataset.version})};
   const cancel=()=>{if(!saving){close(original);node.querySelector('button').focus()}};
   const save=async()=>{
    if(saving||closed)return;
    const title=input.value.trim();
    if(!title){error.textContent='Scrivi un titolo prima di salvare.';input.setAttribute('aria-invalid','true');return}
    if(title===original){close(original);return}
    saving=true;input.disabled=true;for(const button of node.querySelectorAll('button'))button.disabled=true;
    try{const p=await api('/projects/'+encodeURIComponent(node.dataset.projectTitle)+'/title',{method:'PATCH',body:JSON.stringify({title})});
     node.dataset.updated=p.updated||'';close(p.display_title||p.topic);toast?.('Titolo salvato.');
    }catch(e){error.textContent=e.message;input.disabled=false;for(const button of node.querySelectorAll('button'))button.disabled=false;toast?.(e.message)}finally{saving=false}
   };
   node.querySelector('[data-save-title]').onclick=event=>{event.stopPropagation();save()};
   node.querySelector('[data-cancel-title]').onclick=event=>{event.stopPropagation();cancel()};
   input.onkeydown=event=>{if(event.isComposing)return;if(event.key==='Enter'){event.preventDefault();save()}else if(event.key==='Escape'){event.preventDefault();event.stopPropagation();cancel()}};
   input.onblur=event=>{if(!node.contains(event.relatedTarget))save()};
   input.focus();input.select();
  });
 }
}
