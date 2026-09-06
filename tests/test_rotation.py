"""Automated checks for weekly shift rotation.

Scenario reproduced from the user's description, with shifts numbered as they
are configured (cycle order [Schimb 1, Schimb 2, Schimb 3]) and employees A, B,
C starting staggered on shifts 1, 2 and 3 during an anchor week:

    week n   : A=1  B=2  C=3
    week n+1 : A=3  B=1  C=2
    week n+2 : A=2  B=3  C=1
    week n+3 : A=1  B=2  C=3   (the cycle repeats)
"""
from datetime import date, datetime, time

import pytest
from sqlalchemy import select

from app.database import Database
from app.database.models import Employee, Shift, AttendanceSession, ScanEvent
from app.services import EmployeeService, ShiftService, RotationService
from app.attendance import AttendanceEngine, ScannerEvent
from app.attendance.rotation import monday_on_or_before, weeks_since, effective_index

MONDAY = date(2025, 1, 6)  # a Monday used as the rotation anchor


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / 'attendance.db'); d.seed_defaults()
    with d.session() as s:
        s.add_all([
            Shift(name='Schimb 1', start_time=time(6), end_time=time(14), early_clock_in_minutes=60, earliest_clock_out_minutes=10),
            Shift(name='Schimb 2', start_time=time(14), end_time=time(22), early_clock_in_minutes=60, earliest_clock_out_minutes=10),
            Shift(name='Schimb 3', start_time=time(22), end_time=time(6), early_clock_in_minutes=60, earliest_clock_out_minutes=10),
        ])
        s.commit()
    return d


def ids_by_name(db):
    with db.session() as s:
        return {x.name: x.id for x in s.scalars(select(Shift))}


def shift_name(db, shift_id):
    with db.session() as s:
        shift = s.get(Shift, shift_id)
        return shift.name if shift else None


def setup_staggered(db, anchor=MONDAY):
    """Employees A, B, C on a rotation, starting on shifts 1, 2, 3."""
    shifts = ids_by_name(db)
    service = RotationService(db)
    rotation_id = service.create('Rotatie 3 ture', [shifts['Schimb 1'], shifts['Schimb 2'], shifts['Schimb 3']])
    employee_ids = []
    for index, name in enumerate(['Ana', 'Bogdan', 'Cristina']):
        shift_id = shifts[f'Schimb {index + 1}']
        employee_id = EmployeeService(db).create(name, 'X', shift_id=shift_id)
        service.assign(employee_id, rotation_id, start_shift_id=shift_id, anchor=anchor)
        employee_ids.append(employee_id)
    return rotation_id, employee_ids


def test_monday_helpers():
    assert monday_on_or_before(date(2025, 1, 10)) == date(2025, 1, 6)   # Friday -> Monday
    assert monday_on_or_before(date(2025, 1, 6)) == date(2025, 1, 6)    # Monday stays
    assert weeks_since(date(2025, 1, 6), date(2025, 1, 20)) == 2
    # one step per week, wrapping backward through the cycle
    assert [effective_index(3, 0, d) for d in range(4)] == [0, 2, 1, 0]
    assert [effective_index(3, 1, d) for d in range(4)] == [1, 0, 2, 1]
    assert [effective_index(3, 2, d) for d in range(4)] == [2, 1, 0, 2]


def test_rotation_create_and_list(db):
    shifts = ids_by_name(db)
    service = RotationService(db)
    rotation_id = service.create('Turne', [shifts['Schimb 1'], shifts['Schimb 3']])
    rotations = service.list()
    assert len(rotations) == 1
    rotation, cycle, members = rotations[0]
    assert rotation.name == 'Turne' and members == 0
    assert [s.name for s in cycle] == ['Schimb 1', 'Schimb 3']
    service.update(rotation_id, active=False)
    assert service.list()[0][0].active is False


def test_rotation_weekly_pattern(db):
    service = RotationService(db)
    _rotation_id, employee_ids = setup_staggered(db)
    # week n : A=1 B=2 C=3
    for employee_id, expected in zip(employee_ids, ['Schimb 1', 'Schimb 2', 'Schimb 3']):
        assert shift_name(db, service.current_shift_map(MONDAY)[employee_id]) == expected
    # week n+1 : A=3 B=1 C=2
    week2 = date(2025, 1, 13)
    for employee_id, expected in zip(employee_ids, ['Schimb 3', 'Schimb 1', 'Schimb 2']):
        assert shift_name(db, service.current_shift_map(week2)[employee_id]) == expected
    # week n+2 : A=2 B=3 C=1
    week3 = date(2025, 1, 20)
    for employee_id, expected in zip(employee_ids, ['Schimb 2', 'Schimb 3', 'Schimb 1']):
        assert shift_name(db, service.current_shift_map(week3)[employee_id]) == expected
    # week n+3 : back to A=1 B=2 C=3
    week4 = date(2025, 1, 27)
    for employee_id, expected in zip(employee_ids, ['Schimb 1', 'Schimb 2', 'Schimb 3']):
        assert shift_name(db, service.current_shift_map(week4)[employee_id]) == expected


def test_employee_without_rotation_keeps_fixed_shift(db):
    shifts = ids_by_name(db)
    service = RotationService(db)
    service.create('Turne', [shifts['Schimb 1'], shifts['Schimb 2']])
    employee_id = EmployeeService(db).create('Dan', 'X', shift_id=shifts['Schimb 2'])
    for day in [MONDAY, date(2025, 1, 13), date(2025, 2, 3)]:
        assert service.current_shift_map(day)[employee_id] == shifts['Schimb 2']


def test_rotation_engine_uses_current_week_shift(db):
    """An IN on the following week must be validated with that week's shift."""
    shifts = ids_by_name(db)
    _rotation_id, employee_ids = setup_staggered(db)
    employee_id = employee_ids[0]                       # Ana: Schimb 1 on week n, Schimb 3 on week n+1
    engine = AttendanceEngine(db)
    # Week n+1 (Monday 2025-01-13) Ana should be on the overnight Schimb 3 (22:00-06:00).
    result = engine.process(ScannerEvent(employee_id, datetime(2025, 1, 13, 21, 30), 1, 'S1'))
    assert result.accepted and result.shift.name == 'Schimb 3'
    with db.session() as s:
        session = s.scalar(select(AttendanceSession).where(AttendanceSession.employee_id == employee_id))
        assert session.shift_id == shifts['Schimb 3']
    # OUT the next morning at 05:49 is too early for Schimb 3 (earliest 05:50)...
    early = engine.process(ScannerEvent(employee_id, datetime(2025, 1, 14, 5, 49), 1, 'S1'))
    assert not early.accepted and early.reason.startswith('CLOCK_OUT_NOT_ALLOWED')
    # ...and at 05:50 it is accepted, closing the same Schimb 3 session.
    assert engine.process(ScannerEvent(employee_id, datetime(2025, 1, 14, 5, 50), 1, 'S1')).accepted
    with db.session() as s:
        session = s.scalar(select(AttendanceSession).where(AttendanceSession.employee_id == employee_id))
        assert session.shift_id == shifts['Schimb 3'] and session.clock_out is not None


def test_unassign_returns_to_fixed_shift(db):
    shifts = ids_by_name(db)
    service = RotationService(db)
    rotation_id = service.create('Turne', [shifts['Schimb 1'], shifts['Schimb 2']])
    employee_id = EmployeeService(db).create('Ema', 'X', shift_id=shifts['Schimb 1'])
    service.assign(employee_id, rotation_id, start_shift_id=shifts['Schimb 1'], anchor=MONDAY)
    # one week later (2025-01-13) a 2-shift cycle puts Ema on Schimb 2...
    assert service.current_shift_map(date(2025, 1, 13))[employee_id] == shifts['Schimb 2']
    service.assign(employee_id, None)  # take the employee off the rotation
    # ...and back on her fixed Schimb 1 after being unassigned.
    assert service.current_shift_map(date(2025, 1, 13))[employee_id] == shifts['Schimb 1']
    with db.session() as s:
        employee = s.get(Employee, employee_id)
        assert employee.rotation_id is None and employee.rotation_start is None
