"""Durable local fallback queue for scanner events when the primary store is unavailable."""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from app.attendance import ScannerEvent

class OfflineQueue:
    def __init__(self, path: str | Path='data/offline_queue.db'):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db: db.execute('CREATE TABLE IF NOT EXISTS queued_scans (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)')
    def _connect(self): return sqlite3.connect(self.path)
    def enqueue(self,event: ScannerEvent):
        payload=json.dumps({'barcode':event.barcode,'timestamp':event.timestamp.isoformat(),'terminal_id':event.terminal_id,'scanner_id':event.scanner_id})
        with self._connect() as db: db.execute('INSERT INTO queued_scans(payload,created_at) VALUES (?,?)',(payload,datetime.now().isoformat()))
    def count(self):
        with self._connect() as db:return db.execute('SELECT COUNT(*) FROM queued_scans').fetchone()[0]
    def synchronize(self, engine) -> tuple[int,int]:
        """Replay in arrival order. Failed records remain durable for a later attempt."""
        completed=failed=0
        with self._connect() as db:
            rows=list(db.execute('SELECT id,payload FROM queued_scans ORDER BY id'))
            for row_id,payload in rows:
                value=json.loads(payload)
                try:
                    engine.process(ScannerEvent(value['barcode'],datetime.fromisoformat(value['timestamp']),value['terminal_id'],value['scanner_id']))
                    db.execute('DELETE FROM queued_scans WHERE id=?',(row_id,));completed+=1
                except Exception: failed+=1
        return completed,failed
