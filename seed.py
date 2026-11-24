"""Fictional sample records for local demonstrations, never used in live mode."""
import struct
import zlib
from datetime import date, timedelta
from pathlib import Path

from services import Service
from users import User, hash_password


def sample_image(kind="bag"):
    """Draw a small illustrative sample without any third-party dependency."""
    width, height = 360, 240
    rows = []
    for y in range(height):
        pixels = bytearray()
        for x in range(width):
            color = (237, 240, 231)
            if 65 < y < 205 and 90 < x < 270:
                color = (43, 65, 58) if kind == "bag" else (164, 119, 72)
            if kind == "bag" and 48 < y < 80 and (115 < x < 130 or 230 < x < 245):
                color = (43, 65, 58)
            if kind == "bag" and 43 < y < 54 and 115 < x < 245:
                color = (43, 65, 58)
            if 123 < y < 128 and 108 < x < 252:
                color = (196, 186, 152)
            if kind != "bag" and 144 < y < 174 and 228 < x < 276:
                color = (115, 78, 47)
            pixels.extend(color)
        rows.append(b"\0" + bytes(pixels))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def seed_demo(db, upload_dir, *, prefix=''):
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO users(name,email,role) VALUES(?,?,?) ON CONFLICT(email) DO NOTHING",
            ("Jamie Flores", "demo.student2@example.test", "student"),
        )
        if conn.execute("SELECT 1 FROM users WHERE email='demo.admin@example.test'").fetchone():
            return
        users = {}
        for role, name in (("admin", "CSA Admin Reyes"), ("student", "Maria Santos"),
                           ("professor", "Prof. Daniel Cruz"), ("guest", "Alex Rivera")):
            uid = conn.execute("INSERT INTO users(name,email,role,password_hash) VALUES(?,?,?,?)",
                               (name, f"demo.{role}@example.test", role, hash_password("DemoOnly!2026") if role == "admin" else "")).lastrowid
            users[role] = User.from_row(conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
    s = Service(db, upload_dir=upload_dir)
    today = date.today()
    day = (today - timedelta(days=1)).isoformat()
    def upload(kind, owner, picture):
        path = upload_dir / f"{prefix}sample-{picture}-{kind}.png"
        path.write_bytes(sample_image(picture))
        with db.connect() as conn:
            return conn.execute("INSERT INTO uploads(owner_id,kind,path,mime,original_name) VALUES(?,?,?,?,?)",
                                (owner.id, kind, path.name, "image/png", f"Illustrative sample {picture}.png")).lastrowid
    found = s.create_found_report(users["professor"], {
        "category": "bags", "description": "Dark green backpack found near the library tables",
        "place": "Main Library", "date_found": day, "turn_in_deadline": today.isoformat()})
    s.receive_item(users["admin"], {
        "category": "bags", "description": "Dark green canvas backpack", "color": "Green", "brand": "Campus",
        "board_type": "Backpack",
        "place": "Main Library", "date_found": day, "found_report_id": found["id"],
        "private_details": "Small yellow star keychain inside the front pocket; initials MS on inner label",
        "photo_id": upload("item_photo", users["admin"], "bag")})
    s.receive_item(users["admin"], {
        "category": "wallets", "description": "Brown leather folding wallet", "color": "Brown", "brand": "Unbranded",
        "place": "Student Center", "date_found": today.isoformat(),
        "private_details": "Blue receipt dated Monday tucked behind a red loyalty card",
        "photo_id": upload("item_photo", users["admin"], "wallet")})
    s.create_lost_report(users["student"], {
        "category": "bags", "description": "My green Campus backpack with a star keychain",
        "color": "Green", "brand": "Campus", "place": "Main Library", "date_lost": day,
        "identifying_marks": "MS on inner label, yellow star keychain"})
    s.create_lost_report(users["guest"], {
        "category": "wallets", "description": "Brown wallet lost while visiting campus",
        "color": "Brown", "brand": "Unbranded", "place": "Student Center", "date_lost": today.isoformat(),
        "identifying_marks": "Red loyalty card and blue receipt"})
    s.create_found_report(users["professor"], {
        "category": "keys", "description": "Two silver keys on a blue ring",
        "place": "Science Building", "date_found": today.isoformat(),
        "turn_in_deadline": (today + timedelta(days=1)).isoformat()})
    s.run_matching(users["admin"])
