from __future__ import annotations
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.config import load_config, app_dir
from app.logging_setup import configure_logging
from app.database import Database
from app.attendance import AttendanceEngine
from app.services import AdminDataService
from app.ui import KioskShell
from app.export import ExcelExporter
from app.scheduler import ExportScheduler
from app.scanner import ScannerManager
from app.offline import OfflineQueue
from app.sync import SyncService
from app.i18n import set_language


def main():
    # Anchor all relative data/log paths (database, logs, backup, exports, queue)
    # to the application folder (the executable folder when packaged).
    import os
    os.chdir(app_dir())
    config = load_config()
    log = configure_logging()
    log.info('Application startup')
    db = Database(); db.seed_defaults()
    engine = AttendanceEngine(db, config['timezone'], config['duplicate_scan_seconds'])
    data = AdminDataService(db)
    # UI language (English / Română) is stored with the other application settings.
    set_language(data.settings().get('language', 'en'))

    # Durable offline queue preserves any event the primary store could not accept.
    offline_queue = OfflineQueue('data/offline_queue.db')
    # Real COM/serial scanner threads (one per enabled scanner, with reconnects).
    scanner_manager = ScannerManager(engine, offline_queue=offline_queue)
    scanner_manager.configure(data.scanners_flat()).start()
    # Background Excel export scheduler (frequency aware).
    scheduler = ExportScheduler(db, ExcelExporter(db)); scheduler.start()
    # LAN / server synchronization (offline drain + push of new events).
    sync_service = SyncService(db, engine, offline_queue)

    app = QApplication(sys.argv)
    app.setStyleSheet(__import__('app.ui.main_window', fromlist=['DARK']).DARK)

    # Start directly on the employee kiosk; administrators sign in via the
    # 'ADMINISTRATOR LOGIN' button (first run creates the administrator).
    kiosk = KioskShell(db, engine, scanner_manager=scanner_manager,
                       sync_service=sync_service, offline_queue=offline_queue)
    kiosk.showFullScreen()
    sync_timer = QTimer(kiosk); sync_timer.timeout.connect(sync_service.tick); sync_timer.start(30000)

    code = app.exec()
    sync_timer.stop(); scheduler.stop(); scanner_manager.stop()
    log.info('Application shutdown')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
