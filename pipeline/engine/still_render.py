"""An opt-in, read-only view of a video timeline for document export."""
import copy,importlib,math
from contextlib import contextmanager
from pathlib import Path


def output_path(workspace,value,suffix):
    workspace=Path(workspace).resolve();root=(workspace/'output/presentations').resolve()
    path=Path(value).resolve()
    if not Path(value).is_absolute() or not root.is_relative_to(workspace) or not path.is_relative_to(root) or path==root or path.suffix.lower()!=suffix:
        raise ValueError('Il file deve essere in output/presentations del progetto ('+suffix+').')
    return path


def local_asset(workspace,value):
    path=(Path(workspace)/value).resolve();root=(Path(workspace)/'assets').resolve()
    if not path.is_relative_to(root):raise ValueError('Asset esterno al progetto: '+str(value))
    if not path.is_file():raise ValueError('Asset necessario al PDF non disponibile: '+str(value))
    return path


@contextmanager
def workspace_context(workspace):
    """CLI-only context; never used inside the multithreaded application process."""
    root=Path(workspace).resolve();names=['common','cartography','visuals','atlas','history_visuals','image_insets','history_schema','slide_visuals']
    modules=[importlib.import_module(__package__+'.'+name) for name in names]
    previous=[]
    visuals=modules[2];atlas=modules[3]
    try:
        for module in modules:
            if hasattr(module,'ROOT'):previous.append((module,module.ROOT));module.ROOT=root
        visuals.font.cache_clear();visuals.portrait.cache_clear();atlas.label_image.cache_clear()
        yield
    finally:
        for module,value in previous:module.ROOT=value
        visuals.font.cache_clear();visuals.portrait.cache_clear();atlas.label_image.cache_clear()


def static_cartography(spec,slug,name,cache):
    """Reuse a legacy terrain PNG; any missing deterministic cache stays in the export."""
    import numpy as np
    from PIL import Image
    from . import common,cartography
    key=common.fingerprint([spec,'terrain-v7'])[:14]
    original=common.ROOT/'assets/maps'/slug/f'{name}-{key}.png'
    obj=object.__new__(cartography.Cartography);obj.spec=spec;obj.name=name
    obj.center=np.array(spec['center']);obj.scale=np.array(spec['scale'])
    target=original if original.is_file() else Path(cache)/f'{name}-{key}.png'
    if not target.is_file():target.parent.mkdir(parents=True,exist_ok=True);obj.create(target)
    with Image.open(target) as im:obj.image=np.array(im.convert('RGB'))
    obj.path=target;return obj


def _points(data,scene,at):
    points=[]
    places=data.get('places',{})
    if isinstance(places,list):places={p['id']:p for p in places}
    for ident in scene.get('location_ids',[]) or scene.get('visible_places',[]):
        if ident in places:points.append(places[ident]['pos'])
    if data.get('visual_style') not in ('history','atlas'):
        landmarks={p['id']:p for p in data['maps'][scene['map']].get('landmarks',[])}
        for focus in scene.get('focus',[]):
            if focus.get('place') in landmarks:points.append(landmarks[focus['place']]['pos'])
    for key in ('movements','routes','arrows','frontlines'):
        for item in scene.get(key,[]):points.extend(item.get('points',[]))
    for item in scene.get('units',[]):points.extend(item.get('path') or [item['pos']])
    for edge in scene.get('network',{}).get('edges',[]):
        points.extend(edge.get('points') or [places[edge['from']]['pos'],places[edge['to']]['pos']])
    if data.get('visual_style')=='history':
        from .history_territories import selected_layers,state_blend
        from .history_schema import historical_value
        a,b=scene.get('historical_range',[1,1]);v=historical_value(a)+(historical_value(b)-historical_value(a))*min(1,at/scene['duration'])
        year=v-1 if v<=0 else v
        for layer in selected_layers(data,scene):
            for state,opacity in state_blend(layer,year):
                if opacity:points.extend(p for polygon in state.get('polygons',[]) for p in polygon)
    return [p for p in points if isinstance(p,(list,tuple)) and len(p)==2 and all(isinstance(n,(int,float)) and math.isfinite(n) for n in p)]


def _fit_camera(data,scene,at):
    if data.get('presentation_mode')=='slides':return
    points=_points(data,scene,at)
    if not points:return
    if data.get('visual_style') in ('atlas','history'):
        from .atlas import merc
        left,right,top,bottom=80,1840,195,720
        for inset in scene.get('image_insets',[]):
            layout=inset.get('layout',{});x=layout.get('x',.71)*1920;width=layout.get('width',.25)*1920
            if x>960:right=min(right,x-45)
            else:left=max(left,x+width+45)
        if right-left<500:left,right=80,1840
        xs=[p[0] for p in points];ys=[merc(p[1]) for p in points]
        width=max(.15,(max(xs)-min(xs))*1920/(right-left),(max(ys)-min(ys))*1920/(bottom-top))*1.15
        # Fit may widen the approved map, but a single city must not turn into
        # an extreme, blurry close-up beyond the documentary's own camera.
        authored=min(scene['camera_start'][2],scene['camera_end'][2])
        width=max(width,authored)
        if width>170:raise ValueError('La carta è troppo ampia per una singola pagina leggibile: scegli scene regionali già presenti nel progetto.')
        lon=(max(xs)+min(xs))/2-((left+right)/2-960)*width/1920
        my=(max(ys)+min(ys))/2+((top+bottom)/2-540)*width/1920
        view=[lon,math.degrees(math.atan(math.sinh(math.radians(my)))),width]
    else:
        sx,sy=data['maps'][scene['map']]['scale'];xs=[p[0] for p in points];ys=[p[1] for p in points]
        z=min(1250/max(.000001,(max(xs)-min(xs))*sx),540/max(.000001,(max(ys)-min(ys))*sy))/.99
        z=min(z,scene['camera_end'][2])
        view=[(max(xs)+min(xs))/2+40/(sx*z),(max(ys)+min(ys))/2-12/(sy*z),z]
    scene['camera_start']=view;scene['camera_end']=view[:]
    scene['camera_keys']=[{'at':0,'view':view[:]},{'at':1,'view':view[:]}]


def prepare_scene(data,original,page):
    scene=copy.deepcopy(original);scene['_still']=True;cue=page['cue_index'];phase=page['phase']
    for key in ('movements','routes','arrows','units','commanders','callouts','focus','frontlines'):
        if key not in scene:continue
        kept=[]
        for item in scene[key]:
            if not isinstance(item,dict):continue
            if item.get('cue',0)>cue or (item.get('until') is not None and item['until']<=cue):continue
            item['_still_progress']=0 if phase=='start' and item.get('cue',0)==cue else 1
            kept.append(item)
        scene[key]=kept
    if scene.get('network'):
        scene['network']['edges']=[{**m,'_still_progress':0 if phase=='start' and m.get('cue',0)==cue else 1}
            for m in scene['network'].get('edges',[]) if m.get('cue',0)<=cue]
    scene['sfx']=[]
    scene['image_insets']=[item for item in scene.get('image_insets',[])
        if item.get('cue',0)==cue and item.get('asset_id')==page.get('inset_asset_id')]
    # These adjustments affect composition only; dates, coordinates and text stay intact.
    _fit_camera(data,scene,page['time'])
    return scene


class StillRenderer:
    def __init__(self,timeline,workspace,cache):
        from .visuals import Visuals
        self.workspace=Path(workspace).resolve();self.data=copy.deepcopy(timeline)
        self.data['_still']=True;self.data['_still_cache']=str(cache)
        # Render the state that applies at a date, rather than a decorative blend.
        for layer in self.data.get('visual_layers',[]):layer['transition_years']=0
        scenes=self.data['scenes']
        used_media={item.get('asset_id') for scene in scenes for item in scene.get('image_insets',[])}
        used_media.update(scene.get('background_asset_id') for scene in scenes)
        used_art={ident for scene in scenes for ident in scene.get('asset_ids',[])}-set(self.data.get('disabled_visual_asset_ids',[]))
        for item in self.data.get('user_media',[]):
            if item.get('id') in used_media:local_asset(self.workspace,item['path'])
        for item in self.data.get('visual_assets',[]):
            if item.get('id') in used_art:local_asset(self.workspace,item['path'])
        for item in self.data.get('commanders',{}).values():
            if item.get('portrait'):local_asset(self.workspace,item['portrait'])
        self.scenes={s['id']:s for s in self.data['scenes']};self.visual=Visuals(self.data)

    def frame(self,page):
        return self.visual.frame(prepare_scene(self.data,self.scenes[page['scene_id']],page),page['time'])
