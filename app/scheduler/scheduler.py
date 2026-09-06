import calendar
import threading
import time
from datetime import datetime, timedelta
from sqlalchemy import select
from app.database.models import ExportJob

WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

def next_run_time(job, now: datetime | None = None) -> datetime:
    """Next datetime at/after `now` when an enabled export job will fire."""
    now = now or datetime.now()
    hour, minute = (int(x) for x in job.run_time.split(':'))
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now: candidate += timedelta(days=1)
    frequency = job.frequency or 'daily'
    if frequency == 'weekly':
        target = job.weekday if job.weekday is not None else now.weekday()
        while candidate.weekday() != target: candidate += timedelta(days=1)
    elif frequency == 'monthly':
        day = job.month_day or 1
        for _ in range(62):
            last_day = calendar.monthrange(candidate.year, candidate.month)[1]
            if candidate.day == min(day, last_day): return candidate
            candidate += timedelta(days=1)
    return candidate

def is_due(job, now: datetime) -> bool:
    """Whether `now` is a valid date for the job's frequency."""
    frequency = job.frequency or 'daily'
    if frequency == 'weekly': return job.weekday is None or now.weekday() == job.weekday
    if frequency == 'monthly':
        if job.month_day is None: return True
        return now.day == min(job.month_day, calendar.monthrange(now.year, now.month)[1])
    return True

def schedule_text(job) -> str:
    """Human-readable description of a job's recurring schedule."""
    frequency = job.frequency or 'daily'
    if frequency == 'weekly': return WEEKDAYS[job.weekday] if job.weekday is not None else 'Weekly'
    if frequency == 'monthly': return f'Day {job.month_day or 1}'
    return 'Daily'

class ExportScheduler:
    def __init__(self, db, exporter): self.db = db; self.exporter = exporter; self.running = False
    def start(self): self.running = True; threading.Thread(target=self._loop, daemon=True).start()
    def stop(self): self.running = False
    def _loop(self):
        while self.running:
            now = datetime.now()
            with self.db.session() as s:
                for job in s.scalars(select(ExportJob).where(ExportJob.enabled == True, ExportJob.run_time == now.strftime('%H:%M'))):
                    if is_due(job, now) and (not job.last_run or job.last_run.date() != now.date()):
                        try:
                            self.exporter.export(job.destination)
                            job.last_run = now
                        except Exception:
                            pass
                s.commit()
            time.sleep(20)
