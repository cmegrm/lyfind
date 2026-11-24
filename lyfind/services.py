"""Application entry point: delegate each task to a focused OOP service.

The web layer and demo keep using Service. Start here, then open the workflow
module for the task you want to understand. No dynamic method dispatch is used.
"""
from lyfind.workflows.base import AuditLog, WorkflowBase, WorkflowContext
from lyfind.workflows.reports import ReportService
from lyfind.workflows.inventory import InventoryService
from lyfind.workflows.matching import MatchService
from lyfind.workflows.claims import ClaimService
from lyfind.workflows.accounts import AccountService
from lyfind.workflows.dashboard import DashboardService


class Service(WorkflowBase):
    """Compose the services while keeping the public application interface stable."""

    def __init__(self, db, upload_dir=None, matcher=None):
        context = WorkflowContext(db, upload_dir, matcher)
        super().__init__(context)
        self.matching = MatchService(context)
        context.matching = self.matching
        self.reports = ReportService(context)
        self.inventory = InventoryService(context)
        self.claims = ClaimService(context)
        self.accounts = AccountService(context)
        self.overview = DashboardService(context)

    def prepare_matching(self):
        """Load the optional local AI before handling requests."""
        return self.ai.prepare()

    def create_lost_report(self, user, data):
        return self.reports.create_lost_report(user, data)

    def create_lost_report_for_guest(self, staff, data, auth=None, ip='local'):
        return self.reports.create_lost_report_for_guest(staff, data, auth, ip)

    def claim_desk_holds(self, user):
        return self.reports.claim_desk_holds(user)

    def desk_hold_status(self, staff, hold_id):
        return self.reports.desk_hold_status(staff, hold_id)

    def create_found_report(self, user, data):
        return self.reports.create_found_report(user, data)

    def review_report(self, admin, data):
        return self.reports.review_report(admin, data)

    def receive_item(self, admin, data):
        return self.inventory.receive_item(admin, data)

    def set_board_listing(self, admin, item_id, data):
        return self.inventory.set_board_listing(admin, item_id, data)

    def expire_items(self, admin):
        return self.inventory.expire_items(admin)

    def authorize_upload(self, user, kind, claim_id=None):
        return self.inventory.authorize_upload(user, kind, claim_id)

    def file_access(self, user, file_id):
        return self.inventory.file_access(user, file_id)

    def run_matching(self, admin):
        return self.matching.run_matching(admin)

    def decide_match(self, admin, match_id, confirmed):
        return self.matching.decide_match(admin, match_id, confirmed)

    def submit_claim(self, user, data):
        return self.claims.submit_claim(user, data)

    def verify_online(self, admin, claim_id, passed, reason=''):
        return self.claims.verify_online(admin, claim_id, passed, reason)

    def record_consent(self, user, claim_id, data):
        return self.claims.record_consent(user, claim_id, data)

    def verify_in_person(self, admin, claim_id, passed, reason=''):
        return self.claims.verify_in_person(admin, claim_id, passed, reason)

    def approve_claim(self, admin, claim_id, data):
        return self.claims.approve_claim(admin, claim_id, data)

    def release_item(self, admin, claim_id):
        return self.claims.release_item(admin, claim_id)

    def manage_staff(self, admin, data):
        return self.accounts.manage_staff(admin, data)

    def set_blocked(self, admin, user_id, blocked, reason=''):
        return self.accounts.set_blocked(admin, user_id, blocked, reason)

    def set_person_password(self, admin, data):
        return self.accounts.set_person_password(admin, data)

    def update_profile(self, user, data):
        return self.accounts.update_profile(user, data)

    def change_password(self, user, data):
        return self.accounts.change_password(user, data)

    def roster_save(self, admin, data):
        return self.accounts.roster_save(admin, data)

    def roster_import(self, admin, text, **options):
        return self.accounts.roster_import(admin, text, **options)

    def dashboard(self, user):
        return self.overview.dashboard(user)

