import json, re, time
import requests
from .models import Settings

class ModelError(RuntimeError): pass
def extract_json(text):
    text=re.sub(r"<think>.*?</think>","",text,flags=re.S).strip()
    text=re.sub(r"^\x60\x60\x60(?:json)?\s*|\s*\x60\x60\x60$","",text).strip()
    decoder=json.JSONDecoder()
    for i,c in enumerate(text):
        if c in "{[":
            try:return decoder.raw_decode(text[i:])[0]
            except ValueError:pass
    raise ModelError("Il modello non ha restituito un oggetto JSON valido.")

class LLM:
    def __init__(self,config,cancel=lambda:None,audit=None):
        self.config=config;self.cancel=cancel;self.audit=audit;self.calls=0
        self.session=requests.Session()
        self.session.trust_env=False
        self.session.headers.update({"Content-Type":"application/json"})
        if config.get("api_key"):self.session.headers["Authorization"]="Bearer "+config["api_key"]
    def models(self):
        self.cancel()
        try:r=self.session.get(self.config["base_url"]+"/models",timeout=(10,30),allow_redirects=False)
        except requests.RequestException as e:raise ModelError("Server non raggiungibile. Controlla indirizzo, porta e accesso dalla rete.") from e
        if r.status_code!=200:raise ModelError(f"Il server modelli risponde HTTP {r.status_code}. Controlla endpoint e credenziali.")
        data=r.json();return [str(x["id"]) for x in data.get("data",[]) if x.get("id")]
    def chat(self,messages,max_tokens=None):
        self.cancel()
        if self.calls>=self.config.get("request_limit",100):raise ModelError("Raggiunto il limite di richieste per questa esecuzione.")
        payload={"model":self.config["model"],"messages":messages,"stream":False,
                 self.config.get("token_parameter","max_tokens"):max_tokens or self.config["max_tokens"]}
        if self.config.get("temperature") is not None:payload["temperature"]=self.config["temperature"]
        if self.config.get("json_mode"):payload["response_format"]={"type":"json_object"}
        for attempt in range(3):
            self.cancel()
            if self.calls>=self.config.get("request_limit",100):raise ModelError("Raggiunto il limite di richieste per questa esecuzione.")
            self.calls+=1
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
                if choice.get("finish_reason")=="length":raise ModelError("Risposta troncata: aumenta il limite token del server o dell’app.")
                if not text.strip():raise ModelError("Risposta vuota: controlla il modello e il suo formato chat.")
                if self.audit:self.audit({"call":self.calls,"usage":data.get("usage"),"response":text})
                self.cancel();return text
            except requests.Timeout as e:
                raise ModelError("Il modello non ha risposto entro il tempo massimo configurato. Puoi aumentarlo in Amministrazione.") from e
            except requests.ConnectionError as e:
                raise ModelError("Server non raggiungibile. Controlla indirizzo, porta e accesso dalla rete.") from e
            except (requests.RequestException,KeyError,ValueError) as e:
                raise ModelError("Richiesta al modello non completata o risposta incompatibile. Il progetto può essere ripreso.") from e
        raise ModelError("Server temporaneamente non disponibile.")
    def structured(self,system,user,schema,attempts=3):
        spec=schema.model_json_schema() if hasattr(schema,"model_json_schema") else schema
        messages=[{"role":"system","content":system+"\nRispondi soltanto con JSON valido secondo questo schema:\n"+json.dumps(spec,ensure_ascii=False)},
                  {"role":"user","content":user}]
        for attempt in range(attempts):
            text=self.chat(messages)
            try:
                obj=extract_json(text)
                return schema.model_validate(obj).model_dump() if hasattr(schema,"model_validate") else obj
            except (ValueError,ModelError) as e:
                if attempt==attempts-1:raise ModelError("Il modello non riesce a produrre dati validi per questa fase. "+str(e)[:500])
                messages += [{"role":"assistant","content":text},{"role":"user","content":"Correggi il JSON. Errori: "+str(e)[:2400]}]
