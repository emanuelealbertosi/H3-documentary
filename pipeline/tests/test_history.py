"""Regression gates for compatibility and semantic historical rendering."""
import copy,unittest,hashlib
from pathlib import Path
from engine.common import ROOT,read_json,validate_pack,write_json
from engine.history_schema import adapt,validate_document,estimate_timeline,interpolate_year,enrich_timeline
from engine.history_profiles import detect_type,PROFILES,choose_scene
from engine.history_visuals import HistoryVisuals,territory_state

class HistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.doc=read_json(ROOT/'documentaries/rinascimento/documentary.json')
    def test_legacy_contract_returns_same_object(self):
        for slug in ['waterloo','stalingrado','annibale']:
            p=read_json(ROOT/f'battles/{slug}/battle.json');before=copy.deepcopy(p)
            self.assertIs(validate_pack(p),p);self.assertEqual(p,before)
    def test_types(self):
        cases={'Battaglia di Waterloo':'battle','Guerra dei trent’anni':'war','Espansione dell’Impero Romano':'territorial_expansion','Diffusione del Rinascimento':'cultural_movement','Migrazioni barbariche':'migration','Via della Seta':'trade_network','Biografia di Napoleone':'biography','Espansione dell’Islam':'religious_expansion','Guerra Fredda':'political_history','Rivoluzione francese':'revolution','Diffusione della rivoluzione industriale':'economic_history','Invenzione del telegrafo':'technology_history','Esplorazioni oceaniche':'exploration','Storia della famiglia':'general_history'}
        for topic,kind in cases.items():self.assertEqual(detect_type(topic),kind,topic)
        self.assertEqual(len(PROFILES),14)
    def test_select_visual_content(self):
        self.assertEqual(choose_scene({'chart':{'kind':'bar'}},'general_history'),'data_visualization')
        self.assertEqual(choose_scene({'asset_ids':['x']},'general_history'),'artwork')
        self.assertEqual(choose_scene({'person_ids':['x']},'biography'),'person_intro')
    def test_no_year_zero(self):
        self.assertEqual(interpolate_year(-1,1,0),-1)
        self.assertEqual(interpolate_year(-1,1,1),1)
        self.assertNotIn(0,[interpolate_year(-10,10,i/100) for i in range(101)])
    def test_bad_sources_coordinates_and_identifiers(self):
        for mutate in [lambda d:d['scenes'][0].update(sources=['unknown']),lambda d:d['locations'][0].update(pos=[300,90]),lambda d:d['persons'][0].update(id='../escape')]:
            d=copy.deepcopy(self.doc);mutate(d)
            with self.assertRaises(ValueError):validate_document(d)
    def test_missing_quantities_are_rejected(self):
        d=copy.deepcopy(self.doc);d['scenes'][0]['chart']={'kind':'bar','sources':['R1'],'values':[{'label':'Unknown','value':None}]}
        with self.assertRaises(ValueError):validate_document(d)
    def test_scene_event_narration_sync(self):
        d=estimate_timeline(self.doc);s=d['scenes'][2];e=next(e for e in d['events'] if e['id']=='goldsmith')
        self.assertAlmostEqual(e['timestamp_video'],s['start']+s['cues'][0]['start'],places=6)
        self.assertEqual(d['timing_status'],'estimated');self.assertEqual(len(d['narration']),len(d['scenes']))
    def test_persistent_territory_and_loss(self):
        layer={'states':[{'year':-10,'polygons':[[[0,0],[1,0],[1,1]]]},{'year':10,'polygons':[]}]}
        self.assertIsNone(territory_state(layer,-20)[0])
        self.assertEqual(len(territory_state(layer,1)[0]['polygons']),1)
        self.assertEqual(territory_state(layer,11)[0]['polygons'],[])
    def test_all_examples_have_distinct_languages(self):
        report={}
        for p in (ROOT/'documentaries').glob('*/documentary.json'):
            raw=read_json(p);d=validate_pack(raw)
            self.assertEqual(d['voice_speaker'],'if_sara');self.assertEqual(d['width'],1920)
            report[d['slug']]=sorted({s['scene_type'] for s in d['scenes']})
            if d['documentary_type']=='migration':
                self.assertTrue(all(m['semantic']=='migration' for s in d['scenes'] for m in s.get('movements',[])))
        self.assertGreaterEqual(len(report),5);self.assertIn('artwork',report['rinascimento']);self.assertIn('territorial_change',report['impero-romano']);self.assertIn('person_intro',report['napoleone-biografia'])
        write_json(ROOT/'tests/output/history-modes.json',report)
    def test_out_of_order_render_is_deterministic(self):
        d=estimate_timeline(self.doc);v=HistoryVisuals(d);s=d['scenes'][5];t=s['duration']*.6
        a=v.frame(s,t).tobytes();v.frame(d['scenes'][0],2);b=v.frame(s,t).tobytes();self.assertEqual(a,b)
    def test_chart_types_render_with_negative_values(self):
        d=estimate_timeline(self.doc);s=d['scenes'][0]
        out=ROOT/'tests/output/components';out.mkdir(parents=True,exist_ok=True)
        for kind in ['bar','line','comparison']:
            s['scene_type']='data_visualization';s['chart']={'kind':kind,'title':'DATI SINTETICI DI TEST — NON STORICI','unit':'unità','sources':['R1'],'note':'Fixture tecnica, non dati storici','values':[{'label':'A','value':-5,'x':1},{'label':'B','value':7,'x':2},{'label':'C','value':10,'x':5}]}
            v=HistoryVisuals(d);im=v.frame(s,5);self.assertEqual(im.size,(1920,1080));im.save(out/(kind+'.jpg'))

if __name__=='__main__':unittest.main()
