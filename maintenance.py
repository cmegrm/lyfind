"""Staff backups and isolated demo resets."""
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Condition
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from database import Database
from storage import resolve_upload
from users import DomainError, User, require_permission


class WorkspaceMaintenance:
    def __init__(self, db, root, upload_dir, demo_mode):
        self.db = db
        self.upload_dir = upload_dir.resolve()
        data = (root / 'data').resolve()
        self.backups = data / 'backups'
        self.can_reset = (demo_mode and Path(db.path).resolve() == data / 'demo.sqlite3'
                          and self.upload_dir == data / 'test-uploads')
        self.mode = 'demo' if demo_mode else 'live'
        self.condition = Condition()
        self.active = 0
        self.exclusive = False

    @contextmanager
    def request(self):
        with self.condition:
            if self.exclusive:
                raise DomainError('CSA is maintaining this workspace. Try again in a moment.', 503)
            self.active += 1
        try:
            yield
        finally:
            with self.condition:
                self.active -= 1
                self.condition.notify_all()

    @contextmanager
    def _exclusive_request(self):
        """Let other requests finish while this authenticated request remains active."""
        with self.condition:
            if self.exclusive:
                raise DomainError('A maintenance action is already running.', 409)
            self.exclusive = True
            if not self.condition.wait_for(lambda: self.active == 1, timeout=15):
                self.exclusive = False
                raise DomainError('The workspace is busy. Try again in a moment.', 409)
        try:
            yield
        finally:
            with self.condition:
                self.exclusive = False

    def _authorize(self, user):
        require_permission(user, 'manage_staff')
        with self.db.connect() as conn:
            actor = conn.execute('SELECT * FROM users WHERE id=?', (user.id,)).fetchone()
            require_permission(User.from_row(actor) if actor else None, 'manage_staff')

    def backup(self, user):
        self._authorize(user)
        with self._exclusive_request():
            self._authorize(user)
            return {'backup': self._backup()}

    def _backup(self):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        name = f'lyfind-{self.mode}-{stamp}-{uuid4().hex[:8]}.zip'
        self.backups.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.backups) as staging:
            stage = Path(staging)
            snapshot = Database(stage / Path(self.db.path).name)
            with self.db.connect() as source, snapshot.connect() as target:
                source.backup(target)
                if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise DomainError('The database check failed. No backup was saved.', 409)
                files = {resolve_upload(self.upload_dir, row['path'], must_exist=True)
                         for row in target.execute('SELECT path FROM uploads')}
            archive = stage / name
            with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as backup:
                backup.write(snapshot.path, Path(snapshot.path).name)
                for photo in sorted(files):
                    folder = 'test-uploads' if self.mode == 'demo' else 'uploads'
                    backup.write(photo, (Path(folder) / photo.relative_to(self.upload_dir)).as_posix())
            archive.replace(self.backups / name)
        return name

    def reset_demo(self, user, confirmed):
        self._authorize(user)
        if not self.can_reset:
            raise DomainError('Only the local demo workspace can be reset.', 403)
        if confirmed is not True:
            raise DomainError('Confirm that you want to reset the demo.')
        with self._exclusive_request():
            self._authorize(user)
            return self._reset_demo()

    def _reset_demo(self):
        from auth import AuthService
        from seed import seed_demo

        backup = self._backup()
        with tempfile.TemporaryDirectory(dir=self.backups) as staging:
            stage = Path(staging)
            fresh = Database(stage / 'demo.sqlite3')
            fresh.initialize()
            AuthService(fresh, demo_mode=True)
            prefix = f'demo-{uuid4().hex}-'
            seed_demo(fresh, stage / 'test-uploads', prefix=prefix)
            with self.db.connect() as conn:
                old_files = {resolve_upload(self.upload_dir, row['path'])
                             for row in conn.execute('SELECT path FROM uploads')}
            copied = []
            try:
                for photo in (stage / 'test-uploads').iterdir():
                    destination = self.upload_dir / photo.name
                    copied.append(destination)
                    shutil.copyfile(photo, destination)
                with fresh.connect() as source, self.db.connect() as target:
                    source.backup(target)
            except Exception:
                for photo in copied:
                    photo.unlink(missing_ok=True)
                raise
            leftovers = 0
            for photo in old_files:
                try:
                    photo.unlink(missing_ok=True)
                except OSError:
                    leftovers += 1
        return {'backup': backup, 'leftover_files': leftovers}
