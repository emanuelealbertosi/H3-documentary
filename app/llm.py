import copy, hashlib, json, re, time, threading
import requests
from .models import Settings

class ModelError(RuntimeError): pass
class TruncatedResponse(ModelError): pass
class InvalidStructuredData(ModelError):
    """Complete JSON failed validation; data is a pre-callback schema snapshot.

    A Pydantic schema error leaves data=None: callers must not mistake raw or
    partially normalized input for a validated candidate.
    """
    def __init__(self,problem,data=None,repeated=False):
        self.problem=problem;self.data=copy.deepcopy(data);self.repeated=bool(repeated)
        super().__init__('Il modello non riesce a produrre dati validi per questa fase. '+problem)

def provider_error(response,secret=''):
    """Return the provider's useful JSON error without echoing requests or keys."""
    try:
        data=response.json()
    except Exception:
        return ''
    if isinstance(data,dict):
        data=data.get('error',data)
    if isinstance(data,dict):
        parts=[]
        for key in ('message','detail','type','code','param'):
            value=data.get(key)
            if isinstance(value,(str,int,float)) and str(value).strip():parts.append(str(value).strip())
        detail=' · '.join(dict.fromkeys(parts))
    elif isinstance(data,str):detail=data.strip()
    else:detail=''
    if secret:detail=detail.replace(secret,'[chiave rimossa]')
    detail=re.sub(r'(?i)bearer\s+[a-z0-9._~+/-]+','Bearer [chiave rimossa]',detail)
    return re.sub(r'\s+',' ',detail)[:700]

def compatibility_retry(payload,detail,attempt,token_parameter):
    """Adjust one rejected OpenAI-compatible request without changing saved settings."""
    lower=detail.lower()
    context=any(term in lower for term in ('context length','context window','maximum context','too many tokens','prompt is too long','n_ctx'))
    if context and payload.get(token_parameter,0)>512:
        payload[token_parameter]=max(512,int(payload[token_parameter])//2)
        return f"richiesta troppo lunga; spazio di risposta ridotto a {payload[token_parameter]} token"
    if 'reasoning_effort' in payload and any(term in lower for term in ('reasoning_effort','reasoning effort','reasoning parameter')):
        payload.pop('reasoning_effort',None)
        return 'controllo reasoning non accettato; riprovo usando le impostazioni native del server'
    if 'response_format' in payload and any(term in lower for term in ('response_format','json_schema','json schema')):
        payload.pop('response_format',None)
        return 'formato JSON strutturato non accettato; riprovo con lo schema nelle istruzioni'
    if attempt==0:
        return 'rifiuto temporaneo; riprovo una volta la stessa richiesta'
    return ''

def validation_message(error):
    if hasattr(error,'errors'):
        return '; '.join('.'.join(map(str,e['loc']))+': '+e['msg'] for e in error.errors(include_url=False,include_input=False))[:2200]
    return str(error)[:2200]
def extract_json(text):
    text=re.sub(r"<think>.*?</think>","",text,flags=re.S).strip()
    text=re.sub(r"^\x60\x60\x60(?:json)?\s*|\s*\x60\x60\x60$","",text).strip()
    # Only decode the outer response: a complete nested object in a truncated plan is not a plan.
    starts=[i for c in ('{','[') if (i:=text.find(c))>=0]
    if starts:
        try:return json.JSONDecoder().raw_decode(text[min(starts):])[0]
        except ValueError:pass
    raise ModelError("Il modello non ha restituito un oggetto JSON valido.")

def unwrap_schema_echo(obj,spec):
    """Recover data when a small model writes values inside a schema wrapper."""
    if not isinstance(obj,dict):return obj
    required=set(spec.get('required',[])) if isinstance(spec,dict) else set()
    title=str(spec.get('title','')).strip() if isinstance(spec,dict) else ''
    keys=['properties','data','result']
    if title:keys.extend([title,title[:1].lower()+title[1:],re.sub(r'(?<!^)(?=[A-Z])','_',title).lower()])
    for key in dict.fromkeys(keys):
        value=obj.get(key)
        if isinstance(value,dict) and (not required or required<=set(value)):
            return value
    return obj

class LLM:
    def __init__(self,config,cancel=lambda:None,audit=None):
        self.config=config;self.cancel=cancel;self.audit=audit;self.calls=0
        self.session=requests.Session()
        self.session.trust_env=False
        self.session.headers.update({"Content-Type":"application/json"})
        if config.get("api_key"):self.session.headers["Authorization"]="Bearer "+config["api_key"]
    def notify(self,message):
        callback=getattr(self,'progress',None)
        if callback:callback(message)
    def load_lmstudio_model(self):
        """Load the configured model through LM Studio's native management API."""
        if self.config.get('provider')!='lmstudio':return False
        base=self.config['base_url'].rstrip('/')
        if base.endswith('/v1'):base=base[:-3]
        body={'model':self.config['model']}
        if self.config.get('context_length'):body['context_length']=self.config['context_length']
        self.notify('LM Studio: nessun modello caricato; carico '+self.config['model']+'.')
        try:
            response=self.session.post(base+'/api/v1/models/load',json=body,
                timeout=(15,self.config['timeout']),allow_redirects=False)
        except requests.RequestException as error:
            raise ModelError('LM Studio non ha completato il caricamento automatico del modello.') from error
        if response.status_code not in (200,201):
            detail=provider_error(response,self.config.get('api_key',''))
            raise ModelError(f"LM Studio non riesce a caricare {self.config['model']} (HTTP {response.status_code})"+(f": {detail}" if detail else '')+". Apri Developer in LM Studio e controlla il modello selezionato.")
        self.notify('LM Studio: modello caricato; riprendo la richiesta.')
        return True
    def models(self):
        self.cancel()
        try:r=self.session.get(self.config["base_url"]+"/models",timeout=(10,30),allow_redirects=False)
        except requests.RequestException as e:raise ModelError("Server non raggiungibile. Controlla indirizzo, porta e accesso dalla rete.") from e
        if r.status_code!=200:
            detail=provider_error(r,self.config.get('api_key',''))
            raise ModelError(f"Il server modelli risponde HTTP {r.status_code}"+(f": {detail}" if detail else '')+". Controlla endpoint e credenziali.")
        data=r.json();return [str(x["id"]) for x in data.get("data",[]) if x.get("id")]
    def chat(self,messages,max_tokens=None,response_format=None):
        self.cancel()
        if self.calls>=self.config.get("request_limit",100):raise ModelError("Raggiunto il limite di richieste per questa esecuzione.")
        token_parameter=self.config.get("token_parameter","max_tokens")
        payload={"model":self.config["model"],"messages":messages,"stream":False,
                 token_parameter:max_tokens or self.config["max_tokens"]}
        if self.config.get("temperature") is not None:payload["temperature"]=self.config["temperature"]
        reasoning=self.config.get('reasoning_mode','server')
        if reasoning!='server':payload['reasoning_effort']='medium' if reasoning=='on' else 'none'
        if response_format is not None:payload['response_format']=response_format
        elif self.config.get("json_mode"):payload["response_format"]={"type":"json_object"}
        for attempt in range(3):
            self.cancel()
            if self.calls>=self.config.get("request_limit",100):raise ModelError("Raggiunto il limite di richieste per questa esecuzione.")
            self.calls+=1
            started=time.monotonic();finished=threading.Event()
            self.notify(f"Modello: richiesta {self.calls} inviata; attendo la risposta.")
            def heartbeat():
                while not finished.wait(20):
                    try:
                        self.cancel()
                        self.notify(f"Modello: in attesa da {round(time.monotonic()-started)} secondi; la richiesta è ancora aperta.")
                    except Exception:return
            if getattr(self,'progress',None):threading.Thread(target=heartbeat,daemon=True).start()
            try:
                r=self.session.post(self.config["base_url"]+"/chat/completions",json=payload,
                     timeout=(15,self.config["timeout"]),allow_redirects=False)
                if r.status_code in (429,502,503,504) and attempt<2:
                    for _ in range(2**attempt):self.cancel();time.sleep(1)
                    continue
                if r.status_code!=200:
                    detail=provider_error(r,self.config.get('api_key',''))
                    if self.audit:self.audit({"call":self.calls,"model":self.config['model'],"status":r.status_code,"seconds":round(time.monotonic()-started,1),"error":detail or "nessun dettaglio restituito"})
                    if r.status_code==400 and attempt<2:
                        if 'no models loaded' in detail.lower() and self.load_lmstudio_model():
                            continue
                        adjustment=compatibility_retry(payload,detail,attempt,token_parameter)
                        if adjustment:
                            self.notify("Modello: HTTP 400, "+adjustment+".")
                            time.sleep(1)
                            continue
                    message=f"Il modello risponde HTTP {r.status_code}"+(f": {detail}" if detail else '')+"."
                    if r.status_code in (401,403):message+=' Controlla la chiave associata a questo server.'
                    elif r.status_code==400:message+=' Il progetto resta riprendibile; il dettaglio del server è stato conservato.'
                    else:message+=' Verifica endpoint e modello in Amministrazione.'
                    raise ModelError(message)
                data=r.json();choice=data["choices"][0];text=choice["message"].get("content") or ""
                if isinstance(text,list):text="".join(x.get("text","") for x in text if isinstance(x,dict))
                elapsed=round(time.monotonic()-started,1)
                if self.audit:self.audit({"call":self.calls,"model":self.config['model'],"usage":data.get("usage"),"finish_reason":choice.get('finish_reason'),"seconds":elapsed,"response":text})
                self.notify(f"Modello: risposta ricevuta in {elapsed} secondi; controllo i dati.")
                if choice.get("finish_reason")=="length":raise TruncatedResponse("Risposta troncata: il modello ha esaurito lo spazio disponibile prima di completare i dati. Anche il ragionamento può consumare il budget della risposta.")
                if not text.strip():raise ModelError("Risposta vuota: controlla il modello e il suo formato chat.")
                self.cancel();return text
            except requests.Timeout as e:
                raise ModelError("Il modello non ha risposto entro il tempo massimo configurato. Puoi aumentarlo in Amministrazione.") from e
            except requests.ConnectionError as e:
                raise ModelError("Server non raggiungibile. Controlla indirizzo, porta e accesso dalla rete.") from e
            except (requests.RequestException,KeyError,ValueError) as e:
                raise ModelError("Richiesta al modello non completata o risposta incompatibile. Il progetto può essere ripreso.") from e
            finally:finished.set()
        raise ModelError("Server temporaneamente non disponibile.")
    def structured(self,system,user,schema,attempts=3,validator=None,split_on_truncation=False,stop_on_repeated_invalid=False):
        spec=schema.model_json_schema() if hasattr(schema,"model_json_schema") else schema
        response_format=None
        if self.config.get('json_mode') and self.config.get('provider')=='lmstudio':
            name=re.sub(r'[^a-zA-Z0-9_-]','_',spec.get('title','h3_documentary'))[:64]
            response_format={'type':'json_schema','json_schema':{'name':name,'strict':True,'schema':spec}}
        messages=[{"role":"system","content":system+"\nRispondi soltanto con JSON valido secondo questo schema:\n"+json.dumps(spec,ensure_ascii=False)},
                  {"role":"user","content":user}]
        original=list(messages)
        previous_invalid=None
        for attempt in range(attempts):
            validated_data=None;fingerprint_data=None
            try:
                text=self.chat(messages,response_format=response_format)
                obj=unwrap_schema_echo(extract_json(text),spec)
                fingerprint_data=copy.deepcopy(obj)
                obj=schema.model_validate(obj).model_dump() if hasattr(schema,"model_validate") else obj
                validated_data=copy.deepcopy(obj);fingerprint_data=validated_data
                if validator is not None:obj=validator(obj)
                return obj
            except TruncatedResponse:
                previous_invalid=None
                if split_on_truncation or attempt==attempts-1:raise
                self.notify(f"Risposta troppo lunga: richiedo una versione più compatta ({attempt+2}/{attempts}).")
                messages=original+[{"role":"user","content":"La risposta precedente era troncata. Restituisci l'intero JSON in forma compatta: descrizioni brevi, nessuna spiegazione o ragionamento visibile, soltanto campi necessari. Mantieni tutti gli elementi richiesti. Non proseguire dal punto interrotto."}]
            except ValueError as e:
                problem=validation_message(e)
                canonical=json.dumps([fingerprint_data,problem],sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str)
                fingerprint=hashlib.sha256(canonical.encode('utf-8')).hexdigest()
                repeated=fingerprint==previous_invalid;previous_invalid=fingerprint
                if attempt==attempts-1 or (stop_on_repeated_invalid and repeated):
                    raise InvalidStructuredData(problem,validated_data,repeated) from e
                self.notify(f"Correzione dei dati ({attempt+2}/{attempts}): "+problem[:650])
                if repeated:
                    messages=original+[{"role":"user","content":"Dati ripetuti: hai restituito gli stessi dati non validi. Rigenera il JSON completo correggendo concretamente l'errore; non copiare la risposta precedente e non inventare fatti, date o riferimenti mancanti. Errori precisi: "+problem}]
                else:
                    messages=original+[{"role":"assistant","content":text},{"role":"user","content":"Correggi il JSON completo. Errori precisi: "+problem}]
            except ModelError as e:
                # Connection, authentication and timeout failures must not be retried as JSON repairs.
                if 'oggetto JSON valido' not in str(e) or attempt==attempts-1:raise
                previous_invalid=None
                self.notify(f"Formato JSON incompleto: nuovo tentativo {attempt+2}/{attempts}.")
                messages=original+[{"role":"user","content":"Restituisci un unico oggetto JSON completo, compatto e conforme allo schema, senza testo esterno."}]
