"""Shared area semantics and camera extents; no inferred historical borders."""
AREA_KINDS={'territory','influence','cultural','linguistic','religious','alliance','contested'}
AREA_LABELS={'territory':'Territorio','influence':'Zona d’influenza','cultural':'Area culturale',
             'linguistic':'Area linguistica','religious':'Area religiosa','alliance':'Alleanza','contested':'Zona contesa'}


def modern_areas(document):
    direction=document.get('visual_direction') or document.get('metadata',{}).get('visual_direction',{})
    return direction.get('territory_style')==2


def selected_layers(document,scene):
    """An empty selection still means empty; continuity is an explicit authoring choice."""
    layers=document.get('visual_layers',[])
    selected=scene.get('territory_ids',[layer['id'] for layer in layers])
    return [layer for layer in layers if layer['id'] in selected and layer.get('kind') in AREA_KINDS]


def year_value(year):return year+1 if year<0 else year

def state_value(state):return state.get('at',year_value(state['year']))


def scene_area_points(document,scene):
    """Fit every state displayed in the scene, including the state inherited from the past."""
    start,end=sorted(year_value(y) for y in scene.get('historical_range',[1,1]));points=[]
    for layer in selected_layers(document,scene):
        states=sorted(layer.get('states',[]),key=state_value)
        prior=[row for row in states if state_value(row)<=start and start<row.get('valid_until',float('inf'))]
        relevant=([prior[-1]] if prior else [])+[row for row in states if start<state_value(row)<=end]
        # A transition may still contain the preceding geometry at the scene start.
        if prior and layer.get('transition_years',0)>0 and start-year_value(prior[-1]['year'])<layer['transition_years'] and len(prior)>1:
            relevant.append(prior[-2])
        points.extend(point for row in relevant for polygon in row.get('polygons',[]) for point in polygon)
    return points


def area_view(points):
    """Keep the whole area between the header and lower cards at 1920 x 1080."""
    import math
    from .history_schema import fit
    view=fit(points)
    if not points:return view
    ys=[math.degrees(math.asinh(math.tan(math.radians(p[1])))) for p in points]
    view[2]=max(view[2],(max(ys)-min(ys))*1920/490)
    if view[2]>170:
        # Wide empires still fit within the real 565px map band; keep a 25px
        # vertical safety margin before rejecting a source geometry outright.
        if (max(ys)-min(ys))*1920/170<=540:view[2]=170
        else:raise ValueError('Suddividere i territori in scene regionali: area troppo ampia per questa carta.')
    cy=(max(ys)+min(ys))/2-65*view[2]/1920
    view[1]=math.degrees(math.atan(math.sinh(math.radians(cy))))
    return view


def area_style(layer,state):
    kind='contested' if state.get('contested') else layer.get('kind','territory')
    schematic=state.get('schematic',layer.get('schematic',True))
    quality=state.get('geometry_status','')
    soft=kind in {'influence','cultural','linguistic','religious'}
    return {'kind':kind,'fill':45 if soft else 72 if kind=='alliance' else 92,
            'width':2 if soft else 3,'dashed':schematic or kind in {'influence','contested'},
            'hatch':kind=='contested','label':AREA_LABELS.get(kind,'Territorio'),
            'boundary':'area indicativa' if schematic else 'ricostruzione da fonte' if quality=='reconstruction' else 'confine da archivio' if quality=='dataset' else 'confine documentato'}


def state_blend(layer,year):
    """Layers at absolute time; smooth frame-level opacity, including appearance/loss."""
    now=year_value(year);states=sorted(layer.get('states',[]),key=state_value)
    active=[row for row in states if state_value(row)<=now]
    if not active:return []
    if now>=active[-1].get('valid_until',float('inf')):return []
    current=active[-1];years=layer.get('transition_years',0)
    if not years:return [(current,1)]
    q=max(0.,min(1.,(now-state_value(current))/years));fade=q*q*q*(q*(q*6-15)+10)
    return ([(active[-2],1-fade)] if len(active)>1 and fade<1 else [])+[(current,fade)]
