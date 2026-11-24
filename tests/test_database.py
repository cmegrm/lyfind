"""Database reliability: migrations, WAL, integrity, backups, demo reset, concurrency and restarts."""
import base64
import http.cookiejar
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lyfind import maintenance
from lyfind.database import Database, SCHEMA_VERSION
from lyfind.seed import seed_demo, sample_image
from lyfind.users import User
from lyfind.web import Application, make_handler


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = Database(self.root / "t.sqlite3")
        self.db.initialize()

    def test_initialize_is_idempotent_and_keeps_rows(self):
        with self.db.connect() as conn:
            conn.execute("INSERT INTO users(first_name,email,role) VALUES('A','a@example.test','student')")
        for _ in range(3):
            self.db.initialize()
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            self.assertTrue({"lost_reports_open", "items_status", "matches_status"} <= indexes)

    def test_an_older_database_gains_the_new_columns_without_losing_data(self):
        old = self.root / "old.sqlite3"
        conn = sqlite3.connect(old)
        conn.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
              role TEXT NOT NULL, password_hash TEXT, active INTEGER NOT NULL DEFAULT 1, blocked INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT '2026-01-01T00:00:00Z');
            CREATE TABLE lost_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL, category TEXT NOT NULL,
              description TEXT NOT NULL, color TEXT NOT NULL DEFAULT '', brand TEXT NOT NULL DEFAULT '', place TEXT NOT NULL,
              date_lost TEXT NOT NULL, identifying_marks TEXT NOT NULL DEFAULT '', photo_id INTEGER,
              status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL DEFAULT '2026-01-01T00:00:00Z');
            INSERT INTO users(name,email,role) VALUES('Old User','old@example.test','student');
            INSERT INTO lost_reports(owner_id,category,description,place,date_lost) VALUES(1,'bags','Old bag','Gym','2026-01-01');
        """)
        conn.commit()
        conn.close()
        legacy = Database(old)
        legacy.initialize()
        legacy.initialize()
        with legacy.connect() as c:
            user = dict(c.execute("SELECT * FROM users").fetchone())
            report = dict(c.execute("SELECT * FROM lost_reports").fetchone())
        self.assertEqual(user["email_verified"], 1)  # existing people stay confirmed
        self.assertEqual((report["flagged"], report["hidden"], report["description"]), (0, 0, "Old bag"))
        self.assertTrue(legacy.check()["ok"])

    def test_display_name_follows_the_name_parts(self):
        with self.db.connect() as conn:
            user_id = conn.execute(
                "INSERT INTO users(email,role,first_name,middle_name,last_name,suffix) VALUES('parts@example.test','student','Maria','Santos','Reyes','Jr.')"
            ).lastrowid
            stored = conn.execute("SELECT name FROM users WHERE id=?", (user_id,)).fetchone()[0]
            conn.execute("UPDATE users SET last_name=? WHERE id=?", ("Cruz", user_id))
            renamed = conn.execute("SELECT name FROM users WHERE id=?", (user_id,)).fetchone()[0]
        self.assertEqual(stored, "Maria Santos Reyes Jr.")
        self.assertEqual(renamed, "Maria Santos Cruz Jr.")

    def test_connections_use_wal_busy_timeout_and_foreign_keys(self):
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertGreaterEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_check_reports_ok_and_finds_a_broken_reference(self):
        self.assertEqual(self.db.check()["problems"], [])
        raw = sqlite3.connect(self.db.path)
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute("INSERT INTO lost_reports(owner_id,category,description,place,date_lost) VALUES(999,'bags','x','y','2026-01-01')")
        raw.commit()
        raw.close()
        result = self.db.check()
        self.assertFalse(result["ok"])
        self.assertTrue(any("lost_reports" in problem for problem in result["problems"]))

    def test_backup_copies_database_and_uploads_and_never_overwrites(self):
        uploads, backups = self.root / "uploads", self.root / "backups"
        uploads.mkdir()
        (uploads / "photo.jpg").write_bytes(b"photo bytes")
        with self.db.connect() as conn:
            conn.execute("INSERT INTO users(first_name,email,role) VALUES('A','a@example.test','student')")
        first = self.db.backup(uploads, backups, stamp="20260101-000000")
        second = self.db.backup(uploads, backups, stamp="20260101-000000")
        self.assertNotEqual(first, second)
        self.assertEqual((first / "uploads" / "photo.jpg").read_bytes(), b"photo bytes")
        copy = Database(first / "t.sqlite3")
        self.assertTrue(copy.check()["ok"])
        with copy.connect() as conn:
            self.assertEqual(conn.execute("SELECT email FROM users").fetchone()[0], "a@example.test")
        with self.db.connect() as conn:  # the original is untouched
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

    def test_reset_demo_backs_up_first_then_reseeds_and_only_removes_owned_uploads(self):
        db_path, uploads, backups = self.root / "demo.sqlite3", self.root / "uploads", self.root / "backups"
        db = Database(db_path)
        db.initialize()
        seed_demo(db, uploads)
        with db.connect() as conn:
            conn.execute("INSERT INTO users(first_name,email,role) VALUES('Extra','extra@example.test','student')")
            owned = [r[0] for r in conn.execute("SELECT path FROM uploads")]
        (uploads / "not-ours.txt").write_text("keep me")
        made = maintenance.reset_demo(db_path, uploads, backups)
        self.assertTrue(made and (made / "demo.sqlite3").is_file())
        saved = Database(made / "demo.sqlite3")
        with saved.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM users WHERE email='extra@example.test'").fetchone()[0], 1)  # the backup has it
        fresh = Database(db_path)
        with fresh.connect() as conn:
            emails = {r[0] for r in conn.execute("SELECT email FROM users")}
            self.assertEqual(emails, {f"demo.{r}@example.test" for r in ("admin", "student", "professor", "guest")})
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM roster").fetchone()[0], 4)
        self.assertTrue(fresh.check()["ok"])
        self.assertEqual((uploads / "not-ours.txt").read_text(), "keep me")
        self.assertTrue(all((made / "uploads" / name).is_file() for name in owned))

    def test_command_line_refuses_to_reset_live_data_and_checks_a_database(self):
        run = lambda *args: subprocess.run([sys.executable, str(ROOT / "main.py"), *args], capture_output=True, text=True, cwd=ROOT, timeout=60,
                                           env={**os.environ, "LYFIND_NO_VENV": "1"})
        refused = run("--live", "--reset-demo", "--yes", "--database", str(self.root / "csa.sqlite3"))
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("only works on the demo database", refused.stderr + refused.stdout)
        self.assertFalse((self.root / "csa.sqlite3").exists())
        ok = run("--check-db", "--database", str(self.db.path))
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("OK", ok.stdout)

    def test_threads_reading_and_writing_never_hit_database_is_locked(self):
        db = Database(self.root / "busy.sqlite3")
        db.initialize()
        from lyfind.services import Service
        from lyfind.matching import TypedDetailsMatchingService
        service = Service(db, self.root, matcher=TypedDetailsMatchingService())
        with db.connect() as conn:
            for n in range(8):
                conn.execute("INSERT INTO users(first_name,email,role) VALUES(?,?,'student')", (f"S{n}", f"s{n}@example.test"))
            admin = conn.execute("INSERT INTO users(first_name,email,role) VALUES('Admin','admin@example.test','admin')").lastrowid
            people = [User.from_row(r) for r in conn.execute("SELECT * FROM users WHERE role='student'")]
            staff = User.from_row(conn.execute("SELECT * FROM users WHERE id=?", (admin,)).fetchone())
        errors = []

        def work(person):
            try:
                for n in range(4):
                    service.create_lost_report(person, dict(category="bags", description=f"Blue bag {person.id}-{n}", color="blue", brand_choice="unknown",
                                                            place="Library", date_lost=time.strftime("%Y-%m-%d")))
                    service.dashboard(person)
                    service.dashboard(staff)
                    with db.connect() as conn:
                        conn.execute("INSERT INTO rate_events(bucket,at) VALUES('stress',?)", (time.time(),))
            except Exception as error:  # noqa: BLE001 - any failure fails the test below
                errors.append(repr(error))

        with ThreadPoolExecutor(8) as pool:
            list(pool.map(work, people))
        self.assertEqual(errors, [])
        with db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM lost_reports").fetchone()[0], 32)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM rate_events WHERE bucket='stress'").fetchone()[0], 32)
        self.assertTrue(db.check()["ok"])


class PersistenceAcrossRestartTests(unittest.TestCase):
    """Everything must still be there after the server process is replaced."""

    def start(self):
        app = Application(self.db, self.root, demo_mode=True)
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.servers.append(server)
        return app, server, "http://127.0.0.1:" + str(server.server_port)

    def stop(self, server):
        server.shutdown()
        server.server_close()

    def request(self, opener, base, path, data=None, csrf=None):
        headers = {"Content-Type": "application/json"} if data is not None else {}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            response = opener.open(req)
        except urllib.error.HTTPError as error:
            response = error
        raw = response.read()
        return response.status, json.loads(raw) if "json" in response.headers.get("Content-Type", "") else raw

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.servers = []
        self.addCleanup(lambda: [s.server_close() for s in self.servers if s.socket.fileno() != -1])
        env = patch.dict(os.environ, {"ENABLE_AI": "0", "SMTP_HOST": "", "SMTP_FROM": "", "MICROSOFT_TENANT_ID": "", "MICROSOFT_CLIENT_ID": ""})
        env.start()
        self.addCleanup(env.stop)
        self.db = Database(self.root / "demo.sqlite3")
        self.db.initialize()
        seed_demo(self.db, self.root / "data" / "uploads")

    def counts(self):
        with self.db.connect() as conn:
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ("users", "sessions", "lost_reports", "found_reports", "items", "uploads", "matches", "claims", "notifications", "audit_logs", "roster", "email_codes")}

    def test_accounts_sessions_reports_uploads_matches_claims_notifications_and_audit_survive_a_restart(self):
        app, server, base = self.start()
        jar = http.cookiejar.CookieJar()
        browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        csrf = self.request(browser, base, "/api/config")[1]["data"]["csrf_token"]
        # a new guest signs up with an email code
        status, result = self.request(browser, base, "/api/auth/register", {"email": "restart@example.org"}, csrf)
        self.assertEqual(status, 200, result)
        status, result = self.request(browser, base, "/api/auth/register/verify", {"email": "restart@example.org", "code": result["data"]["demo_code"]}, csrf)
        self.assertEqual(status, 200, result)
        status, result = self.request(browser, base, "/api/auth/register/finish", {
            "email": "restart@example.org", "setup_token": result["data"]["setup_token"],
            "first_name": "Restart", "last_name": "Guest", "password": "BlueKettle42!", "confirm": "BlueKettle42!",
        }, csrf)
        self.assertEqual(status, 200, result)
        csrf = result["data"]["csrf_token"]
        # a lost report with a photo
        status, upload = self.request(browser, base, "/api/uploads", {"kind": "report_photo", "name": "p.png", "content": base64.b64encode(sample_image()).decode()}, csrf)
        self.assertEqual(status, 200, upload)
        status, report = self.request(browser, base, "/api/reports/lost", {"category": "other", "description": "Green flask", "color": "Green", "brand_choice": "unknown",
                                                                       "place": "Gym", "date_lost": time.strftime("%Y-%m-%d"), "photo_id": upload["data"]["id"]}, csrf)
        self.assertEqual(status, 200, report)
        # staff move the sample claim one step forward
        staff_jar = http.cookiejar.CookieJar()
        staff = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(staff_jar))
        staff_csrf = self.request(staff, base, "/api/config")[1]["data"]["csrf_token"]
        staff_csrf = self.request(staff, base, "/api/auth/demo", {"role": "admin"}, staff_csrf)[1]["data"]["csrf_token"]
        claim = self.request(staff, base, "/api/dashboard")[1]["data"]["claims"][0]
        self.assertEqual(claim["status"], "step1_pending")
        self.assertEqual(self.request(staff, base, "/api/claims/online", {"claim_id": claim["id"], "passed": True}, staff_csrf)[0], 200)
        self.assertEqual(self.request(staff, base, "/api/matching/run", {}, staff_csrf)[0], 200)
        before = self.counts()
        self.assertGreater(before["sessions"], 1)
        self.stop(server)
        # a brand-new server process on the same files
        app2, server2, base2 = self.start()
        after = self.counts()
        # Starting matching adds an audit entry for the run and the typed-only fallback.
        self.assertEqual(after['audit_logs'], before['audit_logs'] + 2)
        self.assertEqual({k:v for k,v in after.items() if k != 'audit_logs'},
                         {k:v for k,v in before.items() if k != 'audit_logs'})
        self.assertTrue(self.db.check()["ok"])
        status, data = self.request(browser, base2, "/api/dashboard")  # the same cookie still works
        self.assertEqual(status, 200)
        data = data["data"]
        self.assertEqual(data["user"]["email"], "restart@example.org")
        self.assertTrue(any(r["description"] == "Green flask" for r in data["reports"]))
        self.assertEqual(self.request(browser, base2, "/api/files/" + str(upload["data"]["id"]))[1], sample_image())
        status, data = self.request(staff, base2, "/api/dashboard")
        data = data["data"]
        self.assertEqual(next(c for c in data["claims"] if c["id"] == claim["id"])["status"], "step2_pending")  # the transition persisted
        self.assertTrue(data["matches"] and all(m["score_details"] for m in data["matches"]))
        actions = {a["action"] for a in data["audit"]}
        self.assertTrue({"ACCOUNT_CREATED", "LOST_REPORT_CREATED", "STEP1_PASSED", "MATCHING_RUN"} <= actions)
        self.assertTrue(data["notifications"] is not None)
        with self.db.connect() as conn:
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 0)
        self.stop(server2)

    def test_restart_does_not_duplicate_matches_or_seed_rows(self):
        first = self.counts()
        for _ in range(2):
            app, server, base = self.start()
            self.stop(server)
        after = self.counts()
        self.assertEqual(after["matches"], first["matches"])
        self.assertEqual(after["users"], first["users"])
        self.assertEqual(after["roster"], first["roster"])


if __name__ == "__main__":
    unittest.main()
