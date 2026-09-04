import json
from app.source_coordinates import ground_coordinates


def test_full_local_document_corrects_named_location_and_route(tmp_path):
    folder=tmp_path/'assets/documents/doc1';folder.mkdir(parents=True)
    text='''# Registro delle coordinate
| Località | Punto | Latitudine decimale | Longitudine decimale |
| Itaca in vista | Ithaki, Grecia | 38.367000 | 20.717000 |
| Porto di Forco, Itaca | Baia di Dexa | 38.370090 | 20.701680 |
| Eolia | Lipari | 38.467000 | 14.957000 |
'''
    (folder/'original.md').write_text(text,encoding='utf-8')
    (folder/'record.json').write_text(json.dumps({'title':'Dossier del viaggio','original':'original.md'}),encoding='utf-8')
    (folder/'chunks.json').write_text(json.dumps([{'page':1,'text':text}]),encoding='utf-8')
    document={'schema_version':2,'locations':[{'id':'itaca','name':'Itaca','pos':[12.435,38.115]}],
              'scenes':[{'id':'01','focus':['itaca'],'movements':[{'from':'eolia','to':'itaca','points':[[14.957,38.467],[12.435,38.115]]}]}]}
    grounded,changes=ground_coordinates(document,tmp_path)
    assert changes and changes[0]['id']=='itaca'
    assert grounded['locations'][0]['pos']==[20.70168,38.37009]
    assert grounded['scenes'][0]['movements'][0]['points'][-1]==[20.70168,38.37009]
    assert grounded['scenes'][0]['camera_end'][0]>17
    assert document['locations'][0]['pos']==[12.435,38.115]


def test_no_coordinate_change_without_an_explicit_named_source_row(tmp_path):
    folder=tmp_path/'assets/documents/doc1';folder.mkdir(parents=True)
    text='Un luogo diverso ha coordinate 38.367000, 20.717000.'
    (folder/'record.json').write_text(json.dumps({'title':'Nota','original':'original.pdf'}),encoding='utf-8')
    (folder/'chunks.json').write_text(json.dumps([{'page':1,'text':text}]),encoding='utf-8')
    document={'schema_version':2,'locations':[{'id':'itaca','name':'Itaca','pos':[12.435,38.115]}],'scenes':[]}
    grounded,changes=ground_coordinates(document,tmp_path)
    assert not changes and grounded==document
