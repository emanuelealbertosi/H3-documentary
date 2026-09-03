from pathlib import Path
import json
from .store import settings
def library():
    root=Path(settings()["pipeline_path"]);items=[]
    for packfile in sorted([*(root/"battles").glob("*/battle.json"),*(root/"documentaries").glob("*/documentary.json")]):
        try:
            p=json.loads(packfile.read_text(encoding="utf-8"));movie=(root/p.get("output",f'output/{p["slug"]}_documentario_1080p.mp4')).resolve()
            if not movie.is_relative_to(root.resolve()) or not movie.exists():continue
            slug=p["slug"]
            if slug!=packfile.parent.name:continue
            timeline=root/"build"/slug/"timeline.json"
            t=json.loads(timeline.read_text(encoding="utf-8")) if timeline.exists() else p
            thumb=root/"output"/(slug+"_copertina.jpg")
            if not thumb.exists():thumb=root/"output"/p.get("verification_dir","verification")/"opening.jpg"
            items.append({"id":slug,"title":p["title"],"duration":t.get("duration",p.get("target_minutes",0)*60),
              "movie":str(movie),"thumbnail":str(thumb) if thumb.exists() else None,"origin":"Pipeline originale",
              "bytes":movie.stat().st_size,"fps":p.get("fps",24)})
        except (OSError,ValueError,KeyError):continue
    return items
