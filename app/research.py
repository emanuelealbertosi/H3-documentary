"""Public-web discovery and extraction. Retrieved pages are evidence, never instructions."""
import ipaddress,socket,re,time,hashlib,json
from urllib.parse import urlsplit,urljoin,parse_qs,unquote
import requests
from bs4 import BeautifulSoup
from .store import write_json,now

def public_url(url):
    p=urlsplit(url)
    if p.scheme not in ("http","https") or not p.hostname or p.username or p.password:
        raise ValueError("Fonte non valida: serve una pagina web pubblica.")
    if p.port not in (None,80,443):raise ValueError("Porta non consentita per una fonte pubblica.")
    for item in socket.getaddrinfo(p.hostname,p.port or 443,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError("Le fonti storiche non possono accedere alla rete privata.")
    return url
def fetch(url,limit=2500000):
    session=requests.Session();session.trust_env=False
    for _ in range(5):
        public_url(url)
        response=session.get(url,headers={"User-Agent":"DocumentariAI-Studio/1.0 (historical research)"},timeout=(12,35),stream=True,allow_redirects=False)
        if response.status_code in (301,302,303,307,308):
            url=urljoin(url,response.headers.get("Location",""));response.close();continue
        response.raise_for_status()
        content_type=response.headers.get("Content-Type","").lower()
        if not any(t in content_type for t in ("html","text/plain","json")):
            response.close();raise ValueError("Formato fonte non supportato: usa una pagina HTML o testo.")
        data=bytearray()
        for chunk in response.iter_content(32768):
            data.extend(chunk)
            if len(data)>limit:response.close();raise ValueError("Pagina troppo grande.")
        encoding=response.encoding if response.encoding and response.encoding.lower()!="iso-8859-1" else "utf-8"
        text=bytes(data).decode(encoding,errors="replace");response.close()
        return text,url
    raise ValueError("Troppi reindirizzamenti nella fonte.")
def extract(url):
    parsed=urlsplit(url)
    if parsed.hostname in ("archive.org","www.archive.org") and parsed.path.startswith("/details/"):
        raise ValueError("Scheda di catalogo: occorre il testo della fonte, non soltanto la descrizione del libro o video.")
    html,final=fetch(url);soup=BeautifulSoup(html,"html.parser")
    title=soup.title.get_text(" ",strip=True) if soup.title else final
    for node in soup(["script","style","nav","footer","header","aside","form"]):node.decompose()
    body=soup.find("article") or soup.find("main") or soup.body or soup
    text=re.sub(r"\s+"," ",body.get_text(" ",strip=True)).strip()
    if len(text)<650:raise ValueError("La pagina non contiene abbastanza testo consultabile.")
    links=[urljoin(final,a.get("href","")) for a in body.select("a[href]")]
    return {"title":title[:240],"url":final,"text":text[:18000],"links":links,
      "retrieved":now(),"sha256":hashlib.sha256(text.encode()).hexdigest()}
def search(query,search_url=""):
    if search_url:
        p=urlsplit(search_url)
        if p.scheme not in ("http","https") or p.username or p.password:raise ValueError("Indirizzo SearXNG non valido.")
        session=requests.Session();session.trust_env=False
        r=session.get(search_url.rstrip("/")+"/search",params={"q":query,"format":"json"},timeout=(10,35),allow_redirects=False);r.raise_for_status()
        return [{"title":x.get("title",""),"url":x["url"]} for x in r.json().get("results",[])[:8] if x.get("url")]
    html,_=fetch("https://html.duckduckgo.com/html/?q="+requests.utils.quote(query))
    soup=BeautifulSoup(html,"html.parser");out=[]
    for a in soup.select(".result__a"):
        url=a.get("href","")
        if url.startswith("//"):url="https:"+url
        if "duckduckgo.com/l/" in url:url=parse_qs(urlsplit(url).query).get("uddg",[url])[0]
        if url.startswith("http"):out.append({"title":a.get_text(" ",strip=True),"url":url})
    return out[:8]
def discover_wikipedia(topic):
    """Fallback discovery only; Wikipedia references lead to additional consulted sources."""
    url="https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srlimit=3&srsearch="+requests.utils.quote(topic)
    text,_=fetch(url);data=json.loads(text)
    return [{"url":"https://en.wikipedia.org/wiki/"+requests.utils.quote(x["title"].replace(" ","_")),"title":x["title"]} for x in data.get("query",{}).get("search",[])]

def assessment(sources, mode="hybrid"):
    hosts={(urlsplit(s["url"]).hostname or "").lower().removeprefix("www.") for s in sources}
    hosts={"wikipedia.org" if h=="wikipedia.org" or h.endswith(".wikipedia.org") else h for h in hosts}
    sufficient=len(sources)>=3 and len(hosts)>=2 and bool(hosts-{"wikipedia.org", ""})
    fallback=not sufficient and mode=="hybrid"
    return {"mode":mode, "source_count":len(sources), "domains":sorted(hosts),
            "sufficient_sources":sufficient, "fallback_used":fallback,
            "status":"mixed_unverified" if fallback and sources else "model_knowledge_unverified" if fallback else "consulted_sources",
            "notice":("Fonti consultabili insufficienti: il racconto usa anche la conoscenza del modello. "
                       "I contenuti non sono verificati integralmente; la revisione automatica non è una verifica storica indipendente.") if fallback else ""}

def collect(topic,urls,config,folder,cancel,log):
    folder.mkdir(exist_ok=True,parents=True);candidates=[{"url":u,"title":""} for u in urls];errors=[]
    for query in [topic+" history museum archive",topic+" fonti storiche musei archivi"]:
        cancel()
        try:candidates+=search(query,config.get("search_url",""))
        except Exception as e:errors.append("Ricerca: "+str(e)[:180])
    if len(candidates)<4:
        try:candidates+=discover_wikipedia(topic)
        except Exception as e:errors.append("Catalogo: "+str(e)[:180])
    seen=set();sources=[];index=0
    while index<len(candidates) and len(sources)<7 and len(seen)<25:
        cancel();candidate=candidates[index];index+=1;url=candidate["url"].split("#")[0]
        if url in seen:continue
        seen.add(url)
        try:
            page=extract(url)
            page["id"]="S"+str(len(sources)+1)
            if "wikipedia.org" in urlsplit(page["url"]).hostname:
                for link in page["links"]:
                    host=urlsplit(link).hostname or ""
                    if any(part in host for part in (".edu",".gov","museum","archive","livius.org","britannica.com","iwm.org","nam.ac.uk")):
                        candidates.append({"url":link,"title":""})
            page.pop("links")
            sources.append(page);write_json(folder/(page["id"]+".json"),page)
            log("Consultata: "+page["title"])
        except Exception as e:errors.append(url+": "+str(e)[:140])
    cancel()
    report=assessment(sources,config.get("research_mode","hybrid"))
    write_json(folder/"acquisition.json",{"errors":errors,"candidates":candidates,"retrieved":len(sources),"research":report})
    if not report["sufficient_sources"] and not report["fallback_used"]:
        raise ValueError("Fonti consultabili insufficienti. Aggiungi link a musei, archivi o testi storici, oppure configura SearXNG; poi riprendi la ricerca.")
    if report["fallback_used"]:log(report["notice"]+" Proseguo con la modalità ibrida.")
    return sources

def evidence(sources):return "\n\n".join("["+s["id"]+"] "+s["title"]+"\n"+s["url"]+"\n"+s["text"][:12000] for s in sources)
