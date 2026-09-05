"""Completed-film review keeps project identity and saves before selective work."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_js(body):
    if not shutil.which('node'):
        pytest.skip('Node is required for the frontend developer check')
    source = """
      import {readFileSync} from 'node:fs';
      const source=readFileSync('static/final-review.js','utf8');
      const ui=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
    """
    result = subprocess.run(['node', '--input-type=module', '-e', source + body],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)


def test_completed_review_is_explicit_and_separate_from_new_version():
    result = run_js("""
      console.log(JSON.stringify({absent:ui.finalReviewHtml('old',{available:false}),
        ready:ui.finalReviewHtml('old',{available:true}),
        editing:ui.finalReviewHtml('old',{available:true,editing:true})}));
    """)
    assert result['absent'] == ''
    assert 'Riapri revisione' in result['ready']
    assert 'data-final-action="render"' not in result['ready']
    assert 'Prepara nuova versione' in result['ready']
    assert 'Aggiorna questo video' in result['editing']
    assert 'Annulla revisione' in result['editing']
    assert '/projects/old/media' in result['editing']
    assert 'altre scene per mantenere corretta la timeline' in result['editing']


def test_render_waits_for_saved_text_and_preserves_project_id():
    result = run_js("""
      const calls=[];let release;
      const done=ui.performFinalReviewAction('render','existing-project',{
        save:()=>{calls.push('save');return new Promise(resolve=>release=resolve)},
        api:async(path,options)=>{calls.push({path,method:options.method});return {busy:true}}});
      const before=[...calls];release();const state=await done;
      console.log(JSON.stringify({before,calls,state}));
    """)
    assert result['before'] == ['save']
    assert result['calls'] == ['save', {
        'path': '/projects/existing-project/final-review/render', 'method': 'POST'}]
    assert result['state']['busy'] is True


def test_failed_draft_save_never_requests_render():
    result = run_js("""
      let calls=0,error;
      try{await ui.performFinalReviewAction('render','old',{
        save:async()=>{throw Error('Revisione non salvata')},
        api:async()=>{calls++}})}catch(e){error=e.message}
      console.log(JSON.stringify({calls,error}));
    """)
    assert result == {'calls': 0, 'error': 'Revisione non salvata'}


def test_open_and_discard_do_not_save_or_render_and_escape_identifier():
    result = run_js("""
      const calls=[];let saves=0;
      const options={save:async()=>saves++,api:async(path,value)=>calls.push({path,method:value.method})};
      await ui.performFinalReviewAction('open','a/b',options);
      await ui.performFinalReviewAction('discard','a/b',options);
      console.log(JSON.stringify({calls,saves}));
    """)
    assert result == {'saves': 0, 'calls': [
        {'path': '/projects/a%2Fb/final-review', 'method': 'POST'},
        {'path': '/projects/a%2Fb/final-review', 'method': 'DELETE'}]}


def test_busy_review_keeps_previous_film_and_no_duplicate_action_buttons():
    result = run_js("""
      console.log(JSON.stringify(ui.finalReviewHtml('old',{
        available:true,busy:true,editing:false,status:'running',revision_number:2,
        changed_scene_ids:['01','03']})));
    """)
    assert 'Il video già pronto rimane consultabile' in result
    assert 'data-final-action' not in result
    assert 'Revisione 2' in result and '2 scene coinvolte' in result


def test_failure_is_visible_and_allows_same_project_retry():
    result = run_js("""
      console.log(JSON.stringify(ui.finalReviewHtml('old',{
        available:true,editing:true,status:'failed',error:'Errore <script>test</script>'})));
    """)
    assert 'Errore &lt;script&gt;test&lt;/script&gt;' in result
    assert '<script>' not in result
    assert 'Aggiorna questo video' in result and 'Annulla revisione' in result


def test_unknown_action_never_calls_the_server():
    result = run_js("""
      let calls=0,error;
      try{await ui.performFinalReviewAction('regenerate','old',{api:async()=>calls++})}catch(e){error=e.message}
      console.log(JSON.stringify({calls,error}));
    """)
    assert result['calls'] == 0
    assert 'non disponibile' in result['error']


def test_editor_labels_match_completed_film_action():
    value = run_js("""
      const editorSource=readFileSync('static/review-editor.js','utf8');
      const editor=await import('data:text/javascript;base64,'+Buffer.from(editorSource).toString('base64'));
      console.log(JSON.stringify({first:editor.editorHtml(),final:editor.editorHtml({finalReview:true})}));
    """)
    assert 'Continua produzione' in value['first']
    assert 'Aggiorna questo video' in value['final']
    assert 'Continua produzione' not in value['final']
    assert 'nel film già completato' in value['final']
