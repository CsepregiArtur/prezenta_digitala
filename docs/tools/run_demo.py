#!/usr/bin/env python3
"""Run Attendance Control against a throw-away demo database.

Designed for the wiki/screenshot workflow: the real application is started
exactly as `python -m app.main` would start it, but every relative data path is
redirected to the folder given by ``--data`` (default ``.demo``) so the
production ``attendance.db``, ``logs/`` and ``exports/`` are never touched.

    .venv\\Scripts\\python.exe docs\\tools\\run_demo.py --data .demo

Everything is seeded the same way as ``capture_screenshots.py``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "docs" / "tools"))

from capture_screenshots import _reset_database, _seed  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(ROOT / ".demo"),
                        help="folder that receives the demo database/logs (default: .demo)")
    parser.add_argument("--fresh", action="store_true",
                        help="delete the demo folder and reseed before starting")
    parser.add_argument("--reset", action="store_true",
                        help="reseed the demo database but keep logs")
    args = parser.parse_args()

    data_dir = Path(args.data).resolve()
    if args.fresh and data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # The application resolves relative paths against app_dir() -> cwd.
    os.chdir(data_dir)

    from app.database import Database
    from app.services import AdminDataService

    db_path = data_dir / "attendance.db"
    if args.fresh or args.reset or not db_path.exists():
        # Reuse the screenshot seeding so the demo data is identical.
        original = Path.cwd()
        os.chdir(ROOT)
        try:
            db = _reset_database()
            _seed(db)
        finally:
            os.chdir(original)
        if Path(".demo/attendance.db").exists() and data_dir.name != ".demo":
            shutil.copy(ROOT / ".demo" / "attendance.db", db_path)
        elif Path("docs/.capture/attendance.db").exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / "docs" / ".capture" / "attendance.db", db_path)

    print(f"Attendance Control demo — data folder: {data_dir}")

    # Only start external services that make sense without hardware.
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.attendance import AttendanceEngine
    from app.config import load_config
    from app.logging_setup import configure_logging
    from app.offline import OfflineQueue
    from app.scanner import ScannerManager
    from app.scheduler import ExportScheduler
    from app.export import ExcelExporter
    from app.sync import SyncService
    from app.i18n import set_language
    from app.ui import KioskShell
    from app.ui.main_window import DARK

    config = load_config()
    log = configure_logging()
    log.info("Demo startup")
    db = Database(str(db_path))
    engine = AttendanceEngine(db, config["timezone"], config["duplicate_scan_seconds"])
    set_language(AdminDataService(db).settings().get("language", "ro"))

    offline_queue = OfflineQueue(str(data_dir / "offline_queue.db"))
    scanner_manager = ScannerManager(engine, offline_queue=offline_queue)
    scanner_manager.configure(AdminDataService(db).scanners_flat()).start()
    scheduler = ExportScheduler(db, ExcelExporter(db))
    scheduler.start()
    sync_service = SyncService(db, engine, offline_queue)

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK)
    kiosk = KioskShell(db, engine, scanner_manager=scanner_manager,
                       sync_service=sync_service, offline_queue=offline_queue)
    kiosk.showFullScreen()
    timer = QTimer(kiosk)
    timer.timeout.connect(sync_service.tick)
    timer.start(30000)

    code = app.exec()
    timer.stop()
    scheduler.stop()
    scanner_manager.stop()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
