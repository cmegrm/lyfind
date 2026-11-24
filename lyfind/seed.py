"""Fictional sample records for local demonstrations, never used in live mode."""
import struct
import zlib
from datetime import date, timedelta
from pathlib import Path

from lyfind.services import Service
from lyfind.users import User, hash_password, split_display_name


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


DEMO_PASSWORD = "DemoOnly!2026"


def ensure_demo_passwords(db):
    """Older demo databases were seeded without passwords for public roles."""
    with db.connect() as conn:
        rows = conn.execute("SELECT id FROM users WHERE email LIKE 'demo.%@example.test' AND COALESCE(password_hash,'')=''").fetchall()
        for row in rows:
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(DEMO_PASSWORD), row["id"]))


def ensure_demo_roster(db):
    """The sample student and professor may sign in with a school email code. Others need CSA to add them."""
    with db.connect() as conn:
        conn.execute("DELETE FROM roster WHERE lower(email)='2025-2-01345@lpunetwork.edu.ph'")
        for email, name, role, number in (("demo.student@example.test", "Maria Santos", "student", "2025-2-00001"),
                                          ("demo.professor@example.test", "Prof. Daniel Cruz", "professor", ""),
                                          ("2000-9-99999@lpunetwork.edu.ph", "Sample Student", "student", "2000-9-99999"),
                                          ("d.cruz@lpu.edu.ph", "Sample Professor", "professor", "")):
            conn.execute("INSERT OR IGNORE INTO roster(email,name,student_number,role) VALUES(?,?,?,?)", (email, name, number, role))
        conn.execute("UPDATE users SET student_number='2025-2-00001' WHERE email='demo.student@example.test' AND student_number=''")


DEMO_IMAGES = Path(__file__).resolve().parents[1] / "demo_images"


def seed_demo(db, upload_dir):
    """Fictional records. Photos in demo_images/ are sample shots (including internet backpack photos for matching)."""
    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    with db.connect() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email='demo.admin@example.test'").fetchone():
            return
        users = {}
        for role, name in (("admin", "CSA Admin Reyes"), ("student", "Maria Santos"),
                           ("professor", "Prof. Daniel Cruz"), ("guest", "Alex Rivera")):
            first, middle, last, suffix = split_display_name(name)
            uid = conn.execute(
                "INSERT INTO users(email,role,password_hash,first_name,middle_name,last_name,suffix) VALUES(?,?,?,?,?,?,?)",
                (f"demo.{role}@example.test", role, hash_password(DEMO_PASSWORD), first, middle, last, suffix)).lastrowid
            users[role] = User.from_row(conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
    ensure_demo_roster(db)
    s = Service(db, upload_dir=upload_dir)
    s.prepare_matching()  # uses DINOv2 + CLIP when installed, typed details otherwise
    today = date.today()
    day = (today - timedelta(days=1)).isoformat()

    def upload(kind, owner, picture):
        source = DEMO_IMAGES / f"{picture}.jpg"
        if source.is_file():
            name, mime, raw = f"sample-{picture}-{kind}.jpg", "image/jpeg", source.read_bytes()
        else:
            name, mime, raw = f"sample-{picture}-{kind}.png", "image/png", sample_image("bag" if "backpack" in picture else "wallet")
        (upload_dir / name).write_bytes(raw)
        with db.connect() as conn:
            return conn.execute("INSERT INTO uploads(owner_id,kind,path,mime,original_name) VALUES(?,?,?,?,?)",
                                (owner.id, kind, name, mime, f"Demo photo {picture}")).lastrowid

    found = s.create_found_report(users["professor"], {
        "category": "bags", "description": "Dark green backpack found near the library tables",
        "place": "Academic Resource Center (Library)", "date_found": day, "turn_in_deadline": today.isoformat()})
    s.receive_item(users["admin"], {
        "category": "bags", "description": "Dark green canvas backpack with brass zippers", "color": "Green", "brand": "Campus",
        "place": "Academic Resource Center (Library)", "date_found": day, "found_report_id": found["id"],
        "private_details": "Small yellow star keychain inside the front pocket; initials MS on inner label",
        "photo_id": upload("item_photo", users["admin"], "backpack-found")})
    s.receive_item(users["admin"], {
        "category": "wallets", "description": "Brown leather folding wallet", "color": "Brown", "brand": "Unbranded",
        "place": "Freedom Park", "date_found": today.isoformat(),
        "private_details": "Blue receipt dated Monday tucked behind a red loyalty card",
        "photo_id": upload("item_photo", users["admin"], "wallet-found")})
    s.receive_item(users["admin"], {
        "category": "electronics", "description": "Black smartphone with a plain dark case", "color": "Black", "brand_choice": "unknown",
        "place": "Jose P. Laurel (JPL) Building", "date_found": day,
        "private_details": "Small scratch on the lower left corner; lock screen shows a mountain",
        "photo_id": upload("item_photo", users["admin"], "phone-found")})
    s.create_lost_report(users["student"], {
        "category": "bags", "description": "My dark green canvas backpack with brass zippers and a star keychain",
        "color": "Green", "brand": "Campus", "place": "Academic Resource Center (Library)", "date_lost": day,
        "identifying_marks": "MS on inner label, yellow star keychain",
        "photo_id": upload("report_photo", users["student"], "backpack-owner")})
    s.create_lost_report(users["guest"], {
        "category": "wallets", "description": "Brown leather wallet lost while visiting campus",
        "color": "Brown", "brand": "Unbranded", "place": "Freedom Park", "date_lost": today.isoformat(),
        "identifying_marks": "Red loyalty card and blue receipt"})
    s.create_found_report(users["professor"], {
        "category": "keys", "description": "Two silver keys on a blue ring",
        "place": "Sotero H. Laurel (SHL) Building", "date_found": today.isoformat(),
        "turn_in_deadline": (today + timedelta(days=1)).isoformat()})
    # A second guest report stays unchecked so the staff list shows what a flagged report looks like.
    s.create_lost_report(users["guest"], {
        "category": "other", "description": "Silver water bottle with a dented lid",
        "color": "Silver", "brand_choice": "unknown", "place": "Gymnasium", "date_lost": day})
    with db.connect() as conn:
        wallet_report = conn.execute("SELECT id FROM lost_reports WHERE category='wallets'").fetchone()
    s.review_report(users["admin"], {"kind": "lost", "id": wallet_report["id"], "action": "checked"})
    s.run_matching(users["admin"])
    # One claim is already in progress so the staff To do list shows real work.
    with db.connect() as conn:
        wallet = conn.execute("SELECT m.id,m.item_id,m.report_id FROM matches m JOIN items i ON i.id=m.item_id "
                              "WHERE i.category='wallets' AND m.status='suggested'").fetchone()
    if wallet:
        s.decide_match(users["admin"], wallet["id"], True)
        s.submit_claim(users["guest"], {"item_id": wallet["item_id"], "report_id": wallet["report_id"], "consent": True,
                                        "answers": {"details": "A red loyalty card, and a blue receipt tucked behind the cards."}})
