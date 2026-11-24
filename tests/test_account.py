"""People can change their name parts and phone. Accounts cannot be deleted in the app."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_auth_http as http_base


class AccountTests(unittest.TestCase):
    setUp = http_base.HTTPTests.setUp
    tearDown = http_base.HTTPTests.tearDown
    call = http_base.HTTPTests.call
    login = http_base.HTTPTests.login

    def test_student_can_save_name_parts_phone_and_number(self):
        self.login("student")
        status, result = self.call("/api/account/save", {
            "first_name": "Maria", "middle_name": "Santos", "last_name": "Reyes", "suffix": "",
            "phone": "0917 555 0100", "student_number": "2025-2-00001"})
        self.assertEqual(status, 200, result)
        person = result["data"]["user"]
        self.assertEqual(person["name"], "Maria Santos Reyes")
        self.assertEqual(person["first_name"], "Maria")
        self.assertEqual(person["last_name"], "Reyes")
        self.assertEqual(person["phone"], "0917 555 0100")
        self.assertEqual(self.call("/api/dashboard")[1]["data"]["user"]["first_name"], "Maria")

    def test_short_name_and_bad_phone_are_refused(self):
        self.login("guest")
        self.assertEqual(self.call("/api/account/save", {"first_name": "A", "last_name": "Rivera", "phone": ""})[0], 400)
        self.assertEqual(self.call("/api/account/save", {"first_name": "Alex", "last_name": "Rivera", "phone": "123"})[0], 400)

    def test_there_is_no_delete_account_route(self):
        self.login("guest")
        self.assertEqual(self.call("/api/account/delete", {"confirm_email": "demo.guest@example.test"})[0], 404)

    def test_admin_sets_a_guest_password_without_returning_or_logging_it(self):
        self.login("admin")
        people = self.call("/api/dashboard")[1]["data"]["people"]
        guest = next(person for person in people if person["role"] == "guest")
        staff = self.call("/api/dashboard")[1]["data"]["staff"][0]
        new = "OfficeKey42!"
        status, result = self.call("/api/users/password", {"user_id": guest["id"], "password": new, "confirm": new})
        self.assertEqual(status, 200, result)
        self.assertEqual(result["data"], {"ok": True})
        self.assertNotIn(new, json.dumps(result))
        weak = self.call("/api/users/password", {"user_id": guest["id"], "password": "short1a", "confirm": "short1a"})
        self.assertEqual(weak[0], 400)
        staff_try = self.call("/api/users/password", {"user_id": staff["id"], "password": new, "confirm": new})
        self.assertEqual(staff_try[0], 400)
        audit = self.call("/api/dashboard")[1]["data"]["audit"]
        entry = next(row for row in audit if row["action"] == "PASSWORD_SET")
        self.assertNotIn(new, entry["detail"])
        self.login("student")
        self.assertEqual(self.call("/api/users/password", {"user_id": guest["id"], "password": "CampusKey42!", "confirm": "CampusKey42!"})[0], 403)
        signed = self.call("/api/auth/login", {"email": guest["email"], "password": new})
        self.assertEqual(signed[0], 200, signed[1])
        self.assertNotIn(new, json.dumps(signed[1]))
        self.assertNotEqual(self.call("/api/auth/login", {"email": guest["email"], "password": "DemoOnly!2026"})[0], 200)


if __name__ == "__main__":
    unittest.main()
