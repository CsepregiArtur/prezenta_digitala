from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select, desc
from app.database.models import Employee, Shift, AttendanceSession, ScanEvent, ExceptionRecord

@dataclass(frozen=True)
class ScannerEvent: barcode: str; timestamp: datetime; terminal_id: int | None; scanner_id: str | None
@dataclass(frozen=True)
class AttendanceResult: accepted: bool; employee: Employee | None; action: str; timestamp: datetime; reason: str | None; shift: Shift | None

class AttendanceEngine:
    def __init__(self, db, timezone='Europe/Bucharest', duplicate_seconds=5): self.db=db; self.zone=ZoneInfo(timezone); self.duplicate_seconds=duplicate_seconds
    def _local(self, value):
        return value.replace(tzinfo=self.zone) if value.tzinfo is None else value.astimezone(self.zone)
    def _shift_window(self, now, shift):
        start=datetime.combine(now.date(),shift.start_time,tzinfo=self.zone); end=datetime.combine(now.date(),shift.end_time,tzinfo=self.zone)
        if end<=start: end+=timedelta(days=1)
        # Before the overnight shift starts, its relevant session began yesterday.
        if shift.end_time<=shift.start_time and now < start-timedelta(minutes=shift.early_clock_in_minutes): start-=timedelta(days=1); end-=timedelta(days=1)
        return start,end
    def process(self,event: ScannerEvent) -> AttendanceResult:
        now=self._local(event.timestamp); barcode=event.barcode.strip().upper()
        with self.db.session() as s:
            employee=s.get(Employee,barcode); shift=s.get(Shift,employee.assigned_shift_id) if employee and employee.assigned_shift_id else None
            active=s.scalar(select(AttendanceSession).where(AttendanceSession.employee_id==barcode,AttendanceSession.clock_out.is_(None)).order_by(desc(AttendanceSession.clock_in))) if employee else None
            action='OUT' if active else 'IN'; reason=None
            if not employee: reason='UNKNOWN_BARCODE'; action='UNKNOWN'
            elif not employee.active: reason='INACTIVE_EMPLOYEE'; action='REJECTED'
            elif not shift or not shift.active: reason='INVALID_SHIFT'; action='REJECTED'
            else:
                recent=s.scalar(select(ScanEvent).where(ScanEvent.employee_id==barcode).order_by(desc(ScanEvent.timestamp)))
                if recent and (now.replace(tzinfo=None)-recent.timestamp).total_seconds()<self.duplicate_seconds: reason='DUPLICATE_SCAN'; action='REJECTED'
                else:
                    start,end=self._shift_window(now,shift)
                    if not active and now < start-timedelta(minutes=shift.early_clock_in_minutes): reason=f'CLOCK_IN_TOO_EARLY; allowed from {(start-timedelta(minutes=shift.early_clock_in_minutes)).strftime("%H:%M")}'; action='REJECTED'
                    elif active and now < end-timedelta(minutes=shift.earliest_clock_out_minutes): reason=f'CLOCK_OUT_NOT_ALLOWED; earliest {(end-timedelta(minutes=shift.earliest_clock_out_minutes)).strftime("%H:%M")}'; action='REJECTED'
            accepted=reason is None
            s.add(ScanEvent(timestamp=now.replace(tzinfo=None),employee_id=employee.employee_id if employee else None,action=action,terminal_id=event.terminal_id,scanner_id=event.scanner_id,raw_barcode=event.barcode,accepted=accepted,rejection_reason=reason,shift_id=shift.id if shift else None))
            if accepted and action=='IN': s.add(AttendanceSession(employee_id=employee.employee_id,shift_id=shift.id,clock_in=now.replace(tzinfo=None),terminal_in=event.terminal_id))
            elif accepted and action=='OUT': active.clock_out=now.replace(tzinfo=None); active.terminal_out=event.terminal_id
            if not accepted: s.add(ExceptionRecord(timestamp=now.replace(tzinfo=None),employee_id=employee.employee_id if employee else None,problem=reason.split(';')[0],terminal_id=event.terminal_id,scanner_id=event.scanner_id,details=reason))
            s.commit(); return AttendanceResult(accepted,employee,action,now,reason,shift)
