"""Optional delivery controls; absent/default settings keep legacy timing."""
import math

DEFAULT={'style':'original','speed':1.0,'pause_seconds':.18}
STYLES={'original','documentary','calm','engaging','solemn'}


def delivery_options(pack):
    value=pack.get('voice_delivery')
    if not value:return None
    if not isinstance(value,dict):raise ValueError('Impostazioni della lettura non valide.')
    style=value.get('style','original')
    if style not in STYLES:raise ValueError('Stile della lettura non valido.')
    result={'style':style}
    for name,low,high in [('speed',.85,1.15),('pause_seconds',0,.8)]:
        number=value.get(name,DEFAULT[name])
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number) or not low<=number<=high:
            raise ValueError('Parametro della lettura non valido: '+name)
        result[name]=float(number)
    return result if result!=DEFAULT else None
