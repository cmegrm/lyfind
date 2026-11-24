"""Instance matching on real photos: the same bag can match; a second bag cannot, even if the words match."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lyfind.ai_runtime import DINO_DIR, LocalAI
from lyfind.database import Database
from lyfind.matching import AIMatchingService, calculate_match_score, cosine, ScoreWeights
from lyfind.services import Service
from lyfind.users import User

PHOTOS = Path(__file__).resolve().parent / "fixtures" / "photos"
DINO_READY = (DINO_DIR / "config.json").is_file()
try:
    import transformers  # noqa: F401
except ImportError:
    DINO_READY = False


@unittest.skipUnless(DINO_READY and os.getenv('RUN_EXPERIMENTAL_MATCHING_TESTS') == '1', "Historical eight-clue experiment. Production photo checks are in test_proposal_photos.py.")
class RealPhotoMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["HF_HUB_OFFLINE"] = "1"
        cls.ai = LocalAI()
        if not cls.ai.prepare():
            raise unittest.SkipTest(cls.ai.reason)
        cls.svc = AIMatchingService(cls.ai.adapter, ScoreWeights(), cls.ai.calibration)
        cls.owner = str(PHOTOS / "backpack-owner.jpg")
        cls.same = str(PHOTOS / "backpack-same-found.jpg")
        cls.other_bag = str(PHOTOS / "backpack-found.jpg")
        cls.wallet = str(PHOTOS / "wallet.jpg")

    def _lost(self, photo):
        return dict(category="bags", description="dark backpack with zippers", color="black", brand="unknown",
                    place="Academic Resource Center (Library)", date_lost="2026-11-07", identifying_marks="charm on zipper",
                    photo_path=photo)

    def _found(self, photo, **extra):
        row = dict(category="bags", description="dark backpack with zippers", color="black", brand="unknown",
                   place="Academic Resource Center (Library)", date_found="2026-11-07", private_details="charm on zipper",
                   photo_path=photo)
        row.update(extra)
        return row

    def test_same_bag_beats_a_different_bag_and_a_wallet(self):
        owner = self.ai.adapter.embed_image(self.owner)
        same = cosine(owner, self.ai.adapter.embed_image(self.same))
        other = cosine(owner, self.ai.adapter.embed_image(self.other_bag))
        wallet = cosine(owner, self.ai.adapter.embed_image(self.wallet))
        self.assertGreater(same, other + 0.15)
        self.assertGreater(other, wallet)
        self.assertLess(other, 0.76)

    def test_same_bag_can_be_strong_a_second_bag_cannot(self):
        true = self.svc.evaluate(self._lost(self.owner), self._found(self.same))
        lookalike = self.svc.evaluate(self._lost(self.owner), self._found(self.other_bag))
        self.assertEqual(true["level"], "strong")
        self.assertGreaterEqual(true["total"], 80)
        self.assertNotEqual(lookalike["level"], "strong")
        self.assertLess(lookalike["signals"]["photo"], 0.5)

    def test_matching_words_cannot_save_two_different_bags(self):
        """Same typed details, different backpack photos: never Strong. Possible is for staff to compare."""
        result = self.svc.evaluate(self._lost(self.owner), self._found(self.other_bag))
        self.assertNotEqual(result["level"], "strong")
        self.assertLess(result["signals"]["photo"], 0.5)
        self.assertTrue(any("same kind of item" in cap or "not of the same item" in cap for cap in result["caps"]))
        self.assertLessEqual(result["total"], 69)

    def test_same_shoes_from_two_phone_photos_are_suggested(self):
        owner = PHOTOS / "shoe-owner.jpg"
        found = PHOTOS / "shoe-found.jpg"
        if not owner.is_file() or not found.is_file():
            self.skipTest("Shoe photo fixtures are not in tests/fixtures/photos")
        lost = dict(category="other", description="shoes anta kai black", color="Black", brand="anta",
                    place="Gymnasium", date_lost="2026-11-09", identifying_marks="dirty and had scratches",
                    photo_path=str(owner))
        item = dict(category="other", description="Black shoes the brand is Anta", color="Black", brand="Anta",
                    place="Gymnasium", date_found="2026-11-09", private_details="", photo_path=str(found))
        result = self.svc.evaluate(lost, item)
        self.assertIn(result["level"], ("possible", "strong"))
        self.assertGreaterEqual(result["total"], 60)
        self.assertNotEqual(result["level"], "hidden")
        photo = next(row for row in result["reasons"] if row["key"] == "photo")
        self.assertNotIn("not of the same item", photo["text"])
        self.assertGreater(result["signals"]["photo"], 0)
        other = self.svc.evaluate(self._lost(self.owner), self._found(self.other_bag))
        self.assertGreater(result["total"], other["total"])
        card = calculate_match_score(lost, item, self.svc)
        self.assertEqual(card["photoLooksAlike"]["max"], 36.0)
        self.assertEqual(card["wordsFitPhoto"]["max"], 14.0)
        self.assertGreaterEqual(card["overallPercentage"], 60)

    def test_isolated_views_raise_same_shoe_cosine_without_collapsing_a_wallet(self):
        owner = PHOTOS / "shoe-owner.jpg"
        found = PHOTOS / "shoe-found.jpg"
        if not owner.is_file() or not found.is_file():
            self.skipTest("Shoe photo fixtures are not in tests/fixtures/photos")
        adapter = self.ai.adapter
        full = cosine(adapter.embed_image(str(owner)), adapter.embed_image(str(found)))
        views_o = adapter.embed_image_views(str(owner))
        views_f = adapter.embed_image_views(str(found))
        best = max(cosine(a, b) for a in views_o for b in views_f)
        self.assertGreaterEqual(best, full)
        wallet = cosine(adapter.embed_image(str(owner)), adapter.embed_image(self.wallet))
        self.assertLess(wallet, 0.45)

    def test_different_real_phones_are_never_strong(self):
        phones = [PHOTOS / name for name in ("phone-black.jpg", "phone-blue.jpg", "phone-circle.jpg", "phone-clear.jpg")]
        if any(not path.is_file() for path in phones):
            self.skipTest("Phone photo fixtures are not in tests/fixtures/photos")
        for owner in phones:
            for found in phones:
                if owner == found:
                    continue
                lost = dict(category="electronics", description="smartphone in a case", color="black",
                            brand="unknown", place="Canteen / Food park", date_lost="2026-11-10",
                            identifying_marks="", photo_path=str(owner))
                item = dict(category="electronics", description="smartphone in a case", color="black",
                            brand="unknown", place="Canteen / Food park", date_found="2026-11-10",
                            private_details="", photo_path=str(found))
                result = self.svc.evaluate(lost, item)
                self.assertNotEqual(result["level"], "strong", f"{owner.name} vs {found.name} was {result['total']}")
                self.assertLess(result["similarity"]["photo"], 0.88)
                self.assertTrue(any("same kind of item" in cap for cap in result["caps"]),
                                f"{owner.name} vs {found.name} scored {result['similarity']['photo']}")
                self.assertLessEqual(result["total"], 69)

    def test_tricky_same_shoe_photos_stay_visible(self):
        owner = PHOTOS / "shoe-owner.jpg"
        found = PHOTOS / "shoe-found.jpg"
        if not owner.is_file() or not found.is_file():
            self.skipTest("Shoe photo fixtures are not in tests/fixtures/photos")
        with Image.open(found) as picture:
            src = picture.convert("RGB")
        variants = {
            "flip": ImageOps.mirror(src),
            "tilt": src.rotate(12, expand=True, fillcolor=(230, 230, 228)),
            "dark": ImageEnhance.Brightness(src).enhance(0.7),
            "bright": ImageEnhance.Brightness(src).enhance(1.25),
            "tight": src.crop((int(src.width * 0.06), int(src.height * 0.16), int(src.width * 0.96), int(src.height * 0.94))),
        }
        lost = dict(category="other", description="black dress shoe", color="Black", brand="unknown",
                    place="Gymnasium", date_lost="2026-11-09", identifying_marks="", photo_path=str(owner))
        with tempfile.TemporaryDirectory() as folder:
            for name, image in variants.items():
                path = Path(folder) / f"{name}.jpg"
                image.save(path, quality=88)
                item = dict(category="other", description="black dress shoe", color="Black", brand="unknown",
                            place="Gymnasium", date_found="2026-11-09", private_details="", photo_path=str(path))
                result = self.svc.evaluate(lost, item)
                self.assertIn(result["level"], ("possible", "strong"), name)
                self.assertGreaterEqual(result["total"], 60, name)
                self.assertNotEqual(result["level"], "hidden", name)
                photo = next(row for row in result["reasons"] if row["key"] == "photo")
                self.assertNotIn("not of the same item", photo["text"], name)

    def test_a_dull_owner_photo_still_meets_a_clear_office_photo(self):
        owner = PHOTOS / "shoe-owner.jpg"
        found = PHOTOS / "shoe-found.jpg"
        if not owner.is_file() or not found.is_file():
            self.skipTest("Shoe photo fixtures are not in tests/fixtures/photos")
        with Image.open(owner) as picture:
            dull = ImageEnhance.Brightness(picture.convert("RGB")).enhance(0.42)
            dull = ImageEnhance.Contrast(dull).enhance(0.7)
        lost = dict(category="other", description="black dress shoe", color="Black", brand="unknown",
                    place="Gymnasium", date_lost="2026-11-09", identifying_marks="", photo_path="")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "dull-owner.jpg"
            dull.save(path, quality=85)
            lost["photo_path"] = str(path)
            item = dict(category="other", description="black dress shoe", color="Black", brand="unknown",
                        place="Gymnasium", date_found="2026-11-09", private_details="", photo_path=str(found))
            result = self.svc.evaluate(lost, item)
            self.assertIn(result["level"], ("possible", "strong"))
            self.assertGreaterEqual(result["total"], 60)
            photo = next(row for row in result["reasons"] if row["key"] == "photo")
            self.assertIn("darker", photo["text"])
            self.assertNotIn("not of the same item", photo["text"])
            other = self.svc.evaluate(self._lost(self.owner), self._found(self.other_bag))
            self.assertGreater(result["total"], other["total"])

    def test_matching_process_suggests_the_same_shoe_and_hides_a_wallet(self):
        owner = PHOTOS / "shoe-owner.jpg"
        found = PHOTOS / "shoe-found.jpg"
        if not owner.is_file() or not found.is_file():
            self.skipTest("Shoe photo fixtures are not in tests/fixtures/photos")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = Database(Path(temp.name) / "test.sqlite3")
        db.initialize()
        service = Service(db, temp.name, matcher=self.svc)

        def person(role, name):
            with db.connect() as conn:
                cursor = conn.execute("INSERT INTO users(first_name,email,role) VALUES(?,?,?)",
                                      (name, name.replace(" ", ".").lower() + "@example.test", role))
                row = conn.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
            return User.from_row(row)

        def store(src, kind, owner_id):
            dest = Path(temp.name) / Path(src).name
            shutil.copy(src, dest)
            with db.connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO uploads(owner_id,claim_id,kind,path,mime,original_name) VALUES(?,?,?,?,?,?)",
                    (owner_id, None, kind, dest.name, "image/jpeg", dest.name))
            return cursor.lastrowid

        admin = person("admin", "CSA Tester")
        student = person("student", "Student One")
        lost_photo = store(owner, "report_photo", student.id)
        shoe_photo = store(found, "item_photo", admin.id)
        wallet_photo = store(PHOTOS / "wallet.jpg", "item_photo", admin.id)
        report = service.create_lost_report(student, dict(
            category="other", description="black dress shoe", color="Black", brand="unknown",
            place="Gymnasium", date_lost="2026-11-09", identifying_marks="scuffed toe", photo_id=lost_photo))
        shoe = service.receive_item(admin, dict(
            category="other", description="black dress shoe", color="Black", brand="unknown",
            place="Gymnasium", date_found="2026-11-09", private_details="scuffed toe", photo_id=shoe_photo))
        wallet = service.receive_item(admin, dict(
            category="other", description="brown wallet", color="Brown", brand="unknown",
            place="Gymnasium", date_found="2026-11-09", private_details="cards inside", photo_id=wallet_photo))
        result = service.run_matching(admin)
        pairs = {(row["report_id"], row["item_id"]): row for row in result["suggestions"]}
        self.assertIn((report["id"], shoe["id"]), pairs)
        self.assertNotIn((report["id"], wallet["id"]), pairs)
        self.assertGreaterEqual(pairs[(report["id"], shoe["id"])]["score"], 60)
        self.assertIn(pairs[(report["id"], shoe["id"])]["level"], ("possible", "strong"))
        with db.connect() as conn:
            match_id = conn.execute("SELECT id FROM matches WHERE report_id=? AND item_id=?",
                                    (report["id"], shoe["id"])).fetchone()[0]
        confirmed = service.decide_match(admin, match_id, True)
        self.assertEqual(confirmed["status"], "confirmed")
