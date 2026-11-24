"""Small local HTTP application. All authorization remains in the service layer."""
import base64
import binascii
import hmac
import io
import json
import mimetypes
import os
import secrets
from desktop_launcher import instance_id, start
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlparse

from auth import AuthService, REMEMBERED_GUEST_LIFETIME, SESSION_LIFETIME
from domain import DomainError
from maintenance import WorkspaceMaintenance
from services import Service
from storage import resolve_upload
from support import SupportService


def user_json(user):
    if not user:
        return None
    return {key: value for key, value in user.public().items() if key in {'id','name','email','role','quick_guest'}}


class Application:
    def __init__(self, db, root, demo_mode=True, upload_dir=None, setup_key=None, launch_id=None):
        self.root = Path(root)
        self.upload_dir = Path(upload_dir) if upload_dir is not None else self.root / "data" / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.db, self.demo_mode = db, demo_mode
        self.setup_key = None if demo_mode else setup_key
        self.launch_id = launch_id
        self.testing_launch_lock = Lock()
        self.service = Service(db, upload_dir=self.upload_dir)
        self.service.prepare_matching()
        with self.service._tx() as conn:
            self.service._run_matching(conn)
        self.auth = AuthService(db, demo_mode=demo_mode)
        self.support = SupportService(db)
        self.maintenance = WorkspaceMaintenance(db, self.root, self.upload_dir, demo_mode)

    def testing_available(self, handler):
        host = handler.headers.get('Host', '').partition(':')[0].lower()
        return (bool(self.launch_id) and not self.demo_mode and host in ('localhost', '127.0.0.1')
                and handler.client_address[0] == '127.0.0.1')

    def handle(self, handler, method, path, session, user, data):
        if method == "GET":
            if path == "/api/config":
                return {"demo_mode": self.demo_mode, "microsoft_enabled": self.auth.microsoft_enabled,
                        "smtp_enabled": self.auth.smtp_enabled, "csrf_token": session["csrf"],
                        "setup_required": bool(self.setup_key and not self.auth.has_admin()),
                        "testing_available": self.testing_available(handler)}
            if path == "/api/session":
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/dashboard":
                self.require_login(user)
                result = self.service.dashboard(user)
                if user.role == 'admin':
                    result['can_reset_demo'] = self.maintenance.can_reset
                return result
            if path == "/api/support":
                self.require_login(user)
                return self.support.overview(user)
            support_thread_prefix = "/api/support/threads/"
            if path.startswith(support_thread_prefix):
                self.require_login(user)
                owner_id = integer({"user_id": path[len(support_thread_prefix):]}, "user_id")
                return self.support.thread(user, owner_id)
        if method == "POST":
            if path == "/api/testing/open":
                if not self.testing_available(handler):
                    raise DomainError("The testing shortcut is only available in the local desktop app.", 404)
                with self.testing_launch_lock:
                    try:
                        return {"url": start(self.root, browser=False, demo=True) + '#samples'}
                    except (RuntimeError, OSError) as exc:
                        raise DomainError('The testing workspace could not start. Try the testing launcher in your app folder.', 503) from exc
            if path == "/api/auth/setup-admin":
                key = data.get("setup_key")
                expected = self.setup_key
                if (not expected or handler.client_address[0] != '127.0.0.1'
                        or not isinstance(key, str) or not hmac.compare_digest(expected.encode(), key.encode())):
                    raise DomainError("Open LyFind using its launcher to set up the first administrator.", 403)
                admin = self.auth.setup_first_admin(data)
                self.setup_key = None
                handler.new_cookie = self.auth.sign_in(session, admin)
                return {"user": user_json(admin), "csrf_token": session["csrf"]}
            if path == "/api/auth/demo":
                user = self.auth.demo_login(data.get("role"))
                handler.new_cookie = self.auth.sign_in(session, user)
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/auth/guest/request":
                return self.auth.request_code(data.get("email", ""), handler.client_address[0])
            if path in ("/api/auth/guest/quick", "/api/auth/guest/password", "/api/auth/guest/setup", "/api/auth/guest/setup/check"):
                raise DomainError("Request a sign-in code to verify your guest email.", 404)
            if path == "/api/auth/guest/verify":
                user = self.auth.verify_code(data.get("email", ""), data.get("code", ""))
                if data.get('remember_browser') is True:
                    handler.cookie_lifetime = REMEMBERED_GUEST_LIFETIME
                handler.new_cookie = self.auth.sign_in(session, user, lifetime=handler.cookie_lifetime)
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/auth/staff":
                user = self.auth.staff_login(data.get("email", ""), data.get("password", ""))
                handler.new_cookie = self.auth.sign_in(session, user)
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/auth/student":
                user, handler.new_cookie = self.auth.account_login(session, data.get("email"), data.get("password"))
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/auth/student/setup/request":
                return self.auth.request_account_setup_code(data.get("email"), handler.client_address[0])
            if path == "/api/auth/student/setup/check":
                self.auth.check_account_setup_code(data.get("email"), data.get("code"))
                return {"message": "Setup code verified."}
            if path == "/api/auth/student/setup":
                self.auth.set_account_password(data.get("email"), data.get("code"), data.get("password"), data.get("confirmation"))
                return {"message": "Password saved. Sign in with your school email."}
            if path == "/api/logout":
                self.auth.logout(session)
                handler.new_cookie = ""
                return {"message": "Signed out."}
            self.require_login(user)
            if path == "/api/uploads":
                return self.save_upload(user, data)
            if path == "/api/support/send":
                return self.support.send(user, data)
            if path == "/api/maintenance/backup":
                return self.maintenance.backup(user)
            if path == "/api/maintenance/reset-demo":
                result = self.maintenance.reset_demo(user, data.get('confirmed'))
                handler.new_cookie = ''
                return result
            s = self.service
            routes = {
                "/api/reports/lost": lambda: s.create_lost_report(user, data),
                "/api/reports/lost-for-guest": lambda: s.create_guest_lost_report(user, self.auth.guest_email(data.get("email")), data),
                "/api/reports/close": lambda: s.close_lost_report(user, integer(data, "report_id")),
                "/api/reports/found": lambda: s.create_found_report(user, data),
                "/api/reports/duplicate-reviewed": lambda: s.review_duplicate(user, data.get("kind"), integer(data, "report_id")),
                "/api/items/receive": lambda: s.receive_item(user, data),
                "/api/items/correct": lambda: s.correct_item(user, integer(data, "item_id"), data),
                "/api/items/board": lambda: s.set_board_listing(user, integer(data, "item_id"), data),
                "/api/matching/run": lambda: s.run_matching(user),
                "/api/matches/decide": lambda: s.decide_match(user, integer(data, "match_id"), boolean(data, "confirmed")),
                "/api/matches/withdraw": lambda: s.withdraw_invitation(user, integer(data, "match_id"), data),
                "/api/claims/submit": lambda: s.submit_claim(user, data),
                "/api/claims/online": lambda: s.verify_online(user, integer(data, "claim_id"), boolean(data, "passed"), data.get("reason", "")),
                "/api/claims/consent": lambda: s.record_consent(user, integer(data, "claim_id"), data),
                "/api/claims/consent-declined": lambda: s.record_consent_declined(user, integer(data, "claim_id")),
                "/api/claims/end-reservation": lambda: s.end_reservation(user, integer(data, "claim_id"), data),
                "/api/claims/in-person": lambda: s.verify_in_person(user, integer(data, "claim_id"), boolean(data, "passed"), data.get("reason", "")),
                "/api/claims/approve": lambda: s.approve_claim(user, integer(data, "claim_id"), data),
                "/api/claims/release": lambda: s.release_item(user, integer(data, "claim_id")),
                "/api/items/expire": lambda: s.expire_items(user),
                "/api/staff/save": lambda: s.manage_staff(user, data),
                "/api/students/create": lambda: self.auth.issue_account_code(user, data.get("email"), data.get("name")),
                "/api/students/reset": lambda: self.auth.issue_account_code(user, data.get("email"), reset=True),
                "/api/accounts/create": lambda: self.auth.issue_account_code(user, data.get("email"), data.get("name"), role=data.get("role")),
                "/api/accounts/reset": lambda: self.auth.issue_account_code(user, data.get("email"), reset=True),
                "/api/accounts/import/preview": lambda: self.auth.import_accounts(user, data.get("csv")),
                "/api/accounts/import": lambda: self.auth.import_accounts(user, data.get("csv"), data.get("preview") or ""),
            }
            if path in routes:
                return routes[path]()
        raise DomainError("This page or action does not exist.", 404)

    @staticmethod
    def require_login(user):
        if user is None:
            raise DomainError("Please sign in to continue.", 401)

    def save_upload(self, user, data):
        kind, claim_id = str(data.get("kind", "")), data.get("claim_id")
        if claim_id is not None:
            claim_id = integer(data, "claim_id")
        self.service.authorize_upload(user, kind, claim_id)
        content = str(data.get("content", ""))
        if len(content) > 8 * 1024 * 1024:
            raise DomainError("Choose an image smaller than 6 MB.", 413)
        try:
            raw = base64.b64decode(content, validate=True)
        except (ValueError, binascii.Error):
            raise DomainError("The image could not be read.") from None
        if not raw or len(raw) > 6 * 1024 * 1024:
            raise DomainError("Choose an image smaller than 6 MB.")
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            mime, ext = "image/png", ".png"
        elif raw.startswith(b"\xff\xd8\xff"):
            mime, ext = "image/jpeg", ".jpg"
        elif raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
            mime, ext = "image/webp", ".webp"
        else:
            raise DomainError("Upload a PNG, JPEG or WebP image.")
        # Pillow is optional for AI, but also adds image structure validation when available.
        try:
            from PIL import Image
            with Image.open(io.BytesIO(raw)) as image:
                if image.width * image.height > 25_000_000:
                    raise DomainError("Choose an image under 25 megapixels.")
                image.verify()
        except ImportError:
            pass
        except DomainError:
            raise
        except Exception:
            raise DomainError("This image is damaged or unsupported.") from None
        name = Path(str(data.get("name", "image"))).name[:180]
        path = self.upload_dir / (secrets.token_hex(24) + ext)
        try:
            with self.db.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                if kind in {"claimant_photo", "id_photo", "signature"}:
                    claim = conn.execute("SELECT status,in_person_consent FROM claims WHERE id=?", (claim_id,)).fetchone()
                    if not claim or claim["status"] not in {"step2_pending", "verified"} or not claim["in_person_consent"]:
                        raise DomainError("This claim is no longer ready for evidence capture.")
                path.write_bytes(raw)
                cur = conn.execute("INSERT INTO uploads(owner_id,kind,path,mime,original_name,claim_id) VALUES(?,?,?,?,?,?)",
                                   (user.id, kind, path.name, mime, name, claim_id))
                file_id = cur.lastrowid
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return {"id": file_id, "url": f"/api/files/{file_id}"}


def integer(data, name):
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).isdigit():
        raise DomainError(f"{name} must be a record number.")
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise DomainError(f"{name} must be a record number.") from None
    if result < 1:
        raise DomainError(f"{name} must be a positive record number.")
    return result


def boolean(data, name):
    if not isinstance(data.get(name), bool):
        raise DomainError(f"{name} must be true or false.")
    return data[name]


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CSA/1.0"

        @property
        def cookie_name(self):
            return 'reunite_test_session' if app.demo_mode else 'csa_session'

        def log_message(self, fmt, *args):
            # Avoid printing OAuth authorization codes or uploaded identity details.
            if self.path.startswith("/auth/") or self.path == '/api/health':
                return
            super().log_message(fmt, *args)

        def headers_common(self, content_type):
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if self.new_cookie is not None:
                secure = "; Secure" if os.environ.get("COOKIE_SECURE", "0") == "1" else ""
                self.send_header("Set-Cookie", f"{self.cookie_name}={self.new_cookie}; Path=/; HttpOnly; SameSite=Lax; Max-Age={self.cookie_lifetime if self.new_cookie else 0}{secure}")

        def json_response(self, status, data=None, error=None):
            raw = json.dumps({"ok": error is None, **({"data": data} if error is None else {"error": error})}, default=str).encode()
            self.send_response(status)
            self.headers_common("application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def redirect(self, location):
            self.send_response(303)
            self.headers_common("text/plain; charset=utf-8")
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            self.dispatch("GET")

        def do_POST(self):
            self.dispatch("POST")

        def dispatch(self, method):
            self.new_cookie = None
            self.cookie_lifetime = SESSION_LIFETIME
            try:
                with app.maintenance.request():
                    self.dispatch_request(method)
            except DomainError as exc:
                self.json_response(exc.status, error=str(exc))

        def dispatch_request(self, method):
            try:
                # Restrict host to bind address/localhost, closing DNS rebinding access.
                host = self.headers.get("Host", "").split(":")[0].lower()
                allowed = {"127.0.0.1", "localhost", self.server.server_address[0]}
                if host not in allowed:
                    raise DomainError("This host is not allowed.", 403)
                if method == 'GET' and urlparse(self.path).path == '/api/health':
                    return self.json_response(200, {'application':'reunite','instance':instance_id(app.root),'pid':os.getpid(),
                                                    'mode':'test' if app.demo_mode else 'live',
                                                    'launch_id':app.launch_id,
                                                    'setup_required':bool(app.setup_key and not app.auth.has_admin())})
                cookies = SimpleCookie()
                try:
                    cookies.load(self.headers.get("Cookie", ""))
                except Exception:
                    cookies = SimpleCookie()
                token = cookies.get(self.cookie_name)
                session, self.new_cookie = app.auth.session(token.value if token else "")
                user = app.auth.current_user(session)
                parsed = urlparse(self.path)
                path, data = parsed.path, {}
                if method == "POST":
                    origin = self.headers.get("Origin")
                    if origin and urlparse(origin).netloc != self.headers.get("Host"):
                        raise DomainError("This request came from another site.", 403)
                    if not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), session["csrf"]):
                        raise DomainError("Refresh the page and try again.", 403)
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 0 or length > 9 * 1024 * 1024:
                        raise DomainError("This request is too large.", 413)
                    try:
                        data = json.loads(self.rfile.read(length) or b"{}")
                    except (ValueError, UnicodeError):
                        raise DomainError("The submitted data is invalid.") from None
                    if not isinstance(data, dict):
                        raise DomainError("The submitted data must be an object.")
                if method == "GET" and path == "/auth/microsoft":
                    return self.redirect(app.auth.microsoft_start(session))
                if method == "GET" and path == "/auth/microsoft/callback":
                    result = app.auth.microsoft_finish(session, {k: v[0] for k, v in parse_qs(parsed.query).items()})
                    self.new_cookie = app.auth.sign_in(session, result)
                    return self.redirect("/")
                if method == "GET" and path.startswith("/api/files/"):
                    app.require_login(user)
                    file_id = integer({"id": path.rsplit("/", 1)[-1]}, "id")
                    row = app.service.file_access(user, file_id)
                    target = resolve_upload(app.upload_dir, row["path"], must_exist=True)
                    return self.file_response(target, row["mime"])
                if path.startswith("/api/"):
                    return self.json_response(200, app.handle(self, method, path, session, user, data))
                page_paths = ("/", "/index.html", "/account/setup", "/setup")
                if method == "GET" and path in (*page_paths, "/app.js", "/style.css", "/support.js", "/support.css", "/handover.jpg", "/instrument-sans.ttf"):
                    target = app.root / "static" / ("index.html" if path in page_paths else path[1:])
                    return self.file_response(target, mimetypes.guess_type(str(target))[0] or "text/plain")
                raise DomainError("This page does not exist.", 404)
            except DomainError as exc:
                self.json_response(getattr(exc, "status", 400), error=str(exc))
            except (ValueError, TypeError, KeyError):
                self.json_response(400, error="Please check the submitted fields.")
            except Exception:
                import traceback
                traceback.print_exc()
                self.json_response(500, error="The action could not be completed. Please check the local server log.")

        def file_response(self, target, mime):
            if not target.is_file():
                raise DomainError("This file is unavailable.", 404)
            raw = target.read_bytes()
            self.send_response(200)
            self.headers_common(mime)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    return Handler


def serve(app, host="127.0.0.1", port=8765):
    server = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"CSA Lost & Found is ready at http://{host}:{port}", flush=True)
    print("Local demonstration mode" if app.demo_mode else "Live configuration mode", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
