from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__='users'; id: Mapped[int]=mapped_column(primary_key=True); username: Mapped[str]=mapped_column(String(80),unique=True); password_hash: Mapped[str]=mapped_column(String(256)); created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.now)
class Shift(Base):
    __tablename__='shifts'; id: Mapped[int]=mapped_column(primary_key=True); name: Mapped[str]=mapped_column(String(100),unique=True); start_time: Mapped[datetime.time]=mapped_column(Time); end_time: Mapped[datetime.time]=mapped_column(Time); early_clock_in_minutes: Mapped[int]=mapped_column(Integer,default=60); earliest_clock_out_minutes: Mapped[int]=mapped_column(Integer,default=10); active: Mapped[bool]=mapped_column(Boolean,default=True)
class Employee(Base):
    __tablename__='employees'; employee_id: Mapped[str]=mapped_column(String(20),primary_key=True); employee_number: Mapped[str|None]=mapped_column(String(50)); first_name: Mapped[str]=mapped_column(String(100)); last_name: Mapped[str]=mapped_column(String(100)); department: Mapped[str|None]=mapped_column(String(100)); position: Mapped[str|None]=mapped_column(String(100)); active: Mapped[bool]=mapped_column(Boolean,default=True); assigned_shift_id: Mapped[int|None]=mapped_column(ForeignKey('shifts.id')); created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.now); updated_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.now,onupdate=datetime.now)
class Terminal(Base):
    __tablename__='terminals'; id: Mapped[int]=mapped_column(primary_key=True); name: Mapped[str]=mapped_column(String(100),unique=True); active: Mapped[bool]=mapped_column(Boolean,default=True)
class Scanner(Base):
    __tablename__='scanners'; id: Mapped[int]=mapped_column(primary_key=True); scanner_id: Mapped[str]=mapped_column(String(50),unique=True); terminal_id: Mapped[int]=mapped_column(ForeignKey('terminals.id')); com_port: Mapped[str]=mapped_column(String(30)); baud_rate: Mapped[int]=mapped_column(Integer,default=9600); enabled: Mapped[bool]=mapped_column(Boolean,default=True); description: Mapped[str|None]=mapped_column(String(200))
class AttendanceSession(Base):
    __tablename__='attendance_sessions'; id: Mapped[int]=mapped_column(primary_key=True); employee_id: Mapped[str]=mapped_column(ForeignKey('employees.employee_id')); shift_id: Mapped[int|None]=mapped_column(ForeignKey('shifts.id')); clock_in: Mapped[datetime]=mapped_column(DateTime); clock_out: Mapped[datetime|None]=mapped_column(DateTime); terminal_in: Mapped[int|None]=mapped_column(ForeignKey('terminals.id')); terminal_out: Mapped[int|None]=mapped_column(ForeignKey('terminals.id'))
class ScanEvent(Base):
    __tablename__='scan_events'; id: Mapped[int]=mapped_column(primary_key=True); timestamp: Mapped[datetime]=mapped_column(DateTime); employee_id: Mapped[str|None]=mapped_column(ForeignKey('employees.employee_id')); action: Mapped[str]=mapped_column(String(20)); terminal_id: Mapped[int|None]=mapped_column(ForeignKey('terminals.id')); scanner_id: Mapped[str|None]=mapped_column(String(50)); raw_barcode: Mapped[str]=mapped_column(String(200)); accepted: Mapped[bool]=mapped_column(Boolean); rejection_reason: Mapped[str|None]=mapped_column(Text); shift_id: Mapped[int|None]=mapped_column(ForeignKey('shifts.id')); application_timestamp: Mapped[datetime]=mapped_column(DateTime,default=datetime.now); created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.now)
class ExceptionRecord(Base):
    __tablename__='exceptions'; id: Mapped[int]=mapped_column(primary_key=True); timestamp: Mapped[datetime]=mapped_column(DateTime); employee_id: Mapped[str|None]=mapped_column(String(20)); problem: Mapped[str]=mapped_column(String(100)); terminal_id: Mapped[int|None]=mapped_column(Integer); scanner_id: Mapped[str|None]=mapped_column(String(50)); details: Mapped[str|None]=mapped_column(Text)
class ExportJob(Base):
    __tablename__='export_jobs'; id: Mapped[int]=mapped_column(primary_key=True); enabled: Mapped[bool]=mapped_column(Boolean,default=True); run_time: Mapped[str]=mapped_column(String(5)); destination: Mapped[str]=mapped_column(String(500)); frequency: Mapped[str]=mapped_column(String(20),default='daily'); weekday: Mapped[int|None]=mapped_column(Integer); month_day: Mapped[int|None]=mapped_column(Integer); last_run: Mapped[datetime|None]=mapped_column(DateTime)
class ApplicationSetting(Base):
    __tablename__='application_settings'; key: Mapped[str]=mapped_column(String(100),primary_key=True); value: Mapped[str]=mapped_column(Text)
class AuditLog(Base):
    __tablename__='audit_log'; id: Mapped[int]=mapped_column(primary_key=True); timestamp: Mapped[datetime]=mapped_column(DateTime,default=datetime.now); username: Mapped[str|None]=mapped_column(String(80)); action: Mapped[str]=mapped_column(String(200)); details: Mapped[str|None]=mapped_column(Text)
