import json, re, time, threading
import requests
from .models import Settings

class ModelError(RuntimeError): pass
class TruncatedResponse(ModelError): pass

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
    def models(self):
        self.cancel()
        try:r=self.session.get(self.config["base_url"]+"/models",timeout=(10,30),allow_redirects=False)
        except requests.RequestException as e:raise ModelError("Server non raggiungibile. Controlla indirizzo, porta e accesso dalla rete.") from e
        if r.status_code!=200:raise ModelError(f"Il server modelli risponde HTTP {r.status_code}. Controlla endpoint e credenziali.")
        data=r.json();return [str(x["id"]) for x in data.get("data",[]) if x.get("id")]
    def chat(self,messages,max_tokens=None,response_format=None):
        self.cancel()
        if self.calls>=self.config.get("request_limit",100):raise ModelError("Raggiunto il limite di richieste per questa esecuzione.")
        payload={"model":self.config["model"],"messages":messages,"stream":False,
                 self.config.get("token_parameter","max_tokens"):max_tokens or self.config["max_tokens"]}
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
                    raise ModelError(f"Il modello risponde HTTP {r.status_code}. Verifica credenziali, modello, formato JSON e parametro token in Amministrazione.")
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
    def structured(self,system,user,schema,attempts=3,validator=None,split_on_truncation=False):
        spec=schema.model_json_schema() if hasattr(schema,"model_json_schema") else schema
        response_format=None
        if self.config.get('json_mode') and self.config.get('provider')=='lmstudio':
            name=re.sub(r'[^a-zA-Z0-9_-]','_',spec.get('title','h3_documentary'))[:64]
            response_format={'type':'json_schema','json_schema':{'name':name,'strict':True,'schema':spec}}
        messages=[{"role":"system","content":system+"\nRispondi soltanto con JSON valido secondo questo schema:\n"+json.dumps(spec,ensure_ascii=False)},
                  {"role":"user","content":user}]
        original=list(messages)
        for attempt in range(attempts):
            try:
                text=self.chat(messages,response_format=response_format)
                obj=extract_json(text)
                obj=schema.model_validate(obj).model_dump() if hasattr(schema,"model_validate") else obj
                if validator is not None:obj=validator(obj)
                return obj
            except TruncatedResponse:
                if split_on_truncation or attempt==attempts-1:raise
                self.notify(f"Risposta troppo lunga: richiedo una versione più compatta ({attempt+2}/{attempts}).")
                messages=original+[{"role":"user","content":"La risposta precedente era troncata. Restituisci l'intero JSON in forma compatta: descrizioni brevi, nessuna spiegazione o ragionamento visibile, soltanto campi necessari. Mantieni tutti gli elementi richiesti. Non proseguire dal punto interrotto."}]
            except ValueError as e:
                problem=validation_message(e)
                if attempt==attempts-1:raise ModelError("Il modello non riesce a produrre dati validi per questa fase. "+problem[:1200]) from e
                self.notify(f"Correzione dei dati ({attempt+2}/{attempts}): "+problem[:650])
                messages=original+[{"role":"assistant","content":text},{"role":"user","content":"Correggi il JSON completo. Errori precisi: "+problem}]
            except ModelError as e:
                # Connection, authentication and timeout failures must not be retried as JSON repairs.
                if 'oggetto JSON valido' not in str(e) or attempt==attempts-1:raise
                self.notify(f"Formato JSON incompleto: nuovo tentativo {attempt+2}/{attempts}.")
                messages=original+[{"role":"user","content":"Restituisci un unico oggetto JSON completo, compatto e conforme allo schema, senza testo esterno."}]
