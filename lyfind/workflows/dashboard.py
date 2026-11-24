"""Read the records each role is allowed to see."""
import json
from datetime import date, timedelta

from lyfind.claim_answers import ClaimAnswers

from .base import ACTIVE, WorkflowBase


class DashboardService(WorkflowBase):
    """Read the records each role is allowed to see."""

    def dashboard(self, user):
        user = self._guard(user, "view_own")
        with self.db.connect() as conn:
            def rows(sql, params=()):
                return [dict(r) for r in conn.execute(sql, params)]
            result = {"user": user.public(), "items": [], "reports": [], "found_reports": [], "claims": [],
                      "matches": [], "staff": [], "audit": [], "notifications": rows("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100", (user.id,))}
            admin = user.role == "admin"
            if 'view_found_board' in user.permissions():
                listings = conn.execute(
                    "SELECT category,date_found FROM items WHERE status='available' AND board_published=1 "
                    "AND julianday('now')-julianday(received_at)<unclaimed_after_days "
                    "AND NOT EXISTS(SELECT 1 FROM claims c WHERE c.item_id=items.id AND c.status IN ('step1_pending','step2_pending','verified','approved')) "
                    "ORDER BY date_found DESC")
                result['found_board'] = [
                    dict(category=row['category'], area='Campus',
                         week=(date.fromisoformat(row['date_found'])-timedelta(days=date.fromisoformat(row['date_found']).weekday())).isoformat())
                    for row in listings]

            result["reports"] = rows("SELECT r.*,u.name AS owner_name,u.role AS owner_role,u.email AS owner_email,u.phone AS owner_phone,u.student_number AS owner_number FROM lost_reports r JOIN users u ON u.id=r.owner_id " + ("" if admin else "WHERE owner_id=? AND r.hidden=0 ") + "ORDER BY r.hidden, r.flagged DESC, r.id DESC", () if admin else (user.id,))
            result["found_reports"] = rows("SELECT f.*,u.name AS finder_name,u.role AS finder_role,u.email AS finder_email,u.phone AS finder_phone FROM found_reports f JOIN users u ON u.id=f.finder_id " + ("" if admin else "WHERE finder_id=? AND f.hidden=0 ") + "ORDER BY f.hidden, f.id DESC", () if admin else (user.id,))
            claim_sql = "SELECT c.*,u.name AS claimant_name,u.email AS claimant_email,u.phone AS claimant_phone,u.student_number AS claimant_student_number,i.description AS item_description,i.private_details,i.photo_id AS item_photo_id,i.category AS item_category,r.description AS report_description FROM claims c JOIN users u ON u.id=c.claimant_id JOIN items i ON i.id=c.item_id JOIN lost_reports r ON r.id=c.report_id "
            result["claims"] = rows(claim_sql + ("" if admin else "WHERE c.claimant_id=? ") + "ORDER BY c.id DESC", () if admin else (user.id,))
            answers = ClaimAnswers(conn).for_claims(claim["id"] for claim in result["claims"])
            for claim in result["claims"]:
                claim["answers"] = answers[claim["id"]]
                claim["step1_passed"] = bool(claim["online_verified_by"])
                claim["step2_passed"] = bool(claim["in_person_verified_by"])
                if not admin:
                    for field in ("private_details", "item_photo_id", "claimant_photo", "id_photo", "signature"):
                        claim.pop(field, None)
                    claim["item_description"] = claim["item_category"].replace("_", " ").title() + " held by CSA"
            if admin:
                result['matching_status'] = self.ai.status()
                result["items"] = rows("SELECT i.*,u.name AS recorded_by_name, (SELECT COUNT(*) FROM claims c WHERE c.item_id=i.id AND c.status IN ('step1_pending','step2_pending','verified','approved')) AS active_claims FROM items i JOIN users u ON u.id=i.recorded_by ORDER BY i.id DESC")
                result["matches"] = rows("SELECT m.*,i.category,i.description AS item_description,i.private_details,i.photo_id AS item_photo_id,i.place AS item_place,i.color AS item_color,i.date_found,r.description AS report_description,r.photo_id AS report_photo_id,r.place AS report_place,r.color AS report_color,r.date_lost,r.owner_id,r.flagged AS report_flagged,u.name AS owner_name,u.role AS owner_role FROM matches m JOIN items i ON i.id=m.item_id JOIN lost_reports r ON r.id=m.report_id JOIN users u ON u.id=r.owner_id WHERE r.hidden=0 ORDER BY CASE m.status WHEN 'suggested' THEN 0 ELSE 1 END, m.score DESC, m.id DESC")
                for match in result['matches']:
                    match['score_details'] = json.loads(match['score_details'] or '{}')
                result["staff"] = rows("SELECT id,name,email,role,active,blocked,created_at FROM users WHERE role='admin' ORDER BY id")
                result["roster"] = rows("SELECT * FROM roster ORDER BY email LIMIT 2000")
                result["people"] = rows("SELECT u.id,u.name,u.email,u.phone,u.student_number,u.role,u.blocked,u.email_verified,u.created_at,"
                                        "(SELECT COUNT(*) FROM lost_reports r WHERE r.owner_id=u.id) AS reports,"
                                        "(SELECT COUNT(*) FROM claims c WHERE c.claimant_id=u.id) AS claims "
                                        "FROM users u WHERE u.role!='admin' ORDER BY u.blocked DESC, u.id DESC LIMIT 500")
                result["audit"] = rows("SELECT a.*,COALESCE(u.name,'System') AS actor_name FROM audit_logs a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 250")
            else:
                # A short public list: category and date only. No description, photo, place or private details.
                result['recent_found'] = []
                result["matches"] = rows("SELECT m.id,m.report_id,m.item_id,m.status,i.category,i.status AS item_status,r.description AS report_description FROM matches m JOIN items i ON i.id=m.item_id JOIN lost_reports r ON r.id=m.report_id WHERE m.status='confirmed' AND r.owner_id=? AND r.status='open' ORDER BY m.id DESC", (user.id,))
                for match in result["matches"]:
                    busy = conn.execute("SELECT COUNT(*) FROM claims WHERE item_id=? AND status IN ('step1_pending','step2_pending','verified','approved')", (match["item_id"],)).fetchone()[0]
                    attempts = conn.execute("SELECT COUNT(*) FROM claims WHERE claimant_id=? AND item_id=? AND status='rejected'", (user.id, match["item_id"])).fetchone()[0]
                    match["can_claim"] = match["item_status"] == "available" and not busy and attempts < 3
                    match["eligibility_note"] = ("You have used all 3 tries for this item." if attempts >= 3 else "Someone else is already verifying this item." if busy else "This item is no longer available to claim." if match["item_status"] != "available" else "")
            result["stats"] = {"items": len(result["items"]), "reports": len(result["reports"]), "claims": len(result["claims"]),
                               "available": sum(i["status"] == "available" for i in result["items"]),
                               "pending": sum(c["status"] in ACTIVE for c in result["claims"]),
                               "released": sum(c["status"] == "released" for c in result["claims"]),
                               "suggestions": sum(m["status"] == "suggested" for m in result["matches"])}
            return result
