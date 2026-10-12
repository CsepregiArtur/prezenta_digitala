#!/usr/bin/env python3
"""Capture real screenshots of Attendance Control for the web/wiki documentation.

This is a *documentation helper tool*, not part of the application. It starts the
real PySide6 UI, walks through the admin pages and the kiosk, and writes PNG files
into ``docs/screenshots/``. It only ever touches a throw-away demo database
(``docs/.capture/attendance.db``), never the production ``attendance.db``.

Run on Windows (a real desktop session is required for on-screen rendering):

    .venv\\Scripts\\python.exe docs\\tools\\capture_screenshots.py

Optional flags:

    --out DIR     output folder for the PNGs (default: docs/screenshots)
    --keep        keep the temporary capture database after the run
    --only NAME   capture a single image by name (repeatable)
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from datetime import datetime, time as clock_time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
CAPTURE_DIR = DOCS / ".capture"

CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
# The application anchors its data/log paths on app_dir(); run from the project
# root so logs/ and any fallback folders land in the usual place.
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# --------------------------------------------------------------------------- #
# Demo data
# --------------------------------------------------------------------------- #

DEMO_EMPLOYEES = [
    # (first, last, number, department, position, shift)
    ("Andrei", "Popescu", "1001", "Producție", "Operator linie", "Schimb 1"),
    ("Maria", "Ionescu", "1002", "Producție", "Operator linie", "Schimb 2"),
    ("Elena", "Dumitrescu", "1003", "Calitate", "Inspector QC", "Schimb 1"),
    ("Vasile", "Munteanu", "1004", "Logistică", "Depozitar", "Schimb 3"),
    ("Ioana", "Stoica", "1005", "Administrativ", "Contabil", "Schimb 1"),
    ("Cristian", "Barbu", "1006", "Producție", "Mecanic întreținere", "Schimb 2"),
    ("Gabriela", "Nistor", "1007", "Logistică", "Șef depozit", "Schimb 3"),
    ("Mihai", "Radu", "1008", "Producție", "Operator linie", "Schimb 1"),
    ("Daniela", "Enache", "1009", "Calitate", "Inspector QC", "Schimb 2"),
    ("Florin", "Toma", "1010", "Administrativ", "Resurse umane", "Schimb 1"),
    ("Simona", "Cristea", "1011", "Producție", "Operator linie", "Schimb 3"),
    ("Robert", "Iliescu", "1012", "Logistică", "Depozitar", "Schimb 2"),
]

DEMO_SHIFTS = [
    # (name, start, end, early_in, earliest_out)
    ("Schimb 1", clock_time(6, 0), clock_time(14, 0), 60, 10),
    ("Schimb 2", clock_time(14, 0), clock_time(22, 0), 60, 10),
    ("Schimb 3", clock_time(22, 0), clock_time(6, 0), 60, 10),
    ("Administrativ", clock_time(8, 0), clock_time(16, 30), 60, 10),
]

TERMINALS = ["Recepție", "Poarta 1", "Atelier"]
SCANNERS = [
    ("SCN-01", "Recepție", "COM3", 9600, True, "Honeywell Voyager 1250g"),
    ("SCN-02", "Poarta 1", "COM4", 9600, True, "Honeywell Voyager 1250g"),
    ("SCN-03", "Atelier", "COM5", 9600, False, "Honeywell Xenon 1900"),
]


def _reset_database():
    """Create a fresh demo database with realistic data and return it."""
    from app.database import Database

    db_file = CAPTURE_DIR / "attendance.db"
    if db_file.exists():
        db_file.unlink()
    db = Database(str(db_file))
    # Note: seed_defaults() is intentionally NOT called — it inserts two generic
    # "Terminal 1/2" rows that would clash with the demo terminals below.
    return db


def _seed(db) -> None:
    """Populate the demo database: shifts, employees, terminals, scanners, admin."""
    import secrets

    from app.auth import AuthService
    from app.services import AdminDataService, EmployeeService, RotationService, ShiftService

    shifts = ShiftService(db)
    employees = EmployeeService(db)

    shift_ids = {}
    for name, start, end, early, out in DEMO_SHIFTS:
        shifts.create(name, start, end, early, out)
    for shift in shifts.list():
        shift_ids[shift.name] = shift.id

    # A three-shift weekly rotation so the Shift Rotations page has content.
    RotationService(db).create("Rotație 3 ture",
                               [shift_ids["Schimb 1"], shift_ids["Schimb 2"], shift_ids["Schimb 3"]])

    created = []
    for first, last, number, dept, position, shift in DEMO_EMPLOYEES:
        created.append(employees.create(first_name=first, last_name=last,
                                        employee_number=number, department=dept,
                                        position=position,
                                        shift_id=shift_ids.get(shift)))

    # Put the production team on the weekly rotation, staggered across shifts
    # (the classic 3-team roster: A on Schimb 1, B on Schimb 2, C on Schimb 3).
    _assign_rotation(db, created, shift_ids)

    # Export jobs for the Automatic Exports page.
    data = AdminDataService(db)
    data.save_export_job("22:30", "exports", frequency="daily")
    data.save_export_job("07:00", "exports", frequency="weekly", weekday=0)
    data.save_export_job("08:00", "exports", frequency="monthly", month_day=1)
    data.set_setting("site_name", "Zollner Elektronik — Hala 2")
    data.set_setting("language", "ro")

    # Terminals and scanners.
    from app.database.models import Scanner, Terminal

    session = db.session()
    terminal_ids = {name: index + 1 for index, name in enumerate(TERMINALS)}
    for name in TERMINALS:
        session.add(Terminal(id=terminal_ids[name], name=name, active=True))
    session.flush()
    for scanner_id, terminal, port, baud, enabled, description in SCANNERS:
        session.add(Scanner(scanner_id=scanner_id,
                            terminal_id=terminal_ids[terminal],
                            com_port=port, baud_rate=baud, enabled=enabled,
                            description=description))
    session.commit()
    session.close()

    auth = AuthService(db)
    try:
        auth.create_admin("admin", secrets.token_urlsafe(12) + "Aa1!x")
    except Exception as error:  # pragma: no cover - only if the user already exists
        print(f"  [note] administrator not created: {error}")

    _seed_attendance(db, created)


def _assign_rotation(db, employee_ids, shift_ids) -> None:
    """Anchor the demo rotation so members spread evenly across its shifts."""
    from datetime import date

    from app.database.models import Employee
    from app.attendance.rotation import monday_on_or_before

    anchor = monday_on_or_before(date.today())
    cycle = [shift_ids["Schimb 1"], shift_ids["Schimb 2"], shift_ids["Schimb 3"]]

    session = db.session()
    for index, employee_id in enumerate(employee_ids):
        employee = session.get(Employee, employee_id)
        if employee is None:
            continue
        # Only production employees rotate; office staff keep a fixed shift.
        if employee.department == "Administrativ":
            continue
        employee.rotation_id = 1
        employee.rotation_start = anchor
        employee.rotation_start_shift_id = cycle[index % len(cycle)]
    session.commit()
    session.close()


def _seed_attendance(db, employee_ids) -> None:
    """Insert a believable day of clock-in/clock-out events through the engine."""
    from app.attendance import AttendanceEngine, ScannerEvent

    engine = AttendanceEngine(db, "Europe/Bucharest", 5)

    def scan(barcode, when, terminal_id, scanner_id):
        return engine.process(ScannerEvent(barcode=barcode, timestamp=when,
                                          terminal_id=terminal_id,
                                          scanner_id=scanner_id))

    today = datetime.now().replace(microsecond=0)
    yesterday = today - timedelta(days=1)

    # Yesterday: complete sessions (worked hours show up in Reports).
    for index, clock_in, clock_out in [
        (0, yesterday.replace(hour=5, minute=54), yesterday.replace(hour=14, minute=3)),
        (1, yesterday.replace(hour=13, minute=57), yesterday.replace(hour=22, minute=4)),
        (2, yesterday.replace(hour=5, minute=58), yesterday.replace(hour=14, minute=1)),
        (5, yesterday.replace(hour=13, minute=55), yesterday.replace(hour=22, minute=2)),
    ]:
        scan(employee_ids[index], clock_in, 1, "SCN-01")
        scan(employee_ids[index], clock_out, 1, "SCN-01")

    # Yesterday's forgotten clock-out (drives the "missing clock-out" card).
    scan(employee_ids[10], yesterday.replace(hour=21, minute=58), 3, "SCN-03")

    # Today: open sessions (present now).
    scan(employee_ids[0], today.replace(hour=5, minute=52), 1, "SCN-01")
    scan(employee_ids[2], today.replace(hour=5, minute=57), 1, "SCN-01")
    scan(employee_ids[7], today.replace(hour=6, minute=2), 2, "SCN-02")
    scan(employee_ids[8], today.replace(hour=13, minute=56), 2, "SCN-02")
    scan(employee_ids[3], today.replace(hour=21, minute=55), 3, "SCN-03")

    # Rejections so Live Scans and Exceptions look realistic.
    scan("EMP999999", today.replace(hour=7, minute=11), 1, "SCN-01")   # UNKNOWN_BARCODE
    scan(employee_ids[4], today.replace(hour=5, minute=10), 1, "SCN-01")  # CLOCK_IN_TOO_EARLY
    scan(employee_ids[1], today.replace(hour=13, minute=40), 1, "SCN-01")  # CLOCK_OUT_NOT_ALLOWED


# --------------------------------------------------------------------------- #
# Screenshot helpers
# --------------------------------------------------------------------------- #

class Capturer:
    def __init__(self, out_dir: Path, only: set[str] | None = None):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.only = only
        self.written: list[Path] = []

    def wanted(self, name: str) -> bool:
        return not self.only or name in self.only

    def save(self, widget, name: str, *, caption: str | None = None) -> None:
        if not self.wanted(name):
            return
        widget.raise_()
        widget.activateWindow()
        app = _application()
        for _ in range(6):
            app.processEvents()
            time.sleep(0.12)
        pixmap = widget.grab()
        if caption:
            pixmap = self._with_caption(pixmap, caption)
        target = self.out_dir / f"{name}.png"
        pixmap.save(str(target), "PNG")
        self.written.append(target)
        print(f"  [ok] {target.relative_to(ROOT)}  ({pixmap.width()}x{pixmap.height()})")

    @staticmethod
    def _with_caption(pixmap, caption: str):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QFont, QPainter

        band = 34
        canvas = pixmap.copy(0, 0, pixmap.width(), pixmap.height() + band)
        painter = QPainter(canvas)
        painter.fillRect(0, pixmap.height(), pixmap.width(), band, QColor("#0b1014"))
        painter.setPen(QColor("#9fb3c4"))
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        painter.drawText(12, pixmap.height() + 22, caption)
        painter.end()
        return canvas


_APP = None


def _application():
    global _APP
    if _APP is None:
        from PySide6.QtWidgets import QApplication
        _APP = QApplication.instance() or QApplication([])
    return _APP


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DOCS / "screenshots"))
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--only", action="append", default=[])
    args = parser.parse_args()

    out_dir = Path(args.out)
    only = set(args.only) or None

    print("Attendance Control — screenshot capture")
    print(f"  database : {CAPTURE_DIR / 'attendance.db'}")
    print(f"  output   : {out_dir}")

    db = _reset_database()
    _seed(db)

    from app.attendance import AttendanceEngine
    from app.services import AdminDataService
    from app.ui.main_window import DARK, MainWindow, KioskShell
    from app.i18n import set_language

    app = _application()
    app.setStyleSheet(DARK)

    data = AdminDataService(db)
    language = data.settings().get("language", "ro")
    set_language(language)

    engine = AttendanceEngine(db, "Europe/Bucharest", 5)
    capturer = Capturer(out_dir, only)

    print("Capturing kiosk …")
    kiosk = KioskShell(db, engine)
    kiosk.resize(1280, 800)
    kiosk.show()
    capturer.save(kiosk, "01-kiosk",
                  caption="Ecranul kiosk — angajații trec doar cartela; administratorul se autentifică din buton.")

    # Login dialog -------------------------------------------------------------- #
    from app.ui.login import AdminLoginDialog
    dialog = AdminLoginDialog(db)
    dialog.resize(460, 260)
    dialog.show()
    capturer.save(dialog, "02-login",
                  caption="Autentificare administrator (utilizator + parolă, PBKDF2-SHA256).")
    dialog.close()

    # Admin shell --------------------------------------------------------------- #
    print("Capturing admin pages …")
    admin = MainWindow(db, engine, "admin")
    admin.resize(1440, 880)
    admin.show()
    app.processEvents()

    pages = {
        "Dashboard": "03-dashboard",
        "Employees": "04-angajati",
        "Shifts": "05-schimburi",
        "Shift Rotations": "06-rotatii",
        "Attendance": "07-pontaj",
        "Live Scans": "08-scanari-live",
        "Exceptions": "09-exceptii",
        "Terminals & Scanners": "10-scannere",
        "Reports": "11-raport",
        "Excel Export": "12-export-excel",
        "Automatic Exports": "13-export-automat",
        "Settings": "14-setari",
        "System Logs": "15-jurnal",
        "Backup / Restore": "16-backup",
        "Synchronization": "17-sincronizare",
        "About & License": "18-despre",
    }
    captions = {
        "Dashboard": "Tablou de bord — carduri live: angajați, prezenți acum, ieșiri neînregistrate, exceptii.",
        "Employees": "Angajați — adăugare manuală, import Excel/CSV, generare cod de bare, activare/dezactivare.",
        "Shifts": "Schimburi — ore, minute de intrare devreme și ieșire minimă, regula de noapte.",
        "Shift Rotations": "Rotatii de schimburi — ciclu ordonat care avansează în fiecare luni.",
        "Attendance": "Pontaj — sesiuni filtrate pe interval, angajat, schimb și status.",
        "Live Scans": "Scanări live — fiecare citire, cu terminal, scanner și motiv de respingere.",
        "Exceptions": "Exceptii — coduri necunoscute, angajați inactivi, scanări prea devreme, duplicate.",
        "Terminals & Scanners": "Terminale și scannere — port COM, baud, stare live, buton Test Port.",
        "Reports": "Rapoarte — totaluri, medii, ore lucrate și defalcare pe schimburi.",
        "Excel Export": "Export Excel — selecție foi, angajați, interval și destinație.",
        "Automatic Exports": "Exporturi automate — programare săptămânală/lunară și Next Run.",
        "Settings": "Setări — nume site, fus orar, limbă (EN/RO), secundele anti-duplicat.",
        "System Logs": "Jurnal de sistem — erori și evenimente operaționale.",
        "Backup / Restore": "Backup și restaurare — copii cu marcă de timp, restaurare cu confirmare.",
        "Synchronization": "Sincronizare — coadă offline durabilă + push către un server LAN.",
        "About & License": "Despre și licență — versiune, autor, contact.",
    }

    for label, name in pages.items():
        page = admin.page_widgets.get(label)
        if page is None:
            print(f"  [skip] page '{label}' not found")
            continue
        admin.pages.setCurrentWidget(page)
        app.processEvents()
        capturer.save(page, name, caption=captions.get(label))

    # Delegated pages that replace / extend the shell ---------------------------- #
    for label, name, caption in [
        ("Kiosk", "19-mod-kiosk",
         "Mod kiosk pe ecran complet, deblocat cu parola de administrator."),
    ]:
        page = admin.page_widgets.get(label)
        if page is not None:
            if name == "19-mod-kiosk":
                admin.enter_kiosk()
                app.processEvents()
                window = admin.kiosk_window
                window.resize(1280, 800)
                capturer.save(window, name, caption=caption)
                window.close()
            else:
                admin.pages.setCurrentWidget(page)
                capturer.save(page, name, caption=caption)

    admin.close()
    kiosk.close()

    # Barcode artefact ---------------------------------------------------------- #
    print("Capturing artefacts …")
    _capture_barcode(capturer)

    print(f"\nDone — {len(capturer.written)} image(s) written to {out_dir}")
    if not args.keep:
        shutil.rmtree(CAPTURE_DIR, ignore_errors=True)
    return 0


def _capture_barcode(capturer: Capturer) -> None:
    """Render a real generated barcode onto a badge card for the page."""
    from app.barcode import generate_barcode
    if not capturer.wanted("20-cod-de-bare"):
        return

    try:
        target = generate_barcode("EMP000001", CAPTURE_DIR)
    except Exception as error:  # pragma: no cover - depends on optional deps
        print(f"  [skip] barcode generation failed: {error}")
        return

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap

    image = QImage(str(target))
    if image.isNull():
        print("  [skip] generated barcode could not be read back")
        return
    image = image.scaled(760, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    card = QPixmap(image.width() + 80, image.height() + 150)
    card.fill(QColor("#ffffff"))
    painter = QPainter(card)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor("#101418"))
    painter.setFont(QFont("Segoe UI", 15, QFont.Bold))
    painter.drawText(40, 48, "CARTELĂ DE ACCES")
    painter.setFont(QFont("Segoe UI", 11))
    painter.setPen(QColor("#4a5560"))
    painter.drawText(40, 72, "Conține DOAR ID-ul angajatului — fără nume, departament sau parolă")
    painter.drawImage(40, 92, image)
    painter.setPen(QColor("#101418"))
    painter.setFont(QFont("Consolas", 12))
    painter.drawText(40, image.height() + 132, "barcodes/EMP000001.png   ·   Code 128   ·   payload: EMP000001")
    painter.end()

    out = capturer.out_dir / "20-cod-de-bare.png"
    card.save(str(out), "PNG")
    capturer.written.append(out)
    print(f"  [ok] {out.relative_to(ROOT)}  ({card.width()}x{card.height()})")


if __name__ == "__main__":
    raise SystemExit(main())
