from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QTimer, Qt, QDate, QTime, QThread, Signal, QSize, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import *
from PySide6.QtWidgets import QStyle
from app.services import EmployeeService, ShiftService, AdminDataService
from app.export import ExcelExporter, SHEET_NAMES
from app.maintenance import backup_database, restore_database
from app.auth import AuthService
from app.scheduler import next_run_time, schedule_text, WEEKDAYS
from app.ui.login import AdminLoginDialog
from app.i18n import t, reason_text, localize_window, format_kiosk_date
from app import __version__ as APP_VERSION

DARK='''QWidget{background:#14191f;color:#e8edf2;font-family:Segoe UI} QPushButton{background:#2374ab;padding:9px;border-radius:5px;text-align:left} QPushButton:hover{background:#318bc4} QPushButton:checked{background:#55a9d8;border-left:4px solid #ffffff;font-weight:bold} QTableWidget{background:#1c242d;color:#e8edf2;alternate-background-color:#212c37;gridline-color:#34414d;selection-background-color:#2374ab;selection-color:#ffffff} QTableView::item:selected{background:#2374ab;color:#ffffff} QHeaderView::section{background:#263542;color:#e8edf2;padding:7px;border:0} QLineEdit,QComboBox,QDateEdit,QTimeEdit,QSpinBox{background:#222d36;border:1px solid #425464;padding:6px;border-radius:4px}'''
def cell(x): return QTableWidgetItem('—' if x is None or x=='' else str(x))

_ICON_CACHE = {}
def icon_pixmap(name):
    """Resolve a QStyle.StandardPixmap name to a QIcon (cached)."""
    if name not in _ICON_CACHE:
        pixmap = getattr(QStyle.StandardPixmap, name, None)
        _ICON_CACHE[name] = QApplication.style().standardIcon(pixmap) if pixmap else QIcon()
    return _ICON_CACHE[name]

DANGER_QSS = 'QPushButton{background:#8a2f2f} QPushButton:hover{background:#b03a3a}'
SUCCESS_QSS = 'QPushButton{background:#1f7a45} QPushButton:hover{background:#2a9a58}'

def buttons_row(actions):
    """Build an action button row from (label, callable[, style]) tuples."""
    layout = QHBoxLayout()
    for item in actions:
        label, callback = item[0], item[1]
        button = QPushButton(label)
        if len(item) > 2 and item[2]:
            button.setStyleSheet(item[2])
        button.clicked.connect(callback)
        layout.addWidget(button)
    layout.addStretch()
    return layout

def run_port_test(com_port, baud_rate):
    """Open a serial port to prove a scanner is reachable. Runs off the UI thread."""
    import serial
    with serial.Serial(com_port, baud_rate, timeout=2) as port:
        return f'{com_port} opened successfully at {baud_rate} baud'

def run_excel_export(exporter, options):
    return exporter.export(**options)

class TaskWorker(QThread):
    """Runs a callable on a background thread; emits done(result) or failed(error)."""
    done = Signal(str)
    failed = Signal(str)
    def __init__(self, fn):
        super().__init__(); self.fn = fn
    def run(self):
        try:
            self.done.emit(str(self.fn()))
        except Exception as error:
            self.failed.emit(str(error))
class TablePage(QWidget):
    def __init__(self, title, headers, loader, refresh=0, sortable=True):
        super().__init__()
        self.loader = loader
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.search = QLineEdit(placeholderText='Search…')
        self.search.textChanged.connect(self.load)
        refresh_button = QPushButton('Refresh'); refresh_button.clicked.connect(self.load)
        self.info = QLabel()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title, styleSheet='font-size:23px;font-weight:bold'))
        bar = QHBoxLayout(); bar.addWidget(self.search); bar.addWidget(refresh_button); bar.addStretch()
        layout.addLayout(bar)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.info)
        self._sortable = sortable
        self.table.setSortingEnabled(sortable)
        if sortable: self.table.horizontalHeader().setSortIndicatorShown(True)
        self.load()
        if refresh:
            timer = QTimer(self); timer.timeout.connect(self.load); timer.start(refresh)
    def load(self):
        try:
            rows = self.loader(self.search.text().lower())
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, value in enumerate(row): self.table.setItem(r, c, cell(value))
            self.table.setSortingEnabled(self._sortable)
            self.info.setText(f"{len(rows)} {t('record(s)')}")
        except Exception as error:
            self.info.setText(f'Unable to load data: {error}')
class EmployeesPage(TablePage):
    def __init__(self, db):
        self.svc = EmployeeService(db); self.shifts = ShiftService(db)
        super().__init__('Employees', ['Employee ID', 'Name', 'Department', 'Position', 'Shift', 'Status'], self.rows)
        self.layout().insertLayout(2, buttons_row([
            ('Add Employee', self.add),
            ('Edit', self.edit),
            ('Deactivate / Reactivate', self.toggle),
            ('Generate Barcode', self.barcode),
            ('Import (Excel / CSV)', self.import_employees, SUCCESS_QSS),
            ('Save Import Template', self.save_template),
        ]))
        self.import_worker = None

    def rows(self, q):
        names = {x.id: x.name for x in self.shifts.list()}
        return [(e.employee_id, f'{e.first_name} {e.last_name}', e.department, e.position,
                 names.get(e.assigned_shift_id, ''), 'ACTIVE' if e.active else 'INACTIVE')
                for e in self.svc.list(q)]

    def selected(self):
        row = self.table.currentRow()
        return self.table.item(row, 0).text() if row >= 0 else None

    def dialog(self, employee=None):
        dialog = QDialog(self); dialog.setWindowTitle('Employee')
        form = QFormLayout(dialog)
        fields = {key: QLineEdit(getattr(employee, key) or '') for key in ('first_name', 'last_name', 'employee_number', 'department', 'position')}
        shift = QComboBox(); shift.addItem('Unassigned', None)
        for s in self.shifts.list(): shift.addItem(s.name, s.id)
        if employee and employee.assigned_shift_id is not None:
            index = shift.findData(employee.assigned_shift_id)
            if index >= 0: shift.setCurrentIndex(index)
        for key, control in fields.items(): form.addRow(key.replace('_', ' ').title(), control)
        form.addRow('Shift', shift)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        localize_window(dialog)
        return dialog, fields, shift

    @staticmethod
    def _values(fields):
        return {key: control.text().strip() or None for key, control in fields.items()}

    def add(self):
        dialog, fields, shift = self.dialog()
        if dialog.exec():
            try:
                self.svc.create(**self._values(fields), shift_id=shift.currentData()); self.load()
            except Exception as error: QMessageBox.warning(self, 'Employee', str(error))

    def edit(self):
        employee_id = self.selected()
        if not employee_id: return
        employee = next(x for x in self.svc.list() if x.employee_id == employee_id)
        dialog, fields, shift = self.dialog(employee)
        if dialog.exec():
            try:
                self.svc.update(employee_id, **self._values(fields), assigned_shift_id=shift.currentData()); self.load()
            except Exception as error: QMessageBox.warning(self, 'Employee', str(error))

    def toggle(self):
        employee_id = self.selected()
        if employee_id:
            employee = next(x for x in self.svc.list() if x.employee_id == employee_id)
            self.svc.update(employee_id, active=not employee.active); self.load()

    def barcode(self):
        employee_id = self.selected()
        if employee_id:
            try: QMessageBox.information(self, 'Barcode', str(self.svc.barcode(employee_id)))
            except Exception as error: QMessageBox.warning(self, 'Barcode', str(error))

    # -- bulk import --------------------------------------------------------
    def save_template(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save employee import template',
                                              'employees_import_template', 'Excel (*.xlsx);;CSV (*.csv)')
        if not path: return
        try:
            from app import importer
            if path.lower().endswith('.csv'):
                importer.write_template_csv(path)
            else:
                if not path.lower().endswith('.xlsx'): path += '.xlsx'
                importer.write_template_xlsx(path)
            QMessageBox.information(self, 'Import template', f'Template saved:\n{path}')
        except Exception as error: QMessageBox.warning(self, 'Import template', str(error))

    def import_employees(self):
        if self.import_worker and self.import_worker.isRunning(): return
        path, _ = QFileDialog.getOpenFileName(self, 'Import employees', '',
                                              'Spreadsheets (*.xlsx *.csv);;Excel (*.xlsx);;CSV (*.csv)')
        if not path: return
        self.import_worker = TaskWorker(lambda p=path: self._run_import(p))
        self.import_worker.done.connect(self._import_finished)
        self.import_worker.failed.connect(lambda message: QMessageBox.warning(self, 'Import employees', message))
        self.import_worker.start()

    def _run_import(self, path):
        from app import importer
        rows = importer.read_employee_file(path)
        result = self.svc.import_rows(rows)
        summary = f'Imported {result["created"]} employee(s).\nSkipped {result["skipped"]} (employee number already exists).'
        if result['errors']:
            summary += '\n\nNotes:\n- ' + '\n- '.join(result['errors'][:10])
        return summary

    def _import_finished(self, summary):
        QMessageBox.information(self, 'Import employees', summary)
        self.load()

class ShiftsPage(TablePage):
    def __init__(self,db):
        self.svc=ShiftService(db);super().__init__('Shifts',['Name','Start','End','Early IN','Earliest OUT','Status'],self.rows);bar=QHBoxLayout()
        for label,fn in [('Add Shift',self.add),('Edit Shift',self.edit),('Activate / Deactivate',self.toggle)]:b=QPushButton(label);b.clicked.connect(fn);bar.addWidget(b)
        self.layout().insertLayout(2,bar)
    def rows(self,q):return [(x.name,x.start_time.strftime('%H:%M'),x.end_time.strftime('%H:%M'),x.early_clock_in_minutes,x.earliest_clock_out_minutes,'ACTIVE' if x.active else 'INACTIVE') for x in self.svc.list() if q in x.name.lower()]
    def selected(self):
        row=self.table.currentRow()
        return self.table.item(row,0).text() if row>=0 else None
    def dialog(self,shift=None):
        d=QDialog(self);d.setWindowTitle('Shift');f=QFormLayout(d);name=QLineEdit(shift.name if shift else '');start=QTimeEdit();end=QTimeEdit();start.setDisplayFormat('HH:mm');end.setDisplayFormat('HH:mm');start.setTime((shift.start_time if shift else __import__('datetime').time(6)));end.setTime((shift.end_time if shift else __import__('datetime').time(14)));early=QSpinBox();early.setRange(0,720);early.setValue(shift.early_clock_in_minutes if shift else 60);out=QSpinBox();out.setRange(0,720);out.setValue(shift.earliest_clock_out_minutes if shift else 10)
        for label,control in [('Name',name),('Start',start),('End',end),('Early IN minutes',early),('Earliest OUT minutes',out)]:f.addRow(label,control)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);f.addRow(buttons);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);localize_window(d);return d,name,start,end,early,out
    def add(self):
        d,n,st,en,early,out=self.dialog()
        if d.exec():
            try:self.svc.create(n.text(),st.time().toPython(),en.time().toPython(),early.value(),out.value());self.load()
            except Exception as e:QMessageBox.warning(self,'Shift',str(e))
    def edit(self):
        name=self.selected()
        if not name:return
        shift=next(x for x in self.svc.list() if x.name==name);d,n,st,en,early,out=self.dialog(shift)
        if d.exec():
            try:self.svc.update(shift.id,name=n.text(),start_time=st.time().toPython(),end_time=en.time().toPython(),early_clock_in_minutes=early.value(),earliest_clock_out_minutes=out.value());self.load()
            except Exception as e:QMessageBox.warning(self,'Shift',str(e))
    def toggle(self):
        name=self.selected()
        if name:
            shift=next(x for x in self.svc.list() if x.name==name);self.svc.update(shift.id,active=not shift.active);self.load()
class HardwarePage(TablePage):
    def __init__(self, db, engine, manager=None):
        self.data = AdminDataService(db); self.db = db; self.engine = engine; self.manager = manager
        # Must exist BEFORE the base class calls load(): rows() rebuilds it and the
        # constructor must not wipe it afterwards or row actions report 'no row'.
        self.rows_data = []; self.worker = None
        super().__init__('Terminals & Scanners', ['Terminal', 'Scanner ID', 'COM', 'Baud', 'Enabled', 'Status', 'Description'], self.rows, sortable=False)
        self.layout().insertLayout(2, buttons_row([
            ('Add Terminal', self.add_terminal),
            ('Add Scanner', self.add_scanner),
            ('Edit', self.edit_selected),
            ('Enable / Disable', self.toggle_selected),
            ('Delete', self.delete_selected, DANGER_QSS),
            ('Test Port', self.test_port),
            ('Test Scanner Input', self.test_scan),
        ]))
        # Update the live status column in place — a full reload would reset the
        # currently selected row and make the action buttons report 'no row'.
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_statuses)
        if self.manager: self._status_timer.start(3000)

    def rows(self, q):
        out = []; self.rows_data = []
        for terminal, scanners in self.data.terminals():
            name = terminal.name
            if not scanners:
                if q in name.lower():
                    self.rows_data.append(('terminal', terminal))
                    out.append((name, '—', '—', '—', 'ACTIVE' if terminal.active else 'INACTIVE', '—', 'No scanners'))
                continue
            for scanner in scanners:
                text = ' '.join([name, scanner.scanner_id, scanner.com_port, scanner.description or '']).lower()
                if q and q not in text: continue
                if self.manager: status = self.manager.status_of(scanner.scanner_id).title()
                else: status = 'Enabled' if scanner.enabled else 'Disabled'
                self.rows_data.append(('scanner', scanner))
                out.append((name, scanner.scanner_id, scanner.com_port, scanner.baud_rate, 'YES' if scanner.enabled else 'NO', status, scanner.description or ''))
        return out

    def current(self):
        row = self.table.currentRow()
        if row < 0:
            selected = self.table.selectionModel().selectedRows()
            if selected: row = selected[0].row()
        return self.rows_data[row] if 0 <= row < len(self.rows_data) else None

    def _refresh_statuses(self):
        """Live-edit only the Status column so the row selection is never lost."""
        if not self.manager or not hasattr(self, 'rows_data'): return
        for row, (kind, obj) in enumerate(self.rows_data):
            if kind != 'scanner': continue
            item = self.table.item(row, 5)
            if item is not None:
                item.setText(self.manager.status_of(obj.scanner_id).title())

    def reload_manager(self):
        if self.manager:
            try: self.manager.reload(self.data.scanners_flat())
            except Exception as error: QMessageBox.warning(self, 'Scanner', f'Unable to restart scanners: {error}')

    def add_terminal(self):
        name, ok = QInputDialog.getText(self, 'Add Terminal', 'Terminal name')
        if ok and name.strip():
            try:
                self.data.save_terminal(name.strip()); self.load()
            except Exception as error: QMessageBox.warning(self, 'Terminal', str(error))

    def scanner_dialog(self, terminal_id=None, com='COM3', baud=9600, desc='', enabled=True):
        dialog = QDialog(self); dialog.setWindowTitle('Scanner')
        form = QFormLayout(dialog)
        terminal = QComboBox()
        for t, _ in self.data.terminals(): terminal.addItem(t.name, t.id)
        if terminal_id is not None:
            index = terminal.findData(terminal_id)
            if index >= 0: terminal.setCurrentIndex(index)
        port = QLineEdit(com)
        baud_edit = QSpinBox(); baud_edit.setRange(1200, 115200); baud_edit.setSingleStep(1200); baud_edit.setValue(baud)
        description = QLineEdit(desc)
        enabled_box = QComboBox(); enabled_box.addItem('Yes', True); enabled_box.addItem('No', False)
        enabled_box.setCurrentIndex(0 if enabled else 1)
        form.addRow('Terminal', terminal); form.addRow('COM port', port); form.addRow('Baud rate', baud_edit)
        form.addRow('Description', description); form.addRow('Enabled', enabled_box)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        localize_window(dialog)
        return dialog, terminal, port, baud_edit, description, enabled_box

    def add_scanner(self):
        if not self.data.terminals():
            QMessageBox.warning(self, 'Scanner', 'Create a terminal first.'); return
        dialog, terminal, port, baud_edit, description, enabled_box = self.scanner_dialog()
        if dialog.exec():
            scanner_id, ok = QInputDialog.getText(self, 'Add Scanner', 'Scanner ID')
            if not ok or not scanner_id.strip(): return
            try:
                self.data.save_scanner(scanner_id.strip(), terminal.currentData(), port.text().strip(),
                                       description.text().strip(), enabled=bool(enabled_box.currentData()), baud_rate=baud_edit.value())
                self.load(); self.reload_manager()
            except Exception as error: QMessageBox.warning(self, 'Scanner', str(error))

    def edit_selected(self):
        selected = self.current()
        if not selected: return
        kind, obj = selected
        if kind == 'terminal':
            name, ok = QInputDialog.getText(self, 'Rename Terminal', 'Terminal name', text=obj.name)
            if ok and name.strip():
                try:
                    self.data.update_terminal(obj.id, name=name.strip()); self.load()
                except Exception as error: QMessageBox.warning(self, 'Terminal', str(error))
        else:
            dialog, terminal, port, baud_edit, description, enabled_box = self.scanner_dialog(obj.terminal_id, obj.com_port, obj.baud_rate, obj.description or '', obj.enabled)
            if dialog.exec():
                try:
                    self.data.update_scanner(obj.scanner_id, terminal_id=terminal.currentData(), com_port=port.text().strip(),
                                             baud_rate=baud_edit.value(), description=description.text().strip(), enabled=bool(enabled_box.currentData()))
                    self.load(); self.reload_manager()
                except Exception as error: QMessageBox.warning(self, 'Scanner', str(error))

    def toggle_selected(self):
        selected = self.current()
        if not selected: return
        kind, obj = selected
        try:
            if kind == 'terminal': self.data.update_terminal(obj.id, active=not obj.active)
            else: self.data.update_scanner(obj.scanner_id, enabled=not obj.enabled)
            self.load(); self.reload_manager()
        except Exception as error: QMessageBox.warning(self, 'Hardware', str(error))

    def delete_selected(self):
        selected = self.current()
        if not selected: return
        kind, obj = selected
        label = f'Scanner {obj.scanner_id}' if kind == 'scanner' else f'Terminal {obj.name} (and its scanners)'
        answer = QMessageBox.question(self, 'Delete', f'Delete {label}?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes: return
        try:
            if kind == 'terminal': self.data.delete_terminal(obj.id)
            else: self.data.delete_scanner(obj.scanner_id)
            self.load(); self.reload_manager()
        except Exception as error: QMessageBox.warning(self, 'Delete', str(error))

    def test_port(self):
        selected = self.current()
        if not selected:
            QMessageBox.information(self, 'Test Port', 'Select a scanner row first.'); return
        kind, obj = selected
        if kind != 'scanner':
            QMessageBox.information(self, 'Test Port', f'"{obj.name}" is a terminal (no COM port). Select a scanner row to test its port.')
            return
        scanner = obj
        self.worker = TaskWorker(lambda com=scanner.com_port, baud=scanner.baud_rate: run_port_test(com, baud))
        self.worker.done.connect(lambda message: QMessageBox.information(self, 'Test Port', message))
        self.worker.failed.connect(lambda error: QMessageBox.warning(self, 'Test Port', f'{scanner.com_port} could not be opened:\n{error}'))
        self.worker.start()

    def test_scan(self):
        """Simulate a scanner reading a barcode straight through the attendance engine.

        Uses real employees so accepted clock-ins are easy to test, and publishes the
        result to the kiosk exactly like a hardware scan would.
        """
        employees = EmployeeService(self.db).list()
        dialog = QDialog(self); dialog.setWindowTitle('Test Scanner')
        form = QFormLayout(dialog)
        hint = QLabel('Pick an employee to simulate a successful scan, or type any barcode '
                      '(unknown barcodes are recorded as UNKNOWN_BARCODE).')
        hint.setWordWrap(True)
        form.addRow(hint)
        combo = QComboBox(); combo.setEditable(True)
        for e in employees:
            combo.addItem(f'{e.employee_id} · {e.first_name} {e.last_name}', e.employee_id)
        if employees: combo.setCurrentIndex(0)
        else: combo.setEditText('EMP000001')
        form.addRow('Barcode', combo)
        terminal = QComboBox()
        for t, _ in self.data.terminals(): terminal.addItem(t.name, t.id)
        if terminal.count() == 0: terminal.addItem('Terminal 1', None)
        form.addRow('Terminal', terminal)
        scanner_combo = QComboBox()
        scanners = self.data.scanners_flat()
        if scanners:
            for sc in scanners: scanner_combo.addItem(f'{sc.scanner_id} ({sc.com_port})', sc.scanner_id)
        else:
            scanner_combo.addItem('SIMULATOR', 'SIMULATOR')
        form.addRow('Scanner', scanner_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Scan')
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        localize_window(dialog)
        if not dialog.exec(): return
        payload = combo.currentData()
        if payload is None:
            raw = combo.currentText().strip()
            payload = raw.split(' · ')[0].strip() if ' · ' in raw else raw
        from app.attendance import ScannerEvent
        result = self.engine.process(ScannerEvent(payload, datetime.now(), terminal.currentData(), scanner_combo.currentData()))
        if self.manager is not None:
            try: self.manager.publish(result)
            except Exception: pass
        message = f"{'ACCEPTED' if result.accepted else 'REJECTED'}\nAction: {result.action}\nReason: {result.reason or '—'}\nTerminal: {terminal.currentData()}   Scanner: {scanner_combo.currentData()}"
        if not result.accepted and result.reason == 'UNKNOWN_BARCODE':
            message += '\n\nTip: that barcode does not match any employee. Pick one from the list instead.'
        QMessageBox.information(self, 'Scanner test', message)
        self.load()
class DashboardPage(TablePage):
    CARD_STYLE = 'background:#1c242d;border:1px solid #2e3c4a;border-radius:8px;padding:6px'
    def __init__(self, db):
        self.data = AdminDataService(db)
        self.card_values = {}
        super().__init__('ATTENDANCE CONTROL — DASHBOARD', ['Timestamp', 'Employee', 'Action', 'Terminal', 'Scanner', 'Accepted', 'Reason'], self.rows, refresh=3000, sortable=False)
        cards = QWidget()
        grid = QGridLayout(cards); grid.setContentsMargins(0, 4, 0, 4); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8)
        self.card_values = {}
        definitions = [('total_employees', 'Employees'), ('present_now', 'Present now'), ('missing_out', 'Missing clock-out'), ('exceptions_today', 'Exceptions today'),
                       ('scans_today', 'Scans today'), ('accepted_today', 'Accepted scans'), ('terminals', 'Terminals'), ('scanners', 'Scanners')]
        for index, (key, caption) in enumerate(definitions):
            frame = QFrame(); frame.setStyleSheet(self.CARD_STYLE)
            column = QVBoxLayout(frame); column.setContentsMargins(12, 8, 12, 8); column.setSpacing(2)
            value = QLabel('0', styleSheet='font-size:26px;font-weight:bold;color:#55a9d8')
            label = QLabel(caption, styleSheet='font-size:12px;color:#9fb3c4')
            column.addWidget(value); column.addWidget(label)
            self.card_values[key] = value
            grid.addWidget(frame, index // 4, index % 4)
        self.layout().insertWidget(1, cards)
        self.refresh_cards()
    def refresh_cards(self):
        if not self.card_values: return
        values = self.data.summary()
        for key, label in self.card_values.items():
            label.setText(str(values.get(key, 0)))
    def load(self):
        self.refresh_cards()
        super().load()
    def rows(self, q):
        scans = self.data.scans()
        return [(x.timestamp, f'{e.first_name} {e.last_name}' if e else x.employee_id or 'Unknown', x.action, x.terminal_id, x.scanner_id, 'YES' if x.accepted else 'NO', x.rejection_reason) for x, e in scans if q in str(x.employee_id).lower()]
class ExportJobsPage(TablePage):
    def __init__(self, db):
        self.data = AdminDataService(db); self.db = db
        # Must exist BEFORE the base class calls load(): rows() rebuilds it and the
        # constructor must not wipe it afterwards or row actions become no-ops.
        self.jobs = []
        super().__init__('Automatic Exports', ['Enabled', 'Time', 'Frequency', 'Schedule', 'Destination', 'Last Run', 'Next Run', 'Status'], self.rows, sortable=False)
        self.layout().insertLayout(2, buttons_row([
            ('Add Export Job', self.add),
            ('Edit', self.edit),
            ('Enable / Disable', self.toggle),
            ('Run Selected Now', self.run_now, SUCCESS_QSS),
            ('Delete', self.delete_job, DANGER_QSS),
        ]))
    def rows(self, q):
        jobs = list(self.data.export_jobs()); jobs.sort(key=lambda j: j.run_time)
        self.jobs = []; out = []
        for j in jobs:
            haystack = ' '.join([j.destination, j.run_time, j.frequency]).lower()
            if q and q not in haystack: continue
            self.jobs.append(j)
            out.append(('YES' if j.enabled else 'NO', j.run_time, j.frequency.title(), schedule_text(j), j.destination,
                        j.last_run.strftime('%Y-%m-%d %H:%M') if j.last_run else 'Never',
                        next_run_time(j).strftime('%Y-%m-%d %H:%M'), 'READY' if j.enabled else 'DISABLED'))
        return out
    def job(self):
        row = self.table.currentRow()
        return self.jobs[row] if 0 <= row < len(self.jobs) else None
    def dialog(self, job=None):
        dialog = QDialog(self); dialog.setWindowTitle('Export job')
        form = QFormLayout(dialog)
        time_edit = QTimeEdit(); time_edit.setDisplayFormat('HH:mm')
        if job: time_edit.setTime(QTime.fromString(job.run_time, 'HH:mm'))
        destination = QLineEdit(job.destination if job else 'exports')
        frequency = QComboBox(); frequency.addItems(['daily', 'weekly', 'monthly'])
        if job and job.frequency in ('daily', 'weekly', 'monthly'): frequency.setCurrentText(job.frequency)
        weekday = QComboBox()
        for name in WEEKDAYS: weekday.addItem(name)
        if job and job.weekday is not None: weekday.setCurrentIndex(job.weekday)
        month_day = QSpinBox(); month_day.setRange(1, 31); month_day.setValue(job.month_day or 1)
        def sync_enabled():
            weekly = frequency.currentText() == 'weekly'; monthly = frequency.currentText() == 'monthly'
            weekday.setEnabled(weekly); month_day.setEnabled(monthly)
        frequency.currentIndexChanged.connect(lambda *_: sync_enabled()); sync_enabled()
        form.addRow('Time', time_edit); form.addRow('Destination folder', destination)
        form.addRow('Frequency', frequency); form.addRow('Weekday (weekly)', weekday); form.addRow('Day of month (monthly)', month_day)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        localize_window(dialog)
        return dialog, time_edit, destination, frequency, weekday, month_day
    def _collect(self, time_edit, destination, frequency, weekday, month_day):
        chosen = frequency.currentText()
        return dict(run_time=time_edit.time().toString('HH:mm'), destination=destination.text().strip() or 'exports',
                    frequency=chosen, weekday=weekday.currentIndex() if chosen == 'weekly' else None,
                    month_day=month_day.value() if chosen == 'monthly' else None)
    def add(self):
        dialog, time_edit, destination, frequency, weekday, month_day = self.dialog()
        if dialog.exec():
            try:
                self.data.save_export_job(**self._collect(time_edit, destination, frequency, weekday, month_day)); self.load()
            except Exception as error: QMessageBox.warning(self, 'Export job', str(error))
    def edit(self):
        job = self.job()
        if not job: return
        dialog, time_edit, destination, frequency, weekday, month_day = self.dialog(job)
        if dialog.exec():
            try:
                self.data.update_export_job(job.id, **self._collect(time_edit, destination, frequency, weekday, month_day)); self.load()
            except Exception as error: QMessageBox.warning(self, 'Export job', str(error))
    def toggle(self):
        job = self.job()
        if job:
            self.data.update_export_job(job.id, enabled=not job.enabled); self.load()
    def delete_job(self):
        job = self.job()
        if not job: return
        answer = QMessageBox.question(self, 'Delete export job', f'Delete the export job at {job.run_time}?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.data.delete_export_job(job.id); self.load()
    def run_now(self):
        job = self.job()
        if not job: return
        try:
            path = ExcelExporter(self.db).export(job.destination)
            self.data.update_export_job(job.id, last_run=datetime.now())
            QMessageBox.information(self, 'Automatic export', f'Export completed:\n{path}'); self.load()
        except Exception as error: QMessageBox.warning(self, 'Automatic export', str(error))
class AttendancePage(TablePage):
    def __init__(self, db, title='Attendance'):
        self.data = AdminDataService(db)
        super().__init__(title, ['Clock In', 'Employee', 'Shift', 'Clock Out', 'Worked Hours', 'Status'], self.rows, sortable=False)
        bar = QHBoxLayout()
        self.start = QDateEdit(); self.end = QDateEdit()
        self.status_filter = QComboBox(); self.status_filter.addItems(['All', 'OK', 'MISSING OUT'])
        today = QDate.currentDate(); self.start.setDate(today.addDays(-30)); self.end.setDate(today)
        self.start.setCalendarPopup(True); self.end.setCalendarPopup(True)
        self.employee_filter = QComboBox(); self.employee_filter.addItem('All employees', None)
        for e in EmployeeService(db).list(): self.employee_filter.addItem(f'{e.employee_id} — {e.first_name} {e.last_name}', e.employee_id)
        self.shift_filter = QComboBox(); self.shift_filter.addItem('All shifts', None)
        for s in ShiftService(db).list(): self.shift_filter.addItem(s.name, s.id)
        apply = QPushButton('Apply filters'); apply.clicked.connect(self.load)
        for control in (QLabel('From'), self.start, QLabel('To'), self.end, QLabel('Employee'), self.employee_filter,
                        QLabel('Shift'), self.shift_filter, QLabel('Status'), self.status_filter, apply):
            bar.addWidget(control)
        bar.addStretch()
        self.layout().insertLayout(2, bar)
        self.load()
    def filtered(self, q=''):
        """Return matched sessions as dicts so subclasses can re-aggregate."""
        date_from, date_to = self.start.date().toPython(), self.end.date().toPython()
        employee_id = self.employee_filter.currentData()
        shift_id = self.shift_filter.currentData()
        status_wanted = self.status_filter.currentText()
        result = []
        for session, employee, shift in self.data.sessions():
            if employee is None: continue
            status = 'OK' if session.clock_out else 'MISSING OUT'
            if session.clock_in.date() < date_from or session.clock_in.date() > date_to: continue
            if status_wanted != 'All' and status != status_wanted: continue
            if employee_id is not None and employee.employee_id != employee_id: continue
            if shift_id is not None and (shift is None or shift.id != shift_id): continue
            name = f'{employee.first_name} {employee.last_name}'
            if q and q not in (name + employee.employee_id).lower(): continue
            result.append({'session': session, 'employee': employee, 'shift': shift, 'name': name, 'status': status})
        return result
    def rows(self, q):
        if not hasattr(self, 'start'): return []
        return [(r['session'].clock_in, r['name'], r['shift'].name if r['shift'] else '', r['session'].clock_out,
                 round((r['session'].clock_out - r['session'].clock_in).total_seconds() / 3600, 2) if r['session'].clock_out else '', r['status']) for r in self.filtered(q)]

class ReportsPage(AttendancePage):
    def __init__(self, db):
        super().__init__(db, 'Reports')
        self.summary_label = QLabel(styleSheet='background:#1c242d;padding:10px;border-radius:6px;font-size:13px')
        self.layout().addWidget(self.summary_label)
        self.layout().addWidget(QLabel('Totals by shift', styleSheet='font-weight:bold;margin-top:6px'))
        self.shift_table = QTableWidget(0, 3)
        self.shift_table.setHorizontalHeaderLabels(['Shift', 'Sessions', 'Worked hours'])
        self.shift_table.setAlternatingRowColors(True)
        self.layout().addWidget(self.shift_table)
        self.refresh_summary()
    def load(self):
        if hasattr(self, 'summary_label'):
            super().load()
            self.refresh_summary()
        else:
            super().load()
    def refresh_summary(self):
        if not hasattr(self, 'summary_label'): return
        rows = self.filtered()
        worked = [round((r['session'].clock_out - r['session'].clock_in).total_seconds() / 3600, 2) for r in rows if r['session'].clock_out]
        totals = {}
        for r in rows:
            name = r['shift'].name if r['shift'] else 'No shift'
            entry = totals.setdefault(name, [0, 0.0])
            entry[0] += 1
            if r['session'].clock_out:
                entry[1] += round((r['session'].clock_out - r['session'].clock_in).total_seconds() / 3600, 2)
        self.summary_label.setText(
            f'Sessions in range: {len(rows)}     Distinct employees: {len({r["employee"].employee_id for r in rows})}     '
            f'Total worked hours: {round(sum(worked), 2)}     Average per session: {round(sum(worked) / len(worked), 2) if worked else 0}     '
            f'Completed (OK): {sum(1 for r in rows if r["status"] == "OK")}     Missing clock-out: {sum(1 for r in rows if r["status"] == "MISSING OUT")}')
        self.shift_table.setSortingEnabled(False)
        self.shift_table.setRowCount(len(totals))
        for row, (name, (count, hours)) in enumerate(sorted(totals.items())):
            self.shift_table.setItem(row, 0, cell(name)); self.shift_table.setItem(row, 1, cell(count)); self.shift_table.setItem(row, 2, cell(round(hours, 2)))
class Kiosk(QWidget):
    READY = 'SYSTEM ONLINE\n\nREADY TO SCAN'
    def __init__(self, engine, manager=None):
        super().__init__(); self.engine = engine; self.manager = manager; self._shown_time = None
        self.clock = QLabel(alignment=Qt.AlignCenter); self.clock.setStyleSheet('font-size:80px;font-weight:bold;color:#ffffff')
        self.date = QLabel(alignment=Qt.AlignCenter); self.date.setStyleSheet('font-size:22px;color:#9fb3c4')
        self.status = QLabel(t(self.READY), alignment=Qt.AlignCenter)
        self.status.setStyleSheet('font-size:28px;color:#55d68a')
        layout = QVBoxLayout(self); layout.addStretch()
        layout.addWidget(self.date); layout.addWidget(self.clock); layout.addWidget(self.status); layout.addStretch()
        timer = QTimer(self); timer.timeout.connect(self._tick); timer.start(1000)
        self._tick()
    def _tick(self):
        now = datetime.now()
        self.clock.setText(now.strftime('%H:%M:%S'))
        self.date.setText(format_kiosk_date(now))
        if self.manager and self.manager.last_result is not None and self.manager.last_result_time != self._shown_time:
            self._shown_time = self.manager.last_result_time
            self.present(self.manager.last_result)
    def present(self, result):
        employee_id = result.employee.employee_id if result.employee else t('Unknown barcode')
        if result.accepted:
            self.status.setStyleSheet('font-size:28px;color:#55d68a')
            self.status.setText(f'✓ {reason_text("CLOCK " + result.action)}\n\n{employee_id}')
        else:
            self.status.setStyleSheet('font-size:28px;color:#e05f5f')
            self.status.setText(f'⚠ {reason_text(result.reason or "REJECTED")}\n\n{employee_id}')
        QTimer.singleShot(2500, lambda: (self.status.setStyleSheet('font-size:28px;color:#55d68a'), self.status.setText(t(self.READY))))

class KioskWindow(QMainWindow):
    """Full-screen, touch-oriented kiosk used by the 'Enter Kiosk Mode' action."""
    def __init__(self, engine, manager, parent_window):
        super().__init__(); self.parent_window = parent_window
        self.setWindowTitle('Attendance Control — Kiosk')
        central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.addWidget(Kiosk(engine, manager), 1)
        row = QHBoxLayout(); row.addStretch()
        admin = QPushButton('Administrator login'); admin.clicked.connect(self._unlock)
        row.addWidget(admin); layout.addLayout(row)
        localize_window(self)
    def _unlock(self):
        dialog = AdminLoginDialog(self.parent_window.db)
        if dialog.exec():
            self.parent_window.username = dialog.username.text().strip()
            self.parent_window._update_session_label()
            self.close()

class ExcelExportPage(QWidget):
    def __init__(self, db):
        super().__init__(); self.db = db; self.worker = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('EXPORT ATTENDANCE', styleSheet='font-size:23px;font-weight:bold'))
        grid = QGridLayout()
        self.folder = QLineEdit('exports')
        self.start = QDateEdit(); self.end = QDateEdit()
        self.start.setCalendarPopup(True); self.end.setCalendarPopup(True)
        self.start.setDate(QDate.currentDate().addDays(-30)); self.end.setDate(QDate.currentDate())
        self.employee = QComboBox(); self.employee.addItem('All employees', None)
        for e in EmployeeService(db).list(): self.employee.addItem(f'{e.employee_id} — {e.first_name} {e.last_name}', e.employee_id)
        self.department = QLineEdit(placeholderText='All departments')
        controls = [('Destination folder', self.folder), ('From', self.start), ('To', self.end), ('Employee', self.employee), ('Department', self.department)]
        for row, (label, control) in enumerate(controls):
            grid.addWidget(QLabel(label), row, 0); grid.addWidget(control, row, 1)
        layout.addLayout(grid)
        group = QGroupBox('Sheets to include'); sheet_row = QHBoxLayout()
        self.sheet_checks = {}
        for name in SHEET_NAMES:
            check = QCheckBox(name); check.setChecked(True); self.sheet_checks[name] = check; sheet_row.addWidget(check)
        sheet_row.addStretch(); group.setLayout(sheet_row); layout.addWidget(group)
        self.progress = QProgressBar(); self.progress.setVisible(False)
        self.result = QLabel()
        self.button = QPushButton('EXPORT EXCEL')
        self.button.clicked.connect(self.start_export)
        layout.addWidget(self.button); layout.addWidget(self.progress); layout.addWidget(self.result)
        layout.addStretch()
    def selected_sheets(self):
        return [name for name, check in self.sheet_checks.items() if check.isChecked()]
    def start_export(self):
        if self.worker and self.worker.isRunning(): return
        include = self.selected_sheets()
        if not include:
            QMessageBox.warning(self, 'Excel export', 'Select at least one sheet.'); return
        options = dict(directory=self.folder.text().strip() or 'exports', date_from=self.start.date().toPython(),
                       date_to=self.end.date().toPython(), employee_id=self.employee.currentData(),
                       department=self.department.text().strip() or None, include=include)
        self.button.setEnabled(False); self.progress.setVisible(True); self.progress.setRange(0, 0); self.result.setText('Exporting in the background…')
        exporter = ExcelExporter(self.db)
        self.worker = TaskWorker(lambda: run_excel_export(exporter, options))
        self.worker.done.connect(self._on_done); self.worker.failed.connect(self._on_failed)
        self.worker.start()
    def _on_done(self, path):
        self.progress.setVisible(False); self.button.setEnabled(True)
        self.result.setText(f'✓ Export completed: {path}')
        QMessageBox.information(self, 'Excel export', f'Export completed:\n{path}')
    def _on_failed(self, message):
        self.progress.setVisible(False); self.button.setEnabled(True)
        self.result.setText(f'Export failed: {message}')
        QMessageBox.warning(self, 'Excel export', f'Export failed: {message}')

class SyncPage(QWidget):
    def __init__(self, db, sync_service=None, offline_queue=None):
        super().__init__(); self.db = db; self.sync = sync_service; self.offline_queue = offline_queue; self.worker = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('SYNCHRONIZATION', styleSheet='font-size:23px;font-weight:bold'))
        intro = QLabel('Events that could not be saved are kept in a durable local queue and replayed automatically. '
                       'When a server URL is configured, every new scan event is also pushed there so several kiosks can share a central database.')
        intro.setWordWrap(True); layout.addWidget(intro)
        form = QFormLayout()
        self.enabled = QCheckBox('Enable automatic synchronization')
        self.server_url = QLineEdit(placeholderText='https://server.example.com/api/scans')
        self.token = QLineEdit(); self.token.setEchoMode(QLineEdit.Password); self.token.setPlaceholderText('Optional bearer token')
        self.interval = QSpinBox(); self.interval.setRange(1, 1440); self.interval.setSuffix(' min'); self.interval.setValue(5)
        form.addRow(self.enabled); form.addRow('Server URL', self.server_url); form.addRow('Token', self.token); form.addRow('Interval', self.interval)
        layout.addLayout(form)
        layout.addLayout(buttons_row([('Save Settings', self.save_settings), ('Synchronise Now', self.sync_now, SUCCESS_QSS), ('Test Connection', self.test_connection)]))
        self.status_label = QLabel(styleSheet='background:#1c242d;padding:10px;border-radius:6px')
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.refresh(); layout.addStretch()
    def refresh(self):
        if not self.sync:
            self.status_label.setText('Synchronization service is not available.')
            self.setEnabled(False); return
        settings = self.sync.settings()
        self.enabled.setChecked(settings['sync_enabled'])
        self.server_url.setText(settings['sync_server_url'])
        self.token.setText(settings['sync_token'])
        self.interval.setValue(settings['sync_interval_minutes'])
        queue = f' | {self.offline_queue.count()} offline event(s) queued' if self.offline_queue else ''
        self.status_label.setText(self.sync.last_status() + queue)
    def save_settings(self):
        self.sync.save_settings(self.enabled.isChecked(), self.server_url.text(), self.token.text(), self.interval.value())
        QMessageBox.information(self, 'Synchronization', 'Settings saved.'); self.refresh()
    def sync_now(self):
        if not self.sync or (self.worker and self.worker.isRunning()): return
        self.worker = TaskWorker(lambda: self.sync.synchronize_now())
        self.worker.done.connect(lambda message: (self.status_label.setText(message), QMessageBox.information(self, 'Synchronization', message)))
        self.worker.failed.connect(lambda message: QMessageBox.warning(self, 'Synchronization', message))
        self.worker.start()
    def test_connection(self):
        if not self.sync or (self.worker and self.worker.isRunning()): return
        url = self.server_url.text().strip(); token = self.token.text().strip()
        self.worker = TaskWorker(lambda: _format_connection_test(self.sync.test_connection(url, token)))
        self.worker.done.connect(lambda message: QMessageBox.information(self, 'Test Connection', message))
        self.worker.failed.connect(lambda message: QMessageBox.warning(self, 'Test Connection', message))
        self.worker.start()

def _format_connection_test(result):
    ok, message = result
    return f"{'✓' if ok else '✗'} {message}"

class SettingsPage(QWidget):
    def __init__(self, db, username=None):
        super().__init__(); self.db = db; self.username = username or ''
        data = AdminDataService(db)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('SETTINGS', styleSheet='font-size:23px;font-weight:bold'))
        form = QFormLayout()
        self.site = QLineEdit(data.settings().get('site_name', 'Company'))
        form.addRow('Site name', self.site)
        self.language = QComboBox()
        self.language.addItem('English', 'en')
        self.language.addItem('Română', 'ro')
        index = self.language.findData(data.settings().get('language', 'en'))
        self.language.setCurrentIndex(max(0, index))
        form.addRow('Language', self.language)
        layout.addLayout(form)
        layout.addLayout(buttons_row([('Save Settings', self._save_site)]))
        if self.username:
            layout.addWidget(QLabel(f"{t('Logged in as: ')}{self.username}", styleSheet='color:#9fb3c4'))
            layout.addLayout(buttons_row([('Change Password', self.change_password)]))
        layout.addStretch()
    def _save_site(self):
        from app.i18n import set_language
        data = AdminDataService(self.db)
        previous = data.settings().get('language', 'en')
        code = self.language.currentData() or 'en'
        data.set_setting('site_name', self.site.text())
        data.set_setting('language', code)
        set_language(code)
        message = t('Saved')
        if code != previous:
            message += '\n\n' + t('Language will be applied fully after restarting Attendance Control.')
        QMessageBox.information(self, t('Settings'), message)
    def change_password(self):
        if not self.username: return
        dialog = QDialog(self); dialog.setWindowTitle('Change Password')
        form = QFormLayout(dialog)
        old = QLineEdit(); old.setEchoMode(QLineEdit.Password)
        new = QLineEdit(); new.setEchoMode(QLineEdit.Password)
        confirm = QLineEdit(); confirm.setEchoMode(QLineEdit.Password)
        form.addRow('Current password', old); form.addRow('New password', new); form.addRow('Confirm password', confirm)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        localize_window(dialog)
        if dialog.exec():
            try:
                if new.text() != confirm.text(): raise ValueError('Passwords do not match')
                AuthService(self.db).change_password(self.username, old.text(), new.text())
                QMessageBox.information(self, 'Password', 'Password changed')
            except Exception as error: QMessageBox.warning(self, 'Password', str(error))

class BackupPage(QWidget):
    def __init__(self, db):
        super().__init__(); self.db = db
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('BACKUP / RESTORE', styleSheet='font-size:23px;font-weight:bold'))
        layout.addWidget(QLabel(f'Database location: {self.db.path}'))
        layout.addWidget(QLabel('Keep backups on a different drive. A backup of the current database is always created before a restore.'))
        self.backups = QListWidget()
        layout.addWidget(QLabel('Existing backups:'))
        layout.addWidget(self.backups)
        layout.addLayout(buttons_row([('Backup Database Now', self.backup, SUCCESS_QSS), ('Restore Database', self.restore), ('Refresh List', self.load_backups)]))
        self.status = QLabel(); layout.addWidget(self.status)
        layout.addStretch()
        self.load_backups()
    def load_backups(self):
        self.backups.clear()
        folder = Path('backup')
        if folder.exists():
            for item in sorted(folder.glob('*.db'), reverse=True):
                self.backups.addItem(item.name)
        self.status.setText('')
    def backup(self):
        try:
            destination = backup_database(self.db.path)
            self.status.setText(f'Backup created: {destination}'); self.load_backups()
        except Exception as error: QMessageBox.warning(self, 'Backup', str(error))
    def restore(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select database backup', 'backup', 'SQLite databases (*.db)')
        if not path: return
        answer = QMessageBox.question(self, 'Restore database', 'This will replace the current attendance database. A backup of the current database will be created first. Continue?',
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes: return
        try:
            current = restore_database(path, self.db.path)
            self.status.setText(f'Restored successfully. Current database backed up to: {current}\nRestart Attendance Control now.')
        except Exception as error: QMessageBox.warning(self, 'Restore database', str(error))

class AboutPage(QWidget):
    """Version, licensing, copyright and contact information (admin section)."""
    def __init__(self):
        super().__init__()
        from app import APP_NAME, OWNER, CONTACT_URL, LICENSE
        layout = QVBoxLayout(self)
        title = QLabel(f'{APP_NAME} v{APP_VERSION}', styleSheet='font-size:24px;font-weight:bold')
        layout.addWidget(title)
        owner = QLabel(f"{t('Licensed to')}  <b>{OWNER}</b>")
        owner.setTextFormat(Qt.RichText)
        layout.addWidget(owner)
        copyright_line = QLabel('Copyright © 2026 Csepregi Artur. All rights reserved.')
        copyright_line.setStyleSheet('color:#9fb3c4')
        layout.addWidget(copyright_line)
        summary = QLabel(LICENSE)
        summary.setWordWrap(True); summary.setStyleSheet('color:#9fb3c4')
        layout.addWidget(summary)
        row = QHBoxLayout()
        row.addWidget(QLabel(t('Contact: ')))
        contact = QLabel(f'<a href="{CONTACT_URL}">{CONTACT_URL}</a>')
        contact.setTextFormat(Qt.RichText)
        contact.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        row.addWidget(contact); row.addStretch()
        layout.addLayout(row)
        layout.addWidget(QLabel(t('Full license text:'), styleSheet='font-weight:bold'))
        license_text = QPlainTextEdit(); license_text.setReadOnly(True)
        license_path = Path('LICENSE')
        license_text.setPlainText(license_path.read_text(encoding='utf-8') if license_path.exists() else LICENSE)
        layout.addWidget(license_text, 1)

ICON_MAP = {
    'Dashboard': 'SP_DesktopIcon', 'Employees': 'SP_DirHomeIcon', 'Shifts': 'SP_FileIcon',
    'Attendance': 'SP_FileDialogContentsView', 'Live Scans': 'SP_FileDialogListView', 'Exceptions': 'SP_MessageBoxWarning',
    'Terminals & Scanners': 'SP_DriveHDIcon', 'Reports': 'SP_FileDialogDetailedView', 'Excel Export': 'SP_DialogSaveButton',
    'Automatic Exports': 'SP_BrowserReload', 'Settings': 'SP_FileDialogInfoView', 'System Logs': 'SP_FileDialogContentsView',
    'Backup / Restore': 'SP_DriveFDIcon', 'Synchronization': 'SP_ArrowUp', 'About & License': 'SP_MessageBoxInformation',
    'Kiosk': 'SP_ComputerIcon',
}

class KioskShell(QMainWindow):
    """Start-up window: full-screen kiosk plus an administrator login button.

    Employees only ever see this screen. Clicking the login button opens the
    administrator dialog; on success the admin window opens and the kiosk is
    hidden until the administrator logs out, locks, or closes the admin window.
    """
    def __init__(self, db, engine, scanner_manager=None, sync_service=None, offline_queue=None):
        super().__init__()
        self.db = db; self.engine = engine
        self.scanner_manager = scanner_manager; self.sync_service = sync_service; self.offline_queue = offline_queue
        self.admin = None
        self.setWindowTitle('Attendance Control — Kiosk')
        central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        self.kiosk = Kiosk(engine, scanner_manager)
        layout.addWidget(self.kiosk, 1)
        bar = QHBoxLayout(); bar.setContentsMargins(8, 4, 8, 6)
        note = QLabel('Employees scan their badge. Administrators can sign in to manage the system.')
        note.setStyleSheet('color:#9fb3c4')
        login = QPushButton('ADMINISTRATOR LOGIN')
        login.setStyleSheet('QPushButton{background:#2374ab;padding:12px 20px;border-radius:5px;font-weight:bold} QPushButton:hover{background:#318bc4}')
        login.setCursor(Qt.PointingHandCursor)
        login.clicked.connect(self._prompt_login)
        bar.addWidget(note); bar.addStretch(); bar.addWidget(login)
        layout.addLayout(bar)
        localize_window(self)

    def _prompt_login(self):
        dialog = AdminLoginDialog(self.db)
        if dialog.exec():
            self.open_admin(dialog.username.text().strip())

    def open_admin(self, username):
        if self.admin is not None:
            self.admin.show(); self.admin.raise_(); self.admin.activateWindow(); return
        self.admin = MainWindow(self.db, self.engine, username,
                                scanner_manager=self.scanner_manager,
                                sync_service=self.sync_service,
                                offline_queue=self.offline_queue,
                                on_kiosk_return=self._return_to_kiosk)
        self.admin.showMaximized()
        self.hide()

    def _return_to_kiosk(self):
        self.admin = None
        self.showFullScreen()
        self.raise_()

    def closeEvent(self, event):
        # Closing the kiosk quits the whole application.
        if self.admin is not None:
            self.admin._on_kiosk_return = None
            self.admin.close()
        event.accept()

class MainWindow(QMainWindow):
    def __init__(self, db, engine, username=None, scanner_manager=None, sync_service=None, offline_queue=None, on_kiosk_return=None):
        super().__init__()
        self.db = db; self.engine = engine; self.username = username or ''
        self.scanner_manager = scanner_manager; self.sync_service = sync_service; self.offline_queue = offline_queue
        self._on_kiosk_return = on_kiosk_return
        self.kiosk_window = None
        data = AdminDataService(db)
        site = data.settings().get('site_name', 'Company')
        self.setWindowTitle(f'Attendance Control v{APP_VERSION} — {site}')
        self.resize(1380, 840)

        central = QWidget(); self.setCentralWidget(central)
        outer = QHBoxLayout(central); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        # -- left navigation ---------------------------------------------------
        self.nav = QWidget(); self.nav.setObjectName('nav'); self.nav.setStyleSheet('#nav{background:#10151a}')
        self.nav.setFixedWidth(215)
        nav_layout = QVBoxLayout(self.nav); nav_layout.setContentsMargins(8, 10, 8, 10); nav_layout.setSpacing(3)
        brand = QLabel('ATTENDANCE\nCONTROL'); brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet('font-size:16px;font-weight:bold;color:#55a9d8;padding:10px 10px 0 10px')
        nav_layout.addWidget(brand)
        version = QLabel(f'v{APP_VERSION}', alignment=Qt.AlignCenter)
        version.setStyleSheet('color:#7d93a6;font-size:11px;padding:0 10px 8px 10px')
        nav_layout.addWidget(version)
        nav_scroll = QScrollArea(); nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.NoFrame)
        nav_scroll.setStyleSheet('QScrollArea{background:transparent} QScrollArea > QWidget > QWidget{background:transparent}')
        nav_content = QWidget(); self.nav_buttons_layout = QVBoxLayout(nav_content)
        self.nav_buttons_layout.setContentsMargins(0, 0, 0, 0); self.nav_buttons_layout.setSpacing(3)
        nav_layout.addWidget(nav_scroll, 1)
        nav_scroll.setWidget(nav_content)

        # -- pages -------------------------------------------------------------
        self.pages = QStackedWidget()
        log_path = Path('logs/application.log')
        def scan_rows(q):
            return [(x.timestamp, f'{e.first_name} {e.last_name}' if e else x.employee_id or 'Unknown', x.action,
                     x.terminal_id, x.scanner_id, 'YES' if x.accepted else 'NO', x.rejection_reason)
                    for x, e in data.scans() if q in str(x.employee_id).lower()]
        def exception_rows(q):
            return [(x.timestamp, x.employee_id, x.problem, x.terminal_id, x.scanner_id, x.details)
                    for x in data.exceptions() if q in ' '.join([str(x.employee_id or ''), x.problem, x.details or '']).lower()]
        def log_rows(q):
            if not log_path.exists(): return []
            return [(line,) for line in log_path.read_text(errors='replace').splitlines()[-500:] if q in line.lower()]

        self.kiosk_page = Kiosk(engine, scanner_manager)
        definitions = [
            ('Dashboard', DashboardPage(db)),
            ('Employees', EmployeesPage(db)),
            ('Shifts', ShiftsPage(db)),
            ('Attendance', AttendancePage(db)),
            ('Live Scans', TablePage('Live Scans', ['Timestamp', 'Employee', 'Action', 'Terminal', 'Scanner', 'Accepted', 'Reason'], scan_rows, refresh=3000)),
            ('Exceptions', TablePage('Exceptions', ['Timestamp', 'Employee', 'Problem', 'Terminal', 'Scanner', 'Details'], exception_rows)),
            ('Terminals & Scanners', HardwarePage(db, engine, scanner_manager)),
            ('Reports', ReportsPage(db)),
            ('Excel Export', ExcelExportPage(db)),
            ('Automatic Exports', ExportJobsPage(db)),
            ('Settings', SettingsPage(db, self.username)),
            ('System Logs', TablePage('System Logs', ['Entry'], log_rows)),
            ('Backup / Restore', BackupPage(db)),
            ('Synchronization', SyncPage(db, sync_service, offline_queue)),
            ('About & License', AboutPage()),
            ('Kiosk', self.kiosk_page),
        ]
        self.page_widgets = {}
        self.nav_buttons = []
        for label, page in definitions:
            index = self.pages.addWidget(page)
            self.page_widgets[label] = page
            button = QPushButton(label); button.setCheckable(True)
            button.setIcon(icon_pixmap(ICON_MAP.get(label, 'SP_FileIcon')))
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda checked=False, i=index: self.pages.setCurrentIndex(i))
            self.nav_buttons_layout.addWidget(button)
            self.nav_buttons.append(button)
        self.nav_buttons_layout.addStretch()
        outer.addWidget(self.nav)
        outer.addWidget(self.pages, 1)

        self.nav_buttons[0].setChecked(True)
        self.pages.currentChanged.connect(self._sync_nav)

        # -- menu / session ----------------------------------------------------
        session_menu = self.menuBar().addMenu('Session')
        kiosk_action = QAction('Enter Kiosk Mode (full screen)', self); kiosk_action.triggered.connect(self.enter_kiosk)
        lock_action = QAction('Lock / Return to Kiosk', self); lock_action.triggered.connect(self.return_to_kiosk)
        logout_action = QAction('Log Out / Switch User…', self); logout_action.triggered.connect(self.logout)
        exit_action = QAction('Exit', self); exit_action.triggered.connect(self._exit_app)
        about_action = QAction('About Attendance Control', self); about_action.triggered.connect(self.show_about)
        session_menu.addAction(kiosk_action); session_menu.addAction(lock_action)
        session_menu.addAction(logout_action); session_menu.addSeparator()
        session_menu.addAction(about_action); session_menu.addSeparator(); session_menu.addAction(exit_action)
        self._build_session_toolbar()
        self._update_session_label()
        localize_window(self)
        self._update_session_label()
        self.statusBar().addPermanentWidget(QLabel(f'v{APP_VERSION}'))
        self.statusBar().addPermanentWidget(QLabel('© 2026 Csepregi Artur'))

    def _build_session_toolbar(self):
        """Always-visible controls: current administrator, log out to kiosk, close the app."""
        toolbar = QToolBar('Session controls', self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setStyleSheet('QToolBar{background:#1c242d;border-bottom:1px solid #2e3c4a;padding:4px 6px}')
        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        self.session_label = QLabel('')
        self.session_label.setStyleSheet('color:#9fb3c4;padding:0 8px')
        toolbar.addWidget(self.session_label)
        toolbar.addSeparator()
        lock = QAction('Log out → Kiosk', self)
        lock.setIcon(icon_pixmap('SP_ArrowBack'))
        lock.setToolTip('Return to the kiosk screen (administrator login required to come back)')
        lock.triggered.connect(self.return_to_kiosk)
        close = QAction('Close App', self)
        close.setIcon(icon_pixmap('SP_DialogCloseButton'))
        close.setToolTip('Exit Attendance Control')
        close.triggered.connect(self._exit_app)
        toolbar.addAction(lock)
        toolbar.addAction(close)
        self.addToolBar(toolbar)

    def _update_session_label(self):
        text = self.username or t('not logged in')
        self.statusBar().showMessage(t('Session: ') + text)
        if hasattr(self, 'session_label') and self.session_label is not None:
            self.session_label.setText(t('Administrator: ') + text)

    def _sync_nav(self, index):
        for position, button in enumerate(self.nav_buttons):
            button.setChecked(position == index)

    def enter_kiosk(self):
        if self.kiosk_window is None:
            self.kiosk_window = KioskWindow(self.engine, self.scanner_manager, self)
        self.kiosk_window.showFullScreen()

    def logout(self):
        dialog = AdminLoginDialog(self.db)
        if dialog.exec():
            self.username = dialog.username.text().strip()
            self._update_session_label()
            QMessageBox.information(self, 'Session', f'Logged in as {self.username}')
        elif self._on_kiosk_return is not None:
            self.return_to_kiosk()
        else:
            self.close()

    def return_to_kiosk(self):
        """Lock the admin window and hand control back to the startup kiosk."""
        if self._on_kiosk_return is None:
            self._exit_app(); return
        callback = self._on_kiosk_return
        self._on_kiosk_return = None
        QTimer.singleShot(0, callback)
        self.close()

    def show_about(self):
        from app import APP_NAME, OWNER, CONTACT_URL, LICENSE
        html = (f'<h3>{APP_NAME} v{APP_VERSION}</h3>'
                f'<p>Licensed to <b>{OWNER}</b></p>'
                f'<p>{LICENSE}</p>'
                f'<p>Contact: <a href="{CONTACT_URL}">{CONTACT_URL}</a></p>')
        box = QMessageBox(self)
        box.setWindowTitle(t('About Attendance Control'))
        box.setIcon(QMessageBox.Information)
        box.setTextFormat(Qt.RichText)
        box.setText(html)
        box.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        box.exec()

    def _exit_app(self):
        """Quit the whole application (used by Session > Exit)."""
        self._on_kiosk_return = None
        QApplication.instance().closeAllWindows()

    def closeEvent(self, event):
        """When managed by the startup kiosk, closing the admin returns to the kiosk."""
        if self._on_kiosk_return is not None:
            callback = self._on_kiosk_return
            self._on_kiosk_return = None
            event.accept()
            QTimer.singleShot(0, callback)
        else:
            event.accept()
