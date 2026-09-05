from pydantic import BaseModel, Field, ConfigDict, StringConstraints, field_validator, model_validator
from typing import Literal,Annotated
from urllib.parse import urlsplit, urlunsplit
import math,re

class Settings(BaseModel):
    provider: Literal["openai","lmstudio","vllm","ollama"] = "lmstudio"
    base_url: str = "http://localhost:1234/v1"
    model: str = ""
    api_key: str | None = None
    clear_api_key: bool = False
    timeout: int = Field(180, ge=10, le=1800)
    max_tokens: int = Field(8192, ge=512, le=65536)
    context_length: int = Field(0, ge=0, le=262144)
    temperature: float | None = Field(0.25, ge=0, le=2)
    token_parameter: Literal["max_tokens","max_completion_tokens"] = "max_tokens"
    reasoning_mode: Literal["server","on","off"] = "server"
    json_mode: bool = False
    vision: bool = False
    pipeline_path: str = ""
    render_jobs: int = Field(2, ge=1, le=4)
    fps: Literal[24,30] = 30
    request_limit: int = Field(100, ge=10, le=500)
    search_url: str = ""
    research_mode: Literal["hybrid", "strict"] = "hybrid"
    boundary_usage: Literal["commercial", "education_nc"] = "commercial"
    instructions: str = Field("", max_length=12000)
    tts_engine: Literal["kokoro","chatterbox","api"] = "kokoro"
    tts_profile_id: str = Field("", pattern=r"^$|^[a-f0-9]{24}$")
    tts_reference_id: str = Field("", pattern=r"^$|^[a-f0-9]{24}$")
    chatterbox_threads: int = Field(4, ge=1, le=8)

    @field_validator("base_url")
    @classmethod
    def endpoint(cls, value):
        value=value.strip().rstrip("/")
        p=urlsplit(value)
        if p.scheme not in ("http","https") or not p.hostname or p.username or p.password or p.query or p.fragment:
            raise ValueError("Usa un indirizzo HTTP/HTTPS senza credenziali o parametri nella URL.")
        path=p.path.rstrip("/")
        for suffix in ("/chat/completions","/models"):
            if path.endswith(suffix): path=path[:-len(suffix)]
        if path in ("","/api"): path="/v1"
        return urlunsplit((p.scheme,p.netloc,path,"",""))

class ProjectRequest(BaseModel):
    topic: str = Field(min_length=4, max_length=300)
    minutes: int = Field(10, ge=2, le=60)
    notes: str = Field("", max_length=5000)
    source_urls: list[str] = Field(default_factory=list,max_length=12)
    start: bool = True
    use_media: bool = True
    review_visuals: bool = False
    use_documents: bool = True
    document_ids: list[str] = Field(default_factory=list, max_length=24)
    documentary_type: Literal["auto","battle","war","territorial_expansion","migration","cultural_movement","religious_expansion","trade_network","exploration","political_history","revolution","economic_history","technology_history","biography","general_history"] = "auto"
    tts_engine: Literal["default","kokoro","chatterbox","api"] = "default"
    tts_profile_id: str = Field("", pattern=r"^$|^[a-f0-9]{24}$")
    tts_reference_id: str = Field("", pattern=r"^$|^[a-f0-9]{24}$")

    @field_validator("document_ids")
    @classmethod
    def document_identifiers(cls, values):
        if any(not re.fullmatch(r"[a-f0-9]{24}", value) for value in values):
            raise ValueError("Identificatore documento non valido.")
        return list(dict.fromkeys(values))

class VoiceChoice(BaseModel):
    tts_engine: Literal["kokoro","chatterbox","api"]
    tts_profile_id: str = Field("", pattern=r"^$|^[a-f0-9]{24}$")
    tts_reference_id: str = Field("", pattern=r"^$|^[a-f0-9]{24}$")

class TTSProfile(BaseModel):
    id: str = Field("", pattern=r"^$|^[a-f0-9]{24}$")
    name: str = Field(min_length=2,max_length=80)
    provider: Literal["openai","higgs","elevenlabs","google"] = "openai"
    base_url: str
    model: str = Field("",max_length=160)
    voice: str = Field("",max_length=180)
    language: str = Field("it-IT",min_length=2,max_length=30)
    response_format: Literal["mp3","wav","flac","ogg"] = "mp3"
    timeout: int = Field(180,ge=10,le=1800)
    temperature: float = Field(1.0,ge=0.0,le=2.0)
    top_p: float = Field(0.95,ge=0.0,le=1.0)
    top_k: int = Field(50,ge=0,le=1000)
    seed: int = Field(-1,ge=-1,le=2147483647)
    max_new_tokens: int = Field(2048,ge=64,le=32768)
    api_key: str | None = Field(None,max_length=24000)
    clear_api_key: bool = False

    @field_validator("base_url")
    @classmethod
    def tts_endpoint(cls,value):
        value=value.strip().rstrip("/")
        p=urlsplit(value)
        if p.scheme not in ("http","https") or not p.hostname or p.username or p.password or p.query or p.fragment:
            raise ValueError("Usa un indirizzo HTTP/HTTPS senza credenziali o parametri nella URL.")
        path=p.path.rstrip("/")
        for suffix in ("/audio/speech","/audio/voice-clone","/text:synthesize","/status","/model/load","/model/unload"):
            if path.endswith(suffix):path=path[:-len(suffix)]
        return urlunsplit((p.scheme,p.netloc,path,"",""))

class HiggsVoiceUpload(BaseModel):
    reference_id: str = Field(pattern=r"^[a-f0-9]{24}$")
    voice_id: str = Field(min_length=1,max_length=80,pattern=r"^[A-Za-z0-9_-]+$")
    overwrite: bool = False

class TTSTestRequest(TTSProfile):
    reference_id: str = Field("",pattern=r"^$|^[a-f0-9]{24}$")

class GeoPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_-]{1,50}$")
    name: str = Field(min_length=1,max_length=65)
    pos: tuple[float,float] = Field(description='Coordinate geografiche [LONGITUDINE, LATITUDINE], in questo ordine. Non latitudine/longitudine.')
    uncertain: bool = False
    note: str = Field("",max_length=500)
    @field_validator("pos")
    @classmethod
    def position(cls,v):
        if not all(math.isfinite(x) for x in v) or not (-179 <= v[0] <=179 and -78 <= v[1] <=78):
            raise ValueError("Coordinate fuori dalla carta supportata.")
        return v

class Commander(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,50}$")
    name: str
    role: str
    wikipedia_page: str

class Route(BaseModel):
    side: Literal["a","b"] = "a"
    points: list[tuple[float,float]] = Field(min_length=2,max_length=30)
    uncertain: bool = True
    kind: Literal["attack","advance","retreat","reinforcement","march"] = "advance"
    label: str = Field("",max_length=34)
    unit_kind: Literal["infantry","cavalry","artillery"] = "infantry"
    @field_validator("points")
    @classmethod
    def coordinates(cls,points):
        for p in points: GeoPoint(id="p",name="p",pos=p)
        return points

class OutlineScene(BaseModel):
    title: str = Field(max_length=65)
    date: str = Field(max_length=65)
    focus: list[str] = Field(min_length=1,max_length=7,description='Solo ID di places. Non temi, eventi, eserciti o nomi di persone. Deve identificare cosa inquadrare sulla mappa.')
    event: str = Field(max_length=1400)
    source_ids: list[str] = Field(default_factory=list,max_length=8)
    routes: list[Route] = Field(default_factory=list,max_length=4)
    commander_ids: list[str] = Field(default_factory=list,max_length=2,description='Solo ID di commanders, mai nomi liberi. [] se nessun comandante è pertinente.')

class Outline(BaseModel):
    title: str = Field(max_length=120)
    short_title: str = Field(max_length=35)
    description: str = Field(max_length=1000)
    display_date: str = Field(max_length=65)
    factions: tuple[str,str]
    places: list[GeoPoint] = Field(min_length=2,max_length=70)
    commanders: list[Commander] = Field(default_factory=list,max_length=7)
    river_names: list[str] = Field(default_factory=list,max_length=15)
    scenes: list[OutlineScene] = Field(min_length=3,max_length=120)
    uncertainties: list[str] = Field(default_factory=list,max_length=15)
    @model_validator(mode='before')
    @classmethod
    def normalize(cls,value):
        from .outline_normalization import battle_references
        return battle_references(value)
    @model_validator(mode="after")
    def links(self):
        ids={p.id for p in self.places}; cs={p.id for p in self.commanders}
        if len(ids)!=len(self.places) or len(cs)!=len(self.commanders): raise ValueError("Identificatori duplicati.")
        for i,s in enumerate(self.scenes):
            for field,allowed in [('focus',ids),('commander_ids',cs)]:
                missing=set(getattr(s,field))-allowed
                if missing:raise ValueError(f"Scena {i+1} ({s.title}), {field}: {sorted(missing)} non sono ID validi. ID ammessi: {sorted(allowed)}. focus contiene luoghi, non temi o eventi; commander_ids contiene ID di comandanti. Correggi i riferimenti senza inventare coordinate.")
        return self

NarrationText=Annotated[str,StringConstraints(strip_whitespace=True,min_length=120,max_length=1200)]

class NarrationScene(BaseModel):
    index: int
    lines: list[NarrationText] = Field(min_length=2,max_length=2,description='Esattamente due paragrafi narrati completi; ogni paragrafo deve avere sostanza documentaristica, non essere una didascalia breve.')
    fact: str = Field(min_length=10,max_length=140)
    kicker: str = Field(min_length=5,max_length=75)

class NarrationBatch(BaseModel):
    scenes: list[NarrationScene] = Field(min_length=1,max_length=4)

class Review(BaseModel):
    acceptable: bool
    issues: list[str] = Field(default_factory=list,max_length=20)
    source_ids: list[str] = Field(default_factory=list)
    summary: str
