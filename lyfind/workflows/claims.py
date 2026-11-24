"""Ownership checks, consent, approval, and physical handover."""
from lyfind.claim_answers import ClaimAnswers

from lyfind.domain import Claim, Item
from lyfind.users import DomainError

from .base import AuditLog, WorkflowBase, now


class ClaimService(WorkflowBase):
    """Ownership checks, consent, approval, and physical handover."""

    def submit_claim(self, user, data):
        try:
            return self._submit_claim(user, data)
        except DomainError as error:
            if user:
                with self._tx() as conn:
                    if conn.execute("SELECT id FROM users WHERE id=?", (user.id,)).fetchone():
                        AuditLog(conn).record(user, "CLAIM_REFUSED", str(error))
            raise

    def _submit_claim(self, user, data):
        user = self._guard(user, "submit_claim")
        answers = data.get("answers")
        if not isinstance(answers, dict) or not 1 <= len(answers) <= 20:
            raise DomainError("Answer all ownership questions before submitting.")
        for question, answer in answers.items():
            if not isinstance(question, str) or not question.strip():
                raise DomainError("Answer all ownership questions before submitting.")
            if not isinstance(answer, str) or not answer.strip() or len(answer) > 3000:
                raise DomainError("Answer all ownership questions before submitting.")
        if data.get("consent") is not True:
            raise DomainError("Agree to send your answers before submitting.")
        with self._tx() as conn:
            item = self._row(conn, "items", data.get("item_id"))
            report = self._row(conn, "lost_reports", data.get("report_id"))
            if report["owner_id"] != user.id:
                raise DomainError("You can only claim for your own report.", 403)
            if report["status"] != "open" or item["status"] != "available":
                raise DomainError("This item is not open for a new claim.")
            if conn.execute("SELECT julianday('now')-julianday(received_at)>=unclaimed_after_days FROM items WHERE id=?", (item['id'],)).fetchone()[0]:
                raise DomainError('This item has reached the end of its holding period.')
            match = conn.execute("SELECT id FROM matches WHERE item_id=? AND report_id=? AND status='confirmed'", (item["id"], report["id"])).fetchone()
            if not match:
                raise DomainError("Wait until CSA invites you to claim this item.", 403)
            if conn.execute("SELECT id FROM claims WHERE item_id=? AND status IN ('step1_pending','step2_pending','verified','approved')", (item["id"],)).fetchone():
                raise DomainError("This item already has an active claim. Wait for availability.")
            attempts = conn.execute("SELECT COUNT(*) FROM claims WHERE item_id=? AND claimant_id=? AND status='rejected'", (item["id"], user.id)).fetchone()[0]
            if attempts >= 3:
                raise DomainError("You have used all 3 tries for this item.", 403)
            self._daily_cap(conn, user, "claim")
            cursor = conn.execute("INSERT INTO claims(claimant_id,item_id,report_id,online_consent,flagged) VALUES(?,?,?,1,?)",
                                  (user.id, item["id"], report["id"], int(user.role == "guest")))
            ClaimAnswers(conn).save(cursor.lastrowid, answers)
            AuditLog(conn).record(user, "CLAIM_SUBMITTED", f"Claim {cursor.lastrowid}; item {item['id']}")
            return self._row(conn, "claims", cursor.lastrowid)

    def _reject(self, conn, admin, claim, reason):
        if not str(reason).strip():
            raise DomainError("Add a reason so the owner knows what to do next.")
        model = Claim(claim["id"], claim["status"], claim["in_person_consent"])
        model.advance("rejected")
        conn.execute("UPDATE claims SET status=?,reason=? WHERE id=?", (model.status, str(reason).strip(), claim["id"]))
        item = self._row(conn, "items", claim["item_id"])
        if item["status"] == "under_verification":
            model_item = Item(item["id"], item["status"])
            model_item.change_status("available")
            conn.execute("UPDATE items SET status=? WHERE id=?", (model_item.status, item["id"]))
        count = conn.execute("SELECT COUNT(*) FROM claims WHERE claimant_id=? AND item_id=? AND status='rejected'", (claim["claimant_id"], claim["item_id"])).fetchone()[0]
        self._notify(conn, claim["claimant_id"], f"This claim was not approved: {reason}. You have used {count} of 3 tries for this item.", claim["report_id"], claim["id"])
        AuditLog(conn).record(admin, "CLAIM_REJECTED", f"Claim {claim['id']}; attempt {count}; {reason}")

    def verify_online(self, admin, claim_id, passed, reason=""):
        admin = self._guard(admin, "verify_online")
        if not isinstance(passed, bool):
            raise DomainError("Record a pass or fail decision.")
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            if claim["status"] != "step1_pending":
                raise DomainError("The online check is already recorded.")
            if passed:
                model = Claim(claim_id, claim["status"])
                model.advance("step2_pending")
                item = self._row(conn, "items", claim["item_id"])
                model_item = Item(item["id"], item["status"])
                model_item.change_status("under_verification")
                conn.execute("UPDATE claims SET status=?,online_verified_by=?,flagged=0 WHERE id=?", (model.status, admin.id, claim_id))
                conn.execute("UPDATE items SET status=? WHERE id=?", (model_item.status, item["id"]))
                self._notify(conn, claim["claimant_id"], "The online check passed. Bring your ID to the CSA office.", claim["report_id"], claim_id)
                AuditLog(conn).record(admin, "STEP1_PASSED", f"Claim {claim_id}; notes: {str(reason).strip()[:2000]}")
            else:
                self._reject(conn, admin, claim, reason)
            return self._row(conn, "claims", claim_id)

    def record_consent(self, user, claim_id, data):
        user = self._guard(user, "record_consent" if user.role == "admin" else "view_own")
        if data.get("in_person") is not True:
            raise DomainError("The owner must be here and agree to the photos before you continue.")
        purpose = self._text(data, "purpose", maximum=1000)
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            if user.role != "admin" and user.id != claim["claimant_id"]:
                raise DomainError("You cannot start the office check for another owner.", 403)
            if user.role != "admin":
                raise DomainError("Only CSA staff can start the office check, and the owner must be at the office.", 403)
            model = Claim(claim_id, claim["status"], claim["in_person_consent"])
            if model.consent:
                raise DomainError("The office check has already started.")
            model.record_consent()
            conn.execute("UPDATE claims SET in_person_consent=1,consent_at=?,consent_purpose=?,consent_recorded_by=? WHERE id=?", (now(), purpose, user.id, claim_id))
            AuditLog(conn).record(user, "IN_PERSON_CONSENT_RECORDED", f"Claim {claim_id}; purpose: {purpose}")
            return self._row(conn, "claims", claim_id)

    def verify_in_person(self, admin, claim_id, passed, reason=""):
        admin = self._guard(admin, "verify_in_person")
        if not isinstance(passed, bool):
            raise DomainError("Record a pass or fail decision.")
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            if claim["status"] != "step2_pending":
                raise DomainError("Pass the online check before the office visit.")
            if not claim["in_person_consent"]:
                raise DomainError("Start the office check first.")
            if passed:
                model = Claim(claim_id, claim["status"], claim["in_person_consent"])
                model.advance("verified")
                conn.execute("UPDATE claims SET status=?,in_person_verified_by=? WHERE id=?", (model.status, admin.id, claim_id))
                self._notify(conn, claim["claimant_id"], "Both checks passed. CSA will approve the handover, then you can pick the item up.", claim["report_id"], claim_id)
                AuditLog(conn).record(admin, "STEP2_PASSED", f"Claim {claim_id}; ID and ownership proof checked in person; notes: {str(reason).strip()[:2000]}")
            else:
                self._reject(conn, admin, claim, reason)
            return self._row(conn, "claims", claim_id)

    def approve_claim(self, admin, claim_id, data):
        admin = self._guard(admin, "approve_claim")
        evidence = data.get("evidence", data)
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            model = Claim(claim_id, claim["status"], claim["in_person_consent"])
            model.advance("approved")
            if not claim["online_verified_by"] or not claim["in_person_verified_by"]:
                raise DomainError("Pass both checks before approval.")
            ids = []
            for kind in ("claimant_photo", "id_photo", "signature"):
                file_id = self._photo(conn, admin, evidence.get(kind), kind, required=True, claim_id=claim_id)
                file = self._row(conn, "uploads", file_id)
                if not claim["consent_at"] or file["created_at"] < claim["consent_at"]:
                    raise DomainError("Start the office check before taking these photos.")
                ids.append(file_id)
            conn.execute("UPDATE claims SET status=?,claimant_photo=?,id_photo=?,signature=?,evidence_captured_at=?,approved_by=?,approved_at=?,handover_note=? WHERE id=?",
                         (model.status, *ids, now(), admin.id, now(), self._text(data, "handover_note", required=False), claim_id))
            AuditLog(conn).record(admin, "CLAIM_APPROVED", f"Claim {claim_id}; verified evidence recorded")
            self._notify(conn, claim["claimant_id"], "Your claim is approved. Come to the CSA office to pick up the item.", claim["report_id"], claim_id)
            return self._row(conn, "claims", claim_id)

    def release_item(self, admin, claim_id):
        admin = self._guard(admin, "release_item")
        with self._tx() as conn:
            claim = self._row(conn, "claims", claim_id)
            model = Claim(claim_id, claim["status"], claim["in_person_consent"])
            model.advance("released")
            if not all(claim[k] for k in ("online_verified_by", "in_person_verified_by", "claimant_photo", "id_photo", "signature", "approved_by")):
                raise DomainError("Approve the claim and save all three photos before handing it over.")
            for kind in ("claimant_photo", "id_photo", "signature"):
                self._photo(conn, admin, claim[kind], kind, required=True, claim_id=claim_id)
            item = self._row(conn, "items", claim["item_id"])
            model_item = Item(item["id"], item["status"])
            model_item.change_status("released")
            conn.execute("UPDATE claims SET status=?,released_by=?,released_at=? WHERE id=?", (model.status, admin.id, now(), claim_id))
            conn.execute("UPDATE items SET status=? WHERE id=?", (model_item.status, item["id"]))
            conn.execute("UPDATE lost_reports SET status='closed' WHERE id=?", (claim["report_id"],))
            self._notify(conn, claim["claimant_id"], "Done. Your item was handed back and this report is closed.", claim["report_id"], claim_id)
            AuditLog(conn).record(admin, "ITEM_RELEASED", f"Item {item['id']} to claimant {claim['claimant_id']}; claim {claim_id}; handover complete")
            return self._row(conn, "claims", claim_id)
