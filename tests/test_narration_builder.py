from app.models import NarrationBatch
from app.narration_builder import build_narration


def paragraph(label,count=42):return ' '.join([label]+['parola']*(count-1))


def scene(index,count=42):
    return {'index':index,'lines':[paragraph('Primo',count),paragraph('Secondo',count)],'fact':'Cartello storico verificabile.','kicker':'Passaggio della battaglia'}


def outline():
    return {'title':'Waterloo','scenes':[{'title':f'Scena {i+1}','date':'1815','event':'Sintesi breve.','source_ids':[]} for i in range(3)]}


def test_narration_schema_rejects_caption_length_lines():
    import pytest
    with pytest.raises(ValueError):NarrationBatch.model_validate({'scenes':[scene(0,10)]})


def test_short_group_falls_back_to_checkpointed_single_scenes(tmp_path):
    logs=[]
    class Model:
        calls=0
        def structured(self,system,prompt,schema):
            self.calls+=1
            marker=prompt.split('indici esatti ')[1].split('.')[0]
            indices=[int(x) for x in marker.strip('[]').split(',') if x.strip()]
            count=18 if len(indices)>1 else 42
            return {'scenes':[scene(i,count) for i in indices]}
    model=Model();project={'minutes':1.5}
    result=build_narration(model,'Sistema',outline(),project,[],tmp_path,logs.append,lambda:None)
    assert len(result)==3 and all(75<=len(' '.join(row['lines']).split())<=100 for row in result)
    assert model.calls==5  # two failed group attempts, then three valid single scenes
    assert all((tmp_path/f'narration-scene-{i:03}.json').exists() for i in range(3))
    assert (tmp_path/'narration-000.json').exists()
    # Resume uses the completed group and does not call the model.
    class Forbidden:
        def structured(self,*args):raise AssertionError('model called')
    assert build_narration(Forbidden(),'Sistema',outline(),project,[],tmp_path,logs.append,lambda:None)==result
