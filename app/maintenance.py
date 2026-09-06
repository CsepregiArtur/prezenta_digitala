from pathlib import Path
from datetime import datetime
import shutil
def backup_database(db_path='attendance.db', directory='backup'):
    source=Path(db_path); target=Path(directory); target.mkdir(parents=True,exist_ok=True)
    destination=target/f'attendance_{datetime.now():%Y%m%d_%H%M%S}.db'; shutil.copy2(source,destination); return destination
def restore_database(backup_path, db_path='attendance.db'):
    current=backup_database(db_path); shutil.copy2(backup_path,db_path); return current
