"""Sign-up validation, the shared password rulebook, photo uploads and CLIP (skipped without the package)."""
import base64
import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lyfind import passwords
import test_auth_http as http_base
from lyfind.seed import sample_image

ROOT = Path(__file__).resolve().parents[1]


class PasswordRulebookTests(unittest.TestCase):
    def test_checklist_matches_each_rule(self):
        good = passwords.checklist("BlueKettle42!", "Jamie Lee", "jamie@example.org")
        self.assertEqual(good, {"length": True, "identity": True, "letter": True, "mix": True})
        self.assertFalse(passwords.checklist("short1", "A B", "a@b.co")["length"])
        self.assertFalse(passwords.checklist("jamielee-2026!", "Jamie Lee", "x@y.co")["identity"])
        self.assertFalse(passwords.checklist("maria.santos77", "Someone", "maria.santos@example.org")["identity"])
        self.assertFalse(passwords.checklist("1234567890123", "", "")["letter"])
        self.assertFalse(passwords.checklist("onlylettershere", "", "")["mix"])

    def test_spaces_cannot_replace_a_required_symbol(self):
        self.assertIsNotNone(passwords.first_problem("correct horse 1", "Sam", "sam@example.org"))

    def test_spaces_do_not_count_toward_the_length(self):
        self.assertEqual(passwords.counted_length("abcd efg "), 7)
        self.assertIn("Spaces do not count", passwords.first_problem("abc defg", "", ""))
        self.assertIsNone(passwords.first_problem("AbcdEfg1!", "", ""))

    def test_first_problem_is_plain_language_and_none_when_ok(self):
        self.assertIn("8 to 128", passwords.first_problem("abc", "", ""))
        self.assertIn("name or email", passwords.first_problem("samsmith-pass 1", "Sam Smith", "q@example.org"))
        self.assertIsNone(passwords.first_problem("Tr1ck-y pass!", "", ""))

    def test_password_is_eight_to_128_characters(self):
        self.assertIn("8 to 128", passwords.first_problem("short1a", "", ""))
        self.assertIn("128", passwords.first_problem("A1!"+"a"*126, "", ""))
        self.assertIsNone(passwords.first_problem("StaffKey42!", "", ""))


class SignUpTests(unittest.TestCase):
    setUp = http_base.HTTPTests.setUp
    tearDown = http_base.HTTPTests.tearDown
    call = http_base.HTTPTests.call
    login = http_base.HTTPTests.login

    def register(self, **overrides):
        body = {"email": "jamie.new@example.org"}
        body.update(overrides)
        return self.call("/api/auth/register", body)

    def finish(self, email, code, **overrides):
        status, result = self.call("/api/auth/register/verify", {"email": email, "code": code})
        if status != 200:
            return status, result
        body = {"email": email, "setup_token": result["data"]["setup_token"],
                "first_name": "Jamie", "last_name": "Lee", "password": "BlueKettle42!", "confirm": "BlueKettle42!"}
        body.update(overrides)
        status, result = self.call("/api/auth/register/finish", body)
        if status == 200:
            self.csrf = result["data"]["csrf_token"]
        return status, result

    def test_success_needs_the_code_then_lands_as_a_guest(self):
        status, result = self.register()
        self.assertEqual(status, 200, result)
        self.assertNotIn("user", result["data"])
        self.assertEqual(self.call("/api/dashboard")[0], 401)
        status, result = self.finish("jamie.new@example.org", result["data"]["demo_code"])
        self.assertEqual(status, 200, result)
        self.assertEqual(result["data"]["user"]["role"], "guest")
        self.assertEqual(self.call("/api/dashboard")[0], 200)

    def test_email_problems_are_reported_on_the_first_step(self):
        for email in ("bad-email", "demo.guest@example.test"):
            with self.subTest(email=email):
                status, result = self.register(email=email)
                self.assertEqual(status, 400, result)
                self.assertIn("email", result["fields"])

    def test_name_and_password_problems_are_reported_after_the_code(self):
        cases = [
            ("short1@example.org", {"password": "short", "confirm": "short"}, "password"),
            ("confirm1@example.org", {"confirm": "something else 42"}, "confirm"),
            ("noname1@example.org", {"first_name": "", "last_name": ""}, "first_name"),
            ("ident1@example.org", {"password": "jamielee-2026!", "confirm": "jamielee-2026!"}, "password"),
            ("letters1@example.org", {"password": "onlyletterspass", "confirm": "onlyletterspass"}, "password"),
            ("digits1@example.org", {"password": "1234567890123", "confirm": "1234567890123"}, "password"),
        ]
        for email, overrides, field in cases:
            with self.subTest(email=email):
                status, started = self.register(email=email)
                self.assertEqual(status, 200, started)
                status, result = self.finish(email, started["data"]["demo_code"], **overrides)
                self.assertEqual(status, 400, result)
                self.assertIn(field, result["fields"])

    def test_several_problems_come_back_together(self):
        status, result = self.register(email="nope")
        self.assertEqual(status, 400)
        self.assertEqual(set(result["fields"]), {"email"})
        status, started = self.register(email="many@example.org")
        status, result = self.finish("many@example.org", started["data"]["demo_code"], password="abc", confirm="xyz")
        self.assertEqual(status, 400)
        self.assertEqual(set(result["fields"]), {"password", "confirm"})

    def test_duplicate_email_ignores_case_and_spacing(self):
        status, result = self.register()
        self.assertEqual(status, 200)
        status, result = self.finish("jamie.new@example.org", result["data"]["demo_code"])
        self.assertEqual(status, 200, result)
        status, result = self.register(email="  JAMIE.NEW@example.org ")
        self.assertEqual(status, 400)
        self.assertIn("already exists", result["fields"]["email"])

    def test_school_email_is_pointed_to_school_email_sign_in(self):
        status, result = self.register(email="maria@university.edu.ph")
        self.assertEqual(status, 400)
        self.assertIn("school email", result["fields"]["email"])
        self.assertNotIn("Microsoft", result["fields"]["email"])

    def test_confirm_is_optional_for_api_clients_but_checked_when_sent(self):
        status, started = self.call("/api/auth/register", {"email": "nc@example.org"})
        self.assertEqual(status, 200, started)
        status, checked = self.call("/api/auth/register/verify", {"email": "nc@example.org", "code": started["data"]["demo_code"]})
        status, done = self.call("/api/auth/register/finish", {
            "email": "nc@example.org", "setup_token": checked["data"]["setup_token"],
            "first_name": "No", "last_name": "Confirm", "password": "BlueKettle42!",
        })
        self.assertEqual(status, 200, done)

    def test_staff_password_requires_strong_characters(self):
        self.login("admin")
        weak = {"action": "create", "name": "New Staff", "email": "new.staff@example.org", "password": "short1a", "role": "admin"}
        status, result = self.call("/api/staff/save", weak)
        self.assertEqual(status, 400)
        self.assertEqual(result["fields"]["password"], result["error"])
        status, result = self.call("/api/staff/save", {**weak, "password": "abcdefghij12345678901"})
        self.assertEqual(status, 400)
        status, result = self.call("/api/staff/save", {**weak, "password": "CampusKey42!"})
        self.assertEqual(status, 200, result)


class PhotoUploadTests(unittest.TestCase):
    setUp = http_base.HTTPTests.setUp
    tearDown = http_base.HTTPTests.tearDown
    call = http_base.HTTPTests.call
    login = http_base.HTTPTests.login

    def upload(self, raw, name="photo.jpg"):
        return self.call("/api/uploads", {"kind": "report_photo", "name": name, "content": base64.b64encode(raw).decode()})

    def test_png_and_jpeg_are_accepted(self):
        self.login("student")
        self.assertEqual(self.upload(sample_image(), "a.png")[0], 200)
        jpeg = (ROOT / "demo_images" / "wallet-found.jpg").read_bytes()
        self.assertEqual(self.upload(jpeg, "b.jpg")[0], 200)

    def test_iphone_style_jpegs_are_accepted(self):
        """Phone camera JPEGs (EXIF, progressive, Live Photo MPO, .JPG) used to fail Pillow verify/format."""
        self.login("student")
        from io import BytesIO
        from PIL import Image

        def jpeg_bytes(**save):
            buf = BytesIO()
            Image.new("RGB", (24, 24), (12, 24, 36)).save(buf, format="JPEG", quality=90, **save)
            return buf.getvalue()

        status, result = self.upload(jpeg_bytes(), "IMG_6535.JPG")
        self.assertEqual(status, 200, result)

        progressive = jpeg_bytes(progressive=True)
        status, result = self.upload(progressive, "IMG_6535.JPG")
        self.assertEqual(status, 200, result)

        exif = Image.new("RGB", (24, 24), (40, 40, 40)).getexif()
        exif[271] = "Apple"
        exif[272] = "iPhone 14"
        status, result = self.upload(jpeg_bytes(exif=exif.tobytes()), "photo.jpg")
        self.assertEqual(status, 200, result)

        mpo_buf = BytesIO()
        first = Image.new("RGB", (16, 16), (9, 9, 9))
        second = Image.new("RGB", (16, 16), (1, 2, 3))
        first.save(mpo_buf, format="MPO", save_all=True, append_images=[second])
        mpo = mpo_buf.getvalue()
        self.assertTrue(mpo.startswith(b"\xff\xd8\xff"))
        with Image.open(BytesIO(mpo)) as image:
            self.assertEqual(image.format, "MPO")
        status, result = self.upload(mpo, "IMG_6535.JPG")
        self.assertEqual(status, 200, result)

    def test_other_files_and_oversize_photos_are_refused_plainly(self):
        self.login("student")
        status, result = self.upload(b"just text, not an image", "notes.jpg")
        self.assertEqual(status, 400)
        self.assertIn("JPEG, PNG, or WebP", result["error"])
        heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32
        status, result = self.upload(heic, "IMG_6535.JPG")
        self.assertEqual(status, 400)
        self.assertIn("HEIC", result["error"])
        status, result = self.upload(b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 10))
        self.assertIn(status, (400, 413))
        self.assertIn("5 MB", result["error"])

    def test_upload_needs_a_signed_in_user(self):
        self.assertEqual(self.upload(sample_image(), "a.png")[0], 401)


CLIP_READY = bool(importlib.util.find_spec("sentence_transformers") and importlib.util.find_spec("PIL") and (ROOT / "models" / "clip-ViT-B-32").exists())


class SeedAndReasonTests(unittest.TestCase):
    """Work with or without CLIP: the fallback must still explain itself."""
    setUp = http_base.HTTPTests.setUp
    tearDown = http_base.HTTPTests.tearDown
    call = http_base.HTTPTests.call
    login = http_base.HTTPTests.login

    def test_seed_has_images_and_matches_with_reasons(self):
        self.login("admin")
        status, result = self.call("/api/dashboard")
        self.assertEqual(status, 200)
        data = result["data"]
        self.assertTrue(data["matches"], "seed should leave a suggested match")
        match = data["matches"][0]
        explanation = match["score_details"] if isinstance(match["score_details"], dict) else json.loads(match["score_details"])
        self.assertIn(explanation["method"], ("dino_clip_ai", "dino_ai", "clip_ai", "typed_details"))
        self.assertTrue(explanation["reasons"])
        self.assertTrue(all({"key", "label", "points", "max"} <= set(item) for item in explanation["reasons"]))
        self.assertIn("matching_status", data)

    def test_without_ai_the_note_says_it_is_not_an_ai_score(self):
        from lyfind.matching import TypedDetailsMatchingService
        report = dict(category="bags", description="green backpack", color="green", brand="", place="Library", date_lost="2026-01-01")
        item = dict(report, date_found="2026-01-02")
        explanation = TypedDetailsMatchingService().explain(report, item)
        self.assertIn("Photo AI was not used", explanation["note"])
        self.assertLess(explanation["total"], 80)
        self.assertTrue(explanation["reasons"])


@unittest.skipUnless(CLIP_READY, "CLIP is not installed here. Run python3 setup_ai.py to enable it.")
class ClipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from lyfind.ai_runtime import LocalAI
        cls.adapter = LocalAI().prepare()
        if cls.adapter is None:
            raise unittest.SkipTest("CLIP is installed but could not load.")

    def test_same_photo_scores_higher_than_a_different_one(self):
        adapter = self.adapter
        owner = adapter.embed_image(str(ROOT / "demo_images" / "backpack-owner.jpg"))
        same = adapter.embed_image(str(ROOT / "demo_images" / "backpack-found.jpg"))
        other = adapter.embed_image(str(ROOT / "demo_images" / "phone-found.jpg"))

        def cosine(a, b):
            return sum(x * y for x, y in zip(a, b)) / ((sum(x * x for x in a) ** .5) * (sum(y * y for y in b) ** .5))
        self.assertGreater(cosine(owner, same), cosine(owner, other))

    def test_text_and_image_embeddings_share_a_size(self):
        from lyfind.matching import clip_image_vec
        adapter = self.adapter
        text = adapter.embed_text("a dark green backpack")
        if text is None:
            self.skipTest("CLIP text encoder is not loaded.")
        image = clip_image_vec(adapter, str(ROOT / "demo_images" / "backpack-found.jpg"))
        self.assertEqual(len(text), len(image))


if __name__ == "__main__":
    unittest.main()
