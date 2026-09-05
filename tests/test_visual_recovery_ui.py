"""Recoverable visual omissions expose manual cards without bypassing production gates."""
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
      const moduleSource=readFileSync('static/visual-recovery.js','utf8');
      const ui=await import('data:text/javascript;base64,'+Buffer.from(moduleSource).toString('base64'));
      const warning={scene_id:'scene-2',scene_index:1,scene_title:'Il viaggio',element:'movements',reason:'Destinazione non riconosciuta.',placeholder:true,slot_id:'visual-background-scene-2'};
      const slot={id:'visual-background-scene-2',source_type:'scene_background',scene_ids:['scene-2'],enabled:true,state:'blank'};
      const project={status:'review',result:{visual_warnings:[warning]}};
      const visual={ready:true,awaiting_review:true,slots:[slot],visual_warnings:[warning]};
    """
    result = subprocess.run(['node', '--input-type=module', '-e', source + body], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)


def test_visual_omissions_group_by_scene_escape_details_and_do_not_expose_raw_data():
    result = run_js("""
      const first={...warning,scene_title:'<img src=x onerror=bad()>',reason:'Punto <script>bad()</script>',omitted_items:[{data:{secret:'RAW MODEL DATA'}}]};
      const second={...first,element:'territories',reason:'Epoca non valida.'};
      const state={...visual,visual_warnings:[first,first,second,null,'invalid']};
      console.log(JSON.stringify({rows:ui.visualRecoveryRows({},state),html:ui.visualRecoveryHtml('project-1',project,state)}));
    """)
    assert len(result['rows']) == 1
    assert len(result['rows'][0]['issues']) == 2
    assert '1 scena da controllare' in result['html']
    assert '&lt;script&gt;bad()&lt;/script&gt;' in result['html']
    assert '<script>' not in result['html'] and '<img src=x' not in result['html']
    assert 'RAW MODEL DATA' not in json.dumps(result)
    assert 'Gestisci' in result['html'] and '<button' not in result['html']


def test_preparation_warnings_use_public_project_result_until_slots_are_ready():
    result = run_js("""
      const early=ui.visualRecoveryHtml('project-1',{...project,status:'running'},{ready:false,slots:[]});
      const current={...visual,visual_warnings:[{...warning,reason:'Motivo aggiornato.'}]};
      console.log(JSON.stringify({early,latest:ui.visualRecoveryHtml('project-1',project,current),empty:ui.visualRecoveryHtml('project-1',{},{}),invalid:ui.visualRecoveryHtml('project-1',{}, {visual_warnings:'invalid'})}));
    """)
    assert 'Destinazione non riconosciuta' in result['early']
    assert 'Preparazione dei materiali in corso' in result['early']
    assert '<a ' not in result['early'] and 'è ferma' not in result['early']
    assert 'Motivo aggiornato' in result['latest']
    assert 'Destinazione non riconosciuta' not in result['latest']
    assert result['empty'] == result['invalid'] == ''


def test_manual_background_links_and_status_follow_actual_slot_changes():
    result = run_js("""
      const output={pending:ui.visualRecoveryHtml('project-1',project,visual)};
      for(const [name,changes] of Object.entries({linked:{replacement_ready:true},saved:{state:'user'},excluded:{enabled:false,replacement_ready:true}})){
        output[name]=ui.visualRecoveryHtml('project-1',project,{...visual,slots:[{...slot,...changes}]});
      }
      const noSlotId={...warning};delete noSlotId.slot_id;
      output.matched=ui.visualRecoveryRows({}, {...visual,visual_warnings:[noSlotId]})[0];
      console.log(JSON.stringify(output));
    """)
    assert '/projects/project-1/media?slot=visual-background-scene-2' in result['pending']
    assert 'Scene da completare a mano' in result['pending']
    assert 'La produzione è ferma per la revisione' in result['pending']
    assert 'Puoi anche premere Continua produzione lasciando la scheda vuota, oppure escluderla da Gestisci.' in result['pending']
    assert 'Immagine collegata' in result['linked'] and 'Immagine collegata' in result['saved']
    assert 'Scene da completare a mano' not in result['linked']
    assert 'Scheda esclusa' in result['excluded']
    assert all('Destinazione non riconosciuta' in result[key] for key in ('pending', 'linked', 'saved', 'excluded'))
    assert result['matched']['slotId'] == 'visual-background-scene-2'


def test_partial_omission_does_not_claim_that_valid_scene_requires_replacement():
    result = run_js("""
      const partial={...warning,placeholder:false};delete partial.slot_id;
      console.log(JSON.stringify(ui.visualRecoveryHtml('project-1',project,{...visual,visual_warnings:[partial],slots:[]})));
    """)
    assert 'Le scene conservano gli altri elementi validi' in result
    assert 'Elemento omesso' in result
    assert 'Da completare' not in result and 'Scene da completare a mano' not in result
    assert 'href="/projects/project-1/media"' in result
    assert 'visual-background' not in result


def test_polling_preserves_open_details_and_updates_material_state():
    result = run_js("""
      class Target {
        constructor(){this.writes=0;this.details=null}
        set innerHTML(html){this.html=html;this.writes++;this.details=html.includes('<details')?{open:html.includes('data-visual-recovery-details open')}:null}
        get innerHTML(){return this.html||''}
        querySelector(){return this.details}
      }
      const target=new Target();ui.updateVisualRecovery(target,'project-1',project,visual);
      target.details.open=false;ui.updateVisualRecovery(target,'project-1',project,visual);
      const repeatedWrites=target.writes;
      ui.updateVisualRecovery(target,'project-1',project,{...visual,slots:[{...slot,replacement_ready:true}]});
      const afterChange={open:target.details.open,html:target.html};
      ui.updateVisualRecovery(target,'project-2',project,visual);const newProjectOpen=target.details.open;
      ui.updateVisualRecovery(target,'project-2',{},{});
      console.log(JSON.stringify({repeatedWrites,afterChange,newProjectOpen,empty:target.innerHTML}));
    """)
    assert result['repeatedWrites'] == 1
    assert result['afterChange']['open'] is False
    assert 'Immagine collegata' in result['afterChange']['html']
    assert result['newProjectOpen'] is True
    assert result['empty'] == ''


def test_project_updates_recovery_panel_and_keeps_existing_review_gate():
    source = (ROOT / 'static/app.js').read_text(encoding='utf-8')
    assert 'id="project-visual-recovery"' in source
    assert "updateVisualRecovery($('#project-visual-recovery'),id,p,visual)" in source
    assert "const visualReview=p.status==='review'&&visual.awaiting_review" in source
    assert "'/visual-approve'" in source
    assert 'Controlla gli eventuali avvisi e le anteprime' in source
    assert 'mappe e immagini automatiche sono completi' not in source


def test_known_recovery_reasons_and_combined_elements_use_readable_labels():
    result = run_js("""
      const plan="movements[1] termina a 'Capo Malea', ma titolo/event della scena non nominano questa destinazione. La stessa scena deve raccontare esplicitamente la partenza o l’arrivo; altrimenti sposta o rimuovi il movimento.";
      const known={...warning,element:'movements[0], territory_ids, movements[2], asset_ids, scene_type',reason:plan+' Riferimenti visuali non disponibili: unknown_area, picture_2.'};
      console.log(JSON.stringify(ui.visualRecoveryHtml('project-1',project,{...visual,visual_warnings:[known]})));
    """)
    assert '<strong>Percorso, Area, Immagine, Tipo scena</strong>' in result
    assert 'Il percorso verso Capo Malea non è descritto in questa scena; è stato escluso per evitare una freccia incoerente.' in result
    assert 'Un’area o un’immagine prevista non è disponibile.' in result
    for technical in ('movements[', 'territory_ids', 'asset_ids', 'scene_type', 'titolo/event', 'unknown_area', 'picture_2'):
        assert technical not in result


def test_recovery_background_preview_uses_whole_scene_without_changing_normal_insets():
    result = run_js("""
      const mediaSource=readFileSync('static/media.js','utf8');
      const media=await import('data:text/javascript;base64,'+Buffer.from(mediaSource).toString('base64'));
      const makeBox=()=>{const img={style:{}},caption={style:{}};return {style:{width:'25%'},img,caption,querySelector:name=>name==='img'?img:caption}};
      const recovered={...slot,required:true,recovery_reason:'Percorso omesso.',layout:{x:.71,y:.21,width:.25,fit:'cover'}};
      const before=JSON.stringify(recovered),box=makeBox();
      const applied=media.applyRecoveryBackgroundPreview(box,recovered);
      const normal=[];
      for(const candidate of [{...recovered,source_type:'person'},{...recovered,required:false},{...recovered,recovery_reason:''}]){
        const inset=makeBox();normal.push({applied:media.applyRecoveryBackgroundPreview(inset,candidate),width:inset.style.width,fit:inset.img.style.objectFit||''});
      }
      console.log(JSON.stringify({applied,style:box.style,fit:box.img.style.objectFit,caption:box.caption.style.display,unchanged:before===JSON.stringify(recovered),normal}));
    """)
    assert result['applied'] and result['unchanged']
    assert float(result['style']['width'].rstrip('%')) == pytest.approx(1820 / 1920 * 100)
    assert float(result['style']['height'].rstrip('%')) == pytest.approx(765 / 1080 * 100)
    assert result['fit'] == 'contain' and result['caption'] == 'none'
    assert all(item == {'applied': False, 'width': '25%', 'fit': ''} for item in result['normal'])
    source = (ROOT / 'static/media.js').read_text(encoding='utf-8')
    assert "${recoveryBackground?'<p class=\"tiny muted\">Immagine dell’intera scena · posizione automatica." in source
    assert 'if(recoveryBackground)return;\n    const saveLayout' in source
