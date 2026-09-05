"""The editorial draft preserves local work and never starts production by itself."""
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
      const source=readFileSync('static/review-editor.js','utf8');
      const ui=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
      const initial=()=>({available:true,editable:true,revision:'r1',dirty:false,
        scenes:[{id:'01',title:'Partenza',date:'1200 a.C.',lines:['Il viaggio inizia.','La nave parte.'],base_lines:['Il viaggio inizia.','La nave parte.']},{id:'02',title:'Arrivo',lines:['La nave arriva.'],base_lines:['La nave arriva.']}],
        places:[{id:'troia',name:'Troia',pos:[26.2,39.9],base_pos:[26.2,39.9],scene_ids:['01']},{id:'itaca',name:'Itaca',pos:[20.7,38.4],base_pos:[20.7,38.4],scene_ids:['02']}]});
      const apply=(value,patch)=>({...value,revision:'r2',dirty:true,scenes:value.scenes.map(s=>({...s,...patch.scenes.find(x=>x.id===s.id)})),places:value.places.map(p=>({...p,...patch.places.find(x=>x.id===p.id)}))});
    """
    result = subprocess.run(['node', '--input-type=module', '-e', source + body],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)


def test_sparse_patch_preserves_cue_count_and_unedited_places():
    result = run_js("""
      const data=initial(),draft=new ui.ReviewDraft(data);
      draft.setLine('01',1,'La nave lascia il porto.');draft.setPosition('itaca',[20.71,38.41]);
      console.log(JSON.stringify({patch:draft.patch(),dirty:draft.dirty,original:data}));
    """)
    assert result['patch'] == {'revision': 'r1', 'scenes': [
        {'id': '01', 'lines': ['Il viaggio inizia.', 'La nave lascia il porto.']}],
        'places': [{'id': 'itaca', 'pos': [20.71, 38.41]}]}
    assert result['dirty']
    assert result['original']['places'][1]['pos'] == [20.7, 38.4]
    assert result['original']['scenes'][0]['lines'][1] == 'La nave parte.'


def test_saved_server_draft_is_not_mistaken_for_unsaved_input():
    result = run_js("""
      const data=initial();data.dirty=true;data.changed_scene_ids=['01'];let requests=0;
      const draft=new ui.ReviewDraft(data);await draft.save(async()=>{requests++;throw Error('Non richiesto')});
      console.log(JSON.stringify({dirty:draft.dirty,requests,saved:draft.saved.dirty}));
    """)
    assert result == {'dirty': False, 'requests': 0, 'saved': True}


def test_concurrent_save_is_single_request_and_preserves_new_typing():
    result = run_js("""
      const data=initial(),draft=new ui.ReviewDraft(data);let requests=0,release;
      draft.setLine('01',0,'Prima correzione.');
      const writer=patch=>{requests++;return new Promise(resolve=>release=()=>resolve(apply(data,patch)))};
      const first=draft.save(writer),second=draft.save(writer);
      draft.setLine('01',1,'Seconda correzione durante il salvataggio.');release();await Promise.all([first,second]);
      console.log(JSON.stringify({requests,patch:draft.patch(),saved:draft.saved.scenes[0].lines}));
    """)
    assert result['requests'] == 1
    assert result['saved'] == ['Prima correzione.', 'La nave parte.']
    assert result['patch']['revision'] == 'r2'
    assert result['patch']['scenes'][0]['lines'] == [
        'Prima correzione.', 'Seconda correzione durante il salvataggio.']


def test_failed_save_keeps_user_text_coordinates_and_revision_for_retry():
    result = run_js("""
      const draft=new ui.ReviewDraft(initial());draft.setLine('01',0,'Correzione da conservare.');draft.setPosition('itaca',[20.8,38.5]);let error;
      try{await draft.save(async()=>{throw Error('Il progetto è occupato.')})}catch(e){error=e.message}
      console.log(JSON.stringify({error,patch:draft.patch(),dirty:draft.dirty,saving:draft.saving}));
    """)
    assert result['error'] == 'Il progetto è occupato.'
    assert result['dirty'] and result['saving'] is None
    assert result['patch']['revision'] == 'r1'
    assert result['patch']['scenes'][0]['lines'][0] == 'Correzione da conservare.'
    assert result['patch']['places'][0]['pos'] == [20.8, 38.5]


def test_reset_unsaved_and_restore_original_are_distinct_after_reload():
    result = run_js("""
      const data=initial();data.scenes[0].lines[0]='Bozza salvata.';data.places[1].pos=[20.8,38.5];data.dirty=true;
      const draft=new ui.ReviewDraft(data);draft.setLine('01',0,'Altra modifica.');draft.resetScene('01');draft.setPosition('itaca',[21,39]);draft.resetPlace('itaca');
      const reset={dirty:draft.dirty,line:draft.scenes[0].lines[0],pos:draft.places[1].pos};
      draft.restoreScene('01');draft.restorePlace('itaca');console.log(JSON.stringify({reset,patch:draft.patch()}));
    """)
    assert result['reset'] == {'dirty': False, 'line': 'Bozza salvata.', 'pos': [20.8, 38.5]}
    assert result['patch']['scenes'][0]['lines'][0] == 'Il viaggio inizia.'
    assert result['patch']['places'][0]['pos'] == [20.7, 38.4]


def test_invalid_positions_and_nonexistent_cues_never_mutate_the_draft():
    result = run_js("""
      const draft=new ui.ReviewDraft(initial()),errors=[];
      for(const pos of [[180,40],[20,79],[NaN,40],[20,Infinity],['20',40],[20]]){try{draft.setPosition('itaca',pos)}catch(e){errors.push(e.message)}}
      try{draft.setLine('01',2,'Nuovo passaggio non previsto.')}catch(e){errors.push(e.message)}
      console.log(JSON.stringify({errors:errors.length,dirty:draft.dirty,valid:ui.validPosition([-179,-78])}));
    """)
    assert result == {'errors': 7, 'dirty': False, 'valid': True}


def test_readonly_and_empty_narration_do_not_send_save_requests():
    result = run_js("""
      let calls=0;const errors=[],writer=async()=>{calls++};
      const locked=initial();locked.editable=false;locked.reason='Produzione in corso.';
      const a=new ui.ReviewDraft(locked);a.setLine('01',0,'Modifica.');try{await a.save(writer)}catch(e){errors.push(e.message)}
      const b=new ui.ReviewDraft(initial());b.setLine('01',0,'  ');try{await b.save(writer)}catch(e){errors.push(e.message)}
      console.log(JSON.stringify({calls,errors,dirty:a.dirty&&b.dirty}));
    """)
    assert result['calls'] == 0 and result['dirty']
    assert result['errors'][0] == 'Produzione in corso.'
    assert 'Ogni frase' in result['errors'][1]


def test_reviewer_controls_are_optional_and_map_has_an_accessible_alternative():
    result = run_js("console.log(JSON.stringify({html:ui.editorHtml(),words:ui.wordCount(['  Una nuova città.','Una nave arriva.  '])}));")
    assert 'Tutto facoltativo' in result['html']
    assert 'data-review-text><summary>' in result['html']
    assert 'data-review-geography><summary>' in result['html']
    assert 'id="review-lat"' in result['html'] and 'id="review-lon"' in result['html']
    assert 'aria-pressed="false">Mappa dettagliata online' in result['html']
    assert result['words'] == 6


def test_unpositioned_place_can_be_positioned_and_reset_without_inventing_coordinates():
    result = run_js("""
      const data=initial();data.places[1].pos=null;data.places[1].base_pos=null;
      const draft=new ui.ReviewDraft(data);const before=draft.dirty;
      draft.setPosition('itaca',[20.7,38.4]);const patch=draft.patch();draft.resetPlace('itaca');
      console.log(JSON.stringify({before,patch,after:draft.places[1].pos,dirty:draft.dirty}));
    """)
    assert result['before'] is False and result['dirty'] is False and result['after'] is None
    assert result['patch']['places'] == [{'id': 'itaca', 'pos': [20.7, 38.4]}]


def test_offline_land_is_below_optional_online_tiles():
    # Leaflet's built-in tilePane is z-index 200. Sharing that pane let the
    # opaque SVG cover loaded roads and labels, although network requests passed.
    source = (ROOT / 'static/review-editor.js').read_text(encoding='utf-8')
    assert "createPane('reviewLand').style.zIndex='190'" in source
    assert "geoJSON(land,{pane:'reviewLand'" in source
