PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,
 email TEXT NOT NULL UNIQUE COLLATE NOCASE,
 role TEXT NOT NULL CHECK(role IN ('student','professor','guest','admin')),
 password_hash TEXT,
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 blocked INTEGER NOT NULL DEFAULT 0 CHECK(blocked IN (0,1)),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS guest_visit_contacts (
 user_id INTEGER PRIMARY KEY REFERENCES users(id),
 email TEXT NOT NULL CHECK(length(email) BETWEEN 3 AND 254)
);
CREATE TABLE IF NOT EXISTS support_messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id),
 sender_id INTEGER NOT NULL REFERENCES users(id),
 author_role TEXT NOT NULL CHECK(author_role IN ('student','professor','guest','admin')),
 body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 2000),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
 CHECK((author_role = 'admin' AND sender_id <> user_id) OR (author_role <> 'admin' AND sender_id = user_id))
);
CREATE INDEX IF NOT EXISTS support_messages_thread ON support_messages(user_id,id);
CREATE INDEX IF NOT EXISTS support_messages_sender_time ON support_messages(sender_id,created_at);
CREATE TABLE IF NOT EXISTS uploads (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 owner_id INTEGER NOT NULL REFERENCES users(id),
 claim_id INTEGER REFERENCES claims(id),
 kind TEXT NOT NULL,
 path TEXT NOT NULL,
 mime TEXT NOT NULL,
 original_name TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS lost_reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 owner_id INTEGER NOT NULL REFERENCES users(id),
 category TEXT NOT NULL, description TEXT NOT NULL, color TEXT NOT NULL DEFAULT '',
 brand TEXT NOT NULL DEFAULT '', place TEXT NOT NULL, date_lost TEXT NOT NULL,
 identifying_marks TEXT NOT NULL DEFAULT '', photo_id INTEGER REFERENCES uploads(id),
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS found_reports (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 finder_id INTEGER NOT NULL REFERENCES users(id),
 category TEXT NOT NULL, description TEXT NOT NULL, place TEXT NOT NULL,
 date_found TEXT NOT NULL, turn_in_deadline TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'awaiting_turn_in' CHECK(status IN ('awaiting_turn_in','received')),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS items (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 found_report_id INTEGER UNIQUE REFERENCES found_reports(id),
 recorded_by INTEGER NOT NULL REFERENCES users(id),
 category TEXT NOT NULL, description TEXT NOT NULL, color TEXT NOT NULL DEFAULT '',
 brand TEXT NOT NULL DEFAULT '', place TEXT NOT NULL, date_found TEXT NOT NULL,
 private_details TEXT NOT NULL, photo_id INTEGER REFERENCES uploads(id),
 board_type TEXT NOT NULL DEFAULT '',
 board_campus_only INTEGER NOT NULL DEFAULT 0 CHECK(board_campus_only IN (0,1)),
 status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available','under_verification','released','unclaimed')),
 received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
 unclaimed_after_days INTEGER NOT NULL DEFAULT 30 CHECK(unclaimed_after_days > 0)
);
CREATE TABLE IF NOT EXISTS matches (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 report_id INTEGER NOT NULL REFERENCES lost_reports(id),
 item_id INTEGER NOT NULL REFERENCES items(id),
 score REAL NOT NULL CHECK(score BETWEEN 0 AND 100),
 level TEXT NOT NULL CHECK(level IN ('strong','possible')),
 method TEXT NOT NULL,
 score_details TEXT NOT NULL DEFAULT '{}',
 status TEXT NOT NULL DEFAULT 'suggested' CHECK(status IN ('suggested','confirmed','dismissed')),
 withdrawal_reason TEXT NOT NULL DEFAULT '',
 decided_by INTEGER REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
 UNIQUE(report_id,item_id)
);
CREATE TABLE IF NOT EXISTS claims (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 claimant_id INTEGER NOT NULL REFERENCES users(id),
 item_id INTEGER NOT NULL REFERENCES items(id),
 report_id INTEGER NOT NULL REFERENCES lost_reports(id),
 answers TEXT NOT NULL, online_consent INTEGER NOT NULL CHECK(online_consent IN (0,1)),
 status TEXT NOT NULL DEFAULT 'step1_pending' CHECK(status IN ('step1_pending','step2_pending','verified','approved','rejected','released')),
 online_verified_by INTEGER REFERENCES users(id),
 in_person_verified_by INTEGER REFERENCES users(id),
 in_person_consent INTEGER NOT NULL DEFAULT 0 CHECK(in_person_consent IN (0,1)),
 consent_at TEXT, consent_purpose TEXT, consent_recorded_by INTEGER REFERENCES users(id),
 consent_declined_at TEXT,
 reservation_ended INTEGER NOT NULL DEFAULT 0,
 claimant_photo INTEGER REFERENCES uploads(id), id_photo INTEGER REFERENCES uploads(id),
 signature INTEGER REFERENCES uploads(id), evidence_captured_at TEXT,
 approved_by INTEGER REFERENCES users(id), approved_at TEXT,
 released_by INTEGER REFERENCES users(id), released_at TEXT, handover_note TEXT NOT NULL DEFAULT '',
 reason TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
DROP INDEX IF EXISTS one_active_claim_per_item;
CREATE UNIQUE INDEX IF NOT EXISTS one_in_person_claim ON claims(item_id) WHERE status IN ('step2_pending','verified','approved');
CREATE UNIQUE INDEX IF NOT EXISTS one_open_per_claimant ON claims(item_id,claimant_id) WHERE status IN ('step1_pending','step2_pending','verified','approved');
CREATE TABLE IF NOT EXISTS embeddings(cache_key TEXT PRIMARY KEY,vector TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS overdue_notices(report_id INTEGER PRIMARY KEY REFERENCES found_reports(id));
CREATE TABLE IF NOT EXISTS duplicate_reports (
 kind TEXT NOT NULL CHECK(kind IN ('lost','found')),
 report_id INTEGER NOT NULL,
 duplicate_of INTEGER NOT NULL,
 reviewed_by INTEGER REFERENCES users(id),
 PRIMARY KEY(kind,report_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_release_per_item ON claims(item_id) WHERE status='released';
CREATE INDEX IF NOT EXISTS claim_attempts ON claims(claimant_id,item_id,status);
CREATE TABLE IF NOT EXISTS notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER NOT NULL REFERENCES users(id),
 message TEXT NOT NULL, report_id INTEGER REFERENCES lost_reports(id), claim_id INTEGER REFERENCES claims(id),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS audit_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 actor_id INTEGER REFERENCES users(id), action TEXT NOT NULL, detail TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_logs BEGIN SELECT RAISE(ABORT,'Audit logs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_logs BEGIN SELECT RAISE(ABORT,'Audit logs are append-only'); END;
CREATE TRIGGER IF NOT EXISTS item_status_guard BEFORE UPDATE OF status ON items
 WHEN NEW.status != OLD.status AND NOT (
 (OLD.status='available' AND NEW.status IN ('under_verification','unclaimed')) OR
 (OLD.status='under_verification' AND NEW.status IN ('available','released')))
 BEGIN SELECT RAISE(ABORT,'Invalid item status transition'); END;
CREATE TRIGGER IF NOT EXISTS claim_status_guard BEFORE UPDATE OF status ON claims
 WHEN NEW.status != OLD.status AND NOT (
 (OLD.status='step1_pending' AND NEW.status IN ('step2_pending','rejected')) OR
 (OLD.status='step2_pending' AND NEW.status IN ('verified','rejected')) OR
 (OLD.status='verified' AND NEW.status IN ('approved','rejected')) OR
 (OLD.status='approved' AND NEW.status='released'))
 BEGIN SELECT RAISE(ABORT,'Invalid claim status transition'); END;
CREATE TRIGGER IF NOT EXISTS approval_guard BEFORE UPDATE OF status ON claims
 WHEN NEW.status IN ('verified','approved','released') AND
 (NEW.in_person_consent != 1 OR NEW.consent_at IS NULL OR NEW.online_verified_by IS NULL OR
 (NEW.status IN ('approved','released') AND (NEW.in_person_verified_by IS NULL OR NEW.claimant_photo IS NULL OR NEW.id_photo IS NULL OR NEW.signature IS NULL)))
 BEGIN SELECT RAISE(ABORT,'Verification consent and evidence are required'); END;
