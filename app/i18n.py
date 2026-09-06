"""Lightweight UI localization (English <-> Română).

The UI is authored in English. :func:`localize_window` walks a widget tree and
swaps any text that has a Romanian entry in :data:`UI_RO`, so pages, menus,
tables, toolbars and buttons can all be re-localized at runtime (no restart).

Database content (employee names, IDs, logs) is never translated.
"""
from __future__ import annotations

CURRENT_LANGUAGE = 'en'   # 'en' or 'ro'

# English text -> Romanian (keys must match the exact English string used).
UI_RO = {
    # product / nav
    'Attendance Control — Kiosk': 'Attendance Control — Chioșc',
    'Attendance Control — Administrator Setup': 'Attendance Control — Configurare administrator',
    'Attendance Control — Admin Login': 'Attendance Control — Autentificare admin',
    'Employees': 'Angajați', 'Shifts': 'Ture', 'Attendance': 'Pontaj',
    'Live Scans': 'Scanări live', 'Exceptions': 'Excepții',
    'Terminals & Scanners': 'Terminale și scanere', 'Reports': 'Rapoarte',
    'Excel Export': 'Export Excel', 'Automatic Exports': 'Exporturi automate',
    'Settings': 'Setări', 'System Logs': 'Jurnale de sistem',
    'Backup / Restore': 'Backup / Restaurare', 'Synchronization': 'Sincronizare',
    'Kiosk': 'Chioșc', 'Dashboard': 'Panou',
    'ATTENDANCE CONTROL — DASHBOARD': 'CONTROL PONTARE — PANOU',
    'Employees scan their badge. Administrators can sign in to manage the system.':
        'Angajații scanează ecusonul. Administratorii se pot autentifica pentru a gestiona sistemul.',
    'ADMINISTRATOR LOGIN': 'AUTENTIFICARE ADMINISTRATOR',

    # Session menu / toolbar
    'Session': 'Sesiune',
    'Enter Kiosk Mode (full screen)': 'Mod chioșc (ecran întreg)',
    'Lock / Return to Kiosk': 'Blochează / Înapoi la chioșc',
    'Log Out / Switch User…': 'Deconectare / Schimbă utilizator…',
    'Exit': 'Ieșire', 'Close App': 'Închide aplicația',
    'Log out → Kiosk': 'Deconectare → Chioșc',
    'About Attendance Control': 'Despre Attendance Control',
    'Session controls': 'Comenzi sesiune',
    'Return to the kiosk screen (administrator login required to come back)':
        'Revenire la ecranul chioșcului (autentificare administrator necesară pentru revenire)',
    'Exit Attendance Control': 'Ieșire din Attendance Control',

    # shared
    'Search…': 'Caută…', 'Refresh': 'Reîmprospătează', 'record(s)': 'înregistrări',
    'All departments': 'Toate departamentele',

    # Employees page
    'Add Employee': 'Adaugă angajat', 'Edit': 'Editează',
    'Deactivate / Reactivate': 'Dezactivează / Reactivează',
    'Generate Barcode': 'Generează cod de bare',
    'Import (Excel / CSV)': 'Importă (Excel / CSV)',
    'Save Import Template': 'Salvează șablon de import',
    'Employee': 'Angajat', 'Employee ID': 'ID Angajat', 'Name': 'Nume',
    'Department': 'Departament', 'Position': 'Funcție', 'Shift': 'Tură',
    'Status': 'Status', 'First Name': 'Prenume', 'Last Name': 'Nume',
    'Employee Number': 'Număr angajat', 'Unassigned': 'Neasignat',
    'Import employees': 'Import angajați', 'Import template': 'Șablon import',
    'Save employee import template': 'Salvează șablonul de import al angajaților',
    'Spreadsheets (*.xlsx *.csv);;Excel (*.xlsx);;CSV (*.csv)': 'Foi de calcul (*.xlsx *.csv);;Excel (*.xlsx);;CSV (*.csv)',
    'Import (Excel / CSV) employees': 'Importă (Excel / CSV) angajați',

    # Shifts page
    'Add Shift': 'Adaugă tură', 'Edit Shift': 'Editează tură',
    'Activate / Deactivate': 'Activează / Dezactivează',
    'Start': 'Început', 'End': 'Sfârșit',
    'Early IN': 'Intrare timpurie', 'Earliest OUT': 'Ieșire permisă de la',
    'Name': 'Nume', 'Early IN minutes': 'Minute intrare timpurie',
    'Earliest OUT minutes': 'Minute ieșire permisă',

    # Hardware page
    'Add Terminal': 'Adaugă terminal', 'Add Scanner': 'Adaugă scanner',
    'Enable / Disable': 'Activează / Dezactivează', 'Delete': 'Șterge',
    'Test Port': 'Testează portul', 'Test Scanner Input': 'Testează scanarea',
    'Scanner ID': 'ID scanner', 'COM': 'Port COM', 'Baud': 'Baud',
    'Description': 'Descriere', 'Scanner': 'Scanner', 'Terminal': 'Terminal',
    'COM port': 'Port COM', 'Baud rate': 'Viteză (baud)', 'Enabled': 'Activ',
    'Rename Terminal': 'Redenumește terminalul', 'Terminal name': 'Nume terminal',
    'Scanner test': 'Test scanner', 'Rename': 'Redenumește',

    # Attendance / Reports
    'Apply filters': 'Aplică filtre', 'From': 'De la', 'To': 'Până la',
    'All employees': 'Toți angajații', 'All shifts': 'Toate turele',
    'Clock In': 'Intrare', 'Clock Out': 'Ieșire', 'Worked Hours': 'Ore lucrate',
    'Timestamp': 'Moment', 'Action': 'Acțiune', 'Accepted': 'Acceptat',
    'Reason': 'Motiv', 'Problem': 'Problemă', 'Details': 'Detalii',
    'Totals by shift': 'Totaluri pe tură', 'Sessions': 'Sesiuni',
    'Worked hours': 'Ore lucrate', 'Employee': 'Angajat',

    # Excel export
    'EXPORT ATTENDANCE': 'EXPORT PONTAJ', 'Destination folder': 'Folder destinație',
    'Sheets to include': 'Foi de inclus', 'EXPORT EXCEL': 'EXPORT EXCEL',
    'Attendance Summary': 'Rezumat pontaj', 'Raw Scans': 'Scanări brute',
    'All departments': 'Toate departamentele', 'Excel export': 'Export Excel',
    'Select at least one sheet.': 'Selectați cel puțin o foaie.',
    'Exporting in the background…': 'Se exportă în fundal…',
    'Export completed:': 'Export finalizat:', 'Export failed:': 'Export eșuat:',

    # Automatic exports
    'Automatic Exports': 'Exporturi automate', 'Add Export Job': 'Adaugă job export',
    'Run Selected Now': 'Rulează acum', 'Export job': 'Job export',
    'Time': 'Oră', 'Frequency': 'Frecvență', 'Schedule': 'Program',
    'Destination': 'Destinație', 'Last Run': 'Ultima rulare', 'Next Run': 'Următoarea rulare',
    'Weekday (weekly)': 'Ziua (săptămânal)', 'Day of month (monthly)': 'Ziua lunii (lunar)',
    'Destination folder': 'Folder destinație', 'Delete export job': 'Șterge job export',

    # Settings
    'SETTINGS': 'SETĂRI', 'Site name': 'Nume site', 'Language': 'Limbă',
    'English': 'Engleză', 'Română': 'Română', 'Save Settings': 'Salvează setările',
    'Change Password': 'Schimbă parola', 'Saved': 'Salvat',
    'Change Password': 'Schimbă parola', 'Current password': 'Parola curentă',
    'New password': 'Parola nouă', 'Confirm password': 'Confirmă parola',
    'Password changed': 'Parolă schimbată', 'Passwords do not match': 'Parolele nu coincid',

    # Backup
    'BACKUP / RESTORE': 'BACKUP / RESTAURARE', 'Backup / Restore': 'Backup / Restaurare',
    'Backup Database Now': 'Fă backup acum', 'Restore Database': 'Restaurare bază de date',
    'Existing backups:': 'Backup-uri existente:', 'Refresh List': 'Reîmprospătează lista',
    'Database location:': 'Locația bazei de date:',
    'Backup created:': 'Backup creat:',
    'Restore database': 'Restaurează baza de date',
    'Select database backup': 'Selectează backup baza de date',
    'SQLite databases (*.db)': 'Baze de date SQLite (*.db)',
    'Backup': 'Backup',

    # Synchronization
    'SYNCHRONIZATION': 'SINCRONIZARE',
    'Enable automatic synchronization': 'Activează sincronizarea automată',
    'Server URL': 'URL server', 'Token': 'Token', 'Interval': 'Interval',
    'Synchronise Now': 'Sincronizează acum', 'Test Connection': 'Testează conexiunea',
    'Sync failed:': 'Sincronizare eșuată:',

    # System Logs
    'System Logs': 'Jurnale de sistem', 'Entry': 'Intrare',

    # dialogs / messages
    'OK': 'OK', 'Cancel': 'Anulează', 'Save': 'Salvează',
    'Yes': 'Da', 'No': 'Nu', 'Scan': 'Scanează',

    'Create the first administrator.': 'Creează primul administrator.',
    'Administrator authentication is required.': 'Autentificarea administratorului este necesară.',
    'Username': 'Utilizator', 'Password': 'Parolă', 'Confirm password': 'Confirmă parolă',
    'Invalid username or password': 'Utilizator sau parolă incorecte',
    'Create administrator': 'Creează administrator', 'Login': 'Autentificare',
    'Administrator login': 'Autentificare administrator',
    'Unknown barcode': 'Cod de bare necunoscut',
    'Settings': 'Setări', 'Site name': 'Nume site', 'Language': 'Limbă',
    'English': 'Engleză', 'Română': 'Română', 'Save Settings': 'Salvează setările',
    'Saved': 'Salvat',
    'Change Password': 'Schimbă parola',
    'Current password': 'Parola curentă', 'New password': 'Parola nouă',
    'Passwords do not match': 'Parolele nu coincid', 'Password changed': 'Parolă schimbată',
    'Password': 'Parolă',
    'Language will be applied fully after restarting Attendance Control.':
        'Limba va fi aplicată complet după repornirea Attendance Control.',

    # session labels / kiosk
    'SYSTEM ONLINE\n\nREADY TO SCAN': 'SISTEM ONLINE\n\nGATA DE SCANARE',
    'CLOCK': 'PONTARE',
    'Session: ': 'Sesiune: ', 'Administrator: ': 'Administrator: ',
    'Logged in as: ': 'Autentificat ca: ',
    'not logged in': 'nu sunteți autentificat',
    'Employees scan their badge. Administrators can sign in to manage the system.':
        'Angajații scanează ecusonul. Administratorii se pot autentifica pentru a gestiona sistemul.',
}

# Status / small data tokens (safe to translate even inside table cells).
TOKENS_RO = {
    'YES': 'DA', 'NO': 'NU', 'ACTIVE': 'ACTIV', 'INACTIVE': 'INACTIV',
    'OK': 'OK', 'MISSING OUT': 'FĂRĂ IEȘIRE', 'READY': 'ACTIV',
    'DISABLED': 'DEZACTIVAT', 'Enabled': 'Activ', 'Disabled': 'Dezactivat',
    'Connected': 'Conectat', 'Connecting': 'Conectare', 'Offline': 'Offline',
}

# Engine reason / result codes -> Romanian (display only; stored values stay English).
REASONS_RO = {
    'UNKNOWN_BARCODE': 'COD DE BARE NECUNOSCUT',
    'INACTIVE_EMPLOYEE': 'ANGAJAT INACTIV',
    'INVALID_SHIFT': 'TURĂ INVALIDĂ',
    'DUPLICATE_SCAN': 'SCANARE DUPLICAT',
    'CLOCK_IN_TOO_EARLY': 'INTRARE PREA DEVREME',
    'CLOCK_OUT_NOT_ALLOWED': 'IEȘIRE PREA DEVREME',
    'UNKNOWN': 'NECUNOSCUT',
    'REJECTED': 'RESPINS',
    'CLOCK IN': 'INTRARE',
    'CLOCK OUT': 'IEȘIRE',
    'ACCEPTED': 'ACCEPTAT',
}

LANGUAGES = {'en': 'English', 'ro': 'Română'}

_WEEKDAYS_RO = ['Luni', 'Marți', 'Miercuri', 'Joi', 'Vineri', 'Sâmbătă', 'Duminică']
_MONTHS_RO = ['ianuarie', 'februarie', 'martie', 'aprilie', 'mai', 'iunie',
              'iulie', 'august', 'septembrie', 'octombrie', 'noiembrie', 'decembrie']


def format_kiosk_date(value) -> str:
    """Localized kiosk date (weekday, day month year)."""
    if CURRENT_LANGUAGE == 'ro':
        return f'{_WEEKDAYS_RO[value.weekday()]}, {value.day:02d} {_MONTHS_RO[value.month - 1]} {value.year}'
    return value.strftime('%A, %d %B %Y')


def set_language(language: str) -> None:
    global CURRENT_LANGUAGE
    CURRENT_LANGUAGE = 'ro' if str(language).strip().lower().startswith('ro') else 'en'


def t(text: str) -> str:
    """Translate a single exact English string when Romanian is active."""
    if CURRENT_LANGUAGE == 'ro' and text in UI_RO:
        return UI_RO[text]
    return text


def translate_token(text: str) -> str:
    if CURRENT_LANGUAGE == 'ro' and text in TOKENS_RO:
        return TOKENS_RO[text]
    return text


def reason_text(reason: str | None) -> str:
    """Localize a stored engine reason/code for display (keeps extra detail)."""
    if not reason or CURRENT_LANGUAGE != 'ro':
        return reason or ''
    code = reason.split(';')[0].strip()
    if code in REASONS_RO:
        return reason.replace(code, REASONS_RO[code], 1)
    return reason


def localize_window(widget) -> None:
    """Walk a widget tree and translate static text to the active language.

    Translates push/tool buttons, labels, check boxes, group-box titles, table
    headers, cell tokens, menus and toolbar actions. Data (names, IDs) is left alone.
    """
    if CURRENT_LANGUAGE != 'ro' or widget is None:
        return
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (QAbstractButton, QCheckBox, QComboBox,
                                   QGroupBox, QLabel, QLineEdit, QMenuBar,
                                   QTableWidget, QToolButton, QWidget)
    # PySide6 findChildren accepts a single type, so iterate per class.
    for cls in (QLabel, QCheckBox, QToolButton):
        for target in widget.findChildren(cls):
            text = target.text()
            if text and text in UI_RO:
                target.setText(UI_RO[text])
    for target in widget.findChildren(QLineEdit):
        placeholder = target.placeholderText()
        if placeholder and placeholder in UI_RO:
            target.setPlaceholderText(UI_RO[placeholder])
    for target in widget.findChildren(QGroupBox):
        title = target.title()
        if title and title in UI_RO:
            target.setTitle(UI_RO[title])
    for target in widget.findChildren(QAbstractButton):
        text = target.text()
        if text and text in UI_RO:
            target.setText(UI_RO[text])
    for table in widget.findChildren(QTableWidget):
        for column in range(table.columnCount()):
            item = table.horizontalHeaderItem(column)
            if item and item.text() in UI_RO:
                item.setText(UI_RO[item.text()])
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                if item and item.text() in TOKENS_RO:
                    item.setText(TOKENS_RO[item.text()])
    menu_bar = widget.findChild(QMenuBar) if isinstance(widget, QWidget) else None
    if menu_bar is not None:
        for action in menu_bar.actions():
            if action.text() in UI_RO:
                action.setText(UI_RO[action.text()])
            submenu = action.menu()
            if submenu is not None:
                for item in submenu.actions():
                    if item.text() in UI_RO:
                        item.setText(UI_RO[item.text()])
    for action in widget.findChildren(QAction):
        if action.text() in UI_RO:
            action.setText(UI_RO[action.text()])
    for combo in widget.findChildren(QComboBox):
        for index in range(combo.count()):
            text = combo.itemText(index)
            if text in UI_RO:
                combo.setItemText(index, UI_RO[text])
