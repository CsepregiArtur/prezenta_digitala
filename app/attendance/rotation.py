"""Weekly shift rotation.

A rotation is an ordered cycle of shifts (see ShiftRotation / RotationShift).
Employees can be put on a rotation; each Monday they move to the next shift in
the cycle. The direction matches a classic team roster: with a cycle entered as
[Schimb 1, Schimb 2, Schimb 3] and employees starting staggered on each shift
(A on 1, B on 2, C on 3), the week after A is on 3, B on 1 and C on 2 — i.e. an
employee steps one position BACKWARD through the list every Monday (wrapping).

    week n      : A=1  B=2  C=3
    week n+1    : A=3  B=1  C=2
    week n+2    : A=2  B=3  C=1
    week n+3    : back to A=1  B=2  C=3

Everything is deterministic: the shift that applies to an employee on a given
day depends only on the employee's anchor (rotation_start = a Monday) and the
shift they were on at that anchor (rotation_start_shift_id).
"""
from __future__ import annotations
from datetime import date, timedelta
from sqlalchemy import select
from app.database.models import Employee, ShiftRotation, RotationShift

WEEK_START_WEEKDAY = 0  # Monday (datetime.weekday())


def monday_on_or_before(value: date) -> date:
    """Return the Monday of the week containing ``value``."""
    return value - timedelta(days=value.weekday() - WEEK_START_WEEKDAY)


def weeks_since(anchor: date, on: date) -> int:
    """Whole weeks (Mondays) elapsed between the week of ``anchor`` and ``on``."""
    return (monday_on_or_before(on) - monday_on_or_before(anchor)).days // 7


def effective_index(cycle_length: int, start_index: int, delta: int) -> int:
    """Position in the cycle for ``delta`` weeks after ``start_index``."""
    return (start_index - delta) % cycle_length


def shift_id_for(session, employee: Employee, on_date: date):
    """Shift id that applies to ``employee`` on ``on_date``.

    Employees that are not part of an active rotation (or whose rotation is
    incomplete / invalid) simply keep their fixed ``assigned_shift_id``.
    """
    if not (employee.rotation_id and employee.rotation_start and employee.rotation_start_shift_id):
        return employee.assigned_shift_id
    rotation = session.get(ShiftRotation, employee.rotation_id)
    if not rotation or not rotation.active:
        return employee.assigned_shift_id
    ids = session.scalars(
        select(RotationShift.shift_id)
        .where(RotationShift.rotation_id == rotation.id)
        .order_by(RotationShift.position)
    ).all()
    if not ids:
        return employee.assigned_shift_id
    try:
        start = ids.index(employee.rotation_start_shift_id)
    except ValueError:
        # The starting shift is no longer part of the cycle -> use the fixed shift.
        return employee.assigned_shift_id
    delta = weeks_since(employee.rotation_start, on_date)
    return ids[effective_index(len(ids), start, delta)]
