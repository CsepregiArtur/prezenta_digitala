@echo off
REM Build a single-file Windows EXE (everything packed) and drop the docs next to it.
py -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name AttendanceControl ^
  --add-data "config.json;." ^
  --hidden-import pyserial ^
  --hidden-import openpyxl ^
  --hidden-import barcode ^
  --hidden-import PIL ^
  app\main.py

REM Ship licensing and documentation alongside the executable.
if exist dist\AttendanceControl.exe (
  copy /Y LICENSE  dist\LICENSE.txt >nul
  copy /Y README.md dist\README.md >nul
  copy /Y GUIDE.md  dist\GUIDE.md >nul
  echo Build complete: dist\AttendanceControl.exe (single file + docs)
) else (
  echo Build failed - dist\AttendanceControl.exe was not created.
  exit /b 1
)
