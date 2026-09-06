# Attendance Control — Implementation Tracker

This document tracks implementation against the original master specification. Status labels are deliberately conservative:

- ✅ **Complete** — implemented and covered by automated checks where practical.
- 🟡 **Partial** — working foundation exists, but required UI/features remain.
- ⬜ **Pending** — not implemented yet.

Last verified: 6 September 2026

## Current verification

```zsh
python3 -m pytest -q
```

Current result: **36 passed**.

An offscreen PySide6 suite additionally verified that the desktop shell constructs
and reloads successfully with **15 pages** (including the new Synchronization page),
that the dashboard cards reflect live scans, and that Reports aggregates are correct.

The application now **boots directly into the full-screen employee kiosk** (no admin
authentication is required to start). An on-screen **ADMINISTRATOR LOGIN** button opens
the login/first-run dialog; success opens the admin shell and hides the kiosk until the
administrator logs out, locks, or closes the admin window. `scanner_simulator.py` is a
standalone Honeywell scanner simulator that sends typed barcodes over a virtual serial
port, which the running app reads exactly like a real COM scanner.

## Phase tracker

| Phase | Status | Implementation |
| --- | --- | --- |
| 1. Project skeleton, SQLite, configuration, logging, startup | ✅ Complete | `app/main.py`, `app/database/`, `app/config.py`, `app/logging_setup.py` |
| 2. Employee management and barcode generation | ✅ Complete | Employee create/edit/activate UI, sequential IDs, Code 128 PNG generation via `EmployeeService`, plus **bulk import from Excel/CSV** (`app/importer.py`, `EmployeeService.import_rows`) with duplicate skip and shift-name matching, and a **Save Import Template** control (ready templates in `examples/`) |
| 3. Shift management and attendance engine | ✅ Complete | Shift service and add/edit/activate UI, plus day/overnight validation in the dedicated attendance engine |
| 4. Kiosk UI | ✅ Complete | Large clock, ready state, accepted/rejected presentation, automatic return to ready state. The application now starts directly on a full-screen kiosk (`KioskShell`) with an on-screen ADMINISTRATOR LOGIN button that opens the admin dialog and then the admin shell; closing/locking the admin shell returns to the kiosk |
| 5. Honeywell COM/serial scanner integration | ✅ Complete | `ScannerManager` is now started from `app/main.py` with real COM listener threads and a 5 s reconnect loop. The Terminals & Scanners page shows a live per-scanner status (connecting/connected/offline) and a **Test Port** control that opens the selected serial device on a background thread; simulated Test Scanner Input remains. Physical-port validation must be done with real hardware. |
| 6. Multiple scanners and terminals | ✅ Complete | Terminals & Scanners supports add, edit, rename, enable/disable, and delete (with confirmation and cascade for terminals), baud-rate editing, a live status column, and automatic scanner-manager reload after every change |
| 7. Admin dashboard | ✅ Complete | Two rows of live summary cards (Employees, Present now, Missing clock-out, Exceptions today, Scans today, Accepted scans, Terminals, Scanners) driven by `AdminDataService.summary()`; the previous PRESENT NOW = MISSING CLOCK OUT duplicate-value bug is fixed (open sessions are split into *today → present now* and *earlier → missing clock-out*) |
| 8. Attendance reports and exceptions | ✅ Complete | Attendance and Reports share date range + employee + shift + status filters; Reports adds aggregate calculations (sessions, distinct employees, total/average worked hours, OK / missing clock-out counts) plus per-shift totals |
| 9. Excel export | ✅ Complete | Sheet-selection checkboxes, employee picker, date range and destination; export runs in a background `QThread` with an indeterminate progress bar and completion/failure notifications |
| 10. Automatic scheduled exports | ✅ Complete | Add / edit / enable-disable / run-now / delete for export jobs; weekly (weekday) and monthly (day-of-month) schedules are stored and honoured by the scheduler; **Next Run** is computed and displayed; delete confirmation included |
| 11. Authentication, backup/restore, audit logs | ✅ Complete | Secure PBKDF2 auth, first-run administrator creation/login dialog, change-password UI, audit model, readable log viewer, backup/restore with confirmation; the app boots into the kiosk and administrators sign in through the kiosk login button; a **Session** menu provides Log Out / Switch User, Lock / Return to Kiosk, full-screen **Enter Kiosk Mode** with an administrator unlock, and Exit |
| 12. Offline queue/synchronization | ✅ Complete | Durable local SQLite queue preserves failed scanner events and replays them in arrival order through the existing engine. A new Synchronization page configures `sync_enabled`, server URL, token and interval; `app/sync.SyncService` drains the offline queue and pushes unsynchronised scan events to the configured server with a last-id marker. A 30 s timer runs it when enabled; Test Connection and Synchronise Now controls included |
| 13. UI polishing | ✅ Complete | Navigation icons (Qt standard pixmaps), scrollable nav rail, sortable/alternating tables, styled dashboard cards, colour-coded actions, shared searchable data tables, dialogs, and dark theme throughout. Interface **language setting (English / Română)** in Settings with a full Romanian UI catalog (`app/i18n.py`) applied to navigation, menus, pages, tables, kiosk, and login |
| 14. Automated testing | ✅ Complete | **36 automated tests** covering core services/rules plus hardware CRUD, dashboard summary semantics, export-job frequency & next-run, Excel sheet selection, employee Excel/CSV import, LAN sync push & offline drain, database column migration, the threaded scanner-manager pipeline, offscreen UI construction, and row-action resolution. Interactive UI and physical serial tests remain manual |
| 15. PyInstaller EXE | 🟡 Partial | `build_exe.bat` is provided and the code now anchors data/log/queue paths to the executable directory when frozen (`app.config.app_dir`). A native Windows `.exe` must still be built and run on Windows (not possible on this macOS host) |
| 16. Final end-to-end test | 🟡 Partial | Required accepted IN / rejected OUT / accepted OUT sequence and Excel contents are tested end-to-end; final manual UI and packaged-Windows validation must run on Windows with a physical scanner |

## Implemented admin pages

The main application shell currently contains these pages:

1. Dashboard
2. Employees
3. Shifts
4. Attendance
5. Live Scans
6. Exceptions
7. Terminals & Scanners
8. Reports
9. Excel Export
10. Settings
11. System Logs
12. Backup / Restore
13. Automatic Exports
14. Synchronization
15. Kiosk

## Existing architecture used

No second database or attendance engine was added.

| Concern | Existing implementation used by the UI |
| --- | --- |
| Database | `app/database/database.py`, `app/database/models.py` |
| Employees | `app.services.EmployeeService` |
| Shifts | `app.services.ShiftService` |
| Attendance validation | `app.attendance.AttendanceEngine` |
| UI data queries | `app.services.AdminDataService` |
| Barcode generation | `app.barcode.generate_barcode` |
| Scanner connection | `app.scanner.ScannerManager` |
| Excel | `app.export.ExcelExporter` |
| Scheduled exports | `app.scheduler.ExportScheduler` |
| Authentication | `app.auth.AuthService` |
| Backup/restore | `app.maintenance` |

## Kiosk-first startup and the Honeywell scanner simulator

**Startup flow** — `app/main.py` no longer blocks on a login dialog. It starts the
background services (scanner threads, export scheduler, sync timer) and shows a
full-screen `KioskShell` (`app/ui/main_window.py`): the kiosk clock/status plus a
bottom **ADMINISTRATOR LOGIN** button.

- First run: the login button shows the administrator-creation dialog.
- After login: the admin shell (`MainWindow`, 15 pages) opens maximised and the kiosk is hidden.
- The admin window has an always-visible toolbar (and matching **Session** menu): **Log out → Kiosk**
  and **Close App**, plus the current administrator name.
- Session → Log Out / Switch User or Lock / Return to Kiosk (or closing the admin
  window) hides the admin shell and shows the kiosk again.
- Session → Exit or the **Close App** toolbar button closes the whole application.

**Scanner simulator** — `scanner_simulator.py` (project root) is a separate program that
simulates **one or more Honeywell scanners**, each on its own virtual serial port (POSIX pty;
com0com-style COM on Windows). A first port is created on launch; **+ Add scanner port** adds more,
so several scanners can share one terminal in Terminals & Scanners. Scans are sent as
`<barcode> + CR + LF` at 9600 baud and support **one-click batch** sending: a scan list sent in
order (optionally spread across all scanners) or the selected barcode repeated N times, paced by a
configurable delay. Configure one scanner in Terminals & Scanners per virtual port and enable it;
the app reconnects automatically and each scan flows through the real `ScannerManager` →
`AttendanceEngine` → kiosk pipeline with the correct scanner identity.

Run it with:

```zsh
python3 scanner_simulator.py
```

## Remaining work

All implementable code, UI, and automated checks are complete. Only environment-bound
manual steps remain — they require Windows and/or physical hardware and cannot be
executed on this macOS host:

1. Build `dist/AttendanceControl.exe` on Windows with `build_exe.bat` and smoke-test the packaged application (data/log/queue paths already anchor to the executable folder).
2. Connect a Honeywell scanner in USB Serial / COM mode and validate Test Port plus the live connecting/connected/offline status on real hardware.
3. Perform a final manual walk-through of all 15 pages, the Session menu (log out / switch user), and full-screen kiosk mode with the administrator unlock.

## Commands

Run the application:

```zsh
python3 -m app.main
```

Run the standalone Honeywell scanner simulator:

```zsh
python3 scanner_simulator.py
```

Run tests:

```zsh
python3 -m pytest -q
```

Build the Windows executable (on Windows):

```bat
build_exe.bat
```
