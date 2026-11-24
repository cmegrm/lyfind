"""Real offline-model checks for the five-clue matcher used by the website."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from lyfind.ai_runtime import LocalAI, CLIP_DIR
from lyfind.proposal_matching import ProposalMatcher

PHOTOS = Path(__file__).parent / 'fixtures/photos'

@unittest.skipUnless((CLIP_DIR/'modules.json').is_file() and os.getenv('ENABLE_AI','1') != '0', 'Local CLIP models are not enabled here.')
class ProductionPhotoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai=LocalAI()
        with patch('socket.socket.connect',side_effect=RuntimeError('Inference must stay offline')):
            if not cls.ai.prepare():
                raise unittest.SkipTest(cls.ai.reason)
        cls.matcher=ProposalMatcher(cls.ai)

    def rows(self, owner='backpack-owner.jpg', found='backpack-same-found.jpg'):
        lost=dict(category='bags',description='dark backpack with zippers',color='black',brand='unknown',place='Library',date_lost='2026-11-07',photo_path=str(PHOTOS/owner))
        item=dict(lost,date_found='2026-11-07',photo_path=str(PHOTOS/found))
        return lost,item

    def test_identical_photo_can_be_strong_and_uses_proposal_weights(self):
        result=self.matcher.evaluate(*self.rows(found='backpack-owner.jpg'))
        self.assertEqual(result['level'],'strong')
        self.assertGreaterEqual(result['total'],60)
        self.assertEqual(result['weights'],dict(description=30,photo=30,color=15,brand=15,place=5,date=5))
        self.assertIn('similarity',result['note'])

    def test_another_angle_scores_above_a_different_bag(self):
        same=self.matcher.evaluate(*self.rows())
        other=self.matcher.evaluate(*self.rows(found='backpack-found.jpg'))
        self.assertGreater(same['contributions']['photo'],other['contributions']['photo'])
        self.assertGreater(same['total'],other['total'])
        self.assertNotEqual(other['level'],'strong')

    def test_different_category_is_hidden(self):
        lost,item=self.rows(found='wallet.jpg')
        item['category']='wallets'
        result=self.matcher.evaluate(lost,item)
        self.assertEqual((result['total'],result['level']),(0,'hidden'))

    def test_without_owner_photo_uses_description_against_csa_photo(self):
        lost,item=self.rows()
        del lost['photo_path']
        with patch('socket.socket.connect',side_effect=RuntimeError('Inference must stay offline')):
            result=self.matcher.evaluate(lost,item)
        self.assertEqual(result['photo_source'],'owner_description')
        self.assertEqual(result['photo_model'],'CLIP')
        self.assertGreaterEqual(result['total'],0)
        self.assertLessEqual(result['total'],100)
