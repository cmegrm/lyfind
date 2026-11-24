"""Run a complete ownership workflow in a disposable demonstration database.

The images are generated illustrations, not real identity or release evidence.
Running this script never modifies the application's own database.
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lyfind.database import Database
from lyfind.domain import Item
from lyfind.seed import sample_image, seed_demo
from lyfind.services import Service
from lyfind.users import DomainError, User


def demonstrate():
    print("CSA AUTOMATED LOST AND FOUND SYSTEM")
    print("Complete workflow evidence using fictional identities and illustrative images")
    print("The temporary database is separate from the running application.\n")
    with tempfile.TemporaryDirectory(prefix="csa-workflow-") as directory:
        root = Path(directory)
        uploads = root / "uploads"
        db = Database(root / "demo.sqlite3")
        db.initialize()
        seed_demo(db, uploads)
        service = Service(db, upload_dir=uploads)
        with db.connect() as conn:
            admin = User.from_row(conn.execute("SELECT * FROM users WHERE role='admin'").fetchone())
            owner = User.from_row(conn.execute("SELECT * FROM users WHERE role='student'").fetchone())
            report = dict(conn.execute("SELECT * FROM lost_reports WHERE owner_id=? AND category='bags'",
                                       (owner.id,)).fetchone())
            item = dict(conn.execute("SELECT * FROM items WHERE category='bags'").fetchone())

        print(f"[1] CSA has physically received item {item['id']}: {item['description']}")
        print(f"    Item status: {item['status']}")
        print(f"[2] {owner.name} has submitted lost report {report['id']}")
        print(f"    Report status: {report['status']}")
        service.run_matching(admin)
        with db.connect() as conn:
            match = dict(conn.execute("SELECT * FROM matches WHERE report_id=? AND item_id=?",
                                      (report["id"], item["id"])).fetchone())
        print(f"[3] Matching selected {match['method']}: {match['score']:.1f}% ({match['level']})")
        print("    Scores remain restricted to CSA; no owner suggestion notice is sent.")
        service.decide_match(admin, match["id"], True)
        owner_dashboard = service.dashboard(owner)
        assert owner_dashboard["matches"] and "score" not in owner_dashboard["matches"][0]
        print("[4] CSA confirms the match; the owner receives a verification invitation.")
        claim = service.submit_claim(owner, {
            "item_id": item["id"], "report_id": report["id"],
            "answers": {"private_identifying_details": "Yellow star keychain and initials MS on the inner label"},
            "consent": True})
        print(f"[5] Owner submits identifying answers and submission agreement: {claim['status']}")
        claim = service.verify_online(admin, claim["id"], True)
        print(f"[6] CSA passes online verification: {claim['status']}; item is under_verification")
        claim = service.record_consent(admin, claim["id"], {
            "in_person": True,
            "purpose": "Illustrative classroom demo of identity and release evidence capture"})
        assert claim["consent_at"]
        print("[7] CSA records explicit in-person consent with its time and purpose.")
        claim = service.verify_in_person(admin, claim["id"], True)
        print(f"[8] CSA passes the in-person identity and ownership check: {claim['status']}")
        evidence = {}
        for kind in ("claimant_photo", "id_photo", "signature"):
            service.authorize_upload(admin, kind, claim["id"])
            filename = f"illustrative-{kind}.png"
            (uploads / filename).write_bytes(sample_image())
            with db.connect() as conn:
                evidence[kind] = conn.execute(
                    "INSERT INTO uploads(owner_id,claim_id,kind,path,mime,original_name) VALUES(?,?,?,?,?,?)",
                    (admin.id, claim["id"], kind, filename, "image/png", filename)).lastrowid
        print("[9] Save three generated sample evidence images after consent.")
        print("    These images simulate evidence fields; they are not real identity documents or signatures.")
        claim = service.approve_claim(admin, claim["id"], {
            **evidence, "handover_note": "Fictional classroom handover demonstration"})
        print(f"[10] Both verification passes, consent, and evidence permit approval: {claim['status']}")
        claim = service.release_item(admin, claim["id"])
        with db.connect() as conn:
            final_item = dict(conn.execute("SELECT * FROM items WHERE id=?", (item["id"],)).fetchone())
            final_report = dict(conn.execute("SELECT * FROM lost_reports WHERE id=?", (report["id"],)).fetchone())
        assert final_item["status"] == "released" and final_report["status"] == "closed"
        assert claim["released_by"] == admin.id and claim["released_at"]
        print(f"[11] CSA records physical handover: item={final_item['status']}; claim={claim['status']}; report={final_report['status']}")

        print("\nREJECTED INVALID OPERATIONS")
        try:
            service.submit_claim(owner, {"item_id": item["id"], "report_id": report["id"],
                                       "answers": {"details": "Second claim attempt"}, "consent": True})
        except DomainError as error:
            print(f"[X1] Second claim on the released item: REJECTED - {error}")
        else:
            raise AssertionError("A second released item claim was accepted")
        try:
            service.approve_claim(owner, claim["id"], {})
        except DomainError as error:
            print(f"[X2] Student attempts CSA approval: REJECTED - {error}")
        else:
            raise AssertionError("A student approved a claim")
        protected_item = Item(item["id"], "released")
        try:
            protected_item.status = "available"
        except AttributeError:
            print("[X3] Direct assignment to item.status: REJECTED - read-only property")
        else:
            raise AssertionError("The protected status accepted direct assignment")
        try:
            protected_item.change_status("available")
        except DomainError as error:
            print(f"[X4] Released to available state transition: REJECTED - {error}")
        else:
            raise AssertionError("A released item became available")
        try:
            with db.connect() as conn:
                conn.execute("UPDATE audit_logs SET detail='rewritten'")
        except sqlite3.IntegrityError as error:
            print(f"[X5] Rewrite saved audit history: REJECTED - {error}")
        else:
            raise AssertionError("Audit history was rewritten")
        print("\nPERSISTED AUDIT HISTORY")
        with db.connect() as conn:
            entries = conn.execute(
                "SELECT a.action,a.detail,COALESCE(u.name,'System') AS actor "
                "FROM audit_logs a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id").fetchall()
            for entry in entries:
                print(f"  {entry['actor']}: {entry['action']} | {entry['detail']}")
        assert any(entry["action"] == "CLAIM_REFUSED" for entry in entries)
        assert any(entry["action"] == "DENIED_APPROVE_CLAIM" for entry in entries)
        print("\nPASS: full workflow completed and every demonstrated invalid operation was rejected.")


if __name__ == "__main__":
    demonstrate()
