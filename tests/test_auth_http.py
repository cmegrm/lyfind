"""Boundary tests for the actual HTTP server and authentication lifecycle."""
import base64
import http.cookiejar
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from lyfind.database import Database
from lyfind.seed import seed_demo, sample_image
from lyfind.web import Application, host_is_allowed, make_handler, probe_host


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"MICROSOFT_TENANT_ID": "", "MICROSOFT_CLIENT_ID": "", "SMTP_HOST": "", "SMTP_FROM": "", "ENABLE_AI": "0"})
        self.env.start()
        self.db = Database(self.root / "test.sqlite3")
        self.db.initialize()
        seed_demo(self.db, self.root / "data" / "uploads")
        self.app = Application(self.db, self.root, demo_mode=True)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)
        self.jar = http.cookiejar.CookieJar()
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = self.call("/api/config")[1]["data"]["csrf_token"]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()
        self.env.stop()
        self.tmp.cleanup()

    def call(self, path, data=None, csrf=True, headers=None):
        expected_cookie = 'reunite_test_session' if self.app.demo_mode else 'csa_session'
        if data is not None and csrf and not any(cookie.name == expected_cookie for cookie in self.jar):
            self.csrf = self.call('/api/config')[1]['data']['csrf_token']
        request_headers = dict(headers or {})
        if data is not None:
            request_headers["Content-Type"] = "application/json"
            if csrf:
                request_headers["X-CSRF-Token"] = self.csrf
        request = urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, headers=request_headers)
        try:
            response = self.client.open(request)
        except urllib.error.HTTPError as error:
            response = error
        raw = response.read()
        return response.status, json.loads(raw) if "json" in response.headers.get("Content-Type", "") else raw

    def login(self, role):
        status, result = self.call("/api/auth/demo", {"role": role})
        self.assertEqual(status, 200, result)
        self.csrf = result["data"]["csrf_token"]
        return result

    def test_session_cookie_and_csrf_rotate_on_login(self):
        token = next(iter(self.jar)).value
        csrf = self.csrf
        self.login("student")
        self.assertNotEqual(csrf, self.csrf)
        self.assertNotEqual(token, next(iter(self.jar)).value)
        self.assertEqual(self.call("/api/dashboard")[0], 200)

    def test_anonymous_dashboard_and_missing_csrf_denied(self):
        self.assertEqual(self.call("/api/dashboard")[0], 401)
        self.assertEqual(self.call("/api/auth/demo", {"role": "admin"}, csrf=False)[0], 403)

    def test_uploaded_image_remains_accessible_after_storage_moves(self):
        self.login('student')
        raw=sample_image()
        status,result=self.call('/api/uploads',{'kind':'report_photo','name':'sample.png','content':base64.b64encode(raw).decode()})
        self.assertEqual(status,200,result)
        file_id=result['data']['id']
        with self.db.connect() as conn:
            row=dict(conn.execute('SELECT * FROM uploads WHERE id=?',(file_id,)).fetchone())
        self.assertFalse(Path(row['path']).is_absolute())
        old=self.app.upload_dir/row['path']
        moved=self.root/'relocated-uploads';moved.mkdir()
        (moved/old.name).write_bytes(old.read_bytes());old.unlink()
        # Also exercise compatibility with an old absolute record.
        with self.db.connect() as conn:conn.execute('UPDATE uploads SET path=? WHERE id=?',(str(old),file_id))
        self.app.upload_dir=moved;self.app.service.upload_dir=moved
        status,result=self.call('/api/files/'+str(file_id))
        self.assertEqual(status,200)
        self.assertEqual(result,raw)

    def test_cross_origin_action_denied(self):
        status, _ = self.call("/api/auth/demo", {"role": "admin"}, headers={"Origin": "https://another.example"})
        self.assertEqual(status, 403)

    def test_file_access_and_image_validation(self):
        self.login("student")
        self.assertEqual(self.call("/api/files/1")[0], 403)
        bad = {"kind": "report_photo", "name": "image.png", "content": base64.b64encode(b"<script>alert(1)</script>").decode()}
        self.assertEqual(self.call("/api/uploads", bad)[0], 400)
        bad["content"] = base64.b64encode(sample_image()).decode()
        status, result = self.call("/api/uploads", bad)
        self.assertEqual(status, 200, result)
        file_id = result["data"]["id"]
        self.assertEqual(self.call(f"/api/files/{file_id}")[0], 200)
        self.login("guest")
        self.assertEqual(self.call(f"/api/files/{file_id}")[0], 403)

    def test_live_mode_disables_demo_and_known_demo_password(self):
        self.app.demo_mode = self.app.auth.demo_mode = False
        self.assertEqual(self.call("/api/auth/demo", {"role": "admin"})[0], 404)
        status, result = self.call("/api/auth/staff", {"email": "demo.admin@example.test", "password": "DemoOnly!2026"})
        self.assertEqual(status, 401, result)
        self.assertEqual(self.call("/api/auth/school/request", {"email": "2026-1-10003@lpunetwork.edu.ph"})[0], 503)
        self.assertEqual(self.call("/api/auth/register", {"name": "Sam", "email": "sam@example.org", "password": "Long-Secret42!"})[0], 503)

    def test_logout_invalidates_session(self):
        self.login("admin")
        self.assertEqual(self.call("/api/logout", {})[0], 200)
        self.assertEqual(self.call("/api/dashboard")[0], 401)

    def test_disabled_staff_loses_existing_session(self):
        result = self.login("admin")
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET active=0 WHERE id=?", (result["data"]["user"]["id"],))
        self.assertEqual(self.call("/api/dashboard")[0], 401)

    def test_email_and_password_sign_in_for_every_role(self):
        for role in ("admin", "student", "professor", "guest"):
            status, result = self.call("/api/auth/login", {"email": f"demo.{role}@example.test", "password": "DemoOnly!2026"})
            self.assertEqual(status, 200, result)
            self.assertEqual(result["data"]["user"]["role"], role)
            self.csrf = result["data"]["csrf_token"]
            self.assertEqual(self.call("/api/dashboard")[0], 200)

    def test_wrong_password_is_refused_and_locks_after_five_tries(self):
        bad = {"email": "demo.student@example.test", "password": "not-the-password"}
        for _ in range(5):
            status, result = self.call("/api/auth/login", bad)
            self.assertEqual(status, 401)
            self.assertIn("not right", result["error"])
        good = {"email": "demo.student@example.test", "password": "DemoOnly!2026"}
        self.assertEqual(self.call("/api/auth/login", good)[0], 401)

    def test_account_without_a_password_cannot_sign_in(self):
        with self.db.connect() as conn:
            conn.execute("INSERT INTO users(first_name,email,role,password_hash) VALUES('No Password','nopass@example.org','guest','')")
        self.assertEqual(self.call("/api/auth/login", {"email": "nopass@example.org", "password": ""})[0], 401)

    def test_register_needs_the_email_code_before_the_account_works(self):
        status, result = self.call("/api/auth/register", {"email": "Jamie@Example.org"})
        self.assertEqual(status, 200, result)
        self._code = result["data"]["demo_code"]
        self.assertEqual(self.call("/api/auth/login", {"email": "jamie@example.org", "password": "Long-Secret42!"})[0], 401)
        status, checked = self.call("/api/auth/register/verify", {"email": "jamie@example.org", "code": self._code})
        self.assertEqual(status, 200, checked)
        self.assertNotIn("user", checked["data"])
        status, result = self.call("/api/auth/register/finish", {
            "email": "jamie@example.org", "setup_token": checked["data"]["setup_token"],
            "first_name": "Jamie", "last_name": "Lee", "password": "Long-Secret42!", "confirm": "Long-Secret42!",
        })
        self.assertEqual(status, 200, result)
        self.assertEqual(result["data"]["user"]["role"], "guest")
        self.csrf = result["data"]["csrf_token"]
        self.assertEqual(self.call("/api/matching/run", {})[0], 403)
        self.call("/api/logout", {})
        self.csrf = self.call("/api/config")[1]["data"]["csrf_token"]
        status, result = self.call("/api/auth/login", {"email": "jamie@example.org", "password": "Long-Secret42!"})
        self.assertEqual(status, 200, result)

    def test_register_rejects_weak_duplicate_and_university_emails(self):
        self.assertEqual(self.call("/api/auth/register", {"email": "not-an-email"})[0], 400)
        self.assertEqual(self.call("/api/auth/register", {"email": "demo.admin@example.test"})[0], 400)
        self.assertEqual(self.call("/api/auth/register", {"email": "pupil@lpu.edu.ph"})[0], 400)
        status, started = self.call("/api/auth/register", {"email": "sam@example.org"})
        self.assertEqual(status, 200, started)
        status, checked = self.call("/api/auth/register/verify", {"email": "sam@example.org", "code": started["data"]["demo_code"]})
        status, weak = self.call("/api/auth/register/finish", {
            "email": "sam@example.org", "setup_token": checked["data"]["setup_token"],
            "first_name": "", "last_name": "Lee", "password": "short", "confirm": "short",
        })
        self.assertEqual(status, 400)
        self.assertIn("first_name", weak["fields"])
        self.assertIn("password", weak["fields"])
        status, result = self.call("/api/auth/register/finish", {
            "email": "sam@example.org", "setup_token": checked["data"]["setup_token"],
            "first_name": "Sam", "last_name": "Lee", "password": "Long-Secret42!", "confirm": "Long-Secret42!",
        })
        self.assertEqual(status, 200, result)
        self.csrf = result["data"]["csrf_token"]
        self.assertEqual(self.call("/api/auth/register", {"email": "sam@example.org"})[0], 400)


    def test_photos_are_served_and_other_paths_are_not(self):
        (self.root / "static" / "assets").mkdir(parents=True)
        (self.root / "static" / "assets" / "hero.jpg").write_bytes(b"\xff\xd8\xff test photo")
        status, raw = self.call("/assets/hero.jpg")
        self.assertEqual(status, 200)
        self.assertTrue(raw.startswith(b"\xff\xd8"))
        self.assertEqual(self.call("/assets/missing.jpg")[0], 404)
        self.assertEqual(self.call("/assets/..%2Fapp.py")[0], 404)


class LanHostTests(unittest.TestCase):
    def test_localhost_bind_rejects_lan_and_public_names(self):
        self.assertTrue(host_is_allowed("127.0.0.1:8765", "127.0.0.1"))
        self.assertTrue(host_is_allowed("localhost:8765", "127.0.0.1"))
        self.assertFalse(host_is_allowed("192.168.1.8:8765", "127.0.0.1"))
        self.assertFalse(host_is_allowed("evil.example:8765", "127.0.0.1"))

    def test_all_interfaces_allows_private_lan_not_the_public_internet(self):
        self.assertTrue(host_is_allowed("192.168.1.8:8765", "0.0.0.0"))
        self.assertTrue(host_is_allowed("10.2.3.4:8765", "0.0.0.0"))
        self.assertTrue(host_is_allowed("172.16.0.9:8765", "0.0.0.0"))
        self.assertTrue(host_is_allowed("127.0.0.1:8765", "0.0.0.0"))
        self.assertTrue(host_is_allowed("[::1]:8765", "::"))
        self.assertFalse(host_is_allowed("evil.example:8765", "0.0.0.0"))
        self.assertFalse(host_is_allowed("8.8.8.8:8765", "0.0.0.0"))
        self.assertEqual(probe_host("0.0.0.0"), "127.0.0.1")
        self.assertEqual(probe_host("127.0.0.1"), "127.0.0.1")

    def test_lan_browser_can_sign_in_with_matching_origin(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        env = patch.dict(os.environ, {"MICROSOFT_TENANT_ID": "", "MICROSOFT_CLIENT_ID": "", "SMTP_HOST": "", "SMTP_FROM": "", "ENABLE_AI": "0"})
        env.start()
        self.addCleanup(env.stop)
        db = Database(root / "test.sqlite3")
        db.initialize()
        seed_demo(db, root / "data" / "uploads")
        app = Application(db, root, demo_mode=True)
        server = ThreadingHTTPServer(("0.0.0.0", 0), make_handler(app))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), worker.join()))
        port = server.server_port
        lan_host = "192.168.50.10:%s" % port
        origin = "http://%s" % lan_host
        jar = http.cookiejar.CookieJar()
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        def call(path, data=None, extra=None, csrf=True):
            headers = {"Host": lan_host, **(extra or {})}
            if data is not None:
                headers["Content-Type"] = "application/json"
                if csrf:
                    headers["X-CSRF-Token"] = csrf_token
            request = urllib.request.Request(
                "http://127.0.0.1:%s%s" % (port, path),
                data=json.dumps(data).encode() if data is not None else None,
                headers=headers,
            )
            try:
                response = client.open(request)
            except urllib.error.HTTPError as error:
                response = error
            raw = response.read()
            body = json.loads(raw) if "json" in response.headers.get("Content-Type", "") else raw
            return response.status, body

        status, config = call("/api/config")
        self.assertEqual(status, 200, config)
        csrf_token = config["data"]["csrf_token"]
        status, result = call("/api/auth/demo", {"role": "student"}, extra={"Origin": origin})
        self.assertEqual(status, 200, result)
        csrf_token = result["data"]["csrf_token"]
        self.assertEqual(call("/api/dashboard", extra={"Origin": origin})[0], 200)
        status, _ = call("/api/auth/demo", {"role": "admin"}, extra={"Origin": "https://another.example"})
        self.assertEqual(status, 403)
        request = urllib.request.Request("http://127.0.0.1:%s/api/health" % port, headers={"Host": "evil.example:%s" % port})
        try:
            client.open(request)
            denied = 200
        except urllib.error.HTTPError as error:
            denied = error.status
        self.assertEqual(denied, 403)


if __name__ == "__main__":
    unittest.main()
