"""Exercise configured identity and email adapters without external accounts."""
import os
import smtplib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from lyfind.auth import AuthService
from lyfind.configuration import check_configuration
from lyfind.database import Database
from lyfind.users import DomainError


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"MICROSOFT_TENANT_ID":"", "MICROSOFT_CLIENT_ID":"", "MICROSOFT_CLIENT_SECRET":"", "UNIVERSITY_EMAIL_DOMAINS":"", "SMTP_HOST":"", "SMTP_FROM":"", "SMTP_USER":"", "SMTP_SSL":"0"})
        self.env.start();self.addCleanup(self.env.stop)
        self.db = Database(Path(self.temp.name)/"test.sqlite3");self.db.initialize()
        self.auth = AuthService(self.db, demo_mode=False)

    def microsoft(self):
        self.auth.msal_app = MagicMock()
        self.auth.tenant = "11111111-1111-1111-1111-111111111111"
        self.auth.domains = {"university.example"}
        self.auth.msal_app.initiate_auth_code_flow.return_value = {"auth_uri":"https://login.microsoftonline.com/test", "state":"expected", "nonce":"nonce"}
        self.auth.msal_app.acquire_token_by_auth_code_flow.return_value = {"access_token":"test-only", "id_token_claims":{"tid":self.auth.tenant,"preferred_username":"student@university.example","name":"Student"}}
        session,_ = self.auth.session(None)
        self.auth.microsoft_start(session)
        with self.db.connect() as c:
            session=dict(c.execute("SELECT * FROM sessions WHERE token_hash=?",(session['token_hash'],)).fetchone())
        return session

    def test_authorization_flow_is_consumed_once(self):
        session=self.microsoft()
        self.auth.microsoft_finish(session,{'state':'expected'})
        with self.assertRaises(DomainError):self.auth.microsoft_finish(session,{'state':'expected'})
        self.auth.msal_app.acquire_token_by_auth_code_flow.assert_called_once()

    def test_microsoft_valid_identity_creates_public_user(self):
        session=self.microsoft()
        user=self.auth.microsoft_finish(session,{"code":"test-code","state":"expected"})
        self.assertEqual(user.role,"student")
        flow,response=self.auth.msal_app.acquire_token_by_auth_code_flow.call_args.args
        self.assertEqual(flow["state"],"expected")
        self.assertEqual(response["state"],"expected")
        with self.db.connect() as c:self.assertIsNone(c.execute("SELECT oauth_flow FROM sessions").fetchone()[0])

    def test_wrong_tenant_or_email_domain_is_rejected(self):
        for key,value in [("tid","different-tenant"),("preferred_username","student@university.example.evil.test")]:
            with self.subTest(key=key):
                session=self.microsoft()
                self.auth.msal_app.acquire_token_by_auth_code_flow.return_value["id_token_claims"][key]=value
                with self.assertRaises(DomainError):self.auth.microsoft_finish(session,{"state":"expected"})

    def test_sdk_validation_error_rejects_login(self):
        session=self.microsoft()
        self.auth.msal_app.acquire_token_by_auth_code_flow.side_effect=ValueError("state or nonce mismatch")
        with self.assertRaises(DomainError):self.auth.microsoft_finish(session,{"state":"wrong"})

    def test_microsoft_cannot_reuse_guest_identity_for_university_role(self):
        session=self.microsoft()
        with self.db.connect() as c:c.execute("INSERT INTO users(first_name,email,role) VALUES('Guest','student@university.example','guest')")
        with self.assertRaises(DomainError):self.auth.microsoft_finish(session,{"state":"expected"})

    def test_live_smtp_sends_code_over_tls_without_returning_it(self):
        with patch.dict(os.environ,{"SMTP_HOST":"mail.example","SMTP_FROM":"csa@example.org"}),patch('lyfind.auth.smtplib.SMTP') as smtp:
            self.auth.smtp_enabled=True
            result=self.auth.request_school_code("2025-1-12345@lpunetwork.edu.ph")
            self.assertNotIn("demo_code",result)
            client=smtp.return_value
            client.starttls.assert_called_once()
            message=client.send_message.call_args.args[0]
            self.assertEqual(message['To'],"2025-1-12345@lpunetwork.edu.ph")
            self.assertIn("Use this code",message.get_body(preferencelist=("plain",)).get_content())

    def test_failed_mail_removes_unusable_code(self):
        with patch.dict(os.environ,{"SMTP_HOST":"mail.example","SMTP_FROM":"csa@example.org"}),patch('lyfind.auth.smtplib.SMTP',side_effect=smtplib.SMTPException("unavailable")):
            self.auth.smtp_enabled=True
            with self.assertRaises(DomainError):self.auth.request_school_code("2025-1-12345@lpunetwork.edu.ph")
        with self.db.connect() as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM email_codes WHERE used=0").fetchone()[0],0)

    def test_readiness_does_not_expose_credentials(self):
        with patch.dict(os.environ,{"MICROSOFT_CLIENT_SECRET":"never-print-this"}):
            status=check_configuration()
            self.assertNotIn("never-print-this",str(status))
            self.assertFalse(status['Guest email delivery']['configured'])


if __name__=='__main__':unittest.main()
