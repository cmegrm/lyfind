"""Compare reports with inventory and review suggested matches."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from lyfind.storage import resolve_upload
from lyfind.users import DomainError

from .base import AuditLog, WorkflowBase
from lyfind.proposal_matching import ProposalMatcher


def _file_digest(path):
    if not path:
        return ""
    try:
        file_path = Path(path)
        if not file_path.is_file():
            return ""
        return hashlib.sha256(file_path.read_bytes()).hexdigest()
    except OSError:
        return ""


class MatchService(WorkflowBase):
    """Compare reports with inventory and review suggested matches."""

    _OPEN_REPORTS_SQL = "SELECT * FROM lost_reports WHERE status='open' AND hidden=0"
    _AVAILABLE_ITEMS_SQL = (
        "SELECT * FROM items WHERE status='available' "
        "AND julianday('now')-julianday(received_at)<unclaimed_after_days "
        "AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.item_id=items.id "
        "AND c.status IN ('step1_pending','step2_pending','verified','approved'))"
    )

    def run_matching(self, admin):
        admin = self._guard(admin, "run_matching")
        return self.run_matching_unlocked(admin)

    def _pair_cache_key(self, matcher, report, item, photo_digests):
        payload = {
            "v": 1,
            "method": matcher.method,
            "model": getattr(matcher, "model_id", ""),
            "weights": asdict(self.ai.weights),
            "report": {
                "category": report.get("category", ""),
                "description": report.get("description", ""),
                "identifying_marks": report.get("identifying_marks", ""),
                "color": report.get("color", ""),
                "brand": report.get("brand", ""),
                "place": report.get("place", ""),
                "date_lost": report.get("date_lost", ""),
                "photo": photo_digests.get(report.get("photo_path", ""), ""),
            },
            "item": {
                "category": item.get("category", ""),
                "description": item.get("description", ""),
                "private_details": item.get("private_details", ""),
                "color": item.get("color", ""),
                "brand": item.get("brand", ""),
                "place": item.get("place", ""),
                "date_found": item.get("date_found", ""),
                "photo": photo_digests.get(item.get("photo_path", ""), ""),
            },
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _load_candidates(self, conn):
        reports = [dict(r) for r in conn.execute(self._OPEN_REPORTS_SQL)]
        items = [dict(r) for r in conn.execute(self._AVAILABLE_ITEMS_SQL)]
        for row in reports + items:
            if row.get("photo_id"):
                photo = self._row(conn, "uploads", row["photo_id"])
                row["photo_path"] = str(resolve_upload(self.upload_dir, photo["path"])) if self.upload_dir else photo["path"]
        return reports, items

    @staticmethod
    def _has_cache_table(conn):
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_match_cache'"
        ).fetchone() is not None

    def _load_cached(self, conn, keys):
        if not keys or not self._has_cache_table(conn):
            return {}
        cached = {}
        key_list = list(keys)
        for start in range(0, len(key_list), 200):
            chunk = key_list[start:start + 200]
            placeholders = ",".join("?" for _ in chunk)
            rows = conn.execute(
                f"SELECT cache_key, method, result_json FROM ai_match_cache WHERE cache_key IN ({placeholders})",
                chunk,
            ).fetchall()
            for row in rows:
                try:
                    cached[row["cache_key"]] = (row["method"], json.loads(row["result_json"]))
                except (ValueError, TypeError):
                    pass
        return cached

    def _score_pairs(self, matcher, reports, items, cached_map, cacheable, photo_digests):
        scored = []
        new_cache = []
        fallback_count = 0
        for report in reports:
            for item in items:
                if str(report["category"]).strip().casefold() != str(item["category"]).strip().casefold():
                    continue
                cache_key = self._pair_cache_key(matcher, report, item, photo_digests) if cacheable else None
                if cache_key and cache_key in cached_map:
                    method, cached_details = cached_map[cache_key]
                    details = copy.deepcopy(cached_details)
                else:
                    try:
                        details = matcher.evaluate(report, item)
                        method = matcher.method
                        if cacheable and cache_key:
                            new_cache.append((cache_key, method, json.dumps(details)))
                    except Exception:
                        fallback_count += 1
                        details = ProposalMatcher(self.ai, typed_only=True).evaluate(report, item)
                        details["note"] = "The AI check failed for this pair, so only typed details were used. The score is capped below Strong."
                        method = "typed_details"
                scored.append((report["id"], item["id"], details, method))
        for report in reports:
            candidates = [details for rid, _, details, _ in scored if rid == report["id"] and details["level"] != "hidden"]
            if candidates:
                best = max(details["total"] for details in candidates)
                close = [details for details in candidates if best - details["total"] <= 6]
                if len(close) > 1:
                    for details in close:
                        details["similar_candidates"] = len(close) - 1
        return scored, new_cache, fallback_count

    def _persist_results(self, conn, actor, scored, new_cache, fallback_count):
        log = AuditLog(conn)
        if not self.matcher and self.ai.adapter is None:
            log.record(actor, "AI_UNAVAILABLE", "Typed details used. " + self.ai.reason)
        for _ in range(fallback_count):
            log.record(actor, "AI_UNAVAILABLE", "AI evaluation failed; used typed details for this comparison")
        if new_cache and self._has_cache_table(conn):
            conn.executemany(
                "INSERT OR REPLACE INTO ai_match_cache(cache_key, method, result_json) VALUES(?,?,?)",
                new_cache,
            )
        # Suggestions that no longer make sense disappear: report closed or hidden, item gone or already being claimed.
        conn.execute("""DELETE FROM matches WHERE status='suggested' AND (
            report_id NOT IN (SELECT id FROM lost_reports WHERE status='open' AND hidden=0)
            OR item_id NOT IN (SELECT id FROM items WHERE status='available' AND julianday('now')-julianday(received_at)<unclaimed_after_days
                AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.item_id=items.id AND c.status IN ('step1_pending','step2_pending','verified','approved'))))""")
        active_reports = {row[0] for row in conn.execute("SELECT id FROM lost_reports WHERE status='open' AND hidden=0")}
        active_items = {row[0] for row in conn.execute(
            "SELECT id FROM items WHERE status='available' AND julianday('now')-julianday(received_at)<unclaimed_after_days "
            "AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.item_id=items.id AND c.status IN ('step1_pending','step2_pending','verified','approved'))"
        )}
        # Remove any stale suggested match where category no longer agrees.
        conn.execute("""DELETE FROM matches WHERE status='suggested' AND EXISTS (
            SELECT 1 FROM lost_reports r JOIN items i ON i.id=matches.item_id
            WHERE r.id=matches.report_id AND lower(trim(r.category)) != lower(trim(i.category)))""")
        saved = []
        for report_id, item_id, details, method in scored:
            if report_id not in active_reports or item_id not in active_items:
                continue
            score, level = details["total"], details["level"]
            if level not in ("strong", "possible"):
                conn.execute("DELETE FROM matches WHERE report_id=? AND item_id=? AND status='suggested'", (report_id, item_id))
                continue
            old = conn.execute("SELECT * FROM matches WHERE report_id=? AND item_id=?", (report_id, item_id)).fetchone()
            if old and old["status"] != "suggested":
                continue
            conn.execute(
                "INSERT INTO matches(report_id,item_id,score,level,method,score_details) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(report_id,item_id) DO UPDATE SET score=excluded.score,level=excluded.level,method=excluded.method,score_details=excluded.score_details",
                (report_id, item_id, score, level, method, json.dumps(details)),
            )
            saved.append({"report_id": report_id, "item_id": item_id, "score": score, "level": level, "method": method})
        saved.sort(key=lambda m: -m["score"])
        log.record(actor, "MATCHING_RUN", f"{len(saved)} suggestions saved; owners are not notified of suggestions")
        return {"suggestions": saved, "count": len(saved)}

    def run_matching_unlocked(self, actor=None):
        """Read candidates, run AI outside any SQLite write lock, then commit results quickly."""
        matcher = self.matcher if self.matcher else ProposalMatcher(self.ai)
        cacheable = self.matcher is None and matcher.method != "typed_details"
        with self.db.connect() as conn:
            reports, items = self._load_candidates(conn)
            photo_paths = {row["photo_path"] for row in reports + items if row.get("photo_path")}
            photo_digests = {path: _file_digest(path) for path in photo_paths} if cacheable else {}
            keys = set()
            if cacheable:
                for report in reports:
                    for item in items:
                        if str(report["category"]).strip().casefold() == str(item["category"]).strip().casefold():
                            keys.add(self._pair_cache_key(matcher, report, item, photo_digests))
            cached_map = self._load_cached(conn, keys) if cacheable else {}
        scored, new_cache, fallback_count = self._score_pairs(matcher, reports, items, cached_map, cacheable, photo_digests)
        with self._tx() as conn:
            return self._persist_results(conn, actor, scored, new_cache, fallback_count)

    def _run_matching(self, conn, actor=None):
        """Score every open report against every available item using a caller-owned connection."""
        matcher = self.matcher if self.matcher else ProposalMatcher(self.ai)
        cacheable = self.matcher is None and matcher.method != "typed_details"
        reports, items = self._load_candidates(conn)
        photo_paths = {row["photo_path"] for row in reports + items if row.get("photo_path")}
        photo_digests = {path: _file_digest(path) for path in photo_paths} if cacheable else {}
        keys = set()
        if cacheable:
            for report in reports:
                for item in items:
                    if str(report["category"]).strip().casefold() == str(item["category"]).strip().casefold():
                        keys.add(self._pair_cache_key(matcher, report, item, photo_digests))
        cached_map = self._load_cached(conn, keys) if cacheable else {}
        scored, new_cache, fallback_count = self._score_pairs(matcher, reports, items, cached_map, cacheable, photo_digests)
        return self._persist_results(conn, actor, scored, new_cache, fallback_count)

    def decide_match(self, admin, match_id, confirmed):
        admin = self._guard(admin, "decide_match")
        if not isinstance(confirmed, bool):
            raise DomainError("Choose confirm or dismiss.")
        with self._tx() as conn:
            match = self._row(conn, "matches", match_id)
            if match["status"] != "suggested":
                raise DomainError("This suggestion has already been reviewed.")
            item = self._row(conn, "items", match["item_id"])
            report = self._row(conn, "lost_reports", match["report_id"])
            if item["status"] != "available" or report["status"] != "open":
                raise DomainError("The item or report is no longer available for matching.")
            elapsed = conn.execute("SELECT julianday('now')-julianday(received_at)>=unclaimed_after_days FROM items WHERE id=?", (item['id'],)).fetchone()[0]
            if confirmed and elapsed:
                raise DomainError('This item has reached the end of its holding period.')
            if confirmed and (report["flagged"] or report["hidden"]):
                raise DomainError("Check this guest's report first (open Lost reports and press Check report), then invite the owner.")
            status = "confirmed" if confirmed else "dismissed"
            conn.execute("UPDATE matches SET status=?,decided_by=? WHERE id=?", (status, admin.id, match_id))
            if confirmed:
                self._notify(conn, report["owner_id"], "CSA found a possible match. Answer a few questions so we can check that it is yours.", report["id"])
            AuditLog(conn).record(admin, "MATCH_" + status.upper(), f"Match {match_id}")
            return self._row(conn, "matches", match_id)
