"""Protected domain state independent of the HTTP and database layers."""
from lyfind.users import DomainError


class InvalidStateChange(DomainError):
    pass


class Item:
    _ALLOWED = {"available": {"under_verification", "unclaimed"},
                "under_verification": {"available", "released"},
                "released": set(), "unclaimed": set()}

    def __init__(self, item_id, status="available"):
        if status not in self._ALLOWED:
            raise InvalidStateChange("That item status is not used.")
        self.item_id = item_id
        self.__status = status

    @property
    def status(self):
        return self.__status

    def change_status(self, new_status):
        if new_status not in self._ALLOWED[self.__status]:
            raise InvalidStateChange("This item cannot skip or repeat a step.")
        self.__status = new_status


class Claim:
    _NEXT = {"step1_pending": {"step2_pending", "rejected"},
             "step2_pending": {"verified", "rejected"},
             "verified": {"approved", "rejected"},
             "approved": {"released"}, "rejected": set(), "released": set()}

    def __init__(self, claim_id, status="step1_pending", consent=False):
        if status not in self._NEXT:
            raise InvalidStateChange("That claim status is not used.")
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
            raise InvalidStateChange("Start the office check after the online check.")
        self.__consent = True

    def advance(self, status):
        if status not in self._NEXT[self.__status]:
            raise InvalidStateChange("This claim cannot skip a step.")
        if status in {"verified", "approved", "released"} and not self.__consent:
            raise InvalidStateChange("Start the office check before this step.")
        self.__status = status
