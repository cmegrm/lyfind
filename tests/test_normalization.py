"""Normalized storage, migrations, and workflow transactions using temporary files."""
import json
import os
import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lyfind.auth import AuthService
from lyfind.claim_answers import ClaimAnswers
from lyfind.database import Database, SCHEMA_VERSION
from lyfind.seed import seed_demo
from lyfind.services import Service
from lyfind.users import User


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = Database(self.root / 'test.sqlite3')
        self.db.initialize()
        seed_demo(self.db, self.root / 'uploads')
        self.service = Service(self.db, self.root / 'uploads')
        with self.db.connect() as conn:
            self.admin = User.from_row(conn.execute("SELECT * FROM users WHERE role='admin'").fetchone())
            self.claim_id = conn.execute('SELECT id FROM claims LIMIT 1').fetchone()[0]
            self.original = ClaimAnswers(conn).for_claim(self.claim_id)

    def make_legacy(self, answers):
        with self.db.connect() as conn:
            conn.execute("ALTER TABLE claims ADD COLUMN answers TEXT NOT NULL DEFAULT '{}'")
            conn.execute('UPDATE claims SET answers=? WHERE id=?', (answers, self.claim_id))
            conn.execute('DROP TABLE claim_answers')
            conn.execute('PRAGMA user_version = 9')

    def test_answers_are_rows_and_dashboard_keeps_its_dictionary(self):
        with self.db.connect() as conn:
            self.assertNotIn('answers', {r['name'] for r in conn.execute('PRAGMA table_info(claims)')})
            saved = ClaimAnswers(conn).for_claim(self.claim_id)
            self.assertTrue(saved)
        claim = next(c for c in self.service.dashboard(self.admin)['claims'] if c['id'] == self.claim_id)
        self.assertEqual(claim['answers'], saved)

    def test_composite_key_and_foreign_key_reject_invalid_answers(self):
        for claim_id, question, answer in (
            (self.claim_id, next(iter(self.original)), 'duplicate'),
            (999999, 'details', 'missing claim'),
            (self.claim_id, '', 'empty question'),
            (self.claim_id, 'new', ''),
        ):
            with self.subTest(question=question, claim_id=claim_id):
                with self.assertRaises(sqlite3.IntegrityError):
                    with self.db.connect() as conn:
                        ClaimAnswers(conn).save(claim_id, {question: answer})

    def test_failed_answer_write_rolls_back_the_other_answer(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect() as conn:
                ClaimAnswers(conn).save(self.claim_id, {'new': 'temporary', 'invalid': ''})
        with self.db.connect() as conn:
            self.assertEqual(ClaimAnswers(conn).for_claim(self.claim_id), self.original)

    def test_upgrade_preserves_answers_ids_and_creates_a_legacy_backup(self):
        answers = {'details': 'Initials KM', 'contents': 'Blue receipt, red card'}
        self.make_legacy(json.dumps(answers))
        self.db.initialize()
        self.db.initialize()
        with self.db.connect() as conn:
            self.assertEqual(ClaimAnswers(conn).for_claim(self.claim_id), answers)
            self.assertNotIn('answers', {r['name'] for r in conn.execute('PRAGMA table_info(claims)')})
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], SCHEMA_VERSION)
        backups = list((self.root / 'backups' / 'schema_migrations').glob('*/test.sqlite3'))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as conn:
            self.assertEqual(json.loads(conn.execute('SELECT answers FROM claims WHERE id=?', (self.claim_id,)).fetchone()[0]), answers)
        self.assertTrue(self.db.check()['ok'])

    def test_bad_legacy_json_leaves_original_schema_and_version_intact(self):
        self.make_legacy('this is not JSON')
        with self.assertRaisesRegex(ValueError, 'invalid JSON'):
            self.db.initialize()
        with self.db.connect() as conn:
            self.assertEqual(conn.execute('SELECT answers FROM claims WHERE id=?', (self.claim_id,)).fetchone()[0], 'this is not JSON')
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 9)
            self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='claim_answers'").fetchone())

    def test_display_name_is_computed_and_cannot_be_overwritten(self):
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE users SET first_name='John Keneth',middle_name='Lopez',last_name='Miole',suffix='Jr.' WHERE id=?",
                (self.admin.id,),
            )
            name = conn.execute('SELECT name FROM users WHERE id=?', (self.admin.id,)).fetchone()[0]
            self.assertEqual(name, 'John Keneth Lopez Miole Jr.')
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("UPDATE users SET name='Stale cache' WHERE id=?", (self.admin.id,))

    def test_legacy_names_are_migrated_without_breaking_references(self):
        with self.db.connect() as conn:
            people = [dict(row) for row in conn.execute('SELECT id,name,email FROM users')]
            conn.execute('ALTER TABLE users DROP COLUMN name')
            conn.execute("ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ''")
            for person in people:
                conn.execute(
                    "UPDATE users SET name=?,first_name='',middle_name='',last_name='',suffix='' WHERE id=?",
                    (person['name'], person['id']),
                )
            conn.execute('PRAGMA user_version=9')
        self.db.initialize()
        self.db.initialize()
        with self.db.connect() as conn:
            self.assertEqual([dict(row) for row in conn.execute('SELECT id,name,email FROM users')], people)
            name_column = next(row for row in conn.execute('PRAGMA table_xinfo(users)') if row['name']=='name')
            self.assertEqual(name_column['hidden'], 2)  # VIRTUAL generated column
        self.assertTrue(self.db.check()['ok'])
        claim = next(c for c in self.service.dashboard(self.admin)['claims'] if c['id']==self.claim_id)
        self.assertEqual(claim['answers'], self.original)

    def test_profile_and_staff_updates_write_name_parts(self):
        user = self.service.update_profile(self.admin, {
            'first_name': 'John Keneth', 'middle_name': 'Lopez',
            'last_name': 'Miole', 'suffix': 'Jr.', 'phone': '',
        })
        self.assertEqual(user.name, 'John Keneth Lopez Miole Jr.')
        staff = self.service.manage_staff(user, {
            'action': 'create', 'name': 'Daniel Cruz', 'email': 'daniel@example.org',
            'password': 'VioletKettle42!',
        })
        updated = self.service.manage_staff(user, {
            'action': 'update', 'user_id': staff['id'], 'name': 'Daniel Reyes',
        })
        self.assertEqual(updated['name'], 'Daniel Reyes')
        self.assertEqual(updated['last_name'], 'Reyes')

    def test_guest_and_school_signup_write_parts_and_allow_password_login(self):
        with patch.dict(os.environ, {
            'SMTP_HOST': '', 'SMTP_FROM': '', 'MICROSOFT_TENANT_ID': '',
            'MICROSOFT_CLIENT_ID': '', 'UNIVERSITY_EMAIL_DOMAINS': 'lpunetwork.edu.ph,lpu.edu.ph',
        }):
            auth = AuthService(self.db, demo_mode=True)
            email = 'new.guest@example.org'
            sent = auth.register(email)
            setup = auth.verify_signup(email, sent['demo_code'])
            guest = auth.finish_guest(email, setup['setup_token'], 'VioletKettle42!',
                                      first_name='John Keneth', last_name='Miole')
            self.assertEqual(guest.name, 'John Keneth Miole')
            self.assertEqual(auth.password_login(email, 'VioletKettle42!').id, guest.id)
            email = '2025-2-01234@lpunetwork.edu.ph'
            self.service.roster_save(self.admin, {'email': email, 'role': 'student'})
            sent = auth.request_school_code(email)
            setup = auth.verify_school_code(email, sent['demo_code'])
            student = auth.set_school_password(email, setup['setup_token'], 'VioletKettle42!',
                                               first_name='Maria', last_name='Reyes')
            self.assertEqual(student.name, 'Maria Reyes')
            self.assertEqual(student.student_number, '2025-2-01234')
            self.assertEqual(auth.password_login(email, 'VioletKettle42!').id, student.id)

    def test_future_schema_is_refused_without_downgrading_it(self):
        with self.db.connect() as conn:
            conn.execute(f'PRAGMA user_version = {SCHEMA_VERSION + 1}')
        with self.assertRaisesRegex(ValueError, 'newer version'):
            self.db.initialize()
        with self.db.connect() as conn:
            self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], SCHEMA_VERSION + 1)


if __name__ == '__main__':
    unittest.main()
