"""PDF controls use their own endpoint and retain choices during project polling."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_js(body):
    if not shutil.which('node'):
        pytest.skip('Node is only required for the frontend developer check')
    source = """
      import {readFileSync} from 'node:fs';
      const moduleSource=readFileSync('static/presentations.js','utf8');
      const ui=await import('data:text/javascript;base64,'+Buffer.from(moduleSource).toString('base64'));
      class Element {
        constructor(){this.value='';this.checked=false;this.disabled=false;this.textContent='';this.style={};this.attributes={};this.isConnected=true;this.writes=0;this.classList={toggle(){}}}
        set innerHTML(value){this.html=value;this.writes++}
        get innerHTML(){return this.html||''}
        setAttribute(key,value){this.attributes[key]=value}
      }
      function target(){const node=new Element(),children={};for(const name of ['form','fields','variant','narration','create','message','progress','percent','bar','fill','exports'])children[name]=new Element();node.querySelector=selector=>children[selector.match(/data-pdf-([a-z]+)/)[1]];return {node,children}}
    """
    result = subprocess.run(['node', '--input-type=module', '-e', source + body], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)


def test_pdf_controls_explain_variants_and_always_include_sources():
    result = run_js('console.log(JSON.stringify(ui.presentationHtml()));')
    assert 'un’immagine per scena' in result and 'passaggi significativi' in result
    assert 'data-pdf-narration checked' in result
    assert 'testo narrato originale' in result and 'testo può aggiungere pagine' in result
    assert 'Fonti e crediti sono sempre inclusi' in result


def test_pdf_polling_preserves_choices_and_does_not_duplicate_export_requests():
    result = run_js("""
      const {node,children}=target(),calls=[];let release;
      const api=(path,options)=>{calls.push({path,body:JSON.parse(options.body)});return new Promise(resolve=>release=resolve)};
      const update=state=>ui.updatePresentation(node,'project-1',state,{api});
      update({available:false,reason:'Attendi la voce.',exports:[]});const initiallyDisabled=children.create.disabled;
      update({available:true,exports:[]});children.variant.value='teaching';children.narration.checked=false;
      update({available:true,exports:[]});
      const first=children.form.onsubmit({preventDefault(){}});await children.form.onsubmit({preventDefault(){}});
      release({available:true,busy:true,status:'queued',progress:0,exports:[],updated:'2026-09-05T10:00:00Z'});await first;
      update({available:true,busy:true,status:'running',progress:42,exports:[],updated:'2026-09-05T10:00:01Z'});
      const progress=children.bar.attributes['aria-valuenow'];const locked=children.fields.disabled;
      // A late earlier poll must not erase the active export status.
      update({available:true,busy:false,exports:[],updated:'2026-09-05T09:59:59Z'});
      const stillLocked=children.fields.disabled;
      update({available:true,busy:false,status:'completed',progress:100,message:'PDF pronto.',exports:[{path:'workspace/output/presentations/first.pdf',pages:8,name:'first.pdf',bytes:45000,variant:'teaching',narration:'none'}],updated:'2026-09-05T10:01:00Z'});
      const exportsWrites=children.exports.writes;
      update({available:true,busy:false,status:'completed',progress:100,exports:[{path:'workspace/output/presentations/first.pdf',pages:8,name:'first.pdf',bytes:45000,variant:'teaching',narration:'none'}],updated:'2026-09-05T10:01:01Z'});
      console.log(JSON.stringify({calls,initiallyDisabled,progress,locked,stillLocked,unlocked:!children.fields.disabled,variant:children.variant.value,narration:children.narration.checked,renderCount:node.writes,exportsWrites,finalExportsWrites:children.exports.writes,links:children.exports.innerHTML}));
    """)
    assert result['initiallyDisabled'] and result['locked'] and result['stillLocked'] and result['unlocked']
    assert result['calls'] == [{'path': '/projects/project-1/presentation', 'body': {'variant': 'teaching', 'narration': 'none'}}]
    assert result['progress'] == '42'
    assert result['variant'] == 'teaching' and result['narration'] is False
    assert result['renderCount'] == 1
    assert result['exportsWrites'] == result['finalExportsWrites']
    assert 'first.pdf' in result['links'] and '8 pagine' in result['links']


def test_previous_pdfs_remain_downloadable_when_new_export_is_unavailable_or_fails():
    result = run_js("""
      const {node,children}=target();const files=[{path:'workspace/output/presentations/old.pdf',pages:2,name:'old.pdf',bytes:100,variant:'compact',narration:'full'}];
      const options={api:async()=>{throw Error('Il progetto è occupato.')}};
      ui.updatePresentation(node,'project-2',{available:false,reason:'Produzione in corso.',exports:files},options);
      const oldLink=children.exports.innerHTML;
      ui.updatePresentation(node,'project-2',{available:true,exports:files},options);children.variant.value='compact';children.narration.checked=true;
      await children.form.onsubmit({preventDefault(){}});
      console.log(JSON.stringify({error:children.message.textContent,link:children.exports.innerHTML,oldLink,canRetry:!children.create.disabled}));
    """)
    assert result['error'] == 'Il progetto è occupato.' and result['canRetry']
    assert result['link'] == result['oldLink'] and 'old.pdf' in result['link']


def test_pdf_links_encode_paths_escape_names_and_deduplicate_files():
    result = run_js("""
      const file={path:'workspace/output/presentations/test & final.pdf',name:'file" onload="bad.pdf',pages:12,bytes:2500000,variant:'teaching',narration:'full',created:'2026-09-05T09:00:00Z'};
      console.log(JSON.stringify(ui.presentationLinks('project-3',[file,file,{path:'javascript:alert(1)'}])));
    """)
    assert result.count('<a ') == 1
    assert 'path=workspace%2Foutput%2Fpresentations%2Ftest%20%26%20final.pdf' in result
    assert 'download="file&quot; onload=&quot;bad.pdf"' in result
    assert 'javascript:' not in result
