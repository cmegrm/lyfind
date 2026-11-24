"""School-email codes, the allowed-email roster, guest verification, daily caps, staff tools and hidden details."""
import base64
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_auth_http as http_base
from lyfind.auth import DENIED
from lyfind.seed import sample_image
from lyfind.users import DomainError, User


class Base(unittest.TestCase):
    setUp = http_base.HTTPTests.setUp
    tearDown = http_base.HTTPTests.tearDown
    call = http_base.HTTPTests.call
    login = http_base.HTTPTests.login

    def dashboard(self):
        status, result = self.call("/api/dashboard")
        self.assertEqual(status, 200, result)
        return result["data"]

    def sign_in_with_code(self, email, code, password="CampusPass42!"):
        """Check the emailed code, then set the password that later sign-ins use."""
        status, result = self.call("/api/auth/school/verify", {"email": email, "code": code})
        if status != 200:
            return status, result
        status, result = self.call("/api/auth/school/password", {
            "email": email, "setup_token": result["data"]["setup_token"],
            "name": "New Person", "password": password, "confirm": password,
        })
        if status == 200:
            self.csrf = result["data"]["csrf_token"]
        return status, result

    def fresh_client(self):
        """Forget cookies and take a new anti-forgery token, like a new browser."""
        self.jar.clear()
        self.csrf = self.call("/api/config")[1]["data"]["csrf_token"]

    def user_row(self, email):
        with self.db.connect() as conn:
            return dict(conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone())


class SchoolEmailCodeTests(Base):
    def test_an_account_with_a_password_signs_in_with_that_password(self):
        for email, role in (("demo.student@example.test", "student"), ("demo.professor@example.test", "professor")):
            self.fresh_client()
            status, result = self.call("/api/auth/school/request", {"email": email})
            self.assertEqual(status, 400, result)
            self.assertIn("password", result["error"])
            status, result = self.call("/api/auth/login", {"email": email, "password": "DemoOnly!2026"})
            self.assertEqual(status, 200, result)
            self.assertEqual(result["data"]["user"]["role"], role)

    def test_a_new_school_email_sets_a_password_and_then_uses_it(self):
        email = "2024-1-10001@lpunetwork.edu.ph"
        status, result = self.call("/api/auth/school/request", {"email": email})
        self.assertEqual(status, 200, result)
        status, result = self.sign_in_with_code(email, result["data"]["demo_code"], "LockerKey42!")
        self.assertEqual(status, 200, result)
        self.assertEqual(result["data"]["user"]["role"], "student")
        self.fresh_client()
        status, again = self.call("/api/auth/school/request", {"email": email})
        self.assertEqual(status, 400)
        self.assertIn("password", again["error"])
        status, result = self.call("/api/auth/login", {"email": email, "password": "LockerKey42!"})
        self.assertEqual(status, 200, result)
        self.assertEqual(self.call("/api/dashboard")[0], 200)
        row = self.user_row(email)
        self.assertEqual((row["first_name"], row["last_name"], row["name"]), ("New", "Person", "New Person"))

    def test_a_school_account_stores_each_part_of_the_name(self):
        email = "2024-1-10002@lpunetwork.edu.ph"
        status, result = self.call("/api/auth/school/request", {"email": email})
        self.assertEqual(status, 200, result)
        status, checked = self.call("/api/auth/school/verify", {"email": email, "code": result["data"]["demo_code"]})
        self.assertEqual(status, 200, checked)
        token = checked["data"]["setup_token"]
        status, rejected = self.call("/api/auth/school/password", {
            "email": email, "setup_token": token, "first_name": "A", "last_name": "Cruz",
            "password": "LockerKey42!", "confirm": "LockerKey42!",
        })
        self.assertEqual(status, 400, rejected)
        status, created = self.call("/api/auth/school/password", {
            "email": email, "setup_token": token,
            "first_name": "Juan", "middle_name": "Dela", "last_name": "Cruz", "suffix": "Jr.",
            "password": "LockerKey42!", "confirm": "LockerKey42!",
        })
        self.assertEqual(status, 200, created)
        self.assertEqual(created["data"]["user"]["name"], "Juan Dela Cruz Jr.")
        row = self.user_row(email)
        self.assertEqual((row["first_name"], row["middle_name"], row["last_name"], row["suffix"]),
                         ("Juan", "Dela", "Cruz", "Jr."))

    def test_unlisted_address_gets_the_neutral_message_and_no_code(self):
        status, other = self.call("/api/auth/school/request", {"email": "someone.else@gmail.com"})
        self.assertEqual((status, other["error"]), (400, "Use your @lpunetwork.edu.ph school email."))
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM email_codes WHERE email LIKE 'someone.else%'").fetchone()[0], 0)
        self.app.demo_mode = self.app.auth.demo_mode = False
        with patch("lyfind.auth.smtplib.SMTP"), patch.dict(os.environ, {"SMTP_HOST": "mail.example", "SMTP_FROM": "csa@example.org"}):
            self.app.auth.smtp_enabled = True
            status, result = self.call("/api/auth/school/request", {"email": "2026-1-19999@lpunetwork.edu.ph"})
        self.assertEqual((status, result["error"]), (403, DENIED))
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM email_codes WHERE email='2026-1-19999@lpunetwork.edu.ph'").fetchone()[0], 0)

    def test_demo_mode_allows_a_valid_student_email_that_is_not_on_the_roster(self):
        status, result = self.call("/api/auth/school/request", {"email": "2024-1-00001@lpunetwork.edu.ph"})
        self.assertEqual(status, 200, result)
        status, result = self.sign_in_with_code("2024-1-00001@lpunetwork.edu.ph", result["data"]["demo_code"])
        self.assertEqual(status, 200, result)
        self.assertEqual(result["data"]["user"]["role"], "student")
        self.assertEqual(self.user_row("2024-1-00001@lpunetwork.edu.ph")["student_number"], "2024-1-00001")

    def test_empty_roster_allows_the_school_domain_only_and_new_accounts_start_as_students(self):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM roster")
        self.assertEqual(self.call("/api/auth/school/request", {"email": "outsider@gmail.com"})[0], 400)
        status, result = self.call("/api/auth/school/request", {"email": "2026-1-10002@LPUNETWORK.edu.ph"})
        self.assertEqual(status, 200, result)
        status, result = self.sign_in_with_code("2026-1-10002@lpunetwork.edu.ph", result["data"]["demo_code"])
        self.assertEqual(status, 200, result)
        self.assertEqual(result["data"]["user"]["role"], "student")
        self.assertEqual(self.user_row("2026-1-10002@lpunetwork.edu.ph")["email_verified"], 1)

    def test_roster_role_decides_student_or_professor_and_inactive_rows_are_refused(self):
        with self.db.connect() as conn:
            conn.execute("INSERT INTO roster(email,name,role) VALUES('prof.new@lpunetwork.edu.ph','Prof New','professor')")
            conn.execute("INSERT INTO roster(email,name,role,active) VALUES('gone@lpunetwork.edu.ph','Gone','student',0)")
        status, result = self.call("/api/auth/school/request", {"email": "prof.new@lpunetwork.edu.ph"})
        status, result = self.sign_in_with_code("prof.new@lpunetwork.edu.ph", result["data"]["demo_code"])
        self.assertEqual(result["data"]["user"]["role"], "professor")
        self.fresh_client()
        self.assertEqual(self.call("/api/auth/school/request", {"email": "gone@lpunetwork.edu.ph"})[1]["error"], DENIED)

    def test_code_is_hashed_single_use_and_six_digits(self):
        _, result = self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})
        code = result["data"]["demo_code"]
        with self.db.connect() as conn:
            row = dict(conn.execute("SELECT * FROM email_codes").fetchone())
        self.assertNotIn(code, json.dumps(row))
        self.assertEqual(len(row["code_hash"]), 64)
        self.assertAlmostEqual(row["expires"] - row["requested"], 600, delta=1)
        self.assertEqual(self.sign_in_with_code("2024-1-20001@lpunetwork.edu.ph", code)[0], 200)
        self.fresh_client()
        self.assertEqual(self.sign_in_with_code("2024-1-20001@lpunetwork.edu.ph", code)[0], 401)

    def test_expired_code_is_refused(self):
        _, result = self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})
        with self.db.connect() as conn:
            conn.execute("UPDATE email_codes SET expires=?", (time.time() - 1,))
        status, result = self.sign_in_with_code("2024-1-20001@lpunetwork.edu.ph", result["data"]["demo_code"])
        self.assertEqual(status, 401)
        self.assertIn("expired", result["error"])

    def test_five_wrong_tries_cancel_the_code_even_for_the_right_digits(self):
        _, result = self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})
        code = result["data"]["demo_code"]
        wrong = "111111" if code != "111111" else "222222"
        for left in (4, 3, 2, 1):
            status, result = self.sign_in_with_code("2024-1-20001@lpunetwork.edu.ph", wrong)
            self.assertEqual(status, 401)
            self.assertIn(f"{left} ", result["error"])
        status, result = self.sign_in_with_code("2024-1-20001@lpunetwork.edu.ph", wrong)
        self.assertIn("cancelled", result["error"])
        self.assertEqual(self.sign_in_with_code("2024-1-20001@lpunetwork.edu.ph", code)[0], 401)

    def test_resend_needs_a_wait_and_a_new_code_replaces_the_old_one(self):
        status, first = self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})
        status, again = self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})
        self.assertEqual(status, 429)
        self.assertIn("wait", again["error"].lower())
        self.app.auth.resend_seconds = 0
        status, second = self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})
        self.assertEqual(status, 200)
        if second["data"]["demo_code"] != first["data"]["demo_code"]:
            self.assertEqual(self.sign_in_with_code("2024-1-20001@lpunetwork.edu.ph", first["data"]["demo_code"])[0], 401)
        self.assertEqual(self.sign_in_with_code("2024-1-20001@lpunetwork.edu.ph", second["data"]["demo_code"])[0], 200)

    def test_requests_are_limited_per_email_and_per_address(self):
        self.app.auth.resend_seconds = 0
        self.app.demo_mode = self.app.auth.demo_mode = False
        with self.db.connect() as conn:
            conn.execute("DELETE FROM roster")
        with patch("lyfind.auth.smtplib.SMTP"), patch.dict(os.environ, {"SMTP_HOST": "mail.example", "SMTP_FROM": "csa@example.org"}):
            self.app.auth.smtp_enabled = True
            results = [self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})[0] for _ in range(6)]
            self.assertEqual(results, [200] * 5 + [429])
            with self.db.connect() as conn:
                conn.execute("DELETE FROM rate_events")
                for _ in range(20):
                    conn.execute("INSERT INTO rate_events(bucket,at) VALUES(?,?)", ("code:ip:127.0.0.1", time.time()))
            status, result = self.call("/api/auth/school/request", {"email": "2024-1-20002@lpunetwork.edu.ph"})
            self.assertEqual(status, 429)

    def test_wrong_codes_are_limited_per_address(self):
        with self.db.connect() as conn:
            for _ in range(20):
                conn.execute("INSERT INTO rate_events(bucket,at) VALUES(?,?)", ("wrong:ip:127.0.0.1", time.time()))
        _, result = self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})
        status, result = self.sign_in_with_code("2024-1-20001@lpunetwork.edu.ph", result["data"]["demo_code"])
        self.assertEqual(status, 429)

    def test_blocked_or_staff_accounts_get_the_neutral_message(self):
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET blocked=1 WHERE email='demo.student@example.test'")
            conn.execute("INSERT INTO roster(email,name,role) VALUES('demo.admin@example.test','x','student')")
        self.assertEqual(self.call("/api/auth/school/request", {"email": "demo.student@example.test"})[1]["error"], DENIED)
        self.assertEqual(self.call("/api/auth/school/request", {"email": "demo.admin@example.test"})[1]["error"], DENIED)

    def test_live_mode_needs_email_and_never_reveals_codes(self):
        self.app.demo_mode = self.app.auth.demo_mode = False
        with self.db.connect() as conn:
            conn.execute("DELETE FROM roster")
        status, result = self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})
        self.assertEqual(status, 503)
        self.assertNotIn("demo_code", json.dumps(result))
        with patch("lyfind.auth.smtplib.SMTP") as smtp:
            self.app.auth.smtp_enabled = True
            with patch.dict(os.environ, {"SMTP_HOST": "mail.example", "SMTP_FROM": "csa@example.org"}):
                status, result = self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})
        self.assertEqual(status, 200, result)
        self.assertNotIn("demo_code", result["data"])
        self.assertIn("Use this code", smtp.return_value.send_message.call_args.args[0].get_body(preferencelist=('plain',)).get_content())

    def test_demo_code_is_hidden_when_email_is_configured_even_in_demo_mode(self):
        with patch("lyfind.auth.smtplib.SMTP"), patch.dict(os.environ, {"SMTP_HOST": "mail.example", "SMTP_FROM": "csa@example.org"}):
            self.app.auth.smtp_enabled = True
            status, result = self.call("/api/auth/school/request", {"email": "2024-1-20001@lpunetwork.edu.ph"})
        self.assertEqual(status, 200, result)
        self.assertNotIn("demo_code", result["data"])

    def test_config_does_not_leak_the_roster_or_secrets(self):
        config = self.call("/api/config")[1]["data"]
        self.assertTrue(config["school_email_ready"])
        self.assertNotIn("roster", config)
        self.assertEqual(config["school_domains"], ["lpunetwork.edu.ph"])


class StudentEmailFormatTests(Base):
    """LPU student emails look like 2025-2-01345@lpunetwork.edu.ph."""

    def empty_roster(self):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM roster")

    def test_valid_student_email_signs_in_and_the_student_number_is_saved(self):
        self.empty_roster()
        status, result = self.call("/api/auth/school/request", {"email": "2025-2-01345@LPUnetwork.edu.ph"})
        self.assertEqual(status, 200, result)
        status, result = self.sign_in_with_code("2025-2-01345@lpunetwork.edu.ph", result["data"]["demo_code"])
        self.assertEqual(status, 200, result)
        self.assertEqual(result["data"]["user"]["role"], "student")
        self.assertEqual(self.user_row("2025-2-01345@lpunetwork.edu.ph")["student_number"], "2025-2-01345")

    def test_wrong_formats_get_a_friendly_message(self):
        self.empty_roster()
        year = __import__("datetime").date.today().year
        for email in ("maria@lpunetwork.edu.ph", "2025-2-1345@lpunetwork.edu.ph", "2025-22-01345@lpunetwork.edu.ph",
                      "1999-2-01345@lpunetwork.edu.ph", f"{year + 1}-2-01345@lpunetwork.edu.ph", "2025-2-0134a@lpunetwork.edu.ph",
                      "2025-2-01345 @lpunetwork.edu.ph"):
            status, result = self.call("/api/auth/school/request", {"email": email})
            self.assertEqual(status, 400, email)
            self.assertIn("@lpunetwork.edu.ph", result["error"])
        self.assertEqual(self.call("/api/auth/school/request", {"email": f"{year}-2-01345@lpunetwork.edu.ph"})[0], 200)
        self.assertEqual(self.call("/api/auth/school/request", {"email": "2000-9-00001@lpunetwork.edu.ph"})[0], 200)

    def test_campus_codes_are_optional_and_restrict_the_middle_digit(self):
        self.empty_roster()
        self.assertEqual(self.call("/api/auth/school/request", {"email": "2025-7-01345@lpunetwork.edu.ph"})[0], 200)  # empty = any digit
        self.fresh_client()
        self.app.auth.campus_codes = frozenset({"2"})
        self.assertEqual(self.call("/api/auth/school/request", {"email": "2025-7-01345@lpunetwork.edu.ph"})[0], 400)
        self.assertEqual(self.call("/api/auth/school/request", {"email": "2025-2-01345@lpunetwork.edu.ph"})[0], 200)

    def test_professors_use_the_school_domain_and_the_roster_role(self):
        with self.db.connect() as conn:
            conn.execute("INSERT INTO roster(email,name,role) VALUES('maria.prof@lpunetwork.edu.ph','Maria Prof','professor')")
            conn.execute("INSERT INTO roster(email,name,role) VALUES('dr.cruz@lpunetwork.edu.ph','Dr Cruz','professor')")
        for email in ("maria.prof@lpunetwork.edu.ph", "dr.cruz@lpunetwork.edu.ph"):
            self.fresh_client()
            _, result = self.call("/api/auth/school/request", {"email": email})
            status, result = self.sign_in_with_code(email, result["data"]["demo_code"])
            self.assertEqual((status, result["data"]["user"]["role"]), (200, "professor"), email)
            self.assertEqual(self.user_row(email)["student_number"], "")
        self.empty_roster()
        self.fresh_client()
        self.assertEqual(self.call("/api/auth/school/request", {"email": "2026-1-10003@lpunetwork.edu.ph"})[0], 200)  # lpu.edu.ph default role: student

    def test_roster_fills_in_the_student_number_and_staff_see_it(self):
        self.login("admin")
        self.assertEqual(self.call("/api/roster/save", {"action": "add", "email": "2024-1-00077@lpunetwork.edu.ph", "name": "Lea Reyes", "role": "student"})[0], 200)
        csv_text = "email,name,role\n2023-2-00123@lpunetwork.edu.ph,Ben,student\ndr.x@lpunetwork.edu.ph,Dr X,professor\n"
        self.assertEqual(self.call("/api/roster/import", {"csv": csv_text})[0], 200)
        numbers = {row["email"]: row["student_number"] for row in self.dashboard()["roster"]}
        self.assertEqual(numbers["2024-1-00077@lpunetwork.edu.ph"], "2024-1-00077")
        self.assertEqual(numbers["2023-2-00123@lpunetwork.edu.ph"], "2023-2-00123")
        self.assertEqual(numbers["dr.x@lpunetwork.edu.ph"], "")

    def test_staff_see_the_student_number_on_claims_and_people(self):
        self.login("admin")
        data = self.dashboard()
        self.assertTrue(any(person["student_number"] == "2025-2-00001" for person in data["people"]))
        self.assertTrue(all("claimant_student_number" in claim for claim in data["claims"]))

    def test_guests_cannot_sign_up_with_a_school_address_and_demo_accounts_still_work(self):
        body = {"name": "Pat", "email": "2025-2-01345@lpunetwork.edu.ph", "password": "Orchid-Lantern-47!", "confirm": "Orchid-Lantern-47!"}
        self.assertEqual(self.call("/api/auth/register", body)[0], 400)
        status, result = self.call("/api/auth/login", {"email": "demo.guest@example.test", "password": "DemoOnly!2026"})
        self.assertEqual(status, 200, result)


class GuestSignUpTests(Base):
    body = {"email": "visitor@example.org"}
    password = "BlueKettle42!"

    def finish_guest(self, email, code, password=None):
        status, result = self.call("/api/auth/register/verify", {"email": email, "code": code})
        if status != 200:
            return status, result
        status, result = self.call("/api/auth/register/finish", {
            "email": email, "setup_token": result["data"]["setup_token"],
            "first_name": "Visitor", "last_name": "Guest",
            "password": password or self.password, "confirm": password or self.password,
        })
        if status == 200:
            self.csrf = result["data"]["csrf_token"]
        return status, result

    def test_no_account_exists_until_the_code_and_password_are_set(self):
        status, result = self.call("/api/auth/register", self.body)
        self.assertEqual(status, 200, result)
        with self.db.connect() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM users WHERE email=?", ("visitor@example.org",)).fetchone())
        status, login = self.call("/api/auth/login", {"email": "visitor@example.org", "password": self.password})
        self.assertEqual(status, 401)
        self.assertEqual(self.call("/api/dashboard")[0], 401)
        status, ok = self.finish_guest("visitor@example.org", result["data"]["demo_code"])
        self.assertEqual(status, 200, ok)
        self.assertEqual(self.user_row("visitor@example.org")["email_verified"], 1)
        self.assertEqual(self.user_row("visitor@example.org")["first_name"], "Visitor")

    def test_wrong_and_expired_codes_do_not_open_an_account(self):
        _, result = self.call("/api/auth/register", self.body)
        code = result["data"]["demo_code"]
        wrong = "111111" if code != "111111" else "222222"
        self.assertEqual(self.call("/api/auth/register/verify", {"email": "visitor@example.org", "code": wrong})[0], 401)
        with self.db.connect() as conn:
            conn.execute("UPDATE email_codes SET expires=?", (time.time() - 1,))
        self.assertEqual(self.call("/api/auth/register/verify", {"email": "visitor@example.org", "code": code})[0], 401)
        with self.db.connect() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM users WHERE email=?", ("visitor@example.org",)).fetchone())

    def test_resend_replaces_the_code_for_an_unconfirmed_sign_up(self):
        _, result = self.call("/api/auth/register", self.body)
        self.assertEqual(self.call("/api/auth/register/resend", {"email": "visitor@example.org"})[0], 429)
        self.app.auth.resend_seconds = 0
        status, again = self.call("/api/auth/register/resend", {"email": "visitor@example.org"})
        self.assertEqual(status, 200)
        status, verified = self.finish_guest("visitor@example.org", again["data"]["demo_code"])
        self.assertEqual(status, 200, verified)
        self.assertEqual(self.call("/api/auth/register/resend", {"email": "nobody@example.org"})[0], 404)

    def test_disposable_domains_and_the_honeypot_are_refused(self):
        status, result = self.call("/api/auth/register", {**self.body, "email": "x@mailinator.com"})
        self.assertEqual(status, 400)
        self.assertIn("email", result["fields"])
        status, result = self.call("/api/auth/register", {**self.body, "website": "http://spam.example"})
        self.assertEqual(status, 400)
        with self.db.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM users WHERE email LIKE 'visitor%'").fetchone()[0], 0)

    def test_sign_ups_are_limited_per_address(self):
        statuses = [self.call("/api/auth/register", {"email": f"person{n}@example.org"})[0] for n in range(11)]
        self.assertEqual(statuses[:10], [200] * 10)
        self.assertEqual(statuses[10], 429)

    def test_a_confirmed_guest_cannot_be_overwritten_by_a_new_sign_up(self):
        _, result = self.call("/api/auth/register", self.body)
        status, verified = self.finish_guest("visitor@example.org", result["data"]["demo_code"])
        self.assertEqual(status, 200, verified)
        self.app.auth.resend_seconds = 0
        status, result = self.call("/api/auth/register", self.body)
        self.assertEqual(status, 400)
        self.assertEqual(self.call("/api/auth/login", {"email": "visitor@example.org", "password": self.password})[0], 200)

    def test_optional_phone_is_saved_for_pickup(self):
        _, result = self.call("/api/auth/register", {"email": "phone.guest@example.org"})
        status, checked = self.call("/api/auth/register/verify", {"email": "phone.guest@example.org", "code": result["data"]["demo_code"]})
        status, done = self.call("/api/auth/register/finish", {
            "email": "phone.guest@example.org", "setup_token": checked["data"]["setup_token"],
            "first_name": "Phone", "last_name": "Guest", "password": self.password, "confirm": self.password,
            "phone": "0917 555 0199",
        })
        self.assertEqual(status, 200, done)
        self.assertEqual(self.user_row("phone.guest@example.org")["phone"], "0917 555 0199")


class CapsAndFlagsTests(Base):
    report = {"category": "other", "description": "Blue notebook", "color": "Blue", "brand_choice": "unknown",
              "place": "Library", "date_lost": time.strftime("%Y-%m-%d")}

    def test_guest_reports_are_flagged_and_capped_per_day(self):
        self.login("guest")  # the sample guest already has two reports
        status, result = self.call("/api/reports/lost", self.report)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["data"]["flagged"], 1)
        status, result = self.call("/api/reports/lost", self.report)
        self.assertEqual(status, 429)
        self.assertIn("limit of 3 lost reports", result["error"])
        self.assertIn("tomorrow", result["error"])

    def test_students_have_a_higher_cap(self):
        student = User.from_row(self.user_row('demo.student@example.test'))
        service = self.app.service
        made = 0
        with self.assertRaises(DomainError) as caught:
            for _ in range(12):
                service.create_lost_report(student, self.report)
                made += 1
        self.assertEqual(made, 9)  # one sample report already exists
        self.assertEqual(caught.exception.status, 429)
        found = {"category": "other", "description": "Umbrella", "place": "Gym", "date_found": self.report["date_lost"], "turn_in_deadline": self.report["date_lost"]}
        with self.assertRaises(DomainError):
            for _ in range(12):
                service.create_found_report(student, found)

    def test_claim_cap_applies_and_staff_have_none(self):
        row = lambda email: User.from_row(self.user_row(email))
        student, admin = row("demo.student@example.test"), row("demo.admin@example.test")
        with self.db.connect() as conn:
            item, report = conn.execute("SELECT id FROM items LIMIT 1").fetchone()[0], conn.execute("SELECT id FROM lost_reports LIMIT 1").fetchone()[0]
            self.app.service._daily_cap(conn, student, "claim")  # nothing yet
            for _ in range(5):
                conn.execute("INSERT INTO claims(claimant_id,item_id,report_id,online_consent,status) VALUES(?,?,?,1,'rejected')",
                             (student.id, item, report))
            with self.assertRaises(DomainError) as caught:
                self.app.service._daily_cap(conn, student, "claim")
            self.assertIn("limit of 5 claims", str(caught.exception))
            self.app.service._daily_cap(conn, admin, "claim")  # staff have no cap

    def test_a_flagged_report_must_be_checked_before_the_owner_is_invited(self):
        self.login("admin")
        data = self.dashboard()
        pending = next(r for r in data["reports"] if r["flagged"])
        self.assertEqual(pending["owner_role"], "guest")
        service, admin = self.app.service, User.from_row(self.user_row('demo.admin@example.test'))
        guest = User.from_row(self.user_row('demo.guest@example.test'))
        report = service.create_lost_report(guest, {"category": "electronics", "description": "Black smartphone with a plain dark case", "color": "Black",
                                                    "brand_choice": "unknown", "place": "Jose P. Laurel (JPL) Building", "date_lost": time.strftime("%Y-%m-%d", time.gmtime(time.time() - 86400))})
        with self.db.connect() as conn:
            match = conn.execute("SELECT * FROM matches WHERE report_id=?", (report["id"],)).fetchone()
        self.assertIsNotNone(match)
        with self.assertRaises(DomainError) as caught:
            service.decide_match(admin, match["id"], True)
        self.assertIn("Check this guest", str(caught.exception))
        service.review_report(admin, {"kind": "lost", "id": report["id"], "action": "checked"})
        self.assertEqual(service.decide_match(admin, match["id"], True)["status"], "confirmed")

    def test_guest_claims_start_flagged_and_the_online_check_clears_it(self):
        self.login("admin")
        claim = next(c for c in self.dashboard()["claims"])
        self.assertEqual(claim["flagged"], 1)
        status, result = self.call("/api/claims/online", {"claim_id": claim["id"], "passed": True})
        self.assertEqual(status, 200, result)
        self.assertEqual(result["data"]["flagged"], 0)

    def test_input_length_limits(self):
        self.login("student")
        status, result = self.call("/api/reports/lost", {**self.report, "description": "x" * 2500})
        self.assertEqual(status, 400)
        self.assertIn("too long", result["error"])


class StaffToolTests(Base):
    def test_block_and_unblock_end_sessions_and_leave_an_audit_trail(self):
        student = self.user_row("demo.student@example.test")
        self.login("student")
        self.assertEqual(self.call("/api/dashboard")[0], 200)
        self.fresh_client()
        self.login("admin")
        status, result = self.call("/api/users/block", {"user_id": student["id"], "blocked": True, "reason": "Spam reports"})
        self.assertEqual(status, 200, result)
        actions = [a["action"] for a in self.dashboard()["audit"]]
        self.assertIn("USER_BLOCKED", actions)
        person = next(p for p in self.dashboard()["people"] if p["id"] == student["id"])
        self.assertEqual(person["blocked"], 1)
        # the blocked person cannot sign in by password or school email, and sees a neutral message
        self.fresh_client()
        status, result = self.call("/api/auth/login", {"email": "demo.student@example.test", "password": "DemoOnly!2026"})
        self.assertEqual(status, 403)
        self.assertEqual(result["error"], "We could not sign you in. Contact the CSA office.")
        self.assertEqual(self.call("/api/auth/school/request", {"email": "demo.student@example.test"})[1]["error"], DENIED)
        self.fresh_client()
        self.login("admin")
        self.assertEqual(self.call("/api/users/block", {"user_id": student["id"], "blocked": False})[0], 200)
        self.assertIn("USER_UNBLOCKED", [a["action"] for a in self.dashboard()["audit"]])
        self.fresh_client()
        self.assertEqual(self.call("/api/auth/login", {"email": "demo.student@example.test", "password": "DemoOnly!2026"})[0], 200)

    def test_blocking_needs_a_reason_and_never_applies_to_staff_or_non_staff_callers(self):
        self.login("admin")
        student = self.user_row("demo.student@example.test")
        status, result = self.call("/api/users/block", {"user_id": student["id"], "blocked": True, "reason": ""})
        self.assertEqual(status, 400)
        admin = self.user_row("demo.admin@example.test")
        self.assertEqual(self.call("/api/users/block", {"user_id": admin["id"], "blocked": True, "reason": "no"})[0], 403)
        self.fresh_client()
        self.login("student")
        self.assertEqual(self.call("/api/users/block", {"user_id": admin["id"], "blocked": True, "reason": "no"})[0], 403)
        self.assertEqual(self.call("/api/roster/save", {"action": "add", "email": "a@lpunetwork.edu.ph"})[0], 403)
        self.assertEqual(self.call("/api/reports/review", {"kind": "lost", "id": 1, "action": "hide", "reason": "x"})[0], 403)

    def test_blocking_an_active_session_logs_that_person_out(self):
        self.login("student")
        student_cookie = [c for c in self.jar]
        self.assertEqual(self.call("/api/dashboard")[0], 200)
        self.app.service.set_blocked(User.from_row(self.user_row('demo.admin@example.test')),
                                     self.user_row("demo.student@example.test")["id"], True, "Test")
        self.assertEqual(self.call("/api/dashboard")[0], 401)
        self.assertTrue(student_cookie)

    def test_hide_and_restore_a_report_keeps_the_record_and_is_logged(self):
        self.login("admin")
        report = next(r for r in self.dashboard()["reports"] if r["category"] == "bags")
        self.assertTrue(any(m["report_id"] == report["id"] for m in self.dashboard()["matches"]))
        status, result = self.call("/api/reports/review", {"kind": "lost", "id": report["id"], "action": "hide", "reason": "Spam"})
        self.assertEqual(status, 200, result)
        data = self.dashboard()
        hidden = next(r for r in data["reports"] if r["id"] == report["id"])
        self.assertEqual(hidden["hidden"], 1)
        self.assertFalse(any(m["report_id"] == report["id"] for m in data["matches"]))
        self.assertIn("REPORT_HIDDEN", [a["action"] for a in data["audit"]])
        self.assertEqual(self.call("/api/reports/review", {"kind": "lost", "id": report["id"], "action": "hide", "reason": ""})[0], 400)
        self.fresh_client()
        self.login("student")
        self.assertFalse(any(r["id"] == report["id"] for r in self.dashboard()["reports"]))
        with self.db.connect() as conn:
            self.assertIsNotNone(conn.execute("SELECT 1 FROM lost_reports WHERE id=?", (report["id"],)).fetchone())  # never deleted
        self.fresh_client()
        self.login("admin")
        self.assertEqual(self.call("/api/reports/review", {"kind": "lost", "id": report["id"], "action": "unhide"})[0], 200)
        self.assertIn("REPORT_RESTORED", [a["action"] for a in self.dashboard()["audit"]])
        self.assertEqual(next(r for r in self.dashboard()["reports"] if r["id"] == report["id"])["hidden"], 0)

    def test_hide_a_found_report(self):
        self.login("admin")
        found = self.dashboard()["found_reports"][0]
        self.assertEqual(self.call("/api/reports/review", {"kind": "found", "id": found["id"], "action": "hide", "reason": "Prank"})[0], 200)
        self.assertEqual(next(f for f in self.dashboard()["found_reports"] if f["id"] == found["id"])["hidden"], 1)
        self.assertEqual(self.call("/api/reports/review", {"kind": "found", "id": found["id"], "action": "checked"})[0], 400)

    def test_roster_add_toggle_remove_and_csv_import(self):
        self.login("admin")
        self.assertEqual(self.call("/api/roster/save", {"action": "add", "email": "New.Student@lpunetwork.edu.ph", "name": "New Student", "role": "student"})[0], 200)
        self.assertEqual(self.call("/api/roster/save", {"action": "add", "email": "not-an-email"})[0], 400)
        self.assertEqual(self.call("/api/roster/save", {"action": "add", "email": "a@lpunetwork.edu.ph", "role": "admin"})[0], 400)
        roster = self.dashboard()["roster"]
        row = next(r for r in roster if r["email"] == "new.student@lpunetwork.edu.ph")
        self.assertEqual(self.call("/api/roster/save", {"action": "toggle", "id": row["id"]})[0], 200)
        self.assertEqual(next(r for r in self.dashboard()["roster"] if r["id"] == row["id"])["active"], 0)
        self.assertEqual(self.call("/api/roster/save", {"action": "remove", "id": row["id"]})[0], 200)
        csv_text = "Email,Name,Student Number,Role\nann@lpunetwork.edu.ph,Ann,2026-1,student\nbad-row,Bob,2,student\nprof@lpunetwork.edu.ph,Prof,,professor\nx@lpunetwork.edu.ph,X,3,janitor\n"
        status, result = self.call("/api/roster/import", {"csv": csv_text})
        self.assertEqual(status, 200, result)
        self.assertEqual((result["data"]["added"], result["data"]["skipped_count"]), (2, 2))
        self.assertEqual(self.call("/api/roster/import", {"csv": "name\nOnly a name"})[0], 400)
        actions = [a["action"] for a in self.dashboard()["audit"]]
        self.assertIn("ROSTER_IMPORTED", actions)
        self.assertIn("ROSTER_ADDED", actions)
        self.fresh_client()
        _, request = self.call("/api/auth/school/request", {"email": "ann@lpunetwork.edu.ph"})
        self.assertEqual(self.sign_in_with_code("ann@lpunetwork.edu.ph", request["data"]["demo_code"])[0], 200)


class HiddenDetailsAndHygieneTests(Base):
    def test_non_staff_never_receive_found_item_private_details(self):
        for role in ("student", "professor", "guest"):
            self.fresh_client()
            self.login(role)
            text = json.dumps(self.dashboard())
            for secret in ("inside the front pocket", "Blue receipt dated Monday", "private_details", "item_photo_id", "lock screen shows a mountain"):
                self.assertNotIn(secret.lower(), text.lower(), (role, secret))
            for item in self.dashboard()["recent_found"]:
                self.assertEqual(set(item), {"id", "category", "date_found", "status"})  # no place, no description, no photo

    def test_staff_do_see_private_details(self):
        self.login("admin")
        self.assertIn("private_details", json.dumps(self.dashboard()["items"]))

    def test_other_peoples_photos_cannot_be_opened(self):
        self.login("guest")
        for number in range(1, 8):
            self.assertIn(self.call(f"/api/files/{number}")[0], (403, 404, 200))
        with self.db.connect() as conn:
            item_photo = conn.execute("SELECT photo_id FROM items LIMIT 1").fetchone()[0]
        self.assertEqual(self.call(f"/api/files/{item_photo}")[0], 403)

    def test_security_headers_and_cookie_flags(self):
        request = self.client.open(self.base + "/api/config")
        headers = request.headers
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertIn("camera", headers["Permissions-Policy"])
        self.assertEqual(headers["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.jar.clear()
        import urllib.request
        raw = urllib.request.urlopen(self.base + "/api/config")
        cookie = raw.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_session_expiry_and_csrf(self):
        self.login("student")
        with self.db.connect() as conn:
            conn.execute("UPDATE sessions SET expires=?", (time.time() - 5,))
        self.assertEqual(self.call("/api/dashboard")[0], 401)
        self.assertEqual(self.call("/api/reports/lost", {"category": "other"}, csrf=False)[0], 403)

    def test_uploads_check_the_real_image_type(self):
        self.login("student")
        png = base64.b64encode(sample_image()).decode()
        self.assertEqual(self.call("/api/uploads", {"kind": "report_photo", "name": "a.png", "content": png})[0], 200)
        gif = base64.b64encode(b"GIF89a" + b"\x00" * 64).decode()
        self.assertEqual(self.call("/api/uploads", {"kind": "report_photo", "name": "a.png", "content": gif})[0], 400)
        script = base64.b64encode(b"<svg onload=alert(1)>").decode()
        self.assertEqual(self.call("/api/uploads", {"kind": "report_photo", "name": "a.svg", "content": script})[0], 400)
        try:
            import PIL  # noqa: F401
        except ImportError:  # the header check above still ran; the full structure check needs Pillow
            return
        pretend = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"not really a png").decode()
        self.assertEqual(self.call("/api/uploads", {"kind": "report_photo", "name": "a.png", "content": pretend})[0], 400)

    def test_photos_are_never_served_to_guests_for_claims_without_login(self):
        self.assertEqual(self.call("/api/files/1")[0], 401)


if __name__ == "__main__":
    unittest.main()
