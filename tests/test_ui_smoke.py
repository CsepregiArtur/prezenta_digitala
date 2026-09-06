"""Offscreen PySide6 checks that the full admin shell (17 pages) constructs and
that its data-backed pages (dashboard cards, reports) respond to live data.
These run headlessly via QT_QPA_PLATFORM=offscreen.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import sys
from datetime import datetime, time

import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication

from app.database import Database
from app.database.models import Shift
from app.attendance import AttendanceEngine, ScannerEvent
from app.services import EmployeeService


@pytest.fixture(scope='module')
def application():
    instance = QApplication.instance() or QApplication(sys.argv)
    instance.setQuitOnLastWindowClosed(False)
    yield instance
    # Clean up windows/timers before Qt tears down to avoid an offscreen segfault.
    from PySide6.QtCore import QEvent
    for widget in list(instance.topLevelWidgets()):
        widget.close()
        widget.deleteLater()
    instance.sendPostedEvents(None, QEvent.DeferredDelete)
    instance.processEvents()


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / 'ui.db'); d.seed_defaults()
    with d.session() as s:
        s.add(Shift(name='Day', start_time=time(6), end_time=time(14), early_clock_in_minutes=60, earliest_clock_out_minutes=10))
        s.commit()
    return d


def test_shell_constructs_with_all_pages(application, db):
    from app.ui import MainWindow
    window = MainWindow(db, AttendanceEngine(db), username='admin')
    assert window.pages.count() == 17
    names = [type(window.pages.widget(i)).__name__ for i in range(window.pages.count())]
    assert 'DashboardPage' in names and 'HardwarePage' in names and 'ReportsPage' in names
    assert 'ExcelExportPage' in names and 'SyncPage' in names and 'Kiosk' in names and 'AboutPage' in names
    assert 'RotationsPage' in names and 'ShiftsPage' in names
    window.close()


def test_dashboard_cards_reflect_live_scans(application, db):
    from app.ui.main_window import DashboardPage
    eid = EmployeeService(db).create('Ioana', 'Dumitrescu', shift_id=1)
    engine = AttendanceEngine(db)
    now = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
    engine.process(ScannerEvent(eid, now, 1, 'S1'))
    page = DashboardPage(db)
    assert page.card_values['present_now'].text() == '1'
    assert page.card_values['scans_today'].text() == '1'


def test_all_pages_can_be_visited_and_reloaded(application, db):
    from app.ui import MainWindow
    eid = EmployeeService(db).create('Andrei', 'Ionescu', shift_id=1)
    engine = AttendanceEngine(db)
    engine.process(ScannerEvent(eid, datetime.now().replace(hour=8, minute=30), 1, 'S1'))
    window = MainWindow(db, engine, username='admin')
    for index in range(window.pages.count()):
        window.pages.setCurrentIndex(index)
        page = window.pages.widget(index)
        load = getattr(page, 'load', None)
        if callable(load):
            load()
    window.close()


def test_reports_page_shows_aggregates(application, db):
    from app.ui.main_window import ReportsPage
    eid = EmployeeService(db).create('Radu', 'Marinescu', shift_id=1)
    engine = AttendanceEngine(db)
    base = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    engine.process(ScannerEvent(eid, base, 1, 'S1'))
    engine.process(ScannerEvent(eid, base.replace(hour=14), 1, 'S1'))
    page = ReportsPage(db)
    text = page.summary_label.text()
    assert 'Sessions in range: 1' in text and 'Total worked hours: 8.0' in text


def test_row_actions_resolve_after_construction(application, db):
    """Regression: row metadata must not be wiped after the base class loads."""
    from app.ui.main_window import HardwarePage, ExportJobsPage
    from app.scanner import ScannerManager
    from app.services import AdminDataService
    service = AdminDataService(db)
    service.save_scanner('SCANNER A', 1, '/dev/ttys900', 'Front door')
    service.save_export_job('07:30', 'exports', 'weekly', weekday=0)
    engine = AttendanceEngine(db)
    hardware = HardwarePage(db, engine, manager=ScannerManager(engine))
    hardware.table.selectRow(0); hardware.table.setCurrentCell(0, 0)
    selected = hardware.current()
    assert selected is not None and selected[0] == 'scanner' and selected[1].scanner_id == 'SCANNER A'
    jobs = ExportJobsPage(db)
    jobs.table.selectRow(0); jobs.table.setCurrentCell(0, 0)
    job = jobs.job()
    assert job is not None and job.run_time == '07:30'
