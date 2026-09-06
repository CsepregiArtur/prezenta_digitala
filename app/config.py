from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = {"site_name": "Company", "timezone": "Europe/Bucharest", "duplicate_scan_seconds": 5,
           "ui_theme": "dark", "default_export_directory": "exports"}

def app_dir() -> Path:
    """Writable base directory: next to the packaged executable, else the project root."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return ROOT

def load_config(path: Path | None = None) -> dict:
    path = path or ROOT / "config.json"
    if not path.exists():
        path.write_text(json.dumps(DEFAULT, indent=2), encoding="utf-8")
    return DEFAULT | json.loads(path.read_text(encoding="utf-8"))
