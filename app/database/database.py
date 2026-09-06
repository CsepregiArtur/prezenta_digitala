from __future__ import annotations
from pathlib import Path
from sqlalchemy import create_engine, event, select, func, text
from sqlalchemy.orm import Session, sessionmaker
from .models import Base, Employee, Terminal

class Database:
    def __init__(self, path: str | Path = 'attendance.db'):
        self.path=Path(path); self.engine=create_engine(f'sqlite:///{self.path}', connect_args={'check_same_thread':False})
        @event.listens_for(self.engine, 'connect')
        def fk(conn, _): conn.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine); self._migrate(); self.Session=sessionmaker(self.engine, expire_on_commit=False)
    def _migrate(self):
        """Add columns introduced after a database already exists (idempotent)."""
        for table, column, ddl in [('export_jobs','weekday','INTEGER'),('export_jobs','month_day','INTEGER'),
                                   ('employees','rotation_id','INTEGER'),('employees','rotation_start','DATE'),
                                   ('employees','rotation_start_shift_id','INTEGER')]:
            try:
                with self.engine.begin() as conn: conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}'))
            except Exception: pass
    def session(self): return self.Session()
    def next_employee_id(self, session: Session) -> str:
        last=session.scalar(select(func.max(Employee.employee_id)))
        return f'EMP{(int(last[3:]) if last else 0)+1:06d}'
    def seed_defaults(self):
        with self.session() as s:
            if not s.scalar(select(Terminal)):
                s.add_all([Terminal(name='Terminal 1'),Terminal(name='Terminal 2')]); s.commit()
