from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import select
from app.database.models import Employee, Shift, AttendanceSession, ScanEvent, ExceptionRecord, Terminal, Scanner, ApplicationSetting, ExportJob, ShiftRotation, RotationShift
from app.attendance.rotation import monday_on_or_before, weeks_since, effective_index
from app.barcode import generate_barcode

class EmployeeService:
    def __init__(self, db): self.db=db
    def create(self, first_name, last_name, employee_number=None, department=None, position=None, shift_id=None):
        if not first_name.strip() or not last_name.strip(): raise ValueError('First and last name are required')
        with self.db.session() as s:
            eid=self.db.next_employee_id(s); s.add(Employee(employee_id=eid,employee_number=employee_number,first_name=first_name.strip(),last_name=last_name.strip(),department=department,position=position,assigned_shift_id=shift_id)); s.commit()
        return eid
    def update(self, employee_id, **data):
        allowed={'first_name','last_name','employee_number','department','position','assigned_shift_id','active'}
        with self.db.session() as s:
            employee=s.get(Employee,employee_id)
            if not employee: raise ValueError('Employee not found')
            for key,value in data.items():
                if key in allowed: setattr(employee,key,value)
            s.commit()
    def import_rows(self, rows):
        """Bulk create employees from imported rows (see app/importer).

        Returns {'created': int, 'skipped': int, 'errors': [str]}. Rows whose
        employee_number already exists are skipped; a shift name that does not
        match an existing shift is reported and the employee is created unassigned.
        """
        created = skipped = 0
        errors = []
        with self.db.session() as s:
            shifts = {sh.name: sh.id for sh in s.scalars(select(Shift))}
            numbers = {e.employee_number for e in s.scalars(select(Employee)) if e.employee_number}
        seen = set()
        for index, row in enumerate(rows, start=1):
            first = (row.get('first_name') or '').strip()
            last = (row.get('last_name') or '').strip()
            number = (row.get('employee_number') or '').strip() or None
            if not first or not last:
                errors.append(f'Row {index}: first_name and last_name are required (row skipped)')
                continue
            if number and (number in numbers or number in seen):
                skipped += 1
                continue
            shift_id = None
            shift_name = (row.get('shift') or '').strip()
            if shift_name:
                if shift_name in shifts:
                    shift_id = shifts[shift_name]
                else:
                    errors.append(f'Row {index}: shift "{shift_name}" does not exist (employee created without a shift)')
            try:
                self.create(first, last, employee_number=number,
                            department=(row.get('department') or '').strip() or None,
                            position=(row.get('position') or '').strip() or None,
                            shift_id=shift_id)
                created += 1
                if number:
                    seen.add(number)
            except Exception as error:
                errors.append(f'Row {index}: {error}')
        return {'created': created, 'skipped': skipped, 'errors': errors}
    def barcode(self, employee_id): return generate_barcode(employee_id)
    def list(self, query=''):
        with self.db.session() as s:
            q=select(Employee).order_by(Employee.last_name)
            if query: q=q.where((Employee.first_name+' '+Employee.last_name).like(f'%{query}%') | Employee.employee_id.like(f'%{query}%'))
            return list(s.scalars(q))

class ShiftService:
    def __init__(self,db): self.db=db
    def create(self,name,start_time,end_time,early=60,earliest_out=10):
        with self.db.session() as s: s.add(Shift(name=name,start_time=start_time,end_time=end_time,early_clock_in_minutes=early,earliest_clock_out_minutes=earliest_out)); s.commit()

    def list(self):
        with self.db.session() as s: return list(s.scalars(select(Shift).order_by(Shift.name)))
    def update(self, shift_id, **values):
        with self.db.session() as s:
            item=s.get(Shift, shift_id)
            if not item: raise ValueError('Shift not found')
            for key in {'name','start_time','end_time','early_clock_in_minutes','earliest_clock_out_minutes','active'} & values.keys(): setattr(item,key,values[key])
            s.commit()

class RotationService:
    """Weekly shift-rotation configuration.

    A rotation is an ordered cycle of shifts; members move one shift along the
    cycle every Monday (see app.attendance.rotation for the exact rule).
    """
    def __init__(self, db): self.db=db
    def _cycle(self, s, rotation_id):
        return list(s.scalars(select(RotationShift.shift_id).where(RotationShift.rotation_id==rotation_id).order_by(RotationShift.position)))
    def list(self):
        """Return [(ShiftRotation, [Shift, ...], member_count)] ordered by name."""
        with self.db.session() as s:
            rotations=list(s.scalars(select(ShiftRotation).order_by(ShiftRotation.name)))
            shifts={x.id: x for x in s.scalars(select(Shift))}
            counts={}
            for r_id, in s.execute(select(Employee.rotation_id).where(Employee.rotation_id.isnot(None))): counts[r_id]=counts.get(r_id,0)+1
            return [(r,[shifts[sid] for sid in self._cycle(s,r.id) if sid in shifts],counts.get(r.id,0)) for r in rotations]
    def create(self, name, shift_ids):
        if not name.strip(): raise ValueError('Name is required')
        if len(shift_ids) < 2: raise ValueError('Add at least two shifts to the rotation')
        if len(set(shift_ids)) != len(shift_ids): raise ValueError('A rotation cannot repeat the same shift')
        with self.db.session() as s:
            rotation=ShiftRotation(name=name.strip()); s.add(rotation); s.flush()
            for position, sid in enumerate(shift_ids): s.add(RotationShift(rotation_id=rotation.id, shift_id=sid, position=position))
            s.commit(); return rotation.id
    def update(self, rotation_id, name=None, shift_ids=None, active=None):
        with self.db.session() as s:
            rotation=s.get(ShiftRotation, rotation_id)
            if not rotation: raise ValueError('Rotation not found')
            if name is not None:
                if not name.strip(): raise ValueError('Name is required')
                rotation.name=name.strip()
            if active is not None: rotation.active=bool(active)
            if shift_ids is not None:
                if len(shift_ids) < 2: raise ValueError('A rotation needs at least two shifts')
                if len(set(shift_ids)) != len(shift_ids): raise ValueError('A rotation cannot repeat the same shift')
                for item in s.scalars(select(RotationShift).where(RotationShift.rotation_id==rotation_id)): s.delete(item)
                for position, sid in enumerate(shift_ids): s.add(RotationShift(rotation_id=rotation_id, shift_id=sid, position=position))
            s.commit()
    def delete(self, rotation_id):
        with self.db.session() as s:
            if not s.get(ShiftRotation, rotation_id): raise ValueError('Rotation not found')
            for e in s.scalars(select(Employee).where(Employee.rotation_id==rotation_id)):
                e.rotation_id=None; e.rotation_start=None; e.rotation_start_shift_id=None
            for item in s.scalars(select(RotationShift).where(RotationShift.rotation_id==rotation_id)): s.delete(item)
            s.delete(s.get(ShiftRotation, rotation_id)); s.commit()
    def assign(self, employee_id, rotation_id, start_shift_id=None, anchor=None):
        """Put an employee on (or off, when rotation_id is None) a rotation.

        ``start_shift_id`` is the shift they occupy today (defaults to the
        employee's assigned shift); ``anchor`` defaults to today. The week is
        stored as its Monday so the schedule is deterministic from that point.
        """
        with self.db.session() as s:
            employee=s.get(Employee, employee_id)
            if not employee: raise ValueError('Employee not found')
            if rotation_id is None:
                employee.rotation_id=None; employee.rotation_start=None; employee.rotation_start_shift_id=None; s.commit(); return
            rotation=s.get(ShiftRotation, rotation_id)
            if not rotation or not rotation.active: raise ValueError('Rotation not found or inactive')
            cycle=self._cycle(s, rotation_id)
            if len(cycle) < 2: raise ValueError('This rotation has no shifts yet')
            start_shift_id = start_shift_id if start_shift_id is not None else employee.assigned_shift_id
            if start_shift_id is None: start_shift_id=cycle[0]
            if start_shift_id not in cycle: raise ValueError('Starting shift is not part of this rotation')
            employee.rotation_id=rotation_id
            employee.rotation_start=monday_on_or_before(anchor if anchor is not None else date.today())
            employee.rotation_start_shift_id=start_shift_id
            if employee.assigned_shift_id is None: employee.assigned_shift_id=start_shift_id
            s.commit()
    def current_shift_map(self, on_date=None):
        """Return {employee_id: effective_shift_id} for a date (default: today).

        Rotation members get the shift their rotation yields that week; everyone
        else keeps their fixed assigned shift. One query pass over the database.
        """
        on = on_date if on_date is not None else date.today()
        result={}
        with self.db.session() as s:
            rotations={r.id: r for r in s.scalars(select(ShiftRotation))}
            cycles={}
            for item in s.scalars(select(RotationShift).order_by(RotationShift.rotation_id, RotationShift.position)):
                cycles.setdefault(item.rotation_id, []).append(item.shift_id)
            for e in s.scalars(select(Employee)):
                shift_id=e.assigned_shift_id
                rotation=rotations.get(e.rotation_id) if e.rotation_id else None
                ids=cycles.get(e.rotation_id) if e.rotation_id else None
                if (rotation and rotation.active and e.rotation_start and e.rotation_start_shift_id and ids
                        and e.rotation_start_shift_id in ids):
                    delta=weeks_since(e.rotation_start, on)
                    start=ids.index(e.rotation_start_shift_id)
                    shift_id=ids[effective_index(len(ids), start, delta)]
                result[e.employee_id]=shift_id
        return result

class AdminDataService:
    """UI-facing queries and safe configuration persistence; no attendance rules live here."""
    def __init__(self, db): self.db=db
    def sessions(self):
        with self.db.session() as s: return [(x,s.get(Employee,x.employee_id),s.get(Shift,x.shift_id) if x.shift_id else None) for x in s.scalars(select(AttendanceSession).order_by(AttendanceSession.clock_in.desc()))]
    def scans(self):
        with self.db.session() as s: return [(x,s.get(Employee,x.employee_id) if x.employee_id else None) for x in s.scalars(select(ScanEvent).order_by(ScanEvent.timestamp.desc()))]
    def exceptions(self):
        with self.db.session() as s: return list(s.scalars(select(ExceptionRecord).order_by(ExceptionRecord.timestamp.desc())))
    def terminals(self):
        with self.db.session() as s: return [(x,list(s.scalars(select(Scanner).where(Scanner.terminal_id==x.id)))) for x in s.scalars(select(Terminal).order_by(Terminal.name))]
    def save_terminal(self,name):
        with self.db.session() as s: s.add(Terminal(name=name)); s.commit()
    def save_scanner(self, scanner_id, terminal_id, port, description='', enabled=True, baud_rate=9600):
        with self.db.session() as s: s.add(Scanner(scanner_id=scanner_id,terminal_id=terminal_id,com_port=port,description=description,enabled=enabled,baud_rate=baud_rate)); s.commit()
    def update_scanner(self, scanner_id, **values):
        with self.db.session() as s:
            scanner=s.scalar(select(Scanner).where(Scanner.scanner_id==scanner_id))
            if not scanner: raise ValueError('Scanner not found')
            for key in {'scanner_id','terminal_id','com_port','description','enabled','baud_rate'} & values.keys(): setattr(scanner,key,values[key])
            s.commit()
    def settings(self):
        with self.db.session() as s: return {x.key:x.value for x in s.scalars(select(ApplicationSetting))}
    def set_setting(self,key,value):
        with self.db.session() as s:
            item=s.get(ApplicationSetting,key)
            if item: item.value=str(value)
            else: s.add(ApplicationSetting(key=key,value=str(value)))
            s.commit()
    def export_jobs(self):
        with self.db.session() as s: return list(s.scalars(select(ExportJob)))
    def save_export_job(self, run_time, destination, frequency='daily', enabled=True, weekday=None, month_day=None):
        if len(run_time)!=5 or run_time[2]!=':': raise ValueError('Time must use HH:MM')
        with self.db.session() as s: s.add(ExportJob(run_time=run_time,destination=destination,frequency=frequency,enabled=enabled,weekday=weekday,month_day=month_day)); s.commit()
    def update_export_job(self, job_id, **values):
        with self.db.session() as s:
            job=s.get(ExportJob,job_id)
            if not job: raise ValueError('Export job not found')
            for key in {'run_time','destination','frequency','enabled','last_run','weekday','month_day'} & values.keys(): setattr(job,key,values[key])
            s.commit()
    def delete_export_job(self, job_id):
        with self.db.session() as s:
            job=s.get(ExportJob,job_id)
            if not job: raise ValueError('Export job not found')
            s.delete(job); s.commit()
    def get_scanner(self, scanner_id):
        with self.db.session() as s: return s.scalar(select(Scanner).where(Scanner.scanner_id==scanner_id))
    def update_terminal(self, terminal_id, **values):
        with self.db.session() as s:
            terminal=s.get(Terminal,terminal_id)
            if not terminal: raise ValueError('Terminal not found')
            for key in {'name','active'} & values.keys(): setattr(terminal,key,values[key])
            s.commit()
    def delete_scanner(self, scanner_id):
        with self.db.session() as s:
            scanner=s.scalar(select(Scanner).where(Scanner.scanner_id==scanner_id))
            if not scanner: raise ValueError('Scanner not found')
            s.delete(scanner); s.commit()
    def delete_terminal(self, terminal_id):
        with self.db.session() as s:
            terminal=s.get(Terminal,terminal_id)
            if not terminal: raise ValueError('Terminal not found')
            for scanner in s.scalars(select(Scanner).where(Scanner.terminal_id==terminal_id)): s.delete(scanner)
            s.delete(terminal); s.commit()
    def scanners_flat(self):
        with self.db.session() as s: return list(s.scalars(select(Scanner)))
    def summary(self):
        with self.db.session() as s:
            employees=list(s.scalars(select(Employee))); terminals=list(s.scalars(select(Terminal))); scanners=list(s.scalars(select(Scanner)))
            sessions=list(s.scalars(select(AttendanceSession))); scans=list(s.scalars(select(ScanEvent))); exceptions=list(s.scalars(select(ExceptionRecord)))
            today=datetime.now().date(); open_sessions=[x for x in sessions if not x.clock_out]
            return {'total_employees':len(employees),'active_employees':sum(1 for e in employees if e.active),'present_now':sum(1 for x in open_sessions if x.clock_in.date()==today),'missing_out':sum(1 for x in open_sessions if x.clock_in.date()<today),'open_sessions':len(open_sessions),'terminals':len(terminals),'scanners':len(scanners),'enabled_scanners':sum(1 for sc in scanners if sc.enabled),'scans_today':sum(1 for x in scans if x.timestamp.date()==today),'accepted_today':sum(1 for x in scans if x.accepted and x.timestamp.date()==today),'exceptions_today':sum(1 for x in exceptions if x.timestamp.date()==today)}
