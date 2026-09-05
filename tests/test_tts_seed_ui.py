"""Exercise the actual Higgs admin form and its outgoing save/preview payloads."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_js(body):
    if not shutil.which('node'):
        pytest.skip('Node is required for the frontend developer check')
    setup = r"""
      import {readFileSync} from 'node:fs';
      const dependency='data:text/javascript;base64,'+Buffer.from(readFileSync('static/voice-delivery.js','utf8')).toString('base64');
      const source=readFileSync('static/tts-api.js','utf8').replace(/'\.\/voice-delivery\.js[^']*'/,JSON.stringify(dependency));
      const {mountTtsAdmin}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
      const nodes={};
      const node=id=>{
        if(!nodes[id]){
          const classes=new Set();
          nodes[id]={value:'',checked:false,disabled:false,textContent:'',dataset:{},
            classList:{toggle(c,on){if(on)classes.add(c);else classes.delete(c)},remove(c){classes.delete(c)},contains(c){return classes.has(c)}},
            async play(){}};
        }
        return nodes[id];
      };
      globalThis.document={querySelector:selector=>node(selector.slice(1))};
      const requests=[];
      globalThis.fetch=async(url,options)=>{
        requests.push({url,body:JSON.parse(options.body)});
        return {ok:true,json:async()=>({id:'saved'}),headers:{get:()=>null},blob:async()=>new Blob(['fixture'])};
      };
      URL.createObjectURL=()=> 'blob:fixture';URL.revokeObjectURL=()=>{};
      const profile=seed=>({id:'higgs-saved',name:'Higgs sul PC remoto',provider:'higgs',base_url:'http://192.168.1.60:8095/v1',voice:'voce_narratore',seed,has_api_key:true});
      const mount=(profiles=[])=>{
        node('tts-api-provider').value='openai';
        mountTtsAdmin({innerHTML:''},profiles,{toast(){},async reload(){}});
        node('tts-api-preview-text').value='Una frase per la prova della voce.';
      };
      const click=async id=>node(id).onclick({target:node(id)});
      const fixed=checked=>{node('tts-api-keep-seed').checked=checked;node('tts-api-keep-seed').onchange()};
      const selectProvider=provider=>{node('tts-api-provider').value=provider;node('tts-api-provider').onchange()};
    """
    result = subprocess.run(['node', '--input-type=module', '-e', setup + body],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize('seed', [-1, 0, 9173])
def test_saved_seed_restores_without_changing_existing_profiles(seed):
    result = run_js(f"""
      const original=profile({seed});mount([original]);
      const state={{checked:node('tts-api-keep-seed').checked,disabled:node('tts-api-seed').disabled,value:node('tts-api-seed').value}};
      await click('tts-api-save');await click('tts-api-test');
      console.log(JSON.stringify({{state,requests,original}}));
    """)
    assert result['state'] == {'checked': seed >= 0, 'disabled': seed < 0,
                               'value': seed if seed >= 0 else 42}
    assert result['original']['seed'] == seed
    saved, preview = result['requests']
    assert saved['body']['seed'] == preview['body']['seed'] == seed
    assert saved['body']['voice'] == preview['body']['voice'] == 'voce_narratore'
    assert saved['body']['base_url'] == 'http://192.168.1.60:8095/v1'
    assert saved['body']['api_key'] == '' and not saved['body']['clear_api_key']


def test_toggle_remembers_zero_and_custom_seed_and_preview_matches_save():
    result = run_js("""
      mount([profile(0)]);fixed(false);await click('tts-api-save');
      const disabledZero=node('tts-api-seed').value;
      fixed(true);await click('tts-api-test');
      node('tts-api-seed').value='73081';fixed(false);await click('tts-api-test');
      fixed(true);await click('tts-api-save');
      console.log(JSON.stringify({requests,disabledZero,value:node('tts-api-seed').value,enabled:!node('tts-api-seed').disabled}));
    """)
    assert [x['body']['seed'] for x in result['requests']] == [-1, 0, -1, 73081]
    assert result['disabledZero'] == 0
    assert result['value'] == '73081' and result['enabled']


def test_new_higgs_defaults_to_fixed_seed_but_other_providers_hide_control():
    result = run_js("""
      mount();selectProvider('higgs');
      const initial={checked:node('tts-api-keep-seed').checked,value:node('tts-api-seed').value,visible:!node('tts-higgs-seed').classList.contains('hidden')};
      await click('tts-api-save');selectProvider('elevenlabs');await click('tts-api-save');
      console.log(JSON.stringify({initial,requests,hidden:node('tts-higgs-seed').classList.contains('hidden'),disabled:node('tts-api-seed').disabled}));
    """)
    assert result['initial'] == {'checked': True, 'value': 42, 'visible': True}
    assert [x['body']['seed'] for x in result['requests']] == [42, -1]
    assert result['hidden'] and result['disabled']


def test_legacy_profile_without_seed_stays_random_when_reopened():
    result = run_js("""
      const legacy=profile(undefined);mount([legacy]);await click('tts-api-save');
      console.log(JSON.stringify({checked:node('tts-api-keep-seed').checked,seed:requests[0].body.seed}));
    """)
    assert result == {'checked': False, 'seed': -1}


def test_invalid_fixed_seed_is_explained_before_any_network_request():
    result = run_js("""
      mount([profile(42)]);const errors=[];
      for(const value of ['', '-1', '1.5', '2147483648', 'NaN']){
        node('tts-api-seed').value=value;await click('tts-api-save');
        errors.push(node('tts-api-result').textContent);
      }
      node('tts-api-seed').value='2147483647';await click('tts-api-save');
      console.log(JSON.stringify({errors,requests,enabled:!node('tts-api-save').disabled}));
    """)
    assert len(result['errors']) == 5
    assert all('numero intero tra 0 e 2147483647' in text for text in result['errors'])
    assert len(result['requests']) == 1 and result['requests'][0]['body']['seed'] == 2147483647
    assert result['enabled']
