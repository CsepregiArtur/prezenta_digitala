"""LAN / server synchronization.

Two complementary mechanisms:

* Offline replay — events that could not be persisted locally (kept in the
  durable :class:`app.offline.OfflineQueue`) are replayed through the local
  engine, in arrival order, once the store is reachable again.
* Server push — every locally recorded scan event whose id is above the last
  acknowledged marker is POSTed as JSON to a configured server endpoint, so a
  central installation can accumulate activity from several kiosks.

Configuration is stored in the ``application_settings`` table:
``sync_enabled``, ``sync_server_url``, ``sync_token``,
``sync_interval_minutes``.  The push marker is ``sync_last_scan_id``.
"""
from __future__ import annotations
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from sqlalchemy import select
from app.database.models import ApplicationSetting, ScanEvent

log = logging.getLogger(__name__)
DEFAULT_INTERVAL_MINUTES = 5


class SyncService:
    def __init__(self, db, engine=None, offline_queue=None):
        self.db = db
        self.engine = engine
        self.offline_queue = offline_queue
        self._last_attempt = None
        self._last_status = 'Not synchronised yet'

    # -- settings ---------------------------------------------------------
    def settings(self):
        from app.services import AdminDataService
        values = AdminDataService(self.db).settings()
        return {
            'sync_enabled': str(values.get('sync_enabled', 'false')).lower() in ('1', 'true', 'yes'),
            'sync_server_url': values.get('sync_server_url', ''),
            'sync_token': values.get('sync_token', ''),
            'sync_interval_minutes': int(values.get('sync_interval_minutes', DEFAULT_INTERVAL_MINUTES) or DEFAULT_INTERVAL_MINUTES),
        }

    def save_settings(self, enabled, server_url, token, interval_minutes):
        from app.services import AdminDataService
        service = AdminDataService(self.db)
        service.set_setting('sync_enabled', 'true' if enabled else 'false')
        service.set_setting('sync_server_url', (server_url or '').strip())
        service.set_setting('sync_token', (token or '').strip())
        service.set_setting('sync_interval_minutes', str(int(interval_minutes)))
        log.info('Synchronization settings saved (enabled=%s)', enabled)

    def last_status(self): return self._last_status

    # -- offline drain ------------------------------------------------------
    def drain_offline(self) -> tuple[int, int]:
        """Replay locally queued events into the engine. Returns (done, failed)."""
        if not self.offline_queue or not self.engine:
            return (0, 0)
        done, failed = self.offline_queue.synchronize(self.engine)
        if done or failed:
            log.info('Offline queue drained: %d done, %d failed', done, failed)
        return (done, failed)

    # -- server push ---------------------------------------------------------
    def push_pending(self, server_url: str | None = None, token: str | None = None) -> int:
        """POST unsynchronised scan events to the server. Returns events pushed."""
        settings = self.settings()
        url = (server_url or settings['sync_server_url']).strip()
        if not url:
            self._last_status = 'No server URL configured'
            return 0
        auth = token if token is not None else settings['sync_token']
        with self.db.session() as s:
            marker = s.get(ApplicationSetting, 'sync_last_scan_id')
            last_id = int(marker.value) if marker and marker.value else 0
            events = list(s.scalars(select(ScanEvent).where(ScanEvent.id > last_id).order_by(ScanEvent.id)))
            if not events:
                self._last_status = 'No new events to send'
                return 0
            payload = [{
                'id': e.id,
                'timestamp': e.timestamp.isoformat(),
                'employee_id': e.employee_id,
                'action': e.action,
                'terminal_id': e.terminal_id,
                'scanner_id': e.scanner_id,
                'raw_barcode': e.raw_barcode,
                'accepted': e.accepted,
                'rejection_reason': e.rejection_reason,
                'shift_id': e.shift_id,
            } for e in events]
            body = json.dumps({'source': 'attendance-control', 'events': payload}).encode('utf-8')
            request = urllib.request.Request(url, data=body, method='POST')
            request.add_header('Content-Type', 'application/json')
            if auth:
                request.add_header('Authorization', f'Bearer {auth}')
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    if 200 <= response.status < 300:
                        marker = s.get(ApplicationSetting, 'sync_last_scan_id')
                        if marker: marker.value = str(events[-1].id)
                        else: s.add(ApplicationSetting(key='sync_last_scan_id', value=str(events[-1].id)))
                        s.commit()
                        self._last_status = f'Pushed {len(events)} event(s)'
                        log.info('Pushed %d events to %s', len(events), url)
                        return len(events)
                    self._last_status = f'Server rejected push (HTTP {response.status})'
                    return 0
            except (urllib.error.URLError, OSError) as error:
                self._last_status = f'Sync failed: {error}'
                log.warning('Server push failed: %s', error)
                return 0

    def test_connection(self, url: str | None = None, token: str | None = None):
        """Probe the server endpoint with an empty payload. Returns (ok, message)."""
        settings = self.settings()
        url = (url or settings['sync_server_url']).strip()
        if not url: return False, 'No server URL configured'
        auth = token if token is not None else settings['sync_token']
        try:
            body = json.dumps({'source': 'attendance-control', 'events': []}).encode('utf-8')
            request = urllib.request.Request(url, data=body, method='POST')
            request.add_header('Content-Type', 'application/json')
            if auth: request.add_header('Authorization', f'Bearer {auth}')
            with urllib.request.urlopen(request, timeout=10) as response:
                return (200 <= response.status < 300), f'Connection OK (HTTP {response.status})'
        except (urllib.error.URLError, OSError) as error:
            return False, f'Connection failed: {error}'

    # -- combined -------------------------------------------------------------
    def synchronize_now(self) -> str:
        """Local offline drain followed by a server push. Returns a status line."""
        self.drain_offline()
        pushed = self.push_pending()
        self._last_attempt = datetime.now()
        summary = self._last_status
        if self.offline_queue:
            remaining = self.offline_queue.count()
            if remaining:
                summary += f' | {remaining} event(s) still queued offline'
        return summary

    def tick(self):
        """Called periodically from the UI thread; runs the sync when enabled."""
        settings = self.settings()
        if not settings['sync_enabled']:
            return
        interval = max(1, settings['sync_interval_minutes'])
        if self._last_attempt is None or (datetime.now() - self._last_attempt).total_seconds() >= interval * 60:
            self.synchronize_now()
