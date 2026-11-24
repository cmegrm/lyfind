"""Standard WSGI entry point for online hosting (PythonAnywhere, Render, Railway, Gunicorn)."""
import io
import json
import mimetypes
import os
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from lyfind.auth import load_environment
from lyfind.database import Database
from lyfind.domain import DomainError
from lyfind.storage import resolve_upload
from lyfind.web import (
    Application,
    BRAND_FILES,
    host_is_allowed,
    instance_id,
    integer,
    trust_proxy_enabled,
)

ROOT = Path(__file__).resolve().parent
STATIC_FILES = {
    "/", "/index.html", "/boot.js", "/app.js", "/style.css", "/support.js", "/support.css",
    "/accessibility.js", "/accessibility.css", "/report-composer.js", "/report-composer.css",
}


class _Headers(dict):
    def get(self, key, default=""):
        return super().get(key.lower(), default)


class _WSGIContext:
    def __init__(self, environ):
        headers = {}
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                headers[key[5:].replace("_", "-").lower()] = value
        if environ.get("CONTENT_TYPE"):
            headers["content-type"] = environ["CONTENT_TYPE"]
        if environ.get("CONTENT_LENGTH"):
            headers["content-length"] = environ["CONTENT_LENGTH"]
        self.headers = _Headers(headers)
        self.client_address = (environ.get("REMOTE_ADDR", "127.0.0.1"), 0)
        self.new_cookie = None
        self.cookie_lifetime = 8 * 3600


def _common_headers(app, ctx, content_type, cache=False, extra=None):
    headers = [
        ("Content-Type", content_type),
        ("Cache-Control", "public, max-age=3600" if cache else "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "same-origin"),
        ("X-Frame-Options", "DENY"),
        ("Permissions-Policy", "camera=(self), microphone=(), geolocation=(), payment=()"),
        ("Cross-Origin-Opener-Policy", "same-origin"),
        ("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"),
    ]
    if ctx.new_cookie is not None:
        via_https = trust_proxy_enabled() and (ctx.headers.get("X-Forwarded-Proto", "").strip().lower() == "https")
        secure = "; Secure" if (os.environ.get("COOKIE_SECURE", "0") == "1" or via_https) else ""
        cookie_name = "reunite_test_session" if app.demo_mode else "csa_session"
        age = ctx.cookie_lifetime if ctx.new_cookie else 0
        headers.append(("Set-Cookie", f"{cookie_name}={ctx.new_cookie}; Path=/; HttpOnly; SameSite=Lax; Max-Age={age}{secure}"))
    if extra:
        headers.extend(extra)
    return headers


def _status_line(code):
    try:
        phrase = HTTPStatus(code).phrase
    except ValueError:
        phrase = "Error"
    return f"{code} {phrase}"


def make_wsgi_app(app):
    """Wrap an Application instance as a PEP 3333 WSGI callable."""

    def wsgi_app(environ, start_response):
        ctx = _WSGIContext(environ)
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        path = environ.get("PATH_INFO") or "/"
        query = environ.get("QUERY_STRING") or ""
        def _respond(code, raw, content_type, cache=False, extra=None):
            headers = _common_headers(app, ctx, content_type, cache=cache, extra=extra)
            headers.append(("Content-Length", str(len(raw))))
            start_response(_status_line(code), headers)
            return [raw]

        def _json_out(_app, _ctx, _start, code, data=None, error=None, fields=None):
            body = {"ok": error is None, **({"data": data} if error is None else {"error": error})}
            if fields:
                body["fields"] = fields
            return _respond(code, json.dumps(body, default=str).encode(), "application/json; charset=utf-8")

        def _file_out(target, mime, cache=False):
            if not target.is_file():
                raise DomainError("This file is unavailable.", 404)
            return _respond(200, target.read_bytes(), mime, cache=cache)

        if method not in ("GET", "POST"):
            return _json_out(app, ctx, start_response, 405, error="Method not allowed.")

        try:
            with app.maintenance.request():
                host_header = ctx.headers.get("Host", "") or environ.get("SERVER_NAME", "")
                if not host_is_allowed(host_header, os.environ.get("HOST", "0.0.0.0")):
                    raise DomainError("This host is not allowed.", 403)
                if method == "GET" and path == "/api/health":
                    return _json_out(app, ctx, start_response, 200, {
                        "application": "reunite",
                        "instance": instance_id(app.root),
                        "pid": os.getpid(),
                        "mode": "test" if app.demo_mode else "live",
                        "launch_id": app.launch_id,
                        "setup_required": bool(app.setup_key and not app.auth.has_admin()),
                    })
                cookies = SimpleCookie()
                try:
                    cookies.load(ctx.headers.get("Cookie", ""))
                except Exception:
                    cookies = SimpleCookie()
                token = cookies.get("reunite_test_session" if app.demo_mode else "csa_session")
                session, ctx.new_cookie = app.auth.session(token.value if token else "")
                user = app.auth.current_user(session)
                data = {}
                if method == "POST":
                    origin = ctx.headers.get("Origin")
                    if origin and urlparse(origin).netloc != host_header:
                        raise DomainError("This request came from another site.", 403)
                    import hmac
                    if not hmac.compare_digest(ctx.headers.get("X-CSRF-Token", ""), session["csrf"]):
                        raise DomainError("Refresh the page and try again.", 403)
                    length_raw = ctx.headers.get("Content-Length", "0") or "0"
                    length = int(length_raw)
                    if length < 0 or length > 9 * 1024 * 1024:
                        raise DomainError("This request is too large.", 413)
                    body_stream = environ.get("wsgi.input") or io.BytesIO()
                    raw_body = body_stream.read(length) if length else b"{}"
                    try:
                        data = json.loads(raw_body or b"{}")
                    except (ValueError, UnicodeError):
                        raise DomainError("The submitted data is invalid.") from None
                    if not isinstance(data, dict):
                        raise DomainError("The submitted data must be an object.")
                if method == "GET" and path == "/auth/microsoft":
                    return _respond(303, b"", "text/plain; charset=utf-8", extra=[("Location", app.auth.microsoft_start(session))])
                if method == "GET" and path == "/auth/microsoft/callback":
                    result = app.auth.microsoft_finish(session, {k: v[0] for k, v in parse_qs(query).items()})
                    ctx.new_cookie = app.auth.sign_in(session, result)
                    return _respond(303, b"", "text/plain; charset=utf-8", extra=[("Location", "/")])
                if method == "GET" and path.startswith("/api/files/"):
                    app.require_login(user)
                    file_id = integer({"id": path.rsplit("/", 1)[-1]}, "id")
                    row = app.service.file_access(user, file_id)
                    target = resolve_upload(app.upload_dir, row["path"], must_exist=True)
                    return _file_out(target, row["mime"])
                if path.startswith("/api/"):
                    return _json_out(app, ctx, start_response, 200, app.handle(ctx, method, path, session, user, data))
                if method == "GET" and path.startswith("/assets/"):
                    name = Path(path).name
                    kinds = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml"}
                    kind = kinds.get(Path(name).suffix.lower())
                    if not kind:
                        raise DomainError("This page does not exist.", 404)
                    return _file_out(app.root / "static" / "assets" / name, kind, cache=True)
                if method == "GET" and path in BRAND_FILES:
                    return _file_out(app.root / "static" / path[1:], BRAND_FILES[path], cache=True)
                if method == "GET" and path in STATIC_FILES:
                    target = app.root / "static" / ("index.html" if path == "/" else path[1:])
                    return _file_out(target, mimetypes.guess_type(str(target))[0] or "text/plain")
                raise DomainError("This page does not exist.", 404)
        except DomainError as exc:
            if (method == "GET" and not path.startswith(("/api/", "/assets/"))
                    and getattr(exc, "status", 400) in (404, 503)
                    and "text/html" in ctx.headers.get("Accept", "")):
                return _respond(303, b"", "text/plain; charset=utf-8", extra=[("Location", "/")])
            return _json_out(app, ctx, start_response, getattr(exc, "status", 400), error=str(exc), fields=getattr(exc, "fields", None))
        except (ValueError, TypeError, KeyError):
            return _json_out(app, ctx, start_response, 400, error="Please check the submitted fields.")
        except Exception:
            import traceback
            traceback.print_exc()
            return _json_out(app, ctx, start_response, 500, error="The action could not be completed. Please check the server log.")

    return wsgi_app


def create_application(root=ROOT):
    load_environment(Path(root) / ".env")
    demo = os.environ.get("LYFIND_DEMO", "0").strip().casefold() in {"1", "true", "yes"}
    db_path = Path(os.environ.get("LYFIND_DB_PATH") or (Path(root) / "data" / ("demo.sqlite3" if demo else "csa.sqlite3")))
    upload_dir = Path(os.environ.get("LYFIND_UPLOAD_DIR") or (Path(root) / "data" / ("test-uploads" if demo else "uploads")))
    db = Database(db_path)
    db.initialize()
    if demo:
        from lyfind.seed import ensure_demo_passwords, ensure_demo_roster, seed_demo
        upload_dir.mkdir(parents=True, exist_ok=True)
        seed_demo(db, upload_dir)
        ensure_demo_passwords(db)
        ensure_demo_roster(db)
    app = Application(db, root, demo_mode=demo, upload_dir=upload_dir)
    return make_wsgi_app(app)


_cached_app = None


def application(environ, start_response):
    """Lazy-initialized WSGI callable for PythonAnywhere, Gunicorn, and other WSGI hosts."""
    global _cached_app
    if _cached_app is None:
        _cached_app = create_application()
    return _cached_app(environ, start_response)
