"""Physical reception, holding periods, and private file access."""
import os

from lyfind.domain import Item
from lyfind.users import DomainError

from .base import AuditLog, WorkflowBase


class InventoryService(WorkflowBase):
    """Physical reception, holding periods, and private file access."""

    def receive_item(self, admin, data):
        admin = self._guard(admin, "receive_item")
        values = {key: self._text(data, key, key in {"category", "description", "place", "private_details"})
                  for key in ("category", "description", "color", "brand", "place", "private_details")}
        values["category"] = self._category(values["category"])
        values['brand'] = self._brand(data)
        values["date_found"] = self._date(data, "date_found")
        published = data.get('board_published', False)
        if type(published) is not bool:
            raise DomainError('Choose whether this item appears on Found items.')
        values['board_published'] = int(published)
        try:
            values["unclaimed_after_days"] = int(data.get("unclaimed_after_days", os.getenv("UNCLAIMED_DAYS", "30")))
            if not 1 <= values["unclaimed_after_days"] <= 3650:
                raise ValueError()
        except (ValueError, TypeError):
            raise DomainError("Keep the item for between 1 and 3650 days.")
        with self._tx() as conn:
            values["photo_id"] = self._photo(conn, admin, data.get("photo_id"), "item_photo", required=True)
            values["found_report_id"] = data.get("found_report_id") or None
            if values["found_report_id"]:
                report = self._row(conn, "found_reports", values["found_report_id"])
                if report["status"] != "awaiting_turn_in":
                    raise DomainError("This found report has already been received.")
                conn.execute("UPDATE found_reports SET status='received' WHERE id=?", (report["id"],))
                self._notify(conn, report["finder_id"], "CSA received the item you turned in.")
            keys = list(values)
            cursor = conn.execute(f"INSERT INTO items(recorded_by,{','.join(keys)}) VALUES({','.join('?' for _ in range(len(keys)+1))})",
                                  (admin.id, *[values[k] for k in keys]))
            result = self._row(conn, "items", cursor.lastrowid)
            AuditLog(conn).record(admin, "ITEM_RECEIVED", f"Item {result['id']}; physical turn-in confirmed")
        self._run_matching_unlocked()
        return result

    def expire_items(self, admin):
        admin = self._guard(admin, "expire_items")
        with self._tx() as conn:
            rows = conn.execute("SELECT * FROM items WHERE status='available' AND julianday('now')-julianday(received_at)>=unclaimed_after_days AND NOT EXISTS(SELECT 1 FROM claims c WHERE c.item_id=items.id AND c.status IN ('step1_pending','step2_pending','verified','approved'))").fetchall()
            for row in rows:
                model = Item(row["id"], row["status"])
                model.change_status("unclaimed")
                conn.execute("UPDATE items SET status=? WHERE id=?", (model.status, row["id"]))
                AuditLog(conn).record(admin, "ITEM_UNCLAIMED", f"Item {row['id']}; retention period elapsed")
            return {"expired": len(rows)}

    def authorize_upload(self, user, kind, claim_id=None):
        if kind == "item_photo":
            permission = "receive_item"
        elif kind in {"claimant_photo", "id_photo", "signature"}:
            permission = "approve_claim"
        else:
            permission = "report_lost"
        user = self._guard(user, permission)
        if kind not in {"report_photo", "item_photo", "claimant_photo", "id_photo", "signature"}:
            raise DomainError("Unknown upload purpose.")
        if kind in {"claimant_photo", "id_photo", "signature"}:
            with self.db.connect() as conn:
                claim = self._row(conn, "claims", claim_id)
                if claim["status"] not in {"step2_pending", "verified"} or not claim["in_person_consent"]:
                    raise DomainError("Start the office check after the online check, then take the photos.")
        return True

    def file_access(self, user, file_id):
        user = self._guard(user, "view_own")
        with self.db.connect() as conn:
            upload = self._row(conn, "uploads", file_id)
        if user.role != "admin" and not (upload["kind"] == "report_photo" and upload["owner_id"] == user.id):
            raise DomainError("Only CSA staff can open this photo.", 403)
        return upload

    def set_board_listing(self, admin, item_id, data):
        admin = self._guard(admin, 'receive_item')
        published = data.get('published')
        if type(published) is not bool:
            raise DomainError('Choose whether this item appears on Found items.')
        with self._tx() as conn:
            item = self._row(conn, 'items', item_id)
            if published and item['status'] != 'available':
                raise DomainError('Only an available item can be listed.')
            conn.execute('UPDATE items SET board_published=? WHERE id=?', (int(published), item_id))
            AuditLog(conn).record(admin, 'BOARD_LISTING_UPDATED', f'Item {item_id}; listed={published}')
        return {'published': published}
