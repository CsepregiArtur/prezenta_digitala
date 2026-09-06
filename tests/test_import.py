"""Tests for the employee bulk-import feature (Excel/CSV templates + import_rows)."""
from datetime import time
from pathlib import Path

import pytest
from app.database import Database
from app.database.models import Employee
from app.services import EmployeeService, ShiftService
from app import importer


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / 'attendance.db'); d.seed_defaults()
    ShiftService(d).create('A', time(7), time(15), early=60, earliest_out=10)
    return d


def test_template_roundtrip_csv_and_xlsx(tmp_path):
    csv_path = importer.write_template_csv(tmp_path / 'employees.csv')
    xlsx_path = importer.write_template_xlsx(tmp_path / 'employees.xlsx')
    assert csv_path.exists() and xlsx_path.exists()
    rows_csv = importer.read_employee_file(csv_path)
    rows_xlsx = importer.read_employee_file(xlsx_path)
    assert len(rows_csv) == 2 and len(rows_xlsx) == 2
    assert rows_csv[0]['first_name'] == 'Maria' and rows_csv[0]['employee_number'] == '1001'
    assert rows_xlsx[1]['last_name'] == 'Popescu'


def test_read_accepts_friendly_headers(tmp_path):
    path = tmp_path / 'custom.csv'
    path.write_text('First Name,Last Name,Employee Number,Department,Position,Shift\n'
                    'Ana,Badea,2001,HR,Manager,A\n', encoding='utf-8')
    rows = importer.read_employee_file(path)
    assert rows[0]['first_name'] == 'Ana' and rows[0]['employee_number'] == '2001'
    assert rows[0]['shift'] == 'A'


def test_read_rejects_unknown_extension(tmp_path):
    path = tmp_path / 'list.txt'
    path.write_text('a,b\n')
    with pytest.raises(ValueError):
        importer.read_employee_file(path)


def test_import_rows_creates_and_skips_duplicates(db, tmp_path):
    csv_path = importer.write_template_csv(tmp_path / 'employees.csv')
    rows = importer.read_employee_file(csv_path)
    service = EmployeeService(db)
    first = service.import_rows(rows)
    assert first == {'created': 2, 'skipped': 0, 'errors': []}
    second = service.import_rows(rows)
    assert second['created'] == 0 and second['skipped'] == 2
    with db.session() as s:
        from sqlalchemy import select, func
        assert s.scalar(select(func.count()).select_from(Employee)) == 2


def test_import_rows_reports_missing_names_and_unknown_shift(db):
    rows = [
        {'first_name': 'Good', 'last_name': 'Row', 'employee_number': '1', 'shift': 'A'},
        {'first_name': '', 'last_name': 'MissingName', 'employee_number': '2', 'shift': ''},
        {'first_name': 'NoShift', 'last_name': 'Here', 'employee_number': '3', 'shift': 'Zzz'},
    ]
    result = EmployeeService(db).import_rows(rows)
    assert result['created'] == 2 and result['skipped'] == 0
    assert len(result['errors']) == 2
    assert any('required' in error for error in result['errors'])
    assert any('Zzz' in error for error in result['errors'])
