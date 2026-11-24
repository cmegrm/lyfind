"""Protected domain state independent of the HTTP and database layers."""
from users import DomainError


class InvalidStateChange(DomainError):
    pass


class Item:
    _ALLOWED = {"available": {"under_verification", "unclaimed"},
                "under_verification": {"available", "released"},
                "released": set(), "unclaimed": set()}

    def __init__(self, item_id, status="available"):
        if status not in self._ALLOWED:
            raise InvalidStateChange("Invalid item status.")
        self.item_id = item_id
        self.__status = status

    @property
    def status(self):
        return self.__status

    def change_status(self, new_status):
        if new_status not in self._ALLOWED[self.__status]:
            raise InvalidStateChange(f"Item cannot change from {self.__status} to {new_status}.")
        self.__status = new_status


class Claim:
    _NEXT = {"step1_pending": {"step2_pending", "rejected"},
             "step2_pending": {"verified", "rejected"},
             "verified": {"approved", "rejected"},
             "approved": {"released"}, "rejected": set(), "released": set()}

    def __init__(self, claim_id, status="step1_pending", consent=False):
        if status not in self._NEXT:
            raise InvalidStateChange("Invalid claim status.")
        self.claim_id = claim_id
        self.__status, self.__consent = status, bool(consent)

    @property
    def status(self):
        return self.__status

    @property
    def consent(self):
        return self.__consent

    def record_consent(self):
        if self.__status != "step2_pending":
            raise InvalidStateChange("Record in-person consent after online verification.")
        self.__consent = True

    def advance(self, status):
        if status not in self._NEXT[self.__status]:
            raise InvalidStateChange(f"Claim cannot change from {self.__status} to {status}.")
        if status in {"verified", "approved", "released"} and not self.__consent:
            raise InvalidStateChange("In-person evidence consent must be recorded first.")
        self.__status = status
