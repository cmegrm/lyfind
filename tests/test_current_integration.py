"""Regression checks for the combined 2.0 interface and existing LyFind features."""
import json
import tempfile
import unittest
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile
import test_auth_http as httpbase
from lyfind.database import Database
from lyfind.auth import AuthService
from lyfind.seed import seed_demo
from lyfind.users import User, DomainError
from lyfind.passwords import first_problem
from lyfind.workspace_maintenance import WorkspaceMaintenance
from lyfind.services import Service


class IntegrationTests(unittest.TestCase):
    setUp = httpbase.HTTPTests.setUp
    tearDown = httpbase.HTTPTests.tearDown
    call = httpbase.HTTPTests.call
    login = httpbase.HTTPTests.login

    def test_report_retries_are_scoped_to_account_and_conflicting_edits_are_rejected(self):
        self.login('student')
        payload=dict(category='other',description='Blue umbrella for retry test',color='Blue',brand_choice='unknown',place='Gymnasium',date_lost=date.today().isoformat(),submission_key='a'*48)
        first=self.call('/api/reports/lost',payload)
        again=self.call('/api/reports/lost',payload)
        self.assertEqual(first[0],200,first)
        self.assertEqual(again[0],200,again)
        self.assertEqual(first[1]['data']['id'],again[1]['data']['id'])
        self.assertEqual(self.call('/api/reports/lost',{**payload,'description':'Changed after a lost reply'})[0],409)
        self.login('professor')
        other=self.call('/api/reports/lost',payload)
        self.assertEqual(other[0],200,other)
        self.assertNotEqual(other[1]['data']['id'],first[1]['data']['id'])
        self.assertEqual(self.call('/api/reports/lost',{**payload,'submission_key':{}})[0],400)
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM lost_reports WHERE description=?",(payload['description'],)).fetchone()[0],2)

    def test_simultaneous_report_retries_make_one_record(self):
        self.login('student')
        with self.db.connect() as conn:
            person=User.from_row(conn.execute("SELECT * FROM users WHERE email='demo.student@example.test'").fetchone())
        payload=dict(category='other',description='Concurrent retry umbrella',color='Blue',brand_choice='unknown',place='Gymnasium',date_lost=date.today().isoformat(),submission_key='b'*48)
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda _:self.app.service.create_lost_report(person,payload),range(3)))
        self.assertEqual(len({row['id'] for row in results}),1)
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM lost_reports WHERE description=?",(payload['description'],)).fetchone()[0],1)

    def test_found_retry_does_not_create_inventory_or_allow_guest_found_reports(self):
        self.login('professor')
        payload=dict(category='other',description='Found umbrella retry test',place='Gymnasium',date_found=date.today().isoformat(),where_now='security',submission_key='c'*48)
        with self.db.connect() as conn: before=conn.execute('SELECT COUNT(*) FROM items').fetchone()[0]
        first=self.call('/api/reports/found',payload)
        again=self.call('/api/reports/found',payload)
        self.assertEqual(first[0],200,first)
        self.assertEqual(again[0],200,again)
        self.assertEqual(first[1]['data']['id'],again[1]['data']['id'])
        with self.db.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM items').fetchone()[0],before)
        self.login('guest')
        self.assertEqual(self.call('/api/reports/found',payload)[0],403)

    def test_quick_testing_accounts_keep_their_real_role_permissions(self):
        with self.db.connect() as conn:
            conn.execute("INSERT INTO users(email,role,first_name,last_name) VALUES('demo.student2@example.test','student','Jamie','Flores')")
        for selection in ('student', 'student2', 'professor', 'guest', 'admin'):
            status,result=self.call('/api/auth/demo', {'role':selection})
            self.assertEqual(status,200,result)
            self.csrf=result['data']['csrf_token']
            self.assertEqual(result['data']['user']['role'], 'student' if selection=='student2' else selection)
            self.assertEqual(self.call('/api/dashboard')[0],200)
        self.assertEqual(self.call('/api/auth/demo',{'role':{'email':'someone@example.org'}})[0],400)
        self.app.demo_mode=self.app.auth.demo_mode=False
        for selection in ('student','student2','professor','guest','admin'):
            self.assertEqual(self.call('/api/auth/demo',{'role':selection})[0],404)

    def test_guest_email_code_is_single_use_and_cannot_report_found(self):
        status, result = self.call('/api/auth/guest/request', {'email':'integration@example.org'})
        self.assertEqual(status,200,result)
        code=result['data']['demo_code']
        status,result=self.call('/api/auth/guest/verify',{'email':'integration@example.org','code':code,'remember_browser':True})
        self.assertEqual(status,200,result)
        self.csrf=result['data']['csrf_token']
        self.assertEqual(result['data']['user']['role'],'guest')
        self.assertEqual(self.call('/api/reports/found',{})[0],403)
        self.assertEqual(self.call('/api/auth/guest/verify',{'email':'integration@example.org','code':code})[0],401)
        dashboard=self.call('/api/dashboard')[1]['data']
        self.assertNotIn('found_board',dashboard)
        self.assertEqual(dashboard['recent_found'],[])
        self.assertEqual(self.call('/api/auth/guest/request',{'email':'2025-1-12345@lpunetwork.edu.ph'})[0],400)

    def test_profiles_and_private_staff_messages_survive_account_edits(self):
        self.login('student')
        status,result=self.call('/api/account/save',dict(first_name='Maria',middle_name='Cruz',last_name='Santos',suffix='',phone='09171234567',student_number=''))
        self.assertEqual(status,200,result)
        self.assertEqual(result['data']['user']['name'],'Maria Cruz Santos')
        status,result=self.call('/api/support/send',{'message':'Where can I pick up my item?'})
        self.assertEqual(status,200,result)
        uid=self.call('/api/session')[1]['data']['user']['id']
        self.login('guest')
        self.assertEqual(self.call('/api/support/threads/'+str(uid))[0],403)
        self.login('admin')
        self.assertEqual(self.call('/api/support/threads/'+str(uid))[0],200)
        self.assertEqual(self.call('/api/support/send',{'user_id':uid,'message':'Please bring your ID to CSA.'})[0],200)
        self.login('student')
        self.assertEqual(len(self.call('/api/support')[1]['data']['messages']),2)

    def test_curated_board_excludes_private_details_and_respects_staff_choice(self):
        self.login('admin')
        dashboard=self.call('/api/dashboard')[1]['data']
        item=dashboard['items'][0]
        self.assertEqual(self.call('/api/items/board',{'item_id':item['id'],'published':True})[0],200)
        self.login('student')
        listings=self.call('/api/dashboard')[1]['data']['found_board']
        self.assertTrue(listings)
        self.assertEqual(set(listings[0]),{'category','week','area'})
        self.assertNotIn(item['private_details'],json.dumps(listings))
        self.assertEqual(self.call('/api/items/board',{'item_id':item['id'],'published':False})[0],403)
        self.login('professor')
        self.assertTrue(self.call('/api/dashboard')[1]['data']['found_board'])
        self.login('admin')
        self.call('/api/items/board',{'item_id':item['id'],'published':False})
        self.login('student')
        self.assertEqual(self.call('/api/dashboard')[1]['data']['found_board'],[])

    def test_roster_preview_prevents_stale_or_invalid_commits(self):
        self.login('admin')
        csv='email,name,role\n2025-1-12345@lpunetwork.edu.ph,Review Student,student\n'
        status,result=self.call('/api/roster/preview',{'csv':csv})
        self.assertEqual(status,200,result)
        token=result['data']['preview']
        self.assertEqual(self.call('/api/roster/import',{'csv':csv,'preview':'stale'})[0],409)
        status,result=self.call('/api/roster/import',{'csv':csv,'preview':token})
        self.assertEqual(status,200,result)
        self.assertEqual(result['data']['added'],1)

    def test_proposal_weights_and_backup_permissions(self):
        self.login('student')
        self.assertEqual(self.call('/api/maintenance/backup',{})[0],403)
        self.login('admin')
        dashboard=self.call('/api/dashboard')[1]['data']
        self.assertEqual(dashboard['matching_status']['weights'],dict(description=30,photo=30,color=15,brand=15,place_date=10))
        self.assertEqual(dashboard['matching_status']['thresholds'],dict(strong=60,possible=40))
        status,result=self.call('/api/maintenance/backup',{})
        self.assertEqual(status,200,result)
        with ZipFile(self.root/'data/backups'/result['data']['backup']) as archive:
            self.assertIsNone(archive.testzip())
        self.assertEqual(self.call('/api/maintenance/reset-demo',{'confirmed':True})[0],403)


class MaintenanceTests(unittest.TestCase):
    def test_demo_reset_preserves_live_records_and_creates_complete_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            db=Database(root/'data/demo.sqlite3');db.initialize()
            uploads=root/'data/test-uploads'
            seed_demo(db,uploads)
            auth=AuthService(db)
            with db.connect() as conn:
                admin=User.from_row(conn.execute("SELECT * FROM users WHERE role='admin'").fetchone())
                conn.execute("INSERT INTO notifications(user_id,message) VALUES(?,'before reset')",(admin.id,))
            live=Database(root/'data/csa.sqlite3');live.initialize()
            maintenance=WorkspaceMaintenance(db,root,uploads,True)
            with maintenance.request():
                result=maintenance.reset_demo(admin,True)
            with ZipFile(root/'data/backups'/result['backup']) as archive:
                self.assertIn('demo.sqlite3',archive.namelist())
                self.assertTrue(any(name.startswith('test-uploads/') for name in archive.namelist()))
            self.assertTrue(live.check()['ok'])
            with db.connect() as conn:
                self.assertIsNone(conn.execute("SELECT id FROM notifications WHERE message='before reset'").fetchone())
                self.assertIsNotNone(conn.execute("SELECT id FROM users WHERE email='demo.student2@example.test' AND role='student'").fetchone())
                for row in conn.execute('SELECT path FROM uploads'):
                    self.assertTrue((uploads/row['path']).is_file())

    def test_password_space_does_not_replace_number_or_symbol(self):
        self.assertIsNotNone(first_problem('Abcdefgh '))
        self.assertIsNotNone(first_problem('Abcdefgh1 '))
        self.assertIsNone(first_problem('TestSecret42!'))


class UpgradeTests(unittest.TestCase):
    def test_upgrade_keeps_old_accounts_claim_answers_messages_and_listings(self):
        import sqlite3
        from contextlib import closing
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'csa.sqlite3'
            with closing(sqlite3.connect(path)) as conn:
                conn.executescript((Path(__file__).parent/'fixtures/previous_schema.sql').read_text())
                conn.execute("INSERT INTO users(id,name,email,role) VALUES(1,'CSA Manager','office@example.org','admin')")
                conn.execute("INSERT INTO users(id,name,email,role) VALUES(2,'Maria Santos','2025-1-12345@lpunetwork.edu.ph','student')")
                conn.execute("INSERT INTO lost_reports(id,owner_id,category,description,place,date_lost) VALUES(7,2,'bags','Lost bag','Library','2026-11-01')")
                conn.execute("INSERT INTO items(id,category,description,place,date_found,private_details,recorded_by,board_type) VALUES(8,'bags','Received bag','Library','2026-11-01','Secret label',1,'Backpack')")
                conn.execute("INSERT INTO claims(id,claimant_id,item_id,report_id,answers,online_consent,status) VALUES(9,2,8,7,?,1,'step1_pending')",(json.dumps({'details':'Yellow tag inside'}),))
                conn.execute("INSERT INTO support_messages(user_id,sender_id,author_role,body) VALUES(2,2,'student','My earlier question')")
                conn.commit()
            db=Database(path);db.initialize();db.initialize()
            self.assertTrue(db.check()['ok'])
            with db.connect() as conn:
                person=conn.execute('SELECT * FROM users WHERE id=2').fetchone()
                self.assertEqual(person['name'],'Maria Santos')
                self.assertEqual(person['first_name'],'Maria')
                self.assertEqual(conn.execute('SELECT answer FROM claim_answers WHERE claim_id=9').fetchone()[0],'Yellow tag inside')
                self.assertEqual(conn.execute('SELECT body FROM support_messages').fetchone()[0],'My earlier question')
                self.assertEqual(conn.execute('SELECT board_published FROM items WHERE id=8').fetchone()[0],1)
            self.assertTrue(list((Path(folder)/'backups/schema_migrations').glob('*/csa.sqlite3')))
