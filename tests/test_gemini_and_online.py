"""Tests for Gemini AI matching, owner-only marks, match caching, online hosting, Forgot Password, and WSGI."""
import io
import json
import os
import sqlite3
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lyfind.ai_runtime import LocalAI
from lyfind.auth import AuthService
from lyfind.configuration import check_configuration, smtp_password
from lyfind.database import Database, SCHEMA_VERSION
from lyfind.gemini_matching import DEFAULT_GEMINI_MODEL, GeminiClientAdapter, GeminiMatchingService, resolve_gemini_model
from lyfind.proposal_matching import ProposalMatcher
from lyfind.seed import sample_image, seed_demo
from lyfind.services import Service
from lyfind.users import User
from lyfind.web import Application, client_ip, host_is_allowed
from matching import AIMatchingService
from wsgi import make_wsgi_app


class GeminiMatchingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.photo_a = self.root / "owner.png"
        self.photo_b = self.root / "office.png"
        self.photo_a.write_bytes(sample_image())
        self.photo_b.write_bytes(sample_image())

    def test_resolve_model_replaces_deprecated_models(self):
        self.assertEqual(resolve_gemini_model(""), DEFAULT_GEMINI_MODEL)
        self.assertEqual(resolve_gemini_model("gemini-2.5-flash"), DEFAULT_GEMINI_MODEL)
        self.assertEqual(resolve_gemini_model("gemini-2.0-flash"), DEFAULT_GEMINI_MODEL)
        self.assertEqual(resolve_gemini_model("gemini-1.5-pro"), DEFAULT_GEMINI_MODEL)
        self.assertEqual(resolve_gemini_model("gemini-3.5-flash-lite"), "gemini-3.5-flash-lite")

    def test_gemini_adapter_calls_interactions_create_with_store_false_and_schema(self):
        client = MagicMock()
        client.interactions.create.return_value = types.SimpleNamespace(
            output_text=json.dumps({
                "description_similarity": 0.92,
                "photo_similarity": 0.90,
                "same_physical_item": True,
                "summary": "Both records describe the same green backpack with a yellow star keychain.",
            })
        )
        adapter = GeminiClientAdapter(api_key="test-key", model="gemini-4-hydrogen", client=client)
        matcher = GeminiMatchingService(adapter)
        report = dict(
            category="bags", description="green backpack", identifying_marks="yellow star keychain",
            color="Green", brand="Campus", place="Library", date_lost="2026-11-01", photo_path=str(self.photo_a),
        )
        item = dict(
            category="bags", description="green canvas backpack", private_details="yellow star keychain inside",
            color="Green", brand="Campus", place="Library", date_found="2026-11-02", photo_path=str(self.photo_b),
        )
        score, level, details = matcher.evaluate(report, item)
        self.assertEqual(level, "strong")
        self.assertGreaterEqual(score, 90)
        self.assertEqual(details["method"], "gemini_ai")
        self.assertEqual(details["photo_source"], "owner_photo")
        self.assertIn("yellow star keychain", details["statement"])
        kwargs = client.interactions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gemini-4-hydrogen")
        self.assertFalse(kwargs["store"])
        self.assertEqual(kwargs["response_format"]["mime_type"], "application/json")
        image_blocks = [part for part in kwargs["input"] if part["type"] == "image"]
        self.assertEqual(len(image_blocks), 2)
        text_block = kwargs["input"][0]["text"]
        self.assertIn("yellow star keychain", text_block)

    def test_gemini_lookalike_photo_cannot_reach_strong(self):
        client = MagicMock()
        client.interactions.create.return_value = types.SimpleNamespace(
            output_text=json.dumps({
                "description_similarity": 0.85,
                "photo_similarity": 0.55,
                "same_physical_item": False,
                "summary": "Both are black backpacks, but strap stitching and zippers differ.",
            })
        )
        adapter = GeminiClientAdapter(api_key="test-key", client=client)
        matcher = GeminiMatchingService(adapter)
        report = dict(category="bags", description="black backpack", color="Black", brand="Campus", place="Library", date_lost="2026-11-01", photo_path=str(self.photo_a))
        item = dict(report, date_found="2026-11-02", photo_path=str(self.photo_b))
        score, level, details = matcher.evaluate(report, item)
        self.assertEqual(level, "possible")
        self.assertIsNotNone(details["strong_caveat"])

    def test_category_mismatch_never_calls_gemini(self):
        client = MagicMock()
        adapter = GeminiClientAdapter(api_key="test-key", client=client)
        matcher = GeminiMatchingService(adapter)
        score, level, _ = matcher.evaluate(
            dict(category="bags", description="bag", date_lost="2026-11-01"),
            dict(category="phones", description="phone", date_found="2026-11-02"),
        )
        self.assertEqual((score, level), (0.0, "hidden"))
        client.interactions.create.assert_not_called()

    def test_local_ai_uses_gemini_when_api_key_is_set(self):
        fake_client = MagicMock()
        with patch.dict(os.environ, {"ENABLE_AI": "1", "AI_PROVIDER": "auto", "GEMINI_API_KEY": "secret-key-test", "GEMINI_MODEL": "gemini-4-hydrogen"}), \
                patch("google.genai.Client", return_value=fake_client):
            ai = LocalAI()
            adapter = ai.prepare()
            self.assertIsNotNone(adapter)
            status = ai.status()
            self.assertEqual(status["method"], "gemini_ai")
            self.assertFalse(status["local_only"])
            self.assertIn("Gemini", status["model"])
            matcher = ProposalMatcher(ai)
            self.assertEqual(matcher.method, "gemini_ai")


class OwnerMarksAndCachingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = Database(self.root / "cache.sqlite3")
        self.db.initialize()
        seed_demo(self.db, self.root / "uploads")

    def test_live_clip_matcher_includes_owner_marks_and_private_details(self):
        seen_texts = []
        adapter = MagicMock()
        adapter.embed_text.side_effect = lambda text: (seen_texts.append(text), [1.0, 0.0])[1]
        matcher = AIMatchingService(adapter)
        report = dict(category="bags", description="black bag", identifying_marks="blue bunny tag", color="Black", brand="unknown", place="Gym", date_lost="2026-11-01")
        item = dict(category="bags", description="black bag", private_details="blue bunny tag zipped inside", color="Black", brand="unknown", place="Gym", date_found="2026-11-02")
        matcher.explain(report, item)
        self.assertTrue(any("blue bunny tag" in t for t in seen_texts))
        self.assertTrue(any("zipped inside" in t for t in seen_texts))

    def test_match_cache_prevents_duplicate_gemini_calls(self):
        fake_client = MagicMock()
        fake_client.interactions.create.return_value = types.SimpleNamespace(
            output_text=json.dumps({
                "description_similarity": 0.90,
                "photo_similarity": 0.88,
                "same_physical_item": True,
                "summary": "Matches description and photo.",
            })
        )
        service = Service(self.db, upload_dir=self.root / "uploads")
        service.ai.adapter = GeminiClientAdapter(api_key="test-key", client=fake_client)
        service.ai._method = "gemini_ai"
        service.ai._model_name = "Gemini (gemini-4-hydrogen)"
        service.ai._local_only = False
        service.ai.attempted = True

        with self.db.connect() as conn:
            admin = User.from_row(conn.execute("SELECT * FROM users WHERE role='admin' LIMIT 1").fetchone())

        first = service.run_matching(admin)
        first_calls = fake_client.interactions.create.call_count
        self.assertGreater(first_calls, 0)
        self.assertGreater(first["count"], 0)

        # Running matching again with unchanged items/reports must use SQLite cache (0 new API calls)
        second = service.run_matching(admin)
        self.assertEqual(fake_client.interactions.create.call_count, first_calls)
        self.assertEqual(second["count"], first["count"])
        with self.db.connect() as conn:
            cached_rows = conn.execute("SELECT COUNT(*) FROM ai_match_cache WHERE method='gemini_ai'").fetchone()[0]
            self.assertEqual(cached_rows, first_calls)


class OnlineHostingAndSecurityTests(unittest.TestCase):
    def test_allowed_hosts_unblocks_configured_public_domains(self):
        with patch.dict(os.environ, {"ALLOWED_HOSTS": "", "RENDER_EXTERNAL_HOSTNAME": "", "RAILWAY_PUBLIC_DOMAIN": "", "PYTHONANYWHERE_DOMAIN": ""}):
            self.assertFalse(host_is_allowed("lyfind.pythonanywhere.com", "0.0.0.0"))
        with patch.dict(os.environ, {"ALLOWED_HOSTS": "lyfind.pythonanywhere.com,.onrender.com"}):
            self.assertTrue(host_is_allowed("lyfind.pythonanywhere.com", "0.0.0.0"))
            self.assertTrue(host_is_allowed("school-app.onrender.com:443", "0.0.0.0"))
            self.assertFalse(host_is_allowed("evil.example", "0.0.0.0"))

    def test_trust_proxy_extracts_real_client_ip_only_when_enabled(self):
        handler = types.SimpleNamespace(
            client_address=("10.0.0.5", 12345),
            headers={"X-Forwarded-For": "203.0.113.42, 10.0.0.5"},
        )
        with patch.dict(os.environ, {"TRUST_PROXY": "0"}):
            self.assertEqual(client_ip(handler), "10.0.0.5")
        with patch.dict(os.environ, {"TRUST_PROXY": "1"}):
            self.assertEqual(client_ip(handler), "203.0.113.42")

    def test_configuration_checks_gemini_and_smtp_without_leaking_secrets(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "super-secret-gemini-key", "SMTP_PASSWORD": "super-secret-smtp"}):
            self.assertEqual(smtp_password(), "super-secret-smtp")
            status = check_configuration()
            self.assertTrue(status["Gemini AI matching"]["configured"])
            self.assertNotIn("super-secret-gemini-key", str(status))
            self.assertNotIn("super-secret-smtp", str(status))

    def test_wsgi_serves_health_config_and_index(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "static").mkdir()
            (root / "static" / "index.html").write_text("<!doctype html><title>LyFind</title>", encoding="utf-8")
            with patch.dict(os.environ, {"ENABLE_AI": "0", "ALLOWED_HOSTS": "lyfind.pythonanywhere.com"}):
                db = Database(root / "w.sqlite3")
                db.initialize()
                app = Application(db, root, demo_mode=False, upload_dir=root / "uploads")
                wsgi_callable = make_wsgi_app(app)

                captured = {}

                def start_response(status, headers):
                    captured["status"] = status
                    captured["headers"] = dict(headers)

                body = b"".join(wsgi_callable({
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/api/health",
                    "QUERY_STRING": "",
                    "HTTP_HOST": "lyfind.pythonanywhere.com",
                    "REMOTE_ADDR": "127.0.0.1",
                    "wsgi.input": io.BytesIO(),
                }, start_response))
                self.assertTrue(captured["status"].startswith("200"))
                parsed = json.loads(body)
                self.assertTrue(parsed["ok"])
                self.assertEqual(parsed["data"]["mode"], "live")

                body_html = b"".join(wsgi_callable({
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/",
                    "QUERY_STRING": "",
                    "HTTP_HOST": "lyfind.pythonanywhere.com",
                    "REMOTE_ADDR": "127.0.0.1",
                    "wsgi.input": io.BytesIO(),
                }, start_response))
                self.assertTrue(captured["status"].startswith("200"))
                self.assertIn(b"LyFind", body_html)


class SchemaMigrationAndAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_schema_includes_board_published_cache_and_migrates_old_email_codes(self):
        old_db = self.root / "v12.sqlite3"
        conn = sqlite3.connect(old_db)
        conn.executescript("""
            CREATE TABLE email_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL COLLATE NOCASE,
                purpose TEXT NOT NULL CHECK(purpose IN ('school','signup')),
                salt TEXT NOT NULL, code_hash TEXT NOT NULL,
                expires REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0,
                requested REAL NOT NULL
            );
            INSERT INTO email_codes(email,purpose,salt,code_hash,expires,requested) VALUES('a@example.test','signup','s','h',9999999999,1);
        """)
        conn.commit()
        conn.close()

        db = Database(old_db)
        db.initialize()
        with db.connect() as c:
            self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            # Old row preserved and 'reset' purpose now allowed
            self.assertEqual(c.execute("SELECT COUNT(*) FROM email_codes").fetchone()[0], 1)
            c.execute("INSERT INTO email_codes(email,purpose,salt,code_hash,expires,requested) VALUES('b@example.test','reset','s','h',9999999999,1)")
            cols = {row["name"] for row in c.execute("PRAGMA table_info(items)")}
            self.assertIn("board_published", cols)
            tables = {row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("ai_match_cache", tables)
        self.assertTrue(db.check()["ok"])

    def test_microsoft_login_uses_roster_professor_role_and_student_number(self):
        db = Database(self.root / "ms.sqlite3")
        db.initialize()
        with db.connect() as conn:
            conn.execute("INSERT INTO roster(email,name,role,active) VALUES('prof@lpunetwork.edu.ph','Dr. Cruz','professor',1)")
        with patch.dict(os.environ, {"UNIVERSITY_EMAIL_DOMAINS": "lpunetwork.edu.ph"}):
            auth = AuthService(db, demo_mode=False)
            auth.msal_app = MagicMock()
            auth.tenant = "11111111-1111-1111-1111-111111111111"
            auth.domains = {"lpunetwork.edu.ph"}
            auth.msal_app.initiate_auth_code_flow.return_value = {"auth_uri": "https://login.microsoftonline.com/test", "state": "ok"}

            # Professor on roster gets professor role
            auth.msal_app.acquire_token_by_auth_code_flow.return_value = {
                "access_token": "tok",
                "id_token_claims": {"tid": auth.tenant, "preferred_username": "prof@lpunetwork.edu.ph", "name": "Dr. Cruz"},
            }
            session, _ = auth.session(None)
            auth.microsoft_start(session)
            prof = auth.microsoft_finish(session, {"state": "ok"})
            self.assertEqual(prof.role, "professor")

            # Student email derives student_number
            auth.msal_app.acquire_token_by_auth_code_flow.return_value = {
                "access_token": "tok",
                "id_token_claims": {"tid": auth.tenant, "preferred_username": "2024-1-54321@lpunetwork.edu.ph", "name": "Ana Reyes"},
            }
            session2, _ = auth.session(None)
            auth.microsoft_start(session2)
            student = auth.microsoft_finish(session2, {"state": "ok"})
            self.assertEqual(student.role, "student")
            self.assertEqual(student.student_number, "2024-1-54321")

    def test_forgot_password_email_code_flow_resets_password_and_clears_sessions(self):
        db = Database(self.root / "reset.sqlite3")
        db.initialize()
        seed_demo(db, self.root / "uploads")
        auth = AuthService(db, demo_mode=True)

        # Staff admin cannot self-reset here
        with self.assertRaises(Exception):
            auth.request_password_reset("demo.admin@example.test")

        # Sign in student first so an old session exists
        user = auth.password_login("demo.student@example.test", "DemoOnly!2026")
        session, _ = auth.session(None)
        auth.sign_in(session, user)

        req = auth.request_password_reset("demo.student@example.test")
        self.assertIn("demo_code", req)
        verified = auth.verify_password_reset("demo.student@example.test", req["demo_code"])
        updated = auth.finish_password_reset(
            "demo.student@example.test", verified["setup_token"], "FreshRiver-99!", "FreshRiver-99!"
        )
        self.assertEqual(updated.email, "demo.student@example.test")
        # Old sessions cleared
        with db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions WHERE user_id=?", (user.id,)).fetchone()[0], 0)
        # Old password rejected, new password accepted
        with self.assertRaises(Exception):
            auth.password_login("demo.student@example.test", "DemoOnly!2026")
        signed_in = auth.password_login("demo.student@example.test", "FreshRiver-99!")
        self.assertEqual(signed_in.id, user.id)


if __name__ == "__main__":
    unittest.main()
