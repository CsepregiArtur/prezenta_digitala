@echo off
py -m PyInstaller --noconfirm --clean --windowed --name AttendanceControl --add-data "config.json;." app\main.py
if exist dist\AttendanceControl.exe echo Build complete: dist\AttendanceControl.exe
