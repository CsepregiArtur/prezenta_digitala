# Attendance Control

Attendance Control is a local desktop application for employee time tracking. Employees scan a Code 128 barcode at a kiosk; the application records and validates clock-in/clock-out activity in a SQLite database. It is designed for Honeywell scanners configured in USB Serial / COM mode and is intended to be packaged later as a Windows `.exe`.

> 📖 **Full setup & user guide (English + Română):** see [`GUIDE.md`](GUIDE.md).
> Example import files: `examples/employees_import_template.xlsx` / `.csv`.

**Attendance Control v1.0.0** — © 2026 **Csepregi Artur**. All rights reserved.
See [`LICENSE`](LICENSE). Contact: <https://csepregiartur.github.io>

## What it does

- Creates employees with sequential IDs such as `EMP000001`, individually or by importing a whole list from an **Excel/CSV file** (template generator included).
- Generates a Code 128 barcode containing **only** the employee ID.
- Supports regular and overnight shifts, early arrival, and earliest permitted clock-out rules.
- Decides whether a valid scan is IN or OUT based on an employee’s active session.
- Blocks duplicate scans within a configurable period (five seconds by default).
- Retains every scan attempt, including unknown, inactive, too-early, and duplicate scans.
- Supports terminals and individual serial scanners.
- Provides a dark dashboard and touch-oriented kiosk screen.
- Includes live dashboard summary cards, filterable reports with totals, Excel export, scheduled export support, backups, audit logs, and secure password hashing for administrators.
- Supports a durable offline queue plus optional LAN/server synchronization so several kiosks can share a central database.
- Provides a Session menu (log out / switch user) and a full-screen kiosk mode protected by an administrator unlock.
- Interface language can be switched between **English** and **Română** in Settings (applied after restart).

## Access and roles

### Employee / kiosk user

Employees do not log in. They only scan their personal barcode. The application starts directly on the kiosk screen: it shows the large clock, readiness/system status, and a brief accepted/rejected scan result. It does not expose records, reports, configuration, or database administration. The only control on the kiosk is an **ADMINISTRATOR LOGIN** button.

### Administrator

Administrators authenticate with a username and password (passwords use PBKDF2-SHA256 with a random salt; no plain-text password is stored or logged). On the kiosk screen, click **ADMINISTRATOR LOGIN** to open the login dialog — the first run instead creates the administrator. A successful login opens the admin shell, whose toolbar (and the **Session** menu) offers **Log out → Kiosk** and **Close App**: logging out or closing the admin window returns to the kiosk, while **Close App** exits Attendance Control. Admin services cover employee and shift setup, scanner configuration, exports, backups, and audit activity.

> The desktop shell includes Dashboard, Employees, Shifts, Attendance, Live Scans, Exceptions, Terminals & Scanners, Reports, Excel Export, Settings, System Logs, Backup / Restore, Automatic Exports, Synchronization, and Kiosk pages. These pages use the existing SQLite database and service layer; attendance validation remains in the dedicated attendance engine. The Session menu lets the administrator log out / switch users or launch the full-screen kiosk mode.

## Requirements

- Python 3.12+ for development
- Internet access once to install dependencies
- Read/write access to the application folder
- For real scans: Honeywell scanner in USB Serial/COM mode, appropriate scanner drivers, and operating-system permission to open its serial port

The final Windows executable is intended to run without Python installed. It still needs access to its local data folders and scanner drivers where required.

## Install and run

Open a terminal in this project folder.

### macOS / Linux

```zsh
python3 -m pip install -r requirements.txt
python3 -m app.main
```

### Windows

```bat
py -m pip install -r requirements.txt
py -m app.main
```

On macOS, use `python3`; `python` is often not installed as a command.

The first launch creates the database and needed folders automatically.

## Application vs. tests

Open the desktop application:

```zsh
python3 -m app.main
```

Run automated tests:

```zsh
python3 -m pytest -q
```

Tests do not open the normal program window. They run against isolated temporary databases and verify employee creation, early IN, too-early OUT, valid OUT, duplicate scans, unknown/inactive barcodes, overnight shifts, scanner identity, authentication, and backups.

## Data, storage, and permissions

All normal data stays on the local computer. The program does not require cloud services or an internet connection while operating.

| Location | Purpose | Required access |
| --- | --- | --- |
| `attendance.db` | Primary SQLite attendance database | Read/write |
| `config.json` | Non-attendance settings | Read/write |
| `barcodes/` | Employee barcode PNG files | Read/write |
| `exports/` | Generated Excel files | Read/write |
| `backup/` | Timestamped database backups | Read/write |
| `logs/application.log` | Operational and error logs | Read/write |

Do not delete `attendance.db` if you need historical records. Create a backup first. Backups, logs, exports, and the database may contain personal attendance information; restrict folder access using normal Windows/macOS user permissions.

## Configuration

`config.json` stores only application settings—not attendance records. Default values:

```json
{
  "site_name": "Company",
  "timezone": "Europe/Bucharest",
  "duplicate_scan_seconds": 5,
  "ui_theme": "dark",
  "default_export_directory": "exports"
}
```

Attendance data is stored in `attendance.db`, not JSON.

## Attendance rules

Example: a 06:00–14:00 shift with 60 minutes early arrival and a 10 minute earliest clock-out:

- IN at 05:00 or later: accepted; 04:59: rejected.
- OUT at 13:50 or later: accepted; 13:49: rejected.
- A rejected scan creates no attendance session change, but is retained in raw scans and exceptions.
- The actual scan timestamp is always retained; it is never replaced with the scheduled shift time.
- A second scan by the same employee within the duplicate window is rejected as `DUPLICATE_SCAN`.

Overnight shifts work too: for a 22:00–06:00 shift, an IN at 21:30 and OUT at 06:03 the following day are accepted.

## Scanner setup

The scanner manager opens each enabled COM device separately, reads the barcode line, identifies the originating scanner/terminal, and sends a `ScannerEvent` to the attendance engine. It does not rely on keyboard focus.

Configure each scanner with a scanner ID, terminal, COM port (for example `COM3`), baud rate, enabled flag, and description. On disconnect, it writes a log entry and retries every five seconds without terminating the application.

### Simulate a scanner (no hardware needed)

`scanner_simulator.py` is a standalone program that behaves like one or more Honeywell
scanners in USB Serial / COM mode, each on its own virtual serial port:

```zsh
python3 scanner_simulator.py
```

1. A first **scanner port** is created automatically; click **+ Add scanner port** for each
   additional scanner you want. Each row shows a device path (for example `/dev/ttys005`).
2. In the application, add one scanner in **Terminals & Scanners** per path with Enabled = Yes.
   Use the **same Terminal** for several paths to simulate multiple scanners attached to one terminal.
3. Send scans:
   - **Scan now / Enter** sends the selected barcode through the selected scanner (`Via:`).
   - **Batch** — fill the scan list (one barcode per line) and click **Send list**, or **Repeat selected N times**,
     to send many scans with one click (paced by the delay you choose). Tick **Spread across scanners**
     to rotate the list over all your virtual scanners.
   - Auto-demo repeats the selected barcode on a timer.

Every scan is sent as `<barcode>` + CR + LF at 9600 baud over that scanner's virtual port and is
processed by the real scanner → attendance pipeline, so Live Scans shows the correct scanner ID.
The simulator never touches the attendance database. On Windows, use a com0com-style virtual COM
driver; each **Add scanner port** asks for its sender COM (for example `CNCA`).

## Barcodes and privacy

Barcode payload example:

```text
EMP000421
```

Generated image: `barcodes/EMP000421.png`. The barcode must never contain the employee name, department, position, or password. An employee barcode is not an administrator credential.

## Exports and backups

Excel exports are real `.xlsx` workbooks named `Attendance_YYYY-MM-DD.xlsx` and contain:

1. Attendance Summary
2. Raw Scans
3. Exceptions
4. Employees
5. Shifts

They use formatted headers, filters, frozen header rows, and readable column widths. Scheduled exports execute in a background thread.

Backups have names like `backup/attendance_YYYYMMDD_HHMMSS.db`. Restoring a backup first copies the existing database as a safety backup. Store backups securely.

## Build the Windows executable

Build on Windows after installing the requirements:

```bat
build_exe.bat
```

This uses PyInstaller and produces a **single-file** `dist/AttendanceControl.exe` with
everything needed packed into it. The script also copies the licensing and documentation
next to the executable in the `dist` folder:

- `AttendanceControl.exe` (self-contained single file)
- `LICENSE.txt`
- `README.md`
- `GUIDE.md`

The application stores its database, logs, backups, exports and offline queue in the
folder where the EXE is located (see `app.config.app_dir`). A native Windows executable
must be built and tested on Windows; macOS cannot produce the final `.exe` through this
batch script.

## Project structure

```text
app/
  attendance/  Attendance engine and validation
  auth/        Administrator authentication
  barcode/     Code 128 generator
  database/    SQLite models and setup
  export/      Excel export
  scanner/     Serial scanner connection manager
  scheduler/   Background export scheduler
  sync.py      Offline queue + LAN/server synchronization
  ui/          PySide6 kiosk, login, and admin shell
  main.py      Application entry point
scanner_simulator.py   Standalone Honeywell scanner simulator (virtual serial ports, batch scans)
tests/         Automated tests
```

## Troubleshooting


### `ModuleNotFoundError: No module named 'PySide6'`

Install packages from the project folder:

```zsh
python3 -m pip install -r requirements.txt
```

### Scanner offline

Check USB Serial/COM mode, COM port, baud rate, device drivers, and whether another program has already opened the port. Inspect `logs/application.log` for the exact connection error.
