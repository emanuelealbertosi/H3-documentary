"""Exercise the reusable voice controls without a browser or a TTS server."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_js(body):
    if not shutil.which('node'):
        pytest.skip('Node is only required for the frontend developer check')
    setup = """
      import {readFileSync} from 'node:fs';
      const source=readFileSync('static/voice-delivery.js','utf8');
      const ui=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
    """
    result = subprocess.run(['node', '--input-type=module', '-e', setup + body], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)


def test_saved_delivery_roundtrip_and_safe_preview_markup():
    result = run_js("""
      const saved={style:'calm',speed:.91,pause_seconds:.42};
      const markup=ui.voiceDeliveryFields('voice',saved,{text:'</textarea><script>alert(1)</script>'});
      const values={'voice-style':{value:saved.style},'voice-speed':{value:String(saved.speed)},'voice-pause':{value:String(saved.pause_seconds)}};
      globalThis.document={getElementById:id=>values[id]};
      console.log(JSON.stringify({markup,value:ui.readVoiceDelivery('voice'),default:ui.normalizeDelivery(),bounds:ui.normalizeDelivery({style:'unknown',speed:9,pause_seconds:-1})}));
    """)
    assert result['value'] == {'style': 'calm', 'speed': .91, 'pause_seconds': .42}
    assert result['default'] == {'style': 'original', 'speed': 1, 'pause_seconds': .18}
    assert result['bounds'] == {'style': 'original', 'speed': 1.15, 'pause_seconds': 0}
    assert 'value="calm" selected' in result['markup'] and 'value="0.91"' in result['markup']
    assert '<script>' not in result['markup'] and '&lt;script&gt;' in result['markup']


def test_controls_keep_choice_on_engine_change_and_preview_exact_settings():
    result = run_js("""
      const nodes={};
      class Element {
        constructor(id,value=''){this.id=id;this.value=value;this.listeners={};this.textContent='';this.disabled=false;this.isConnected=true;this.classList={remove(){}};this.playCount=0;nodes[id]=this}
        addEventListener(type,callback){(this.listeners[type]??=[]).push(callback)}
        removeEventListener(type,callback){this.listeners[type]=(this.listeners[type]||[]).filter(x=>x!==callback)}
        async emit(type){for(const callback of this.listeners[type]||[])await callback({target:this})}
        querySelector(selector){return nodes[selector.match(/id="([^"]+)"/)[1]]}
        pause(){}
        async play(){this.playCount++}
      }
      new Element('voice');new Element('engine','api:profile-higgs');new Element('reference','saved-sample');
      new Element('voice-style','solemn');new Element('voice-speed','.93');new Element('voice-pause','.44');
      for(const name of ['speed-value','pause-value','capabilities','result','preview','original','player'])new Element('voice-'+name);
      new Element('voice-text','Una prova breve.');
      globalThis.document={getElementById:id=>nodes[id],head:{append(){}},createElement:()=>({})};
      const requests=[];let revoked=0;
      URL.createObjectURL=()=> 'blob:voice-fixture';URL.revokeObjectURL=()=>revoked++;
      const tts={engines:[{id:'api:profile-higgs',delivery_capabilities:{styles:['original','solemn'],note:'Indicazioni espressive abilitate.'}},{id:'kokoro',delivery_capabilities:{styles:['original'],note:'Velocità e pause disponibili.'}}]};
      const options={tts,engineId:'engine',referenceId:'reference',requestPreview:async payload=>{requests.push(payload);const blob=new Blob(['fixture']);blob.h3StyleFallback=payload.tts_delivery.style!=='original';return blob}};
      ui.bindVoiceDelivery('voice',options);ui.bindVoiceDelivery('voice',options);
      nodes.engine.value='kokoro';await nodes.engine.emit('change');const unsupported=nodes['voice-capabilities'].textContent;
      const preserved=ui.readVoiceDelivery('voice');
      nodes.engine.value='api:profile-higgs';await nodes.engine.emit('change');
      await nodes['voice-preview'].emit('click');const fallbackMessage=nodes['voice-result'].textContent;await nodes['voice-original'].emit('click');
      const state={requests,unsupported,preserved,fallbackMessage,plays:nodes['voice-player'].playCount,buttonsEnabled:!nodes['voice-preview'].disabled&&!nodes['voice-original'].disabled,revoked};
      ui.disposeVoiceDelivery();state.listeners=nodes['voice-preview'].listeners.click.length;
      console.log(JSON.stringify(state));
    """)
    assert 'non applica lo stile' in result['unsupported']
    selected = {'style': 'solemn', 'speed': .93, 'pause_seconds': .44}
    assert result['preserved'] == selected
    assert len(result['requests']) == 2, 'Repeated project refresh must not duplicate preview listeners.'
    assert result['requests'][0] == {'tts_engine': 'api', 'tts_profile_id': 'profile-higgs',
                                    'tts_reference_id': 'saved-sample', 'text': 'Una prova breve.', 'tts_delivery': selected}
    assert result['requests'][1]['tts_delivery'] == {'style': 'original', 'speed': 1, 'pause_seconds': .18}
    assert result['plays'] == 2 and result['buttonsEnabled'] and result['revoked'] == 1
    assert result['listeners'] == 0
    assert 'non ha accettato le indicazioni espressive' in result['fallbackMessage']
    assert 'interpretazione originale' in result['fallbackMessage']


def test_preview_http_contract_keeps_reference_and_handles_backend_error():
    result = run_js("""
      const delivery={style:'documentary',speed:.96,pause_seconds:.3};let captured;
      globalThis.fetch=async(url,options)=>{captured={url,options};return {ok:true,headers:{get:key=>key==='X-Voice-Style-Fallback'?'true':null},blob:async()=>new Blob(['audio'],{type:'audio/wav'})}};
      const blob=await ui.requestVoicePreview({text:'Breve prova',tts_engine:'chatterbox',tts_reference_id:'sample',tts_delivery:delivery});
      globalThis.fetch=async()=>({ok:false,json:async()=>({detail:'Attendi la fine della produzione in corso.'})});
      let error;try{await ui.requestVoicePreview({})}catch(e){error=e.message}
      console.log(JSON.stringify({captured,type:blob.type,fallback:blob.h3StyleFallback,error}));
    """)
    assert result['captured']['url'] == '/api/tts/preview'
    options = result['captured']['options']
    assert options['method'] == 'POST' and options['headers']['X-DocumentariAI'] == 'studio'
    assert json.loads(options['body'])['tts_reference_id'] == 'sample'
    assert result['type'] == 'audio/wav'
    assert result['fallback'] is True
    assert result['error'] == 'Attendi la fine della produzione in corso.'


def test_saved_higgs_profile_keeps_endpoint_and_key_while_preview_uses_delivery():
    result = run_js(r"""
      const dependency='data:text/javascript;base64,'+Buffer.from(source).toString('base64');
      const moduleSource=readFileSync('static/tts-api.js','utf8').replace(/'\.\/voice-delivery\.js[^']*'/,JSON.stringify(dependency));
      const {mountTtsAdmin}=await import('data:text/javascript;base64,'+Buffer.from(moduleSource).toString('base64'));
      const nodes={};
      const node=id=>nodes[id]??={value:'',checked:false,disabled:false,textContent:'',dataset:{},classList:{toggle(){},remove(){}},async play(){}};
      globalThis.document={querySelector:selector=>node(selector.slice(1))};
      const sent=[];globalThis.fetch=async(url,options)=>{sent.push({url,body:JSON.parse(options.body)});return {ok:true,headers:{get:key=>key==='X-Voice-Style-Fallback'?'true':null},json:async()=>({id:'saved-higgs'}),blob:async()=>new Blob(['fixture'])}};
      URL.createObjectURL=()=> 'blob:fixture';URL.revokeObjectURL=()=>{};
      const profile={id:'saved-higgs',name:'Higgs remoto',provider:'higgs',base_url:'http://192.168.1.60:8095/v1',voice:'voce_mia',response_format:'wav',has_api_key:true,style_protocol:'higgs_tags'};
      const delivery={style:'solemn',speed:.95,pause_seconds:.4};
      mountTtsAdmin({innerHTML:''},[profile],{toast(){},async reload(){},getDelivery:()=>delivery});
      const restored=node('tts-api-style-protocol').checked;
      node('tts-api-preview-text').value='Testo scelto per la prova.';node('tts-api-reference').value='sample-higgs';
      await node('tts-api-test').onclick({target:node('tts-api-test')});
      const fallbackMessage=node('tts-api-result').textContent;
      await node('tts-api-save').onclick({target:node('tts-api-save')});
      node('tts-api-provider').value='openai';node('tts-api-provider').onchange();
      await node('tts-api-save').onclick({target:node('tts-api-save')});
      console.log(JSON.stringify({restored,sent,fallbackMessage}));
    """)
    assert result['restored'] is True
    assert 'non ha accettato le indicazioni espressive' in result['fallbackMessage']
    preview, saved, other_provider = result['sent']
    assert preview['url'] == '/api/tts/profiles/test'
    assert preview['body']['text'] == 'Testo scelto per la prova.'
    assert preview['body']['tts_delivery'] == {'style': 'solemn', 'speed': .95, 'pause_seconds': .4}
    assert preview['body']['reference_id'] == 'sample-higgs'
    assert saved['body']['style_protocol'] == 'higgs_tags'
    assert saved['body']['id'] == 'saved-higgs'
    assert saved['body']['base_url'] == 'http://192.168.1.60:8095/v1'
    assert saved['body']['api_key'] == '' and not saved['body']['clear_api_key']
    assert other_provider['body']['style_protocol'] == 'none'
    assert other_provider['body']['id'] == '' and other_provider['body']['api_key'] == ''
