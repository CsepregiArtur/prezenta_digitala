"""Threaded, focus-independent COM scanner integration with live status."""
from __future__ import annotations
import logging
import threading
import time
from datetime import datetime

class ScannerManager:
    """Owns one listener thread per enabled scanner.

    Threads are daemonic and reconnect every few seconds while offline. Connection
    health is exposed through :attr:`status` so the UI can render live state.
    """
    def __init__(self, engine, offline_queue=None):
        self.engine = engine; self.offline_queue = offline_queue
        self.scanners = []; self.running = False; self.threads = []
        self.log = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self.status = {}         # scanner_id -> connecting | connected | offline
        self.last_seen = {}      # scanner_id -> datetime
        self.last_result = None
        self.last_result_time = None

    def configure(self, scanners):
        self.scanners = list(scanners); return self

    def start(self):
        if self.running: return
        self.running = True
        for scanner in self.scanners:
            if scanner.enabled: self._spawn(scanner)

    def stop(self):
        self.running = False
        self.threads.clear()

    def reload(self, scanners=None):
        """Pick up configuration changes without restarting the process."""
        if scanners is not None: self.scanners = list(scanners)
        self.stop(); self.start()

    def _spawn(self, scanner):
        self._set(scanner.scanner_id, 'connecting')
        thread = threading.Thread(target=self._listen, args=(scanner,), daemon=True)
        self.threads.append(thread); thread.start()

    def _set(self, scanner_id, value):
        with self._lock:
            self.status[scanner_id] = value
            if value == 'connected': self.last_seen[scanner_id] = datetime.now()

    def status_of(self, scanner_id):
        return self.status.get(scanner_id, 'stopped')

    def _listen(self, scanner):
        try:
            import serial
        except ImportError:
            self.log.error('pyserial is not installed; scanner %s cannot connect', scanner.scanner_id)
            self._set(scanner.scanner_id, 'offline'); return
        while self.running:
            try:
                with serial.Serial(scanner.com_port, scanner.baud_rate, timeout=1) as port:
                    self.log.info('Scanner %s connected on %s', scanner.scanner_id, scanner.com_port)
                    self._set(scanner.scanner_id, 'connected')
                    while self.running:
                        raw = port.readline().decode(errors='replace').strip()
                        if not raw: continue
                        from app.attendance import ScannerEvent
                        event = ScannerEvent(raw, datetime.now(), scanner.terminal_id, scanner.scanner_id)
                        try:
                            result = self.engine.process(event)
                            self._remember(result)
                            if self.offline_queue: self.offline_queue.synchronize(self.engine)
                        except Exception as error:
                            self.log.exception('Scan persistence failed: %s', error)
                            if self.offline_queue: self.offline_queue.enqueue(event)
            except Exception as error:
                self._set(scanner.scanner_id, 'offline')
                self.log.warning('Scanner %s offline: %s', scanner.scanner_id, error)
                time.sleep(5)

    def publish(self, result):
        """Expose the most recent processed scan to any watching kiosk."""
        with self._lock:
            self.last_result = result
            self.last_result_time = datetime.now()

    def _remember(self, result):
        self.publish(result)
