"""Flexible historical outline, backed by the pipeline's common adapter."""
import sys
from pathlib import Path
from pydantic import BaseModel,Field,ConfigDict,model_validator
from .models import GeoPoint

def history_tools(path):
    root=str(Path(path).resolve())
    if root not in sys.path:sys.path.insert(0,root)
    from engine.history_profiles import detect_type
    from engine.history_authoring import outline_prompt,compile_outline
    return detect_type,outline_prompt,compile_outline

class HistoryScene(BaseModel):
    model_config=ConfigDict(extra="allow")
    title:str=Field(max_length=65)
    date:str=Field(max_length=65)
    historical_range:tuple[int,int]
    scene_type:str
    focus:list[str]=Field(default_factory=list,max_length=8)
    event:str=Field(max_length=1400)
    source_ids:list[str]=Field(default_factory=list)
    person_ids:list[str]=Field(default_factory=list)
    event_ids:list[str]=Field(default_factory=list)
    asset_ids:list[str]=Field(default_factory=list)
    territory_ids:list[str]=Field(default_factory=list)
    movements:list[dict]=Field(default_factory=list)

class HistoryOutline(BaseModel):
    model_config=ConfigDict(extra="allow")
    documentary_type:str
    title:str=Field(max_length=120)
    short_title:str=Field(max_length=35)
    description:str
    display_date:str
    historical_period:dict
    analysis:dict
    places:list[GeoPoint]=Field(default_factory=list,max_length=100)
    persons:list[dict]=Field(default_factory=list,max_length=20)
    entities:list[dict]=Field(default_factory=list)
    events:list[dict]=Field(default_factory=list)
    visual_layers:list[dict]=Field(default_factory=list)
    visual_assets:list[dict]=Field(default_factory=list)
    scenes:list[HistoryScene]=Field(min_length=3,max_length=120)
    uncertainties:list[str]=Field(default_factory=list)
    @model_validator(mode="after")
    def references(self):
        ids={p.id for p in self.places}
        if len(ids)!=len(self.places):raise ValueError("Luoghi duplicati")
        for s in self.scenes:
            if not set(s.focus)<=ids:raise ValueError("Luogo della scena inesistente")
        return self
