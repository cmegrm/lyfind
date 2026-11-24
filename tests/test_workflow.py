"""Behavioral checks for the persistent ownership and release workflow.

All identities and file records are temporary fixtures. No external service is used.
"""
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lyfind.database import Database
from lyfind.domain import Claim, Item
from lyfind.matching import (AIMatchingService, ClipAdapter, EmbeddingAdapter, MatchingService,
                      MatchingServiceFactory, TypedDetailsMatchingService)
from lyfind.auth import AuthService
from lyfind.services import Service
from lyfind.users import (CSAAdministrator, DomainError, Guest, Professor, Student, User,
                   check_password, hash_password, require_permission)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Database(Path(self.temp.name) / "test.sqlite3")
        self.db.initialize()
        self.service = Service(self.db, self.temp.name,
                               matcher=TypedDetailsMatchingService())
        self.admin = self.user("admin", "CSA Test Administrator")
        self.student = self.user("student", "Student One")
        self.other = self.user("student", "Student Two")
        self.guest = self.user("guest", "Guest One")
        self.today = date.today().isoformat()

    def user(self, role, name):
        with self.db.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users(first_name,email,role) VALUES(?,?,?)",
                (name, name.replace(" ", ".").lower() + "@example.test", role))
            row = conn.execute("SELECT * FROM users WHERE id=?",
                               (cursor.lastrowid,)).fetchone()
        return User.from_row(row)

    def row(self, table, record_id):
        with self.db.connect() as conn:
            return dict(conn.execute(f"SELECT * FROM {table} WHERE id=?",
                                     (record_id,)).fetchone())

    def upload(self, kind, owner=None, claim_id=None, created_at=None):
        owner = owner or self.admin
        from lyfind.seed import sample_image
        (Path(self.temp.name) / "test-image.png").write_bytes(sample_image())
        with self.db.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO uploads(owner_id,claim_id,kind,path,mime,original_name) "
                "VALUES(?,?,?,?,?,?)",
                (owner.id, claim_id, kind, "test-image.png", "image/png", "test-image.png"))
            if created_at:
                conn.execute("UPDATE uploads SET created_at=? WHERE id=?",
                             (created_at, cursor.lastrowid))
        return cursor.lastrowid

    def report(self, user=None, **overrides):
        data = dict(category="electronics", description="Black study headphones",
                    color="black", brand="Acme", place="Library", date_lost=self.today,
                    identifying_marks="A green label under the left ear cup")
        data.update(overrides)
        return self.service.create_lost_report(user or self.student, data)

    def item(self, **overrides):
        data = dict(category="electronics", description="Turned in black headphones",
                    color="black", brand="Acme", place="Library", date_found=self.today,
                    private_details="PRIVATE-IDENTIFIER-CX147 green label left ear cup",
                    photo_id=self.upload("item_photo"))
        data.update(overrides)
        return self.service.receive_item(self.admin, data)

    def confirm(self, report, item):
        self.service.run_matching(self.admin)
        with self.db.connect() as conn:
            match = conn.execute("SELECT * FROM matches WHERE report_id=? AND item_id=?",
                                 (report["id"], item["id"])).fetchone()
        self.assertIsNotNone(match, "Expected matching test fixtures to produce a suggestion")
        if match["status"] == "suggested":
            self.service.decide_match(self.admin, match["id"], True)
        return dict(match)

    def claim(self, user=None, report=None, item=None):
        user = user or self.student
        report = report or self.report(user)
        item = item or self.item()
        self.confirm(report, item)
        return self.service.submit_claim(user, dict(
            item_id=item["id"], report_id=report["id"],
            answers={"details": "green label under the left ear cup"}, consent=True))

    def verified_claim(self):
        claim = self.claim()
        self.service.verify_online(self.admin, claim["id"], True)
        self.service.record_consent(self.admin, claim["id"], dict(
            in_person=True, purpose="Capture ownership and release evidence"))
        return self.service.verify_in_person(self.admin, claim["id"], True)

    def evidence(self, claim_id, **overrides):
        result = {kind: self.upload(kind, claim_id=claim_id)
                  for kind in ("claimant_photo", "id_photo", "signature")}
        result.update(overrides)
        return result

    def test_missing_physical_photo_prevents_inventory_record(self):
        photo=self.upload("item_photo")
        (Path(self.temp.name)/"test-image.png").unlink()
        with self.assertRaises(DomainError):self.service.receive_item(self.admin,dict(category='bags',description='Bag',place='Library',date_found=self.today,private_details='Label',photo_id=photo))
        with self.db.connect() as conn:self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0],0)

    def test_invalid_ai_output_uses_fallback_instead_of_false_strong_score(self):
        class InvalidMatcher(TypedDetailsMatchingService):
            method='clip_ai'
            def evaluate(self,report,item):raise ValueError('The embedding model returned non-finite values.')
        self.service.matcher=InvalidMatcher()
        report=self.report();item=self.item()
        with self.db.connect() as conn:
            match=conn.execute("SELECT * FROM matches WHERE report_id=? AND item_id=?",(report['id'],item['id'])).fetchone()
            self.assertEqual(match['method'],'typed_details')
            self.assertTrue(conn.execute("SELECT 1 FROM audit_logs WHERE action='AI_UNAVAILABLE'").fetchone())

    def test_missing_evidence_prevents_approval_and_release(self):
        claim=self.verified_claim();evidence=self.evidence(claim['id'])
        target=Path(self.temp.name)/"test-image.png"
        target.unlink()
        with self.assertRaises(DomainError):self.service.approve_claim(self.admin,claim['id'],evidence)
        self.assertEqual(self.row('claims',claim['id'])['status'],'verified')
        from lyfind.seed import sample_image
        target.write_bytes(sample_image())
        self.service.approve_claim(self.admin,claim['id'],evidence)
        target.unlink()
        with self.assertRaises(DomainError):self.service.release_item(self.admin,claim['id'])
        self.assertEqual(self.row('claims',claim['id'])['status'],'approved')
        self.assertEqual(self.row('items',claim['item_id'])['status'],'under_verification')

    def test_legacy_upload_paths_work_after_relocation(self):
        photo=self.upload('item_photo')
        with self.db.connect() as conn:conn.execute("UPDATE uploads SET path=? WHERE id=?",('C:/old-installation/uploads/test-image.png',photo))
        self.assertEqual(self.item(photo_id=photo)['photo_id'],photo)

    def test_invalid_answer_types_are_rejected(self):
        report=self.report();item=self.item();self.confirm(report,item)
        for answer in [None,[],{},True]:
            with self.subTest(answer=answer),self.assertRaises(DomainError):
                self.service.submit_claim(self.student,{'item_id':item['id'],'report_id':report['id'],'answers':{'details':answer},'consent':True})

    def test_reserved_invitation_does_not_offer_another_claim(self):
        report=self.report();item=self.item();self.confirm(report,item)
        other_report=self.report(self.other);self.confirm(other_report,item)
        self.claim(report=report,item=item)
        invite=self.service.dashboard(self.other)['matches'][0]
        self.assertFalse(invite['can_claim'])
        self.assertTrue(invite['eligibility_note'])
        self.assertNotIn('score',invite)

    def test_record_ids_do_not_silently_truncate(self):
        for value in [True,1.5,-1,'1.5']:
            with self.subTest(value=value),self.db.connect() as conn,self.assertRaises(DomainError):
                self.service._row(conn,'users',value)

    def test_complete_release_and_second_claim_refused(self):
        claim = self.verified_claim()
        approved = self.service.approve_claim(self.admin, claim["id"],
                                             self.evidence(claim["id"]))
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(self.row("items", claim["item_id"])["status"], "under_verification")
        released = self.service.release_item(self.admin, claim["id"])
        self.assertEqual(released["status"], "released")
        self.assertEqual(released["released_by"], self.admin.id)
        self.assertTrue(released["released_at"])
        self.assertEqual(self.row("items", claim["item_id"])["status"], "released")
        self.assertEqual(self.row("lost_reports", claim["report_id"])["status"], "closed")
        another_report = self.report(self.other)
        with self.assertRaises(DomainError):
            self.service.submit_claim(self.other, dict(
                item_id=claim["item_id"], report_id=another_report["id"],
                answers={"details": "claimed later"}, consent=True))
        with self.assertRaises(DomainError):
            self.service.release_item(self.admin, claim["id"])
        self.assertEqual(self.row("items", claim["item_id"])["status"], "released")
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM claims WHERE status='released'").fetchone()[0], 1)
            actions = {r[0] for r in conn.execute("SELECT action FROM audit_logs")}
        self.assertIn("ITEM_RELEASED", actions)
        self.assertIn("CLAIM_REFUSED", actions)

    def test_found_queue_is_not_inventory_until_physical_receipt(self):
        report = self.service.create_found_report(self.student, dict(
            category="electronics", description="Headphones awaiting handoff", place="Library",
            date_found=self.today, turn_in_deadline=(date.today() + timedelta(days=1)).isoformat()))
        self.assertEqual(report["status"], "awaiting_turn_in")
        self.assertEqual(self.service.dashboard(self.admin)["items"], [])
        item = self.item(found_report_id=report["id"])
        self.assertEqual(item["status"], "available")
        self.assertEqual(self.row("found_reports", report["id"])["status"], "received")
        with self.assertRaises(DomainError):
            self.item(found_report_id=report["id"])

    def test_guest_cannot_report_found_or_perform_staff_actions(self):
        with self.assertRaises(DomainError):
            self.service.create_found_report(self.guest, dict(
                category="keys", description="Keys with a yellow tag", place="Gate 1",
                date_found=self.today, where_now="security"))
        self.assertEqual(self.report(self.guest)["owner_id"], self.guest.id)
        with self.assertRaises(DomainError):
            self.service.manage_staff(self.guest, {"action": "create"})
        with self.assertRaises(DomainError):
            self.service.receive_item(self.student, {})

    def test_found_report_needs_a_turn_in_day_only_when_the_finder_holds_it(self):
        base = dict(category="wallets", description="Brown wallet", place="Freedom Park", date_found=self.today)
        with self.assertRaises(DomainError):
            self.service.create_found_report(self.student, {**base, "where_now": "with_me"})
        with self.assertRaises(DomainError):
            self.service.create_found_report(self.student, {**base, "where_now": "my pocket"})
        with self.assertRaises(DomainError):
            self.service.create_found_report(self.student, {**base, "where_now": "left", "time_found": "midnight"})
        saved = self.service.create_found_report(self.student, {**base, "where_now": "left", "time_found": "Evening"})
        self.assertEqual(saved["where_now"], "left")

    def test_lost_report_keeps_a_time_of_day_and_rejects_nonsense(self):
        saved = self.report(time_lost="Afternoon")
        self.assertEqual(saved["time_lost"], "Afternoon")
        with self.assertRaises(DomainError):
            self.report(time_lost="Tomorrow")

    def test_confirmation_required_and_owner_privacy(self):
        report, item = self.report(), self.item()
        self.service.run_matching(self.admin)
        user_dashboard = self.service.dashboard(self.student)
        self.assertEqual(user_dashboard["matches"], [])
        self.assertEqual(user_dashboard["notifications"], [])
        self.assertEqual(user_dashboard["items"], [])
        self.assertNotIn("PRIVATE-IDENTIFIER-CX147", json.dumps(user_dashboard))
        with self.assertRaises(DomainError):
            self.service.submit_claim(self.student, dict(item_id=item["id"], report_id=report["id"],
                                     answers={"details": "green label"}, consent=True))
        self.confirm(report, item)
        dashboard = self.service.dashboard(self.student)
        self.assertEqual(len(dashboard["matches"]), 1)
        self.assertTrue(dashboard["notifications"])
        for hidden in ("score", "private_details", "item_photo_id", "method"):
            self.assertNotIn(hidden, dashboard["matches"][0])

    def test_owner_cannot_claim_using_someone_elses_report(self):
        report, item = self.report(), self.item()
        self.confirm(report, item)
        with self.assertRaises(DomainError) as caught:
            self.service.submit_claim(self.other, dict(item_id=item["id"], report_id=report["id"],
                                     answers={"details": "green label"}, consent=True))
        self.assertEqual(caught.exception.status, 403)

    def test_second_active_claim_is_refused_before_online_check(self):
        item = self.item()
        first_report, second_report = self.report(), self.report(self.other)
        self.confirm(first_report, item)
        self.confirm(second_report, item)
        first = self.claim(self.student, first_report, item)
        self.assertEqual(first["status"], "step1_pending")
        self.assertEqual(self.row("items", item["id"])["status"], "available")
        with self.assertRaises(DomainError):
            self.service.submit_claim(self.other, dict(item_id=item["id"], report_id=second_report["id"],
                                     answers={"details": "also mine"}, consent=True))
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0], 1)

    def test_simultaneous_claim_submissions_reserve_item_once(self):
        report, item = self.report(), self.item()
        self.confirm(report, item)

        def attempt():
            try:
                self.service.submit_claim(self.student, dict(
                    item_id=item["id"], report_id=report["id"],
                    answers={"details": "green label under the left ear cup"}, consent=True))
                return True
            except DomainError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            successes = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sorted(successes), [False, True])
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0], 1)

    def test_three_rejections_block_same_pair_and_unlock_item(self):
        report, item = self.report(), self.item()
        for _ in range(3):
            claim = self.claim(self.student, report, item)
            self.service.verify_online(self.admin, claim["id"], False, "Answers do not identify the item")
            self.assertEqual(self.row("items", item["id"])["status"], "available")
        with self.assertRaises(DomainError) as caught:
            self.claim(self.student, report, item)
        self.assertEqual(caught.exception.status, 403)
        other_claim = self.claim(self.other, self.report(self.other), item)
        self.assertEqual(other_claim["status"], "step1_pending")

    def test_consent_and_both_verification_steps_are_required(self):
        claim = self.claim()
        with self.assertRaises(DomainError):
            self.service.record_consent(self.admin, claim["id"], dict(in_person=True, purpose="Evidence"))
        with self.assertRaises(DomainError):
            self.service.verify_in_person(self.admin, claim["id"], True)
        with self.assertRaises(DomainError):
            self.service.approve_claim(self.admin, claim["id"], {})
        self.service.verify_online(self.admin, claim["id"], True)
        with self.assertRaises(DomainError):
            self.service.verify_in_person(self.admin, claim["id"], True)
        with self.assertRaises(DomainError):
            self.service.authorize_upload(self.admin, "id_photo", claim["id"])
        with self.assertRaises(DomainError):
            self.service.record_consent(self.student, claim["id"], dict(in_person=True, purpose="Evidence"))
        with self.assertRaises(DomainError):
            self.service.record_consent(self.admin, claim["id"], dict(in_person=False, purpose="Evidence"))
        self.assertEqual(self.row("claims", claim["id"])["status"], "step2_pending")

    def test_approval_rejects_missing_wrong_claim_or_preconsent_evidence(self):
        claim = self.verified_claim()
        with self.assertRaises(DomainError):
            self.service.approve_claim(self.admin, claim["id"], {})
        evidence = self.evidence(claim["id"])
        wrong_claim_signature = self.upload("signature", claim_id=None)
        with self.assertRaises(DomainError):
            self.service.approve_claim(self.admin, claim["id"], dict(evidence, signature=wrong_claim_signature))
        old_id = self.upload("id_photo", claim_id=claim["id"], created_at="2000-01-01T00:00:00Z")
        with self.assertRaises(DomainError):
            self.service.approve_claim(self.admin, claim["id"], dict(evidence, id_photo=old_id))
        self.assertEqual(self.row("claims", claim["id"])["status"], "verified")
        self.assertIsNone(self.row("claims", claim["id"])["approved_by"])
        self.service.approve_claim(self.admin, claim["id"], evidence)

    def test_in_person_rejection_restores_item_availability(self):
        claim = self.claim()
        self.service.verify_online(self.admin, claim["id"], True)
        self.service.record_consent(self.admin, claim["id"], dict(in_person=True, purpose="Ownership evidence"))
        rejected = self.service.verify_in_person(self.admin, claim["id"], False, "Ownership proof did not match")
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(self.row("items", claim["item_id"])["status"], "available")

    def test_private_files_are_admin_only_except_own_report_image(self):
        item = self.item()
        with self.assertRaises(DomainError):
            self.service.file_access(self.student, item["photo_id"])
        self.assertEqual(self.service.file_access(self.admin, item["photo_id"])["kind"], "item_photo")
        report_photo = self.upload("report_photo", self.student)
        self.assertEqual(self.service.file_access(self.student, report_photo)["id"], report_photo)
        with self.assertRaises(DomainError):
            self.service.file_access(self.other, report_photo)

    def test_claimant_dashboard_contains_no_item_secret_or_evidence_ids(self):
        claim = self.verified_claim()
        self.service.approve_claim(self.admin, claim["id"], self.evidence(claim["id"]))
        dashboard = self.service.dashboard(self.student)
        self.assertNotIn("PRIVATE-IDENTIFIER-CX147", json.dumps(dashboard))
        for field in ("private_details", "item_photo_id", "claimant_photo", "id_photo", "signature"):
            self.assertNotIn(field, dashboard["claims"][0])
        self.assertEqual(self.service.dashboard(self.other)["claims"], [])

    def test_expiry_ignores_reserved_items(self):
        reserved = self.claim()
        ordinary = self.item()
        old_date = (datetime.now(timezone.utc) - timedelta(days=31)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.db.connect() as conn:
            conn.execute("UPDATE items SET received_at=?", (old_date,))
        result = self.service.expire_items(self.admin)
        self.assertEqual(result["expired"], 1)
        self.assertEqual(self.row("items", ordinary["id"])["status"], "unclaimed")
        self.assertEqual(self.row("items", reserved["item_id"])["status"], "available")

    def test_foreign_keys_audit_and_direct_status_guards(self):
        item = self.item()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect() as conn:
                conn.execute("INSERT INTO notifications(user_id,message) VALUES(99999,'invalid owner')")
        for statement in ("UPDATE audit_logs SET detail='rewritten'", "DELETE FROM audit_logs"):
            with self.assertRaises(sqlite3.IntegrityError):
                with self.db.connect() as conn:
                    conn.execute(statement)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect() as conn:
                conn.execute("UPDATE items SET status='released' WHERE id=?", (item["id"],))
        self.assertEqual(self.row("items", item["id"])["status"], "available")

    def test_account_status_is_reloaded_before_service_operation(self):
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET active=0 WHERE id=?", (self.student.id,))
        self.assertTrue(self.student.active, "Fixture retains stale session state")
        with self.assertRaises(DomainError) as caught:
            self.report(self.student)
        self.assertEqual(caught.exception.status, 403)

    def test_staff_cannot_promote_public_identity_or_remove_last_admin(self):
        with self.assertRaises(DomainError):
            self.service.manage_staff(self.admin, dict(action="update", user_id=self.guest.id,
                                                      name="Promoted guest", active=True, role="admin"))
        with self.assertRaises(DomainError):
            self.service.manage_staff(self.admin, dict(action="update", user_id=self.admin.id,
                                                      active=False, role="admin"))
        self.assertEqual(self.row("users", self.guest.id)["role"], "guest")
        self.assertEqual(self.row("users", self.admin.id)["active"], 1)

    def test_fallback_matching_records_reason_and_no_owner_notice(self):
        self.report()
        self.item()
        service = Service(self.db, self.temp.name)
        result = service.run_matching(self.admin)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["suggestions"][0]["method"], "typed_details")
        with self.db.connect() as conn:
            self.assertTrue(conn.execute("SELECT id FROM audit_logs WHERE action='AI_UNAVAILABLE'").fetchone())
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0], 0)

    def test_invalid_input_does_not_create_records(self):
        for overrides in ({"description": ""}, {"date_lost": "not-a-date"},
                          {"date_lost": (date.today() + timedelta(days=1)).isoformat()}):
            with self.assertRaises(DomainError):
                self.report(**overrides)
        with self.assertRaises(DomainError):
            self.item(photo_id=None)
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM lost_reports").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)

    def test_staff_can_file_a_lost_report_for_an_existing_guest(self):
        made = self.service.create_lost_report_for_guest(self.admin, dict(
            guest_email=self.guest.email, category="electronics",
            description="Silver water bottle with a dented lid", color="silver",
            brand_choice="unknown", place="Library", date_lost=self.today))
        saved = self.row("lost_reports", made["id"])
        self.assertEqual(saved["owner_id"], self.guest.id)
        self.assertEqual(saved["flagged"], 0)
        with self.assertRaises(DomainError):
            self.service.create_lost_report_for_guest(self.admin, dict(
                guest_email=self.student.email, category="electronics",
                description="Not a guest", color="black", brand_choice="unknown",
                place="Library", date_lost=self.today))
        with self.assertRaises(DomainError):
            self.service.create_lost_report_for_guest(self.student, dict(
                guest_email=self.guest.email, category="electronics",
                description="Students cannot file this", color="black",
                brand_choice="unknown", place="Library", date_lost=self.today))

    def test_a_new_visitor_gets_a_code_and_the_report_saves_when_they_finish(self):
        import os
        from unittest.mock import patch
        email = "desk.visitor@example.test"
        details = dict(guest_email=email, category="bags", description="Dark green backpack with a front pocket",
                       color="green", brand_choice="unknown", place="Library", date_lost=self.today)
        with patch.dict(os.environ, {"SMTP_HOST": "", "SMTP_FROM": ""}):
            auth = AuthService(self.db, demo_mode=True)
            sent = {}
            deliver = auth._deliver

            def capture(conn, address, code, purpose):
                sent["code"] = code
                return deliver(conn, address, code, purpose)

            auth._deliver = capture
            held = self.service.create_lost_report_for_guest(self.admin, details, auth)
        self.assertEqual(held["status"], "waiting")
        self.assertNotIn(sent["code"], str(held))
        with self.db.connect() as conn:
            self.assertIsNone(conn.execute("SELECT id FROM users WHERE lower(email)=?", (email,)).fetchone())
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM lost_reports WHERE description=?", (details["description"],)).fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT status FROM desk_holds WHERE guest_email=?", (email,)).fetchone()[0], "waiting")
        checked = auth.verify_signup(email, sent["code"])
        visitor = auth.finish_guest(email, checked["setup_token"], "BlueKettle42!", "BlueKettle42!",
                                    first_name="Desk", last_name="Visitor")
        self.assertEqual(self.service.claim_desk_holds(visitor), 1)
        with self.db.connect() as conn:
            report = conn.execute("SELECT id, owner_id, flagged FROM lost_reports WHERE description=?", (details["description"],)).fetchone()
            hold = conn.execute("SELECT status, report_id FROM desk_holds WHERE guest_email=?", (email,)).fetchone()
        self.assertEqual(report["owner_id"], visitor.id)
        self.assertEqual(report["flagged"], 0)
        self.assertEqual(hold["status"], "saved")
        self.assertEqual(hold["report_id"], report["id"])


class DomainAndMatchingTests(unittest.TestCase):
    def test_status_properties_and_invalid_moves(self):
        item, claim = Item(1), Claim(1)
        with self.assertRaises(AttributeError):
            item.status = "released"
        with self.assertRaises(AttributeError):
            claim.status = "approved"
        with self.assertRaises(DomainError):
            item.change_status("released")
        with self.assertRaises(DomainError):
            claim.advance("approved")
        item.change_status("under_verification")
        item.change_status("released")
        with self.assertRaises(DomainError):
            item.change_status("available")

    def test_role_polymorphism(self):
        student = Student(1, "Student", "student@example.test")
        professor = Professor(2, "Professor", "professor@example.test")
        guest = Guest(3, "Guest", "guest@example.test")
        admin = CSAAdministrator(4, "CSA", "csa@example.test")
        for user in (student, professor):
            require_permission(user, "report_found")
        with self.assertRaises(DomainError):
            require_permission(admin, "report_found")
        with self.assertRaises(DomainError):
            require_permission(guest, "report_found")
        require_permission(admin, "approve_claim")
        with self.assertRaises(DomainError):
            require_permission(student, "approve_claim")

    def test_abstraction_factory_and_score_thresholds(self):
        with self.assertRaises(TypeError):
            MatchingService()
        with self.assertRaises(TypeError):
            EmbeddingAdapter()
        events = []
        service = MatchingServiceFactory.create(False, log=lambda *entry: events.append(entry))
        self.assertIsInstance(service, TypedDetailsMatchingService)
        self.assertEqual(events[0][0], "AI_UNAVAILABLE")
        report = dict(category="electronics", description="headphones", color="black", brand="Acme",
                      place="Library", date_lost="2026-01-01")
        item = dict(report, date_found="2026-01-02")
        # Typed details alone can reach Possible, never Strong.
        score, level = service.compare(report, item)
        self.assertEqual(level, "possible")
        self.assertLessEqual(score, 79.0)
        self.assertEqual(service.compare(report, dict(item, category="bags")), (0.0, "hidden"))
        different_brand = service.compare(report, dict(item, brand="Different"))
        self.assertLessEqual(different_brand[0], 69.0)
        self.assertLess(service.compare(report, dict(item, brand="Different", color="red"))[0], different_brand[0])
        self.assertEqual(service.compare(report, dict(item, date_found="2025-12-31")), (0.0, "hidden"))

    def test_ai_service_uses_embedding_interface_and_expected_weights(self):
        class Adapter(EmbeddingAdapter):
            def embed_text(self, text):
                return [1.0, 0.0]

            def embed_image(self, path):
                return [1.0, 0.0]

        service = MatchingServiceFactory.create(True, Adapter())
        self.assertIsInstance(service, AIMatchingService)
        report = dict(category="electronics", description="headphones", color="black", brand="Acme",
                      place="Library", date_lost="2026-01-01")
        item = dict(report, date_found="2026-01-02", photo_path="fixture.png")
        score, level = service.compare(report, item)
        self.assertEqual(level, "strong")
        self.assertGreaterEqual(score, 85)
        score, level = service.compare(report, dict(item, color="red", brand="Other"))
        self.assertEqual(level, "possible")  # colour and brand contradict, so it cannot be Strong
        self.assertLessEqual(score, 69)
        # If the place differs as well, an identical photo is not enough: the pair drops below 60 and is hidden.
        score, level = service.compare(report, dict(item, color="red", brand="Other", place="Other"))
        self.assertEqual(level, "hidden")
        self.assertLess(score, 60)

    def test_clip_adapter_translates_domain_text_request_to_encoder(self):
        class Encoder:
            def __init__(self):
                self.inputs = []

            def encode(self, value):
                self.inputs.append(value)
                return (0.25, 0.75)

        encoder = Encoder()
        adapter = ClipAdapter(encoder)
        self.assertEqual(adapter.embed_text("Black headphones"), [0.25, 0.75])
        self.assertEqual(encoder.inputs, ["Black headphones"])

    def test_password_hash_is_salted_and_verifiable(self):
        encoded = hash_password("classroom-test-password")
        self.assertNotIn("classroom-test-password", encoded)
        self.assertTrue(check_password("classroom-test-password", encoded))
        self.assertFalse(check_password("incorrect-password", encoded))
        self.assertFalse(check_password("anything", "invalid"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
