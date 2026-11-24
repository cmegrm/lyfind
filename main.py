"""Run the CSA web application using Python 3.10 or newer."""
import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

from lyfind.auth import load_environment
from lyfind.database import Database
from lyfind.passwords import first_problem
from lyfind.users import hash_password, split_display_name

ROOT = Path(__file__).resolve().parent


def create_admin(db, email, name, password):
    weak = first_problem(password, name, email)
    if weak:
        raise ValueError(weak)
    with db.connect() as conn:
        if conn.execute("SELECT 1 FROM users WHERE lower(email)=?", (email.lower(),)).fetchone():
            raise ValueError("An account with that email already exists.")
        first, middle, last, suffix = split_display_name(name)
        conn.execute("INSERT INTO users(email,role,password_hash,first_name,middle_name,last_name,suffix) VALUES(?,?,?,?,?,?,?)",
                     (email.strip().lower(), "admin", hash_password(password), first, middle, last, suffix))


def use_project_python():
    """Run with the project's .venv Python (where AI is installed) when it exists."""
    env = ROOT / ".venv"
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists() or os.environ.get("LYFIND_NO_VENV"):
        return
    if Path(sys.prefix).resolve() == env.resolve():
        return
    os.environ["LYFIND_NO_VENV"] = "1"
    if os.name == "nt":
        raise SystemExit(subprocess.call([str(python), *sys.argv]))
    os.execv(str(python), [str(python), *sys.argv])


def main():
    use_project_python()
    setup_key = os.environ.pop('REUNITE_DESKTOP_SETUP_KEY', None)
    launch_id = os.environ.pop('REUNITE_DESKTOP_LAUNCH_ID', None)
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        load_environment(Path(os.environ['LOCALAPPDATA']) / 'LyFind' / 'email.env')
    load_environment(ROOT / ".env")
    parser = argparse.ArgumentParser(description="CSA Automated Lost and Found System")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                        help="Bind address. Default 0.0.0.0 lets phones/Windows on the same Wi-Fi open the site. Use 127.0.0.1 for this computer only.")
    parser.add_argument("--lan", action="store_true", help="Listen on the local network (same as --host 0.0.0.0)")
    parser.add_argument("--database", default=None, help="Override the database path")
    parser.add_argument("--demo", action="store_true", help="Open the isolated classroom workspace")
    parser.add_argument("--live", action="store_true", help="Disable all demonstration logins and displayed email codes")
    parser.add_argument("--backup", action="store_true", help="Copy the database and uploads into data/backups/<timestamp>/ and exit")
    parser.add_argument("--check-db", action="store_true", help="Run SQLite integrity and foreign-key checks and exit")
    parser.add_argument("--reset-demo", action="store_true", help="Back up, then wipe and re-seed the DEMO database and exit (never touches live data)")
    parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation (with --reset-demo)")
    parser.add_argument("--create-admin", action="store_true", help="Create the first real staff account and exit")
    parser.add_argument("--check-config", action="store_true", help="Check local live integration settings without exposing credentials")
    args = parser.parse_args()
    if args.check_config:
        from lyfind.configuration import check_configuration
        checks = check_configuration()
        for label, check in checks.items():
            print(label + ": " + ("LOCAL SETTINGS PRESENT" if check["configured"] else "SETUP REQUIRED"))
            if check["missing"]:
                print("  Missing settings: " + ", ".join(check["missing"]))
            if check.get("sdk_installed") is False:
                print("  Install requirements/live.txt for the Microsoft SDK.")
        print("This checks local settings only; live service verification is still required.")
        return
    demo = args.demo and not args.live and not args.create_admin
    database_path = Path(args.database) if args.database else ROOT / "data" / ("demo.sqlite3" if demo else "csa.sqlite3")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    upload_dir = ROOT / 'data' / ('test-uploads' if demo else 'uploads')
    if demo and (args.database or args.host != '127.0.0.1' or args.lan):
        parser.error('The testing workspace uses its own database on localhost.')
    if not demo and database_path.resolve() == (ROOT / 'data/demo.sqlite3').resolve():
        parser.error('Use the testing workspace to open the demo database.')
    backups = ROOT / "data" / "backups"
    if args.backup or args.check_db or args.reset_demo:
        from lyfind.maintenance import backup, reset_demo, server_answering
        if args.check_db or args.backup:
            if not database_path.exists():
                raise SystemExit("There is no database at " + str(database_path) + " yet. Start the server once first.")
            Database(database_path).initialize()
        if args.check_db:
            result = Database(database_path).check()
            print("Database check: " + ("OK" if result["ok"] else "PROBLEMS FOUND") + f" (schema version {result['schema_version']})")
            for problem in result["problems"]:
                print("  " + problem)
            raise SystemExit(0 if result["ok"] else 1)
        if args.backup:
            print("Backup saved to " + str(backup(database_path, upload_dir, backups)))
            return
        if not demo or database_path.name != "demo.sqlite3":
            raise SystemExit("--reset-demo only works on the demo database (data/demo.sqlite3), never on live data.")
        from lyfind.web import probe_host
        if server_answering(probe_host(args.host), args.port):
            raise SystemExit("Stop the server first, then run --reset-demo again.")
        if not args.yes:
            if not sys.stdin.isatty():
                raise SystemExit("Add --yes to confirm. A backup is saved first.")
            if input("This wipes the demo data and creates fresh sample records (a backup is saved first). Type yes: ").strip().lower() != "yes":
                raise SystemExit("Nothing was changed.")
        made = reset_demo(database_path, upload_dir, backups)
        print("Demo data reset." + (" Backup saved to " + str(made) if made else ""))
        return
    db = Database(database_path)
    db.initialize()
    if args.create_admin:
        create_admin(db, input("Staff email: ").strip(), input("Full name: ").strip(), getpass.getpass("Password (12+ characters): "))
        print("Administrator created. Start the application with --live.")
        return
    if demo:
        from lyfind.seed import ensure_demo_passwords, ensure_demo_roster, seed_demo
        upload_dir.mkdir(parents=True, exist_ok=True)
        from lyfind.storage import resolve_upload
        with db.connect() as conn:
            for row in conn.execute('SELECT path FROM uploads'):
                source = resolve_upload(ROOT / 'data/uploads', row['path'])
                target = resolve_upload(upload_dir, row['path'])
                if source.is_file() and not target.exists():
                    import shutil
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
        seed_demo(db, upload_dir)
        ensure_demo_passwords(db)
        ensure_demo_roster(db)
        with db.connect() as conn:
            conn.execute("INSERT INTO users(email,role,first_name,last_name,password_hash) VALUES(?,'student','Jamie','Flores',?) ON CONFLICT(email) DO NOTHING",
                         ('demo.student2@example.test',hash_password('DemoOnly!2026')))
            conn.execute("UPDATE users SET password_hash=? WHERE email='demo.student2@example.test' AND (password_hash IS NULL OR password_hash='')",
                         (hash_password('DemoOnly!2026'),))
    from lyfind.web import Application, serve
    host = "0.0.0.0" if args.lan else args.host
    serve(Application(db, ROOT, demo_mode=demo, upload_dir=upload_dir,
                      setup_key=setup_key if host == '127.0.0.1' else None, launch_id=launch_id), host, args.port)


if __name__ == "__main__":
    main()
