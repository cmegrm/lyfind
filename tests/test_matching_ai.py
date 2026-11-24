"""Five-clue scoring, offline loading and migration regression checks."""
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from lyfind.matching import AIMatchingService, ClipAdapter, HybridAdapter, ScoreWeights, TypedDetailsMatchingService, settle_ambiguity
from lyfind.ai_runtime import LocalAI
import test_workflow as fixtures


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.report=dict(category='bags',description='green canvas backpack',color='green',brand='Acme',place='Library',date_lost='2026-01-01',identifying_marks='yellow star keychain')
        self.item=dict(self.report,description='green backpack with brass zips',date_found='2026-01-02',photo_path='received.png',private_details='yellow star keychain inside')
        self.adapter=MagicMock()
        self.adapter.embed_text.side_effect=lambda s: [1,0]
        self.adapter.embed_image.side_effect=lambda s: [1,0]
        self.ai=AIMatchingService(self.adapter)

    def test_every_signal_is_reported_and_adds_up(self):
        d=self.ai.evaluate(dict(self.report,photo_path='owner.png'),self.item)
        self.assertEqual(set(d['signals']),{'photo','text_image','description','category','color','brand','place','date'})
        self.assertEqual(d['level'],'strong');self.assertGreaterEqual(d['total'],80)
        self.assertAlmostEqual(sum(d['contributions'].values()),d['raw_total'],delta=0.1)
        self.assertEqual(len(d['reasons']),8);self.assertTrue(all({'key','label','text','points','max','ok','state'}<=set(r) for r in d['reasons']))
        self.assertEqual(d['photo_source'],'owner_photo')

    def test_owner_without_a_photo_still_uses_words_against_the_item_photo(self):
        d=self.ai.evaluate(self.report,self.item)
        self.assertIsNone(d['signals']['photo']);self.assertIsNotNone(d['signals']['text_image'])
        self.assertEqual(d['photo_source'],'owner_description')
        self.assertEqual(next(r for r in d['reasons'] if r['key']=='photo')['state'],'unknown')

    def test_category_filter_runs_before_any_model_inference(self):
        self.assertEqual(self.ai.compare(self.report,dict(self.item,category='keys')),(0.0,'hidden'))
        self.adapter.embed_text.assert_not_called();self.adapter.embed_image.assert_not_called()

    def test_weights_are_configurable_and_reject_invalid_totals(self):
        w=ScoreWeights(photo=50,text_image=10,description=10,category=5,color=10,brand=5,place=5,date=5)
        self.assertEqual(AIMatchingService(self.adapter,w).evaluate(self.report,self.item)['weights']['photo'],50)
        for kwargs in [dict(photo=40),dict(photo=float('nan')),dict(photo=-1,text_image=51),dict(photo=100,text_image=0,description=0,category=0,color=0,brand=0,place=0,date=0)]:
            with self.assertRaises(ValueError):ScoreWeights(**{**dict(photo=36,text_image=14,description=14,category=4,color=8,brand=6,place=10,date=8),**kwargs})

    def test_typed_details_alone_never_reach_strong(self):
        d=TypedDetailsMatchingService().evaluate(self.report,self.item)
        self.assertIsNone(d['signals']['photo']);self.assertIsNone(d['signals']['text_image'])
        self.assertEqual(d['level'],'possible');self.assertLessEqual(d['total'],79.0);self.assertGreaterEqual(d['total'],60)
        self.assertIn('Photo AI was not used',d['note'])

    def test_photos_that_do_not_look_alike_block_strong(self):
        self.adapter.embed_image.side_effect=lambda s: [0,1] if s=='owner.png' else [1,0]
        self.adapter.embed_text.side_effect=lambda s: [0,1]
        d=self.ai.evaluate(dict(self.report,photo_path='owner.png'),self.item)
        self.assertEqual(d['level'],'hidden');self.assertLess(d['total'],60)
        self.assertTrue(any('not of the same item' in cap for cap in d['caps']))

    def test_same_item_from_another_angle_is_possible_not_hidden(self):
        # DINOv2 raw ~0.61 (same shoes, different viewpoint) used to vanish below the Strong floor.
        self.adapter.embed_image.side_effect=lambda s: [0.61, 0.792] if s=='owner.png' else [1, 0]
        d=self.ai.evaluate(dict(self.report,photo_path='owner.png'),self.item)
        self.assertEqual(d['level'],'possible')
        self.assertGreaterEqual(d['total'],60)
        self.assertGreater(d['signals']['photo'], 0)
        self.assertTrue(any('different angles' in cap for cap in d['caps']))
        photo = next(r for r in d['reasons'] if r['key']=='photo')
        self.assertIn('another angle', photo['text'])
        self.assertNotIn('not of the same item', photo['text'])

    def test_impossible_and_far_apart_dates(self):
        self.assertEqual(self.ai.compare(self.report,dict(self.item,date_found='2025-12-31')),(0.0,'hidden'))
        score,level=self.ai.compare(self.report,dict(self.item,date_found='2026-03-20'))
        self.assertEqual(level,'hidden');self.assertLess(score,60)
        near=self.ai.compare(self.report,dict(self.item,date_found='2026-01-20'))
        self.assertLessEqual(near[0],74)

    def test_colour_and_brand_contradictions_cap_the_score(self):
        for change in (dict(color='red'),dict(brand='Other')):
            score,level=self.ai.compare(self.report,dict(self.item,**change))
            self.assertLessEqual(score,69);self.assertNotEqual(level,'strong')
        score,_=self.ai.compare(dict(self.report,brand='unknown'),self.item)  # unknown is missing evidence, not a mismatch
        self.assertGreater(score,69)

    def test_empty_descriptions_and_missing_fields_do_not_crash(self):
        bare=dict(category='bags',description='',color='',brand='',place='',date_lost='2026-01-01')
        for service in (self.ai,TypedDetailsMatchingService()):
            info=service.evaluate(bare,dict(bare,date_found='2026-01-02',private_details='',photo_path='received.png'))
            self.assertIn(info['level'],('hidden','possible'));self.assertIsNone(info['signals']['description'])

    def test_look_alike_wallets_rank_the_right_one_first(self):
        base=dict(category='wallets',color='black',brand='unknown',place='Gym',date_lost='2026-01-01',description='black wallet',identifying_marks='red round sticker')
        right=dict(base,date_found='2026-01-02',private_details='red round sticker on the back');wrong=dict(right,private_details='blue tape on the front')
        typed=TypedDetailsMatchingService()
        self.assertGreater(typed.evaluate(base,right)['total'],typed.evaluate(base,wrong)['total'])

    def test_owner_only_marks_outrank_a_generic_description(self):
        lost=dict(category='bags',description='black backpack',color='black',brand='unknown',place='Gym',date_lost='2026-01-01',identifying_marks='yellow star keychain')
        right=dict(lost,date_found='2026-01-02',private_details='yellow star keychain inside')
        wrong=dict(lost,date_found='2026-01-02',description='black backpack',private_details='plain empty bag')
        typed=TypedDetailsMatchingService()
        self.assertGreater(typed.evaluate(lost,right)['signals']['description'],typed.evaluate(lost,wrong)['signals']['description'])

    def test_two_look_alikes_cannot_both_be_strong(self):
        a=self.ai.evaluate(dict(self.report,photo_path='owner.png'),self.item);b=dict(a)
        entries=[(1,1,a),(1,2,b)]
        settle_ambiguity(entries)
        self.assertEqual((a['level'],b['level']),('possible','possible'));self.assertLess(a['total'],80);self.assertTrue(a['ambiguous'])
        lone=self.ai.evaluate(dict(self.report,photo_path='owner.png'),self.item);settle_ambiguity([(1,1,lone)])
        self.assertEqual(lone['level'],'strong')

    def test_photo_match_uses_the_instance_encoder_not_clip(self):
        instance=MagicMock(); clip=MagicMock()
        instance.embed_image.side_effect=lambda p: [1.0, 0.0] if 'owner' in p else [0.05, 0.998]
        clip.embed_image.side_effect=lambda p: [1.0, 0.0]
        clip.embed_text.side_effect=lambda s: [1.0, 0.0]
        d=AIMatchingService(HybridAdapter(instance, clip)).evaluate(dict(self.report,photo_path='owner.png'),self.item)
        self.assertEqual(d['method'],'dino_clip_ai')
        self.assertLess(d['signals']['photo'],0.5)
        self.assertEqual(d['level'],'hidden')
        instance.embed_image.assert_called()
        clip.embed_image.assert_called()

    def test_clip_text_is_shortened_before_encoding(self):
        encoder=MagicMock();encoder.encode.side_effect=[ValueError('too long'),[.5,.5]]
        self.assertEqual(ClipAdapter(encoder).embed_text('x'*400),[.5,.5])
        self.assertLessEqual(len(encoder.encode.call_args_list[0].args[0]),200)

    def test_local_loader_missing_model_does_not_import_or_download(self):
        with tempfile.TemporaryDirectory() as folder, patch('lyfind.ai_runtime.CLIP_DIR',Path(folder)),patch('lyfind.ai_runtime.DINO_DIR',Path(folder)),patch('lyfind.ai_runtime.MODEL_DIR',Path(folder)),patch.dict(os.environ,{'ENABLE_AI':'1'}):
            engine=LocalAI()
            self.assertIsNone(engine.prepare())
            self.assertFalse(engine.status()['ready'])
            self.assertIn('not prepared',engine.reason)

    def test_prepared_loader_forbids_remote_code_and_network_resolution(self):
        with tempfile.TemporaryDirectory() as folder:
            clip=Path(folder,'clip'); clip.mkdir(); (clip/'modules.json').write_text('[]')
            missing=Path(folder,'no-dino')
            lib=types.ModuleType('sentence_transformers');lib.SentenceTransformer=MagicMock()
            torch=types.ModuleType('torch');torch.set_num_threads=MagicMock()
            with patch('lyfind.ai_runtime.CLIP_DIR',clip),patch('lyfind.ai_runtime.MODEL_DIR',clip),patch('lyfind.ai_runtime.DINO_DIR',missing),patch.dict('sys.modules',{'sentence_transformers':lib,'torch':torch}),patch.dict(os.environ,{'ENABLE_AI':'1'}):
                engine=LocalAI();self.assertIsNotNone(engine.prepare())
                kwargs=lib.SentenceTransformer.call_args.kwargs
                self.assertTrue(kwargs['local_files_only']);self.assertFalse(kwargs['trust_remote_code'])
                self.assertEqual(os.environ['HF_HUB_OFFLINE'],'1')
                engine.prepare();lib.SentenceTransformer.assert_called_once()
                self.assertEqual(engine.status()['method'],'clip_ai')


class ScorePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.fx=fixtures.WorkflowTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)

    def test_saved_breakdown_is_visible_only_to_admin(self):
        self.fx.report();self.fx.item()
        admin=self.fx.service.dashboard(self.fx.admin)
        self.assertEqual(admin['matches'][0]['score_details']['weights']['photo'],ScoreWeights().photo)
        self.assertIn('matching_status',admin)
        owner=self.fx.service.dashboard(self.fx.student)
        self.assertNotIn('matching_status',owner)
        self.assertEqual(owner['matches'],[])
        self.fx.service.decide_match(self.fx.admin,admin['matches'][0]['id'],True)
        for match in self.fx.service.dashboard(self.fx.student)['matches']:
            self.assertNotIn('score_details',match);self.assertNotIn('score',match)

    def test_rerun_removes_only_unreviewed_below_threshold_suggestions(self):
        report=self.fx.report();item=self.fx.item()
        with self.fx.db.connect() as c:c.execute("UPDATE items SET color='red',brand='Other',place='Other' WHERE id=?",(item['id'],))
        self.fx.service.run_matching(self.fx.admin)
        self.assertEqual(self.fx.service.dashboard(self.fx.admin)['matches'],[])

    def test_legacy_schema_migrates_without_losing_records(self):
        self.fx.report();self.fx.item()
        with self.fx.db.connect() as c:
            c.execute('ALTER TABLE matches DROP COLUMN score_details')
            before=c.execute('SELECT COUNT(*) FROM matches').fetchone()[0]
        self.fx.db.initialize();self.fx.db.initialize()
        with self.fx.db.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM matches').fetchone()[0],before)
            self.assertEqual(json.loads(c.execute('SELECT score_details FROM matches').fetchone()[0]),{})


if __name__=='__main__':unittest.main()
