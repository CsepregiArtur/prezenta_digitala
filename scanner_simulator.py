#!/usr/bin/env python3
"""Honeywell Scanner Simulator for Attendance Control.

Run this on its own (before or while Attendance Control is open). It creates a
*virtual serial port* and lets you type a barcode or press buttons to send a scan
line — exactly like a Honeywell scanner in USB Serial / COM mode (9600 baud,
line terminated with CR + LF).

How to use
----------
1. Run:  python3 scanner_simulator.py
2. Click “Create virtual serial port”; note the device path shown (e.g.
   /dev/ttys005 on macOS/Linux).
3. In Attendance Control → Terminals & Scanners → Add Scanner:
   COM port = that path, Enabled = Yes. The app reconnects automatically.
4. Back here, pick an employee (or type a barcode) and press Enter / “Scan now”.
   The kiosk / live-scans screen in Attendance Control reacts to each scan.

On Windows there is no built-in virtual port; install a com0com-style driver and
type the sender side (e.g. CNCA) as the output COM port.

This file never touches the attendance database — it only writes to a serial port.
"""

import errno
import os
import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QGroupBox, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

DARK = '''
QWidget{background:#14191f;color:#e8edf2;font-family:Segoe UI;font-size:13px}
QGroupBox{border:1px solid #34414d;border-radius:6px;margin-top:12px;font-weight:bold}
QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;color:#8fb6d6}
QPushButton{background:#2374ab;padding:8px 14px;border-radius:5px;border:none}
QPushButton:hover{background:#318bc4}
QPushButton:disabled{background:#2a3440;color:#77848f}
QLineEdit,QComboBox,QPlainTextEdit,QSpinBox{background:#222d36;border:1px solid #425464;padding:6px;border-radius:4px}
QPlainTextEdit{font-family:Menlo,Consolas,monospace}
'''


class SerialPortSource:
    """Small abstraction over the virtual serial port the scanner data is sent to."""

    def __init__(self):
        self.master = None          # POSIX pty master file descriptor (we write to it)
        self.slave = None           # POSIX pty slave fd kept open so writes never fail
        self.device = None          # POSIX slave path, e.g. /dev/ttys005
        self.windows_port = ''      # Windows/com0com sender COM

    @property
    def ready(self) -> bool:
        if os.name == 'posix':
            return self.master is not None
        return bool(self.windows_port)

    def device_name(self) -> str:
        return self.device or self.windows_port or ''

    def create_virtual_port(self) -> str:
        """Create a virtual serial pair and return the path to configure as the scanner's COM port."""
        if os.name == 'posix':
            import pty
            try:
                master, slave = pty.openpty()
            except OSError as error:
                raise RuntimeError(f'Could not create a virtual serial port: {error}') from error
            self.close()
            self.master = master
            # Keep the slave open ourselves. Writing to a pty master whose slave
            # side is closed raises OSError [Errno 5] (input/output error), so this
            # guarantees the simulator can send even before the app connects — the
            # bytes are simply buffered until Attendance Control opens the port.
            self.slave = slave
            self.device = os.ttyname(slave)
            # Never block the UI: if the app is not reading fast enough we raise a
            # clear message instead of freezing (or worse) on a full kernel buffer.
            try:
                import fcntl
                flags = fcntl.fcntl(master, fcntl.F_GETFL)
                fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            except Exception:
                pass
            return self.device
        raise RuntimeError('On Windows, create a com0com-style pair and type the sender COM (e.g. CNCA) as the output port.')

    def send(self, text: str) -> None:
        line = (str(text).strip() + '\r\n').encode('ascii', 'replace')
        if os.name == 'posix' and self.master is not None:
            try:
                os.write(self.master, line)
            except OSError as error:
                if getattr(error, 'errno', None) in (errno.EAGAIN, errno.EWOULDBLOCK):
                    raise RuntimeError(
                        'The virtual port buffer is full — Attendance Control is not reading from it. '
                        'Make sure a scanner with COM port ' + (self.device or '?') +
                        ' is enabled and shows “Connected”, or pause Auto-demo.'
                    ) from error
                raise RuntimeError(
                    'Could not write to the virtual port. Make sure Attendance Control has an '
                    'enabled scanner with COM port ' + (self.device or '?') +
                    ' and that its status shows “Connected”. (details: ' + str(error) + ')'
                ) from error
        elif os.name == 'nt' and self.windows_port:
            import serial
            with serial.Serial(self.windows_port, 9600, timeout=1) as port:
                port.write(line)
        else:
            raise RuntimeError('No virtual serial port is ready. Create one (or set an output COM on Windows) first.')

    def close(self) -> None:
        for descriptor in (self.slave, self.master):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        self.slave = None
        self.master = None


class SimulatorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.ports = []                 # list of {'name': str, 'source': SerialPortSource}
        self._outbox = []               # paced send queue of (SerialPortSource, payload)
        self._scanner_counter = 0
        self.auto_timer = QTimer(self); self.auto_timer.timeout.connect(self._send_auto)
        self.queue_timer = QTimer(self); self.queue_timer.timeout.connect(self._drain)
        self.setWindowTitle('Honeywell Scanner Simulator — Attendance Control')
        self.resize(740, 780)
        self._build_ui()
        self._load_employees()
        # Convenience: create the first virtual scanner cable right away on POSIX.
        if os.name == 'posix':
            self._add_scanner()

    # -- UI -----------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel('Simulates one or more Honeywell scanners, each over its own virtual serial '
                       'port. In Attendance Control add one scanner per port; several scanners can '
                       'share the same terminal.')
        intro.setWordWrap(True); intro.setStyleSheet('color:#9fb3c4')
        layout.addWidget(intro)

        # 1. Scanners (virtual cables) ----------------------------------------
        group = QGroupBox('1 · Scanners (virtual cables)')
        box = QVBoxLayout(group)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Scanner', 'COM / device path', 'Status'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet(
            'QTableWidget{background:#1c242d;gridline-color:#34414d;border-radius:4px} '
            'QHeaderView::section{background:#263542;padding:6px;border:0}')
        box.addWidget(self.table)
        row = QHBoxLayout()
        add_btn = QPushButton('+ Add scanner port')
        add_btn.setStyleSheet('QPushButton{background:#1f7a45} QPushButton:hover{background:#2a9a58}')
        add_btn.clicked.connect(self._add_scanner)
        remove_btn = QPushButton('Remove selected')
        remove_btn.setStyleSheet('QPushButton{background:#8a2f2f} QPushButton:hover{background:#b03a3a}')
        remove_btn.clicked.connect(self._remove_scanner)
        copy_btn = QPushButton('Copy path'); copy_btn.clicked.connect(self._copy_path)
        row.addWidget(add_btn); row.addWidget(remove_btn); row.addWidget(copy_btn); row.addStretch()
        box.addLayout(row)
        hint = QLabel('One port per scanner. In Attendance Control → Terminals & Scanners add a scanner '
                      'for every path below (use the same Terminal to attach several scanners to it) with '
                      'Enabled = Yes. The app reconnects automatically.')
        hint.setWordWrap(True); hint.setStyleSheet('color:#9fb3c4')
        box.addWidget(hint)
        layout.addWidget(group)

        # 2. Send a scan -------------------------------------------------------
        group = QGroupBox('2 · Send a scan')
        box = QVBoxLayout(group)
        send_row = QHBoxLayout()
        send_row.addWidget(QLabel('Via:'))
        self.scanner_combo = QComboBox()
        send_row.addWidget(self.scanner_combo)
        send_row.addWidget(QLabel('Barcode:'))
        self.combo = QComboBox(); self.combo.setEditable(True); self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.lineEdit().returnPressed.connect(self._send_selected)
        send_row.addWidget(self.combo, 1)
        self.send_btn = QPushButton('Scan now')
        self.send_btn.setStyleSheet('QPushButton{background:#1f7a45;padding:9px 18px} QPushButton:hover{background:#2a9a58}')
        self.send_btn.clicked.connect(self._send_selected)
        send_row.addWidget(self.send_btn)
        box.addLayout(send_row)
        quick = QLabel('Quick buttons (first employees) — or type any barcode above and press Enter:')
        quick.setStyleSheet('color:#9fb3c4')
        box.addWidget(quick)
        self.quick_row = QHBoxLayout()
        box.addLayout(self.quick_row)
        auto = QHBoxLayout()
        auto.addWidget(QLabel('Auto-demo:'))
        self.auto_check = QCheckBox('Repeat every')
        self.auto_interval = QSpinBox(); self.auto_interval.setRange(1, 60); self.auto_interval.setValue(3)
        self.auto_interval.setSuffix(' s'); self.auto_interval.valueChanged.connect(self._auto_changed)
        auto.addWidget(self.auto_check); auto.addWidget(self.auto_interval); auto.addStretch()
        box.addLayout(auto)
        layout.addWidget(group)

        # 3. Batch / multiple scans ---------------------------------------------
        group = QGroupBox('3 · Batch: many scans with one click')
        box = QVBoxLayout(group)
        box.addWidget(QLabel('Scan list — one barcode per line (sent in order):'))
        self.list_edit = QPlainTextEdit(); self.list_edit.setFixedHeight(90)
        self.list_edit.setPlaceholderText('EMP000001\nEMP000002\nEMP000003\nEMP000004')
        box.addWidget(self.list_edit)
        row = QHBoxLayout()
        row.addWidget(QLabel('Delay between scans:'))
        self.delay = QSpinBox(); self.delay.setRange(20, 5000); self.delay.setSingleStep(50)
        self.delay.setValue(300); self.delay.setSuffix(' ms')
        row.addWidget(self.delay)
        self.spread = QCheckBox('Spread across scanners')
        row.addWidget(self.spread); row.addStretch()
        box.addLayout(row)
        row2 = QHBoxLayout()
        send_list = QPushButton('Send list (one click)')
        send_list.clicked.connect(self._send_list)
        row2.addWidget(send_list)
        row2.addWidget(QLabel('Repeat selected:'))
        self.repeat = QSpinBox(); self.repeat.setRange(1, 500); self.repeat.setValue(5)
        row2.addWidget(self.repeat)
        repeat_btn = QPushButton('times'); repeat_btn.clicked.connect(self._send_repeat)
        row2.addWidget(repeat_btn); row2.addStretch()
        box.addLayout(row2)
        note = QLabel('Tip: to simulate a real line of employees, put different barcodes in the list. '
                      'The same barcode more than once within ~5 s is rejected as a duplicate by Attendance Control.')
        note.setWordWrap(True); note.setStyleSheet('color:#9fb3c4')
        box.addWidget(note)
        layout.addWidget(group)

        # 4. Activity ----------------------------------------------------------
        group = QGroupBox('4 · Activity')
        box = QVBoxLayout(group)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setPlaceholderText('Sent scan lines will appear here…')
        box.addWidget(self.log)
        layout.addWidget(group, 1)

        footer = QLabel('Sent as: <barcode> + CR + LF · 9600 baud · this file only writes to virtual serial ports.')
        footer.setStyleSheet('color:#9fb3c4')
        layout.addWidget(footer)

    def _load_employees(self):
        items = []
        database = Path('attendance.db')
        if database.exists():
            try:
                connection = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
                try:
                    for employee_id, first, last in connection.execute(
                            'SELECT employee_id, first_name, last_name FROM employees ORDER BY employee_id'):
                        items.append(f'{employee_id} · {first} {last}')
                finally:
                    connection.close()
            except Exception:
                pass
        if not items:
            items = ['EMP000001 · Sample employee 1', 'EMP000002 · Sample employee 2',
                     'EMP000003 · Sample employee 3', 'EMP000004 · Sample employee 4']
        self._employee_payloads = [item.split(' · ')[0] for item in items]
        self.combo.addItems(items)
        self.combo.setCurrentIndex(0)
        self.list_edit.setPlainText('\n'.join(self._employee_payloads[:4]))
        for item in items[:6]:
            payload = item.split(' · ')[0]
            button = QPushButton(payload)
            button.clicked.connect(lambda checked=False, value=payload: self._send_single(value))
            self.quick_row.addWidget(button)
        self.quick_row.addStretch()

    # -- scanner ports ----------------------------------------------------------
    def _add_scanner(self):
        self._scanner_counter += 1
        name = f'Scanner {self._scanner_counter}'
        source = SerialPortSource()
        if os.name == 'posix':
            try:
                device = source.create_virtual_port()
            except Exception as error:
                self._scanner_counter -= 1
                QMessageBox.warning(self, 'Add scanner port', str(error)); return
        else:
            com, ok = QInputDialog.getText(self, 'Add scanner port',
                                           f'com0com sender COM for {name} (e.g. CNCA):')
            if not ok or not com.strip():
                self._scanner_counter -= 1; return
            source.windows_port = com.strip(); source.device = com.strip()
        self.ports.append({'name': name, 'source': source})
        self._sync_scanners()
        self._log(f'{name} ready → {source.device_name()}')
        self.table.selectRow(len(self.ports) - 1)

    def _remove_scanner(self):
        row = self.table.currentRow()
        if not (0 <= row < len(self.ports)):
            QMessageBox.information(self, 'Remove scanner', 'Select a scanner row to remove first.')
            return
        port = self.ports.pop(row)
        port['source'].close()
        self._sync_scanners()
        self._log(f'Removed {port["name"]} ({port["source"].device_name()})')

    def _sync_scanners(self):
        self.table.setRowCount(len(self.ports))
        self.scanner_combo.clear()
        for index, port in enumerate(self.ports):
            source = port['source']
            device = source.device_name()
            self.scanner_combo.addItem(f'{port["name"]}  ({device})', index)
            items = [QTableWidgetItem(port['name']), QTableWidgetItem(device),
                     QTableWidgetItem('Ready' if source.ready else 'Not configured')]
            for column, item in enumerate(items):
                self.table.setItem(index, column, item)
        if self.ports:
            self.table.selectRow(len(self.ports) - 1)
            self.scanner_combo.setCurrentIndex(len(self.ports) - 1)

    def _selected_source(self):
        index = self.scanner_combo.currentIndex()
        if 0 <= index < len(self.ports):
            return self.ports[index]['source']
        return None

    def _sources(self):
        return [port['source'] for port in self.ports if port['source'].ready]

    def _copy_path(self):
        source = self._selected_source()
        if source and source.device_name():
            QApplication.clipboard().setText(source.device_name())

    # -- sending ----------------------------------------------------------------
    @staticmethod
    def _payload(raw):
        raw = (raw or '').strip()
        return raw.split(' · ')[0].strip() if ' · ' in raw else raw

    def _enqueue(self, source, payload):
        self._outbox.append((source, payload))
        if not self.queue_timer.isActive():
            self.queue_timer.start(max(20, self.delay.value()))

    def _drain(self):
        if not self._outbox:
            self.queue_timer.stop(); return
        source, payload = self._outbox.pop(0)
        try:
            source.send(payload)
            self._log(f'SENT  [{source.device_name()}]  {payload}')
        except Exception as error:
            self._log(f'ERROR {error}')
            self._outbox.clear(); self.queue_timer.stop()
            QMessageBox.warning(self, 'Scanner simulator', str(error))
        if not self._outbox:
            self.queue_timer.stop()

    def _send_single(self, raw):
        payload = self._payload(raw)
        if not payload:
            return
        source = self._selected_source()
        if source is None or not source.ready:
            QMessageBox.warning(self, 'Scanner simulator',
                                'No virtual scanner is ready.\n\nClick “+ Add scanner port” first, then add '
                                'that COM port to a scanner in Attendance Control.')
            return
        self._enqueue(source, payload)

    def _send_selected(self):
        self._send_single(self.combo.currentText())

    def _send_auto(self):
        import random
        if self._employee_payloads:
            payload = random.choice(self._employee_payloads)
            self._send_single(payload)

    def _auto_changed(self):
        if self.auto_check.isChecked():
            self.auto_timer.start(max(1000, self.auto_interval.value() * 1000))
        else:
            self.auto_timer.stop()

    def _send_list(self):
        lines = [line.strip() for line in self.list_edit.toPlainText().splitlines() if line.strip()]
        sources = self._sources()
        if not lines:
            QMessageBox.information(self, 'Send list', 'Add at least one barcode to the list.'); return
        if not sources:
            QMessageBox.warning(self, 'Send list', 'No virtual scanner is ready. Add a scanner port first.'); return
        selected = self.scanner_combo.currentIndex()
        queued = 0
        for i, raw in enumerate(lines):
            payload = self._payload(raw)
            if not payload: continue
            source = sources[i % len(sources)] if self.spread.isChecked() else sources[selected if 0 <= selected < len(sources) else 0]
            self._enqueue(source, payload); queued += 1
        self._log(f'Queued {queued} scan(s) from the list')

    def _send_repeat(self):
        payload = self._payload(self.combo.currentText())
        if not payload:
            QMessageBox.information(self, 'Repeat', 'Choose or type a barcode first.'); return
        source = self._selected_source()
        if source is None or not source.ready:
            QMessageBox.warning(self, 'Repeat', 'No virtual scanner is ready. Add a scanner port first.'); return
        count = self.repeat.value()
        for _ in range(count):
            self._enqueue(source, payload)
        self._log(f'Queued {count} × {payload}')

    # -- misc -------------------------------------------------------------------
    def _log(self, message):
        self.log.appendPlainText(message)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def closeEvent(self, event):
        self.auto_timer.stop(); self.queue_timer.stop()
        for port in self.ports:
            port['source'].close()
        event.accept()


def main():
    import traceback

    def _excepthook(exc_type, exc_value, exc_traceback):
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        print('\nThe simulator stopped with an error (see traceback above).')
        try:
            input('Press Enter to close…')
        except EOFError:
            pass
    sys.excepthook = _excepthook

    app = QApplication(sys.argv)
    app.setApplicationName('Honeywell Scanner Simulator')
    app.setStyleSheet(DARK)
    window = SimulatorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
