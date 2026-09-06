import logging
from pathlib import Path
from .config import ROOT

def configure_logging() -> logging.Logger:
    folder = ROOT / "logs"; folder.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(folder / "application.log", encoding="utf-8"), logging.StreamHandler()])
    return logging.getLogger("attendance_control")
