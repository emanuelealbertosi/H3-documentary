"""Opt-in authoring test against an already installed, free localhost model.

Never reads application credentials/settings or calls a paid remote endpoint.
Produces a plan only, without research, narration, TTS or video.
"""
import argparse,json,sys,time
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--url',default='http://localhost:1234/v1')
    p.add_argument('--topic',default='Il ritorno di Ulisse da Troia a Itaca nella tradizione letteraria');p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if urlsplit(args.url).hostname not in ('localhost','127.0.0.1','::1'):p.error('This opt-in test permits localhost only.')
    from app.models import Settings
    from app.llm import LLM
    from app.general import history_tools
    from app.research import assessment
    from app.research_policy import author_system
    from app.runner import SYSTEM
    from app.outline_builder import build_history_outline
    from app.store import write_json
    from engine.history_profiles import detect_type
    folder=args.output.resolve();folder.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    def cancel():
        if time.monotonic()-started>600:raise RuntimeError('Local smoke test time budget exceeded; completed checkpoints preserved.')
    def log(message):print(message,flush=True)
    def audit(data):write_json(folder/'audit'/f'{time.time_ns()}-{data["call"]:03}.json',data)
    cfg=Settings(base_url=args.url,model=args.model,timeout=180,max_tokens=8192,request_limit=18).model_dump()
    research=assessment([]);llm=LLM(cfg,cancel,audit);llm.progress=log
    try:
        kind=detect_type(args.topic)
        outline=build_history_outline(llm,author_system(SYSTEM,research),{'topic':args.topic,'minutes':2,'notes':'Esplicita il carattere letterario del racconto.'},
                                     kind,[],research,folder,history_tools(str(ROOT/'pipeline'))[1],log,cancel)
        write_json(folder/'outline.json',outline)
        result={'passed':True,'scenes':len(outline['scenes']),'calls':llm.calls,'seconds':round(time.monotonic()-started,2),
                'narrative_basis':outline.get('narrative_basis'),'scope':'Real local model; structural validation only, not independent historical verification or video rendering.'}
    except Exception as error:
        result={'passed':False,'calls':llm.calls,'seconds':round(time.monotonic()-started,2),'error':str(error)}
        write_json(folder/'result.json',result);raise
    write_json(folder/'result.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
