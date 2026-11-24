"""Small local HTTP application. All authorization remains in the service layer."""
import base64
import binascii
import hashlib
import hmac
import io
import json
import mimetypes
import os
import secrets
import socket
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from lyfind.auth import AuthService
from lyfind.domain import DomainError
from lyfind.language import decorate
from lyfind.services import Service
from lyfind.support import SupportService
from lyfind.workspace_maintenance import WorkspaceMaintenance
from desktop_launcher import start
from threading import Lock, Thread
from lyfind.storage import resolve_upload


def instance_id(root):
    return hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:24]


def user_json(user):
    if not user:
        return None
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "phone": getattr(user, "phone", ""), "student_number": getattr(user, "student_number", ""),
            "first_name": getattr(user, "first_name", ""), "middle_name": getattr(user, "middle_name", ""),
            "last_name": getattr(user, "last_name", ""), "suffix": getattr(user, "suffix", ""),
            "blocked": user.blocked}


# Logo and icon files that live next to index.html. A fixed list, so no other file in static/ is reachable.
BRAND_FILES = {"/lyfind-logo.svg": "image/svg+xml", "/lyfind-logo-white.svg": "image/svg+xml",
               "/favicon-32.png": "image/png", "/apple-touch-icon.png": "image/png"}


def request_hostname(host_header):
    """Hostname from a Host header, without the port. Supports IPv6 brackets."""
    raw = (host_header or "").strip().lower()
    if not raw:
        return ""
    if raw.startswith("["):
        end = raw.find("]")
        return raw[1:end] if end != -1 else ""
    if raw.count(":") == 1:
        return raw.split(":")[0]
    return raw


def _ipv4_octets(host):
    parts = host.split(".")
    if len(parts) != 4:
        return None
    try:
        nums = [int(part) for part in parts]
    except ValueError:
        return None
    if any(part < 0 or part > 255 for part in nums):
        return None
    return nums


def is_loopback_host(host):
    name = (host or "").lower().strip("[]")
    if name in {"localhost", "127.0.0.1", "::1"}:
        return True
    octets = _ipv4_octets(name)
    return bool(octets and octets[0] == 127)


def is_private_lan_host(host):
    """Classroom Wi-Fi and similar private ranges — not a public internet hostname."""
    name = (host or "").lower().strip("[]").split("%", 1)[0]
    octets = _ipv4_octets(name)
    if octets:
        a, b = octets[0], octets[1]
        if a == 10:
            return True
        if a == 192 and b == 168:
            return True
        if a == 172 and 16 <= b <= 31:
            return True
        if a == 169 and b == 254:
            return True
        if a == 100 and 64 <= b <= 127:
            return True
        return False
    if ":" not in name:
        return False
    if name == "::1" or name.startswith("fe80:"):
        return True
    return name.startswith("fc") or name.startswith("fd")


def _configured_allowed_hosts():
    hosts = []
    raw = os.environ.get("ALLOWED_HOSTS", "")
    for item in raw.split(","):
        cleaned = request_hostname(item)
        if cleaned:
            hosts.append(cleaned)
    for env_key in ("RENDER_EXTERNAL_HOSTNAME", "RAILWAY_PUBLIC_DOMAIN", "PYTHONANYWHERE_DOMAIN"):
        cleaned = request_hostname(os.environ.get(env_key, ""))
        if cleaned:
            hosts.append(cleaned)
    return hosts


def trust_proxy_enabled():
    return os.environ.get("TRUST_PROXY", "0").strip().casefold() in {"1", "true", "yes"}


def client_ip(handler):
    """Return the caller IP, respecting reverse-proxy headers only when TRUST_PROXY=1."""
    direct = handler.client_address[0] if getattr(handler, "client_address", None) else "local"
    if not trust_proxy_enabled():
        return direct
    headers = getattr(handler, "headers", None)
    if headers is None:
        return direct
    forwarded = (headers.get("X-Forwarded-For") or "").strip()
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    real_ip = (headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip[:64]
    return direct


def host_is_allowed(host_header, bind_host):
    """Block DNS rebinding while allowing localhost, private LAN, or explicitly configured public hosts."""
    name = request_hostname(host_header)
    if not name:
        return False
    for allowed in _configured_allowed_hosts():
        if allowed == "*" or name == allowed or (allowed.startswith(".") and name.endswith(allowed)):
            return True
    bind = (bind_host or "").lower().strip("[]")
    if is_loopback_host(name):
        return True
    if bind in {"0.0.0.0", "::", ""}:
        return is_private_lan_host(name)
    return name == bind or name == bind.split("%", 1)[0]


def lan_ipv4_addresses():
    """Best-effort IPv4 addresses other devices on this Wi-Fi can use."""
    found = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.0.0.1", 1))
            address = sock.getsockname()[0]
            if is_private_lan_host(address) and address not in found:
                found.append(address)
    except OSError:
        pass
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = item[4][0]
            if is_private_lan_host(address) and address not in found:
                found.append(address)
    except OSError:
        pass
    return found


def bind_is_all_interfaces(host):
    return (host or "").lower().strip("[]") in {"0.0.0.0", "::", ""}


def probe_host(bind_host):
    """Address to use when checking if our own server is already answering."""
    return "127.0.0.1" if bind_is_all_interfaces(bind_host) else bind_host

class Application:
    def __init__(self, db, root, demo_mode=True, upload_dir=None, setup_key=None, launch_id=None):
        self.root = Path(root)
        self.upload_dir = Path(upload_dir) if upload_dir is not None else self.root / "data" / "uploads"
        self.setup_key = setup_key if not demo_mode else None
        self.launch_id = launch_id
        self.testing_lock = Lock()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.db, self.demo_mode = db, demo_mode
        self.service = Service(db, upload_dir=self.upload_dir)
        self.service.prepare_matching()
        if self.service.ai.status().get("local_only", True):
            self.service.matching.run_matching_unlocked()
        else:
            Thread(target=self._run_startup_matching_safe, daemon=True).start()
        self.auth = AuthService(db, demo_mode=demo_mode)
        self.support = SupportService(db)
        self.maintenance = WorkspaceMaintenance(db, self.root, self.upload_dir, demo_mode)

    def _run_startup_matching_safe(self):
        try:
            self.service.matching.run_matching_unlocked()
        except Exception:
            pass

    def testing_available(self, handler):
        return bool(self.launch_id and not self.demo_mode and handler.client_address[0] == '127.0.0.1')

    def handle(self, handler, method, path, session, user, data):
        if method == "GET":
            if path == "/api/config":
                return {"demo_mode": self.demo_mode, "microsoft_enabled": self.auth.microsoft_enabled,
                        "smtp_enabled": self.auth.smtp_enabled, "school_email_ready": self.auth.can_send_codes,
                        "school_domains": sorted(self.auth.school_domains), "csrf_token": session["csrf"],
                        "setup_required": bool(self.setup_key and not self.auth.has_admin()),
                        "testing_available": self.testing_available(handler)}
            if path == "/api/session":
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/dashboard":
                self.require_login(user)
                result = decorate(self.service.dashboard(user))
                if user.role == 'admin':
                    result['can_reset_demo'] = self.maintenance.can_reset
                return result
            if path == '/api/support':
                self.require_login(user)
                return self.support.overview(user)
            if path.startswith('/api/support/threads/'):
                self.require_login(user)
                return self.support.thread(user, integer({'id': path.rsplit('/',1)[-1]}, 'id'))
        if method == "POST":
            if path == '/api/testing/open':
                if not self.testing_available(handler):
                    raise DomainError('Open the local desktop launcher to use the testing shortcut.', 403)
                with self.testing_lock:
                    return {'url': start(self.root, browser=False, demo=True)}
            if path == '/api/auth/setup-admin':
                key = data.get('setup_key')
                if (not self.setup_key or not isinstance(key, str)
                        or handler.client_address[0] != '127.0.0.1'
                        or not hmac.compare_digest(key, self.setup_key)):
                    raise DomainError('Open the desktop launcher to create the first administrator.', 403)
                user = self.auth.setup_first_admin(data)
                self.setup_key = None
                handler.new_cookie = self.auth.sign_in(session, user)
                return {'user': user_json(user), 'csrf_token': session['csrf']}
            ip = client_ip(handler)
            if path == '/api/auth/guest/request':
                return self.auth.request_guest_code(data.get('email'), ip)
            if path == '/api/auth/guest/verify':
                user = self.auth.verify_guest_code(data.get('email'), data.get('code'), ip)
                handler.cookie_lifetime = 30*86400 if data.get('remember_browser') is True else 8*3600
                handler.new_cookie = self.auth.sign_in(session, user, lifetime=handler.cookie_lifetime)
                desk_saved = self.service.claim_desk_holds(user)
                return {'user': user_json(user), 'csrf_token': session['csrf'], 'desk_saved': desk_saved}
            if path == "/api/auth/demo":
                user = self.auth.demo_login(data.get("role"))
                handler.new_cookie = self.auth.sign_in(session, user)
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/auth/school/request":
                return self.auth.request_school_code(data.get("email", ""), ip)
            if path == "/api/auth/school/verify":
                return self.auth.verify_school_code(data.get("email", ""), data.get("code", ""), ip)
            if path == "/api/auth/school/password":
                user = self.auth.set_school_password(
                    data.get("email", ""), data.get("setup_token", ""), data.get("password", ""), data.get("confirm"),
                    data.get("name", ""), ip, data.get("first_name", ""), data.get("middle_name", ""),
                    data.get("last_name", ""), data.get("suffix", ""), data.get("phone", ""))
                handler.new_cookie = self.auth.sign_in(session, user)
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/auth/login":
                user = self.auth.password_login(data.get("email", ""), data.get("password", ""), ip)
                handler.new_cookie = self.auth.sign_in(session, user)
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/auth/reset/request":
                return self.auth.request_password_reset(data.get("email", ""), ip)
            if path == "/api/auth/reset/verify":
                return self.auth.verify_password_reset(data.get("email", ""), data.get("code", ""), ip)
            if path == "/api/auth/reset/password":
                user = self.auth.finish_password_reset(
                    data.get("email", ""), data.get("setup_token", ""), data.get("password", ""), data.get("confirm"), ip)
                handler.new_cookie = self.auth.sign_in(session, user)
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/auth/register":
                return self.auth.register(data.get("email", ""), ip, data.get("website", ""))
            if path == "/api/auth/register/resend":
                return self.auth.resend_signup_code(data.get("email", ""), ip)
            if path == "/api/auth/register/verify":
                return self.auth.verify_signup(data.get("email", ""), data.get("code", ""), ip)
            if path == "/api/auth/register/finish":
                user = self.auth.finish_guest(
                    data.get("email", ""), data.get("setup_token", ""), data.get("password", ""), data.get("confirm"),
                    ip, data.get("phone", ""), data.get("first_name", ""), data.get("middle_name", ""),
                    data.get("last_name", ""), data.get("suffix", ""), data.get("name", ""))
                desk_saved = self.service.claim_desk_holds(user)
                handler.new_cookie = self.auth.sign_in(session, user)
                return {"user": user_json(user), "csrf_token": session["csrf"], "desk_saved": desk_saved}
            if path == "/api/auth/staff":
                user = self.auth.staff_login(data.get("email", ""), data.get("password", ""), ip)
                handler.new_cookie = self.auth.sign_in(session, user)
                return {"user": user_json(user), "csrf_token": session["csrf"]}
            if path == "/api/logout":
                self.auth.logout(session)
                handler.new_cookie = ""
                return {"message": "Signed out."}
            self.require_login(user)
            if path == "/api/account/save":
                return {"user": user_json(self.service.update_profile(user, data))}
            if path == "/api/account/password":
                return self.service.change_password(user, data)
            if path == "/api/uploads":
                return self.save_upload(user, data)
            if path == "/api/ai/describe-photo":
                return self.describe_photo(user, data)
            if path == '/api/support/send':
                return self.support.send(user, data)
            if path == '/api/maintenance/backup':
                return self.maintenance.backup(user)
            if path == '/api/maintenance/reset-demo':
                result = self.maintenance.reset_demo(user, data.get('confirmed'))
                handler.new_cookie = ''
                return result
            if path == '/api/maintenance/clear-demo':
                result = self.maintenance.clear_demo(user, data.get('confirmed'))
                handler.new_cookie = ''
                return result
            s = self.service
            routes = {
                "/api/reports/lost": lambda: s.create_lost_report(user, data),
                "/api/reports/lost-for-guest": lambda: s.create_lost_report_for_guest(user, data, self.auth, ip),
                "/api/reports/desk-hold": lambda: s.desk_hold_status(user, integer(data, "hold_id")),
                "/api/reports/found": lambda: s.create_found_report(user, data),
                "/api/items/board": lambda: s.set_board_listing(user, integer(data, 'item_id'), data),
                "/api/items/receive": lambda: s.receive_item(user, data),
                "/api/matching/run": lambda: s.run_matching(user),
                "/api/matches/decide": lambda: s.decide_match(user, integer(data, "match_id"), boolean(data, "confirmed")),
                "/api/claims/submit": lambda: s.submit_claim(user, data),
                "/api/claims/online": lambda: s.verify_online(user, integer(data, "claim_id"), boolean(data, "passed"), data.get("reason", "")),
                "/api/claims/consent": lambda: s.record_consent(user, integer(data, "claim_id"), data),
                "/api/claims/in-person": lambda: s.verify_in_person(user, integer(data, "claim_id"), boolean(data, "passed"), data.get("reason", "")),
                "/api/claims/approve": lambda: s.approve_claim(user, integer(data, "claim_id"), data),
                "/api/claims/release": lambda: s.release_item(user, integer(data, "claim_id")),
                "/api/items/expire": lambda: s.expire_items(user),
                "/api/staff/save": lambda: s.manage_staff(user, data),
                "/api/reports/review": lambda: s.review_report(user, data),
                "/api/users/block": lambda: s.set_blocked(user, integer(data, "user_id"), boolean(data, "blocked"), data.get("reason", "")),
                "/api/users/password": lambda: s.set_person_password(user, data),
                "/api/roster/save": lambda: s.roster_save(user, data),
                "/api/roster/preview": lambda: s.roster_import(user, data.get("csv", ""), preview_only=True),
                "/api/roster/import": lambda: s.roster_import(user, data.get("csv", ""), expected=data.get("preview")) ,
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
        if len(content) > 7 * 1024 * 1024:
            raise DomainError("That photo is too big. Choose one that is 5 MB or smaller.", 413)
        try:
            raw = base64.b64decode(content, validate=True)
        except (ValueError, binascii.Error):
            raise DomainError("The image could not be read.") from None
        if not raw or len(raw) > 5 * 1024 * 1024:
            raise DomainError("That photo is too big. Choose one that is 5 MB or smaller.")
        mime, ext = inspect_photo(raw)
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

    def describe_photo(self, user, data):
        content = str(data.get("content", ""))
        if not content:
            raise DomainError("Choose a photo first.")
        if len(content) > 7 * 1024 * 1024:
            raise DomainError("That photo is too big. Choose one that is 5 MB or smaller.", 413)
        try:
            raw = base64.b64decode(content, validate=True)
        except (ValueError, binascii.Error):
            raise DomainError("The image could not be read.") from None
        if not raw or len(raw) > 5 * 1024 * 1024:
            raise DomainError("That photo is too big. Choose one that is 5 MB or smaller.")
        inspect_photo(raw)
        if not os.environ.get("GEMINI_API_KEY", "").strip():
            raise DomainError("Gemini AI auto-fill is not set up on this server.", 503)
        from lyfind.gemini_matching import GeminiClientAdapter
        try:
            return GeminiClientAdapter().describe_photo_bytes(raw)
        except Exception:
            raise DomainError("Gemini could not read that photo right now. You can still type the details manually.", 503) from None


# JPEG magic also covers iPhone Live Photo stills (MPO). HEIC is refused with a clearer message.
_PHOTO_KINDS = {
    "PNG": ("image/png", ".png", {"PNG"}),
    "JPEG": ("image/jpeg", ".jpg", {"JPEG", "MPO"}),
    "WEBP": ("image/webp", ".webp", {"WEBP"}),
}
_HEIF_BRANDS = {b"heic", b"heif", b"heix", b"mif1", b"msf1"}


def sniff_photo_kind(raw):
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if raw.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "WEBP"
    if len(raw) >= 12 and raw[4:8] == b"ftyp" and raw[8:12].rstrip(b" ").lower() in _HEIF_BRANDS:
        raise DomainError("iPhone HEIC photos are not accepted. Save or export the photo as JPEG, PNG, or WebP.")
    raise DomainError("Use a JPEG, PNG, or WebP photo. Other file types are not accepted.")


def inspect_photo(raw):
    kind = sniff_photo_kind(raw)
    mime, ext, formats = _PHOTO_KINDS[kind]
    try:
        from PIL import Image
    except ImportError:
        return mime, ext
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in formats:
                raise DomainError("This image is damaged or unsupported.")
            width, height = image.size
            if not width or not height:
                raise DomainError("This image is damaged or unsupported.")
            if width * height > 25_000_000:
                raise DomainError("Choose an image under 25 megapixels.")
            # Decode pixels instead of verify(): iPhone JPEG/MPO stills pass load()
            # even when EXIF, progressive, or a second Live Photo frame is present.
            image.load()
    except DomainError:
        raise
    except Exception:
        raise DomainError("This image is damaged or unsupported.") from None
    return mime, ext


def integer(data, name):
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).isdigit():
        raise DomainError("Choose a valid record.")
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise DomainError("Choose a valid record.") from None
    if result < 1:
        raise DomainError("Choose a valid record.")
    return result


def boolean(data, name):
    if not isinstance(data.get(name), bool):
        raise DomainError("That answer was not yes or no. Refresh the page and try again.")
    return data[name]


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CSA/1.0"

        def log_message(self, fmt, *args):
            # Avoid printing OAuth authorization codes or uploaded identity details.
            if self.path.startswith("/auth/"):
                return
            super().log_message(fmt, *args)

        def headers_common(self, content_type, cache=False):
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "public, max-age=3600" if cache else "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Permissions-Policy", "camera=(self), microphone=(), geolocation=(), payment=()")
            self.send_header("Cross-Origin-Opener-Policy", "same-origin")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if self.new_cookie is not None:
                via_https = trust_proxy_enabled() and (self.headers.get("X-Forwarded-Proto", "").strip().lower() == "https")
                secure = "; Secure" if (os.environ.get("COOKIE_SECURE", "0") == "1" or via_https) else ""
                self.send_header("Set-Cookie", f"{'reunite_test_session' if app.demo_mode else 'csa_session'}={self.new_cookie}; Path=/; HttpOnly; SameSite=Lax; Max-Age={self.cookie_lifetime if self.new_cookie else 0}{secure}")

        def json_response(self, status, data=None, error=None, fields=None):
            body = {"ok": error is None, **({"data": data} if error is None else {"error": error})}
            if fields:
                body["fields"] = fields
            raw = json.dumps(body, default=str).encode()
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
            self.cookie_lifetime = 8*3600
            try:
                with app.maintenance.request():
                    return self.dispatch_request(method)
            except DomainError as exc:
                self.json_response(exc.status, error=str(exc))

        def dispatch_request(self, method):
            try:
                # Restrict Host to localhost or private LAN IPs (not public names — DNS rebinding).
                if not host_is_allowed(self.headers.get("Host", ""), self.server.server_address[0]):
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
                token = cookies.get("reunite_test_session" if app.demo_mode else "csa_session")
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
                if method == "GET" and path.startswith("/assets/"):
                    name = Path(path).name
                    kinds = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml"}
                    kind = kinds.get(Path(name).suffix.lower())
                    if not kind:
                        raise DomainError("This page does not exist.", 404)
                    return self.file_response(app.root / "static" / "assets" / name, kind, cache=True)
                if method == "GET" and path in BRAND_FILES:
                    return self.file_response(app.root / "static" / path[1:], BRAND_FILES[path], cache=True)
                if method == "GET" and path in ("/", "/index.html", "/boot.js", "/app.js", "/style.css", "/support.js", "/support.css", "/accessibility.js", "/accessibility.css", "/report-composer.js", "/report-composer.css"):
                    target = app.root / "static" / ("index.html" if path == "/" else path[1:])
                    return self.file_response(target, mimetypes.guess_type(str(target))[0] or "text/plain")
                raise DomainError("This page does not exist.", 404)
            except DomainError as exc:
                address = urlparse(self.path).path
                if method == "GET" and not address.startswith(("/api/", "/assets/")) and getattr(exc, "status", 400) in (404, 503) \
                        and "text/html" in self.headers.get("Accept", ""):
                    # A person who typed a wrong address or opened an unavailable sign-in lands on the app, not on raw JSON.
                    return self.redirect("/")
                self.json_response(getattr(exc, "status", 400), error=str(exc), fields=getattr(exc, "fields", None))
            except (ValueError, TypeError, KeyError):
                self.json_response(400, error="Please check the submitted fields.")
            except Exception:
                import traceback
                traceback.print_exc()
                self.json_response(500, error="The action could not be completed. Please check the local server log.")

        def file_response(self, target, mime, cache=False):
            if not target.is_file():
                raise DomainError("This file is unavailable.", 404)
            raw = target.read_bytes()
            self.send_response(200)
            self.headers_common(mime, cache=cache)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    return Handler


def serve(app, host="127.0.0.1", port=8765):
    server = ThreadingHTTPServer((host, port), make_handler(app))
    print("LyFind is ready. Open it in a browser — this is a local website, not an App Store app.", flush=True)
    print(f"This computer:  http://127.0.0.1:{port}", flush=True)
    if bind_is_all_interfaces(host):
        lan = lan_ipv4_addresses()
        if lan:
            for address in lan:
                print(f"Other devices on the same Wi-Fi:  http://{address}:{port}", flush=True)
        else:
            print("Other devices: could not detect a LAN IP. On this computer run ipconfig (Windows) or ifconfig (Mac) and open http://THAT-IP:%s" % port, flush=True)
        print("Phones, Windows, and other PCs share this computer's database. Do not start a second copy unless you want separate data.", flush=True)
        print("macOS may ask to allow incoming connections. Windows Defender Firewall may block Python until you allow it.", flush=True)
        print("This-computer-only: python3 main.py --host 127.0.0.1", flush=True)
    elif is_loopback_host(host):
        print("Other devices cannot connect (listening on this computer only). For the same Wi-Fi, start with: python3 main.py --lan", flush=True)
    else:
        print(f"Network address:  http://{host}:{port}", flush=True)
    print("Demonstration mode (sample accounts enabled). Fictional records; codes appear on screen when email is disconnected." if app.demo_mode else "Live mode", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
