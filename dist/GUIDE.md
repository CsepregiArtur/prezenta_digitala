# Attendance Control — Complete User & Setup Guide
# Attendance Control — Ghid complet de utilizare și configurare

Two languages / Două limbi:

- **English** (below, first)
- **Română** (mai jos, după secțiunea în engleză)

---

# ENGLISH

## 1. Overview & the login flow

Attendance Control is a local time-tracking desktop application. Employees do not
log in — they **scan a barcode** at the kiosk. Administrators sign in with a
username and password.

When you start the app (`python3 -m app.main`), it opens **directly in kiosk mode**
(full screen, big clock). The kiosk shows only two things:

- the scan result for the last badge scanned (✓ CLOCK IN / CLOCK OUT, or ⚠ a reason),
- an **ADMINISTRATOR LOGIN** button at the bottom.

Click **ADMINISTRATOR LOGIN**:

- **First run:** the dialog asks you to create the first administrator
  (username + password, minimum 8 characters, plus confirmation).
- **Later runs:** it asks for the administrator username and password.

After a successful login the **admin window** opens. From the admin window:

- use the left **navigation** to open a page,
- use the **Session** menu or the top toolbar to **Log out → Kiosk**, **Close App**,
  or **Enter Kiosk Mode**.

Data lives in a local SQLite file (`attendance.db`) — no cloud needed.

---

## 2. First run — recommended order

1. Start the app and click **ADMINISTRATOR LOGIN** → create the administrator.
2. Go to **Shifts** and create the shifts (see section 3).
3. Go to **Employees** and add users one by one, or **import** a list from Excel/CSV
   (see section 4).
4. Generate barcodes for employees (see section 5).
5. Go to **Terminals & Scanners** and configure your scanner(s) (see section 6).
6. Test with **Test Scanner Input** or the simulator, then scan for real.

---

## 3. Set up Shifts (working conditions)

Open **Shifts** and click **Add Shift**. Each shift has:

| Field | Meaning |
| --- | --- |
| **Name** | Short label, e.g. `Morning` or `A`. Unique. |
| **Start** | When the shift starts (HH:MM). |
| **End** | When the shift ends (HH:MM). If end ≤ start it is treated as an **overnight** shift (e.g. 22:00 → 06:00). |
| **Early clock-in (min)** | How many minutes **before start** an employee may clock in. Default 60. |
| **Earliest clock-out (min)** | How many minutes **before end** an employee may clock out. Default 10. |
| **Active** | Only active shifts are used for validation (deactivate a shift to stop using it). |

**What the minutes mean (example shift A = 07:00–15:00):**

- Early clock-in 60 → the **earliest allowed clock-in** is `07:00 − 60 min = 06:00`.
  Scanning before 06:00 is rejected (`CLOCK_IN_TOO_EARLY`). There is **no "too late"**
  rejection: someone can still clock in at 13:40 if they have no open session — that is
  treated as their (late) start.
- Earliest clock-out 10 → the **earliest allowed clock-out** is `15:00 − 10 min = 14:50`.
  An OUT scan before 14:50 is rejected (`CLOCK_OUT_NOT_ALLOWED`).

**Full rule summary (one employee, one scan):**

| Situation | Result |
| --- | --- |
| Barcode does not match any employee | `UNKNOWN_BARCODE`, recorded as exception |
| Employee is deactivated | `INACTIVE_EMPLOYEE`, rejected |
| No active shift, or no shift assigned | `INVALID_SHIFT`, rejected |
| Same employee scanned within the duplicate window (~5 s) | `DUPLICATE_SCAN`, rejected |
| Clock-in earlier than start − early minutes | `CLOCK_IN_TOO_EARLY`, rejected |
| Clock-out earlier than end − earliest-out minutes | `CLOCK_OUT_NOT_ALLOWED`, rejected |
| Otherwise, with no open session | **CLOCK IN** accepted |
| Otherwise, with an open session | **CLOCK OUT** accepted |

Overnight shifts work too: for a 22:00–06:00 shift an IN at 21:30 and an OUT at
06:03 the next day are accepted.

### 3.1 Weekly shift rotation (rotating shifts)

Shifts can **rotate every week** between employees. A rotation is an ordered
cycle of shifts; every **Monday** each member moves to the next shift in the
cycle. Example with shifts `Schimb 1`, `Schimb 2`, `Schimb 3` and employees
A, B, C starting on shifts 1, 2 and 3:

| Week | A | B | C |
| --- | --- | --- | --- |
| 1 | Schimb 1 | Schimb 2 | Schimb 3 |
| 2 | Schimb 3 | Schimb 1 | Schimb 2 |
| 3 | Schimb 2 | Schimb 3 | Schimb 1 |
| 4 | Schimb 1 | Schimb 2 | Schimb 3 (cycle repeats) |

**How to set it up:**

1. On the **Shifts** page, create the shifts you want to rotate (section 3).
2. Open **Shift Rotations** and click **Add Rotation**:
   - Give the rotation a name (e.g. `Rotatie 3 ture`).
   - Build the **shift order** with **Add**, then use **Up / Down** to arrange
     it, and **Remove** to take a shift out. A rotation needs at least two shifts
     and cannot repeat the same shift.
3. Go to **Employees** and **Add Employee** / **Edit** an employee:
   - **Shift** = the employee's fixed / fallback shift.
   - **Rotation** = pick the rotation created above (or *No rotation*).
   - **Starting shift (today)** = the shift the employee is on *right now*.
     It must be part of the rotation.
   To reproduce the table above, put A on Schimb 1, B on Schimb 2 and C on
   Schimb 3 as their starting shifts on the same week.

**What changes automatically:**

- Every **Monday** the employee's effective shift advances to the previous shift
  in the list (wrapping around), so everyone works every shift in turn.
- The **Employees** list, the Excel export and **scan validation** all use the
  shift that applies to the **current week** for rotating employees; past
  attendance sessions keep the shift that was recorded when they clocked in.
- Taking an employee off the rotation (set **Rotation** to *No rotation* and
  save) returns them to their fixed **Shift**.
- **Activate / Deactivate** pauses a whole rotation without deleting it;
  deactivated members fall back to their fixed **Shift**. **Delete** removes the
  rotation and its members keep their fixed shift.

---

## 4. Set up Users (Employees)

Open **Employees**.

### 4.1 Add one user manually
Click **Add Employee** and fill in:

- **First Name**, **Last Name** (required),
- **Employee Number** (optional — your own external number; used to avoid
  duplicates during import),
- **Department**, **Position** (optional),
- **Shift** (optional — pick one of the shifts you created),
- **Rotation** and **Starting shift (today)** (optional — see section 3.1 to
  put the employee on a weekly rotating schedule).

The application assigns the internal **Employee ID** automatically
(`EMP000001`, `EMP000002`, …). **This ID is the barcode content.**

You can later **Edit**, **Deactivate / Reactivate**, or **Generate Barcode**
for a selected row.

### 4.2 Import the whole list from Excel / CSV
Instead of typing, import a whole list in one go:

1. Create your file. Two templates already exist in the project:
   - `examples/employees_import_template.xlsx`
   - `examples/employees_import_template.csv`
   You can also click **Save Import Template** on the Employees page and choose
   Excel or CSV to create your own copy anywhere.
2. Edit the file. **Columns** (header names are flexible — case/space-insensitive):

   | Column | Required | Meaning |
   | --- | --- | --- |
   | `first_name` | yes | First name |
   | `last_name` | yes | Last name |
   | `employee_number` | no | Your number; rows with an existing number are skipped as duplicates |
   | `department` | no | Department |
   | `position` | no | Position / job title |
   | `shift` | no | The shift **name** (must match a shift you created, e.g. `A`) |

   Example rows are included in the template — delete or replace them.
3. Click **Import (Excel / CSV)**, choose the file (`.xlsx` or `.csv`), and wait
   for the summary. The app reports how many were created, how many were skipped
   (employee number already exists), and any notes (e.g. a shift name that does
   not exist yet — the employee is still created, without a shift).

> Import never touches shifts — create the shifts first so the `shift` column can match.

---

## 5. Barcodes

A barcode contains **only the employee ID** (e.g. `EMP000421`) — never the name,
department or password. To generate PNG files, select an employee and click
**Generate Barcode**. Files are saved as `barcodes/EMP000421.png`. Print them and
give each employee their own badge.

---

## 6. Set up Terminals & Scanners

Open **Terminals & Scanners**. You manage two levels:

### Terminals
A terminal is a physical location (e.g. "Reception", "Gate 1"). Add one per
place where scans happen.

### Scanners
Each scanner is a Honeywell (or compatible) device in **USB Serial / COM mode**.
One terminal can have **several scanners** attached (e.g. an IN door and an OUT
door, or two doors on the same terminal).

**Add Scanner** fields:

| Field | Meaning |
| --- | --- |
| Scanner ID | Unique name, e.g. `SCAN1` — appears in Live Scans |
| Terminal | Which terminal it belongs to |
| COM port | e.g. `COM3` on Windows, `/dev/tty.usbserial-...` on macOS |
| Baud rate | Default 9600 (must match the device) |
| Enabled | Yes = the app keeps a listener thread on this port |
| Description | Free text |

**Status column** shows live connection state: `Connecting` → `Connected` /
`Offline`. If a device disconnects, the app logs it and retries every 5 seconds
automatically — you do not need to restart.

**Test Port** opens the selected scanner’s COM port on a background thread and
reports success/failure (pick a **scanner** row, not a terminal row).
**Test Scanner Input** simulates a badge scan straight through the attendance
engine (pick a real employee to see an accepted CLOCK IN).

### No hardware? Use the simulator
Run (a separate window, in another terminal):

```zsh
python3 scanner_simulator.py
```

1. A first **scanner port** is created automatically; click **+ Add scanner port**
   for each extra scanner (to simulate several scanners on one terminal).
2. In the app, add one scanner per device path shown (COM port = that path).
3. Send scans: pick employee + **Scan now**, or use the **batch** controls
   (**Send list** / repeat N times, with a delay; tick **Spread across scanners**
   to rotate).

Each virtual scan flows through the same real pipeline, so the kiosk and
**Live Scans** react exactly as with hardware. On Windows use a com0com-style
driver and enter the sender COM for each added port.

---

## 7. Day-to-day operation

- An employee scans their badge at the kiosk.
- The kiosk briefly shows the result: **✓ CLOCK IN**, **✓ CLOCK OUT**, or a
  rejection reason, then returns to **READY TO SCAN**.
- The app decides IN/OUT from whether the employee has an **open session**.
- Every attempt is stored in **Live Scans**; rejected ones also appear in
  **Exceptions**.

### Duplicates
A second scan by the same employee within the duplicate window (5 seconds by
default in `config.json`) is rejected as a duplicate — this prevents one badge
being scanned twice by accident.

---

## 8. Working with the data

| Page | What it shows |
| --- | --- |
| Dashboard | Live summary cards + the latest scans (auto-refresh) |
| Live Scans | Every scan attempt, newest first |
| Attendance | Completed sessions with date/employee/shift/status filters |
| Exceptions | Every rejected scan (unknown, inactive, too early, etc.) |
| Reports | Attendance with filters + totals (sessions, hours, per-shift) |
| Excel Export | Write a 5-sheet `.xlsx` (choose sheets, date range, employee) |
| Automatic Exports | Schedule exports daily / weekly / monthly |
| System Logs | The application log file |
| Synchronization | Offline queue + LAN/server push settings |
| Backup / Restore | Copy or restore the database |

---

## 9. Scheduled exports & synchronization

- **Automatic Exports**: add a job with a time, destination folder and frequency
  (daily / weekly weekday / monthly day). The app runs enabled jobs in the
  background; the **Next Run** column shows when it will fire.
- **Synchronization**: events that cannot be saved are kept in a durable local
  queue and replayed automatically. You can also enable a server URL so every new
  scan is pushed to a central server (several kiosks share one database).

---

## 10. Backup / restore

- **Backup Database Now** copies `attendance.db` into `backup/` with a timestamped name.
- **Restore Database** asks for a `.db` file, first backs up the current database
  automatically (safety), then replaces the active one. Restart afterwards.

---

## 11. Session, kiosk and closing

- **Session → Log out / Switch User** returns to the kiosk (or lets another
  administrator sign in). **Log out → Kiosk** / **Lock / Return to Kiosk** hides the
  admin window and shows the kiosk again.
- **Close App** / **Session → Exit** closes the whole application.
- **Enter Kiosk Mode** previews the full-screen kiosk from the admin window; the
  **Administrator login** button there unlocks back to the admin window.

---

### Language — English / Română
Open **Settings**, choose the interface language (**English** or **Română**), and click **Save Settings**.
The choice is remembered and is applied completely after you restart Attendance Control.

The main screens (navigation, menus, pages, tables, kiosk, login) are translated; employee names and
other data you enter stay as typed.

## 12. Troubleshooting

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError: PySide6` | Run `python3 -m pip install -r requirements.txt` from the project folder. |
| Kiosk shows `UNKNOWN_BARCODE` | The scanned ID is not an employee (or the employee was removed). Create the employee / print the correct barcode. |
| Scan rejected `DUPLICATE_SCAN` | Same employee scanned twice within ~5 s — wait and scan again. |
| Scan rejected `CLOCK_IN_TOO_EARLY` | Too early: earliest clock-in = shift start − early minutes. |
| Scan rejected `CLOCK_OUT_NOT_ALLOWED` | Too early to clock out: earliest clock-out = shift end − earliest-out minutes. |
| Scanner shows `Offline` | Check COM path, baud, driver, and that no other program opened the port. The app retries every 5 s. |
| “Select a row first” | Click a row in the table first, then the button. |

---

# ROMÂNĂ

## 1. Prezentare generală și fluxul de autentificare

Attendance Control este o aplicație desktop locală de pontaj. Angajații **nu se
autentifică** — ei **scanează un cod de bare** la chioșc. Administratorii se
autentifică cu utilizator și parolă.

La pornire (`python3 -m app.main`) aplicația se deschide **direct în modul chioșc**
(pe tot ecranul, cu ceas mare). Chioșcul afișează doar:

- rezultatul ultimei scanări (✓ INTRARE / IEȘIRE, sau ⚠ un motiv),
- un buton **ADMINISTRATOR LOGIN** în partea de jos.

Apăsați **ADMINISTRATOR LOGIN**:

- **La prima rulare:** dialogul vă cere să creați primul administrator
  (utilizator + parolă, minim 8 caractere, plus confirmare).
- **La rulările următoare:** cere utilizatorul și parola administratorului.

După autentificare se deschide **fereastra de administrare**. Din ea:

- folosiți **navigarea** din stânga pentru a deschide o pagină,
- folosiți meniul **Session** sau bara de sus pentru **Log out → Kiosk**,
  **Close App** sau **Enter Kiosk Mode**.

Datele sunt stocate local într-un fișier SQLite (`attendance.db`) — nu e nevoie de cloud.

---

## 2. Prima rulare — ordinea recomandată

1. Porniți aplicația și apăsați **ADMINISTRATOR LOGIN** → creați administratorul.
2. Deschideți **Shifts** și creați turele (vezi secțiunea 3).
3. Deschideți **Employees** și adăugați utilizatorii unul câte unul, sau
   **importați** o listă din Excel/CSV (vezi secțiunea 4).
4. Generați codurile de bare pentru angajați (vezi secțiunea 5).
5. Deschideți **Terminals & Scanners** și configurați scanerele (vezi secțiunea 6).
6. Testați cu **Test Scanner Input** sau cu simulatorul, apoi scanați real.

---

## 3. Configurarea turelor (condițiile de lucru)

Deschideți **Shifts** și apăsați **Add Shift**. Fiecare tură are:

| Câmp | Semnificație |
| --- | --- |
| **Name** | Etichetă scurtă, ex. `Dimineață` sau `A`. Unică. |
| **Start** | Când începe tura (HH:MM). |
| **End** | Când se termină tura (HH:MM). Dacă sfârșit ≤ început, tura este tratată ca **peste noapte** (ex. 22:00 → 06:00). |
| **Early clock-in (min)** | Cu câte minute **înainte de start** poate intra un angajat. Implicit 60. |
| **Earliest clock-out (min)** | Cu câte minute **înainte de final** poate ieși un angajat. Implicit 10. |
| **Active** | Doar turele active sunt folosite la validare (dezactivați o tură pentru a nu o mai folosi). |

**Ce înseamnă minutele (exemplu tură A = 07:00–15:00):**

- Early clock-in 60 → **cea mai devreme intrare permisă** este `07:00 − 60 min = 06:00`.
  Scanarea înainte de 06:00 este respinsă (`CLOCK_IN_TOO_EARLY`). **Nu există
  respingere „prea târziu”**: cineva poate intra și la 13:40 dacă nu are o sesiune
  deschisă — e tratat ca început (întârziat) al turei.
- Earliest clock-out 10 → **cea mai devreme ieșire permisă** este `15:00 − 10 min = 14:50`.
  O scanare de ieșire înainte de 14:50 este respinsă (`CLOCK_OUT_NOT_ALLOWED`).

**Rezumatul complet al regulilor (un angajat, o scanare):**

| Situație | Rezultat |
| --- | --- |
| Codul de bare nu corespunde niciunui angajat | `UNKNOWN_BARCODE`, înregistrat ca excepție |
| Angajat dezactivat | `INACTIVE_EMPLOYEE`, respins |
| Fără tură activă sau fără tură asignată | `INVALID_SHIFT`, respins |
| Același angajat scanat în fereastra de duplicate (~5 s) | `DUPLICATE_SCAN`, respins |
| Intrare mai devreme de start − minutele de early | `CLOCK_IN_TOO_EARLY`, respins |
| Ieșire mai devreme de final − minutele de earliest-out | `CLOCK_OUT_NOT_ALLOWED`, respins |
| Altfel, fără sesiune deschisă | **INTRARE (CLOCK IN)** acceptată |
| Altfel, cu sesiune deschisă | **IEȘIRE (CLOCK OUT)** acceptată |

Turele peste noapte funcționează: pentru o tură 22:00–06:00, o intrare la 21:30 și
o ieșire la 06:03 a doua zi sunt acceptate.

### 3.1 Rotația săptămânală a turelor (ture rotative)

Turele pot **să se rotească săptămânal** între angajați. O rotație este un ciclu
ordonat de ture; în fiecare **luni** fiecare membru trece la tura următoare din
ciclu. Exemplu cu turele `Schimb 1`, `Schimb 2`, `Schimb 3` și angajații A, B, C
care pornesc pe turele 1, 2 și 3:

| Săptămâna | A | B | C |
| --- | --- | --- | --- |
| 1 | Schimb 1 | Schimb 2 | Schimb 3 |
| 2 | Schimb 3 | Schimb 1 | Schimb 2 |
| 3 | Schimb 2 | Schimb 3 | Schimb 1 |
| 4 | Schimb 1 | Schimb 2 | Schimb 3 (ciclul se repetă) |

**Cum se configurează:**

1. Pe pagina **Shifts**, creați turele pe care vreți să le rotiți (secțiunea 3).
2. Deschideți **Shift Rotations** și apăsați **Add Rotation**:
   - Dați un nume rotației (ex. `Rotatie 3 ture`).
   - Construiți **ordinea turelor** cu **Add**, apoi aranjați cu **Up / Down**
     și scoateți cu **Remove**. O rotație are nevoie de cel puțin două ture și nu
     poate repeta aceeași tură.
3. Mergeți la **Employees** și **Add Employee** / **Edit** un angajat:
   - **Shift** = tura fixă / de rezervă a angajatului.
   - **Rotation** = alegeți rotația creată mai sus (sau *No rotation*).
   - **Starting shift (today)** = tura pe care angajatul o are *acum*. Trebuie să
     facă parte din rotație.
   Pentru a reproduce tabelul de mai sus, puneți pe A pe Schimb 1, pe B pe
   Schimb 2 și pe C pe Schimb 3 ca ture de pornire, în aceeași săptămână.

**Ce se schimbă automat:**

- În fiecare **luni**, tura efectivă a angajatului avansează la tura anterioară
  din listă (cu revenire la capăt), astfel încât toată lumea lucrează pe rând
  fiecare tură.
- Lista **Employees**, exportul Excel și **validarea scanărilor** folosesc tura
  care se aplică în **săptămâna curentă** pentru angajații rotativi; sesiunile de
  pontaj din trecut păstrează tura înregistrată la intrare.
- Scoaterea unui angajat de pe rotație (setați **Rotation** pe *No rotation* și
  salvați) îl readuce la **Shift**-ul fix.
- **Activate / Deactivate** pune pe pauză întreaga rotație fără să o șteargă;
  membrii dezactivați revin la **Shift**-ul fix. **Delete** șterge rotația, iar
  membrii rămân cu tura lor fixă.

---

## 4. Configurarea utilizatorilor (Employees)

Deschideți **Employees**.

### 4.1 Adăugare manuală
Apăsați **Add Employee** și completați:

- **First Name**, **Last Name** (obligatorii),
- **Employee Number** (opțional — numărul vostru extern; folosit să evitați
  duplicatele la import),
- **Department**, **Position** (opționale),
- **Shift** (opțional — alegeți una dintre turele create),
- **Rotation** și **Starting shift (today)** (opțional — vezi secțiunea 3.1
  pentru a pune angajatul pe un program rotativ săptămânal).

Aplicația atribuie automat **Employee ID** intern (`EMP000001`, `EMP000002`, …).
**Acest ID este conținutul codului de bare.**

Ulterior puteți **Edit**, **Deactivate / Reactivate** sau **Generate Barcode**
pentru rândul selectat.

### 4.2 Importul întregii liste din Excel / CSV
În loc să tastați, importați toată lista dintr-o dată:

1. Creați fișierul. Există deja două șabloane în proiect:
   - `examples/employees_import_template.xlsx`
   - `examples/employees_import_template.csv`
   Puteți apăsa și **Save Import Template** pe pagina Employees și alege Excel sau
   CSV ca să creați o copie oriunde.
2. Editați fișierul. **Coloanele** (anteturile sunt flexibile — nu contează
   majusculele/spațiile):

   | Coloană | Obligatorie | Semnificație |
   | --- | --- | --- |
   | `first_name` | da | Prenume |
   | `last_name` | da | Nume |
   | `employee_number` | nu | Numărul vostru; rândurile cu număr existent sunt sărite ca duplicate |
   | `department` | nu | Departament |
   | `position` | nu | Funcția |
   | `shift` | nu | **Numele** turei (trebuie să corespundă unei ture create, ex. `A`) |

   Șablonul conține rânduri exemplu — ștergeți-le sau înlocuiți-le.
3. Apăsați **Import (Excel / CSV)**, alegeți fișierul (`.xlsx` sau `.csv`) și
   așteptați rezumatul. Aplicația raportează câți au fost creați, câți au fost
   săriți (număr existent) și eventualele observații (ex. un nume de tură care nu
   există încă — angajatul se creează oricum, fără tură).

> Importul nu atinge turele — creați întâi turele ca coloana `shift` să poată
> corespunde.

---

## 5. Codurile de bare

Codul de bare conține **doar ID-ul angajatului** (ex. `EMP000421`) — niciodată
numele, departamentul sau parola. Pentru a genera fișierele PNG, selectați un
angajat și apăsați **Generate Barcode**. Fișierele sunt salvate ca
`barcodes/EMP000421.png`. Printați-le și dați fiecărui angajat ecusonul lui.

---

## 6. Configurarea terminalelor și scanerelor

Deschideți **Terminals & Scanners**. Administrați două niveluri:

### Terminale
Un terminal este o locație fizică (ex. „Recepție”, „Poarta 1”). Adăugați câte
unul pentru fiecare loc unde au loc scanări.

### Scanere
Fiecare scanner este un dispozitiv Honeywell (sau compatibil) în modul
**USB Serial / COM**. Un terminal poate avea **mai multe scanere** atașate (ex.
o ușă de intrare și una de ieșire, sau două uși pe același terminal).

**Add Scanner** — câmpuri:

| Câmp | Semnificație |
| --- | --- |
| Scanner ID | Nume unic, ex. `SCAN1` — apare în Live Scans |
| Terminal | Terminalul din care face parte |
| COM port | ex. `COM3` pe Windows, `/dev/tty.usbserial-...` pe macOS |
| Baud rate | Implicit 9600 (trebuie să corespundă dispozitivului) |
| Enabled | Da = aplicația ține un fir de ascultare pe acest port |
| Description | Text liber |

**Coloana Status** arată starea live: `Connecting` → `Connected` / `Offline`.
Dacă un dispozitiv se deconectează, aplicația înregistrează și reîncearcă automat
la fiecare 5 secunde — nu trebuie să reporniți.

**Test Port** deschide portul COM al scanerului selectat pe un fir de fundal și
raportează succes/eroare (alegeți un rând de **scanner**, nu un rând de terminal).
**Test Scanner Input** simulează o scanare direct prin motorul de pontaj (alegeți
un angajat real ca să vedeți o INTRARE acceptată).

### Fără hardware? Folosiți simulatorul
Rulați (o fereastră separată, în alt terminal):

```zsh
python3 scanner_simulator.py
```

1. Un prim **port de scanner** se creează automat; apăsați **+ Add scanner port**
   pentru fiecare scanner suplimentar (pentru a simula mai multe scanere pe un terminal).
2. În aplicație adăugați câte un scanner pentru fiecare cale afișată (COM port = acea cale).
3. Trimiteți scanări: alegeți angajat + **Scan now**, sau folosiți comenzile de
   **batch** (**Send list** / repetare de N ori, cu întârziere; bifați
   **Spread across scanners** pentru rotație).

Fiecare scanare virtuală trece prin aceeași conductă reală, deci chioșcul și
**Live Scans** reacționează exact ca la hardware. Pe Windows folosiți un driver de
tip com0com și introduceți COM-ul expeditor pentru fiecare port adăugat.

---

## 7. Operarea zilnică

- Angajatul scanează ecusonul la chioșc.
- Chioșcul afișează scurt rezultatul: **✓ CLOCK IN**, **✓ CLOCK OUT** sau un motiv
  de respingere, apoi revine la **READY TO SCAN**.
- Aplicația decide INTRARE/IEȘIRE după dacă angajatul are o **sesiune deschisă**.
- Fiecare încercare este salvată în **Live Scans**; cele respinse apar și în
  **Exceptions**.

### Duplicate
O a doua scanare a aceluiași angajat în fereastra de duplicate (5 secunde implicit,
în `config.json`) este respinsă ca duplicat — previne scanarea accidentală de două ori.

---

## 8. Lucrul cu datele

| Pagină | Ce afișează |
| --- | --- |
| Dashboard | Carduri rezumat live + ultimele scanări (auto-reîmprospătare) |
| Live Scans | Fiecare scanare, cea mai recentă prima |
| Attendance | Sesiuni finalizate cu filtre dată/angajat/tură/status |
| Exceptions | Fiecare scanare respinsă (necunoscută, inactivă, prea devreme etc.) |
| Reports | Pontaj cu filtre + totaluri (sesiuni, ore, pe tură) |
| Excel Export | Scrie un `.xlsx` cu 5 foi (alegeți foile, intervalul, angajatul) |
| Automatic Exports | Programează exporturi zilnic / săptămânal / lunar |
| System Logs | Fișierul de log al aplicației |
| Synchronization | Coada offline + setări de sincronizare LAN/server |
| Backup / Restore | Copiază sau restaurează baza de date |

---

## 9. Exporturi programate și sincronizare

- **Automatic Exports**: adăugați un job cu oră, folder destinație și frecvență
  (zilnic / săptămânal cu ziua / lunar cu ziua). Aplicația rulează joburile active
  în fundal; coloana **Next Run** arată când va rula.
- **Synchronization**: evenimentele care nu pot fi salvate sunt păstrate într-o
  coadă locală durabilă și redate automat. Puteți activa și un URL de server ca
  fiecare scanare nouă să fie trimisă către un server central (mai multe chioșcuri
  împart o singură bază de date).

---

## 10. Backup / restaurare

- **Backup Database Now** copiază `attendance.db` în `backup/` cu nume cu dată/oră.
- **Restore Database** cere un fișier `.db`, face automat mai întâi o copie de
  siguranță a bazei curente, apoi o înlocuiește. Reporniți după restaurare.

---

## 11. Sesiune, chioșc și închidere

- **Session → Log out / Switch User** revine la chioșc (sau lasă alt administrator
  să se autentifice). **Log out → Kiosk** / **Lock / Return to Kiosk** ascunde
  fereastra de administrare și arată din nou chioșcul.
- **Close App** / **Session → Exit** închide întreaga aplicație.
- **Enter Kiosk Mode** previzualizează chioșcul pe tot ecranul din fereastra de
  administrare; butonul **Administrator login** de acolo deblochează înapoi.

---

### Limbă — Română / English
Deschideți **Settings**, alegeți limba interfeței (**Română** sau **English**) și apăsați
**Save Settings**. Alegerea este salvată și se aplică complet după repornirea Attendance Control.

Ecranele principale (navigare, meniuri, pagini, tabele, chioșc, autentificare) sunt traduse;
numele angajaților și alte date introduse rămân așa cum au fost scrise.

## 12. Depanare

| Problemă | Soluție |
| --- | --- |
| `ModuleNotFoundError: PySide6` | Rulați `python3 -m pip install -r requirements.txt` din folderul proiectului. |
| Chioșcul arată `UNKNOWN_BARCODE` | ID-ul scanat nu este un angajat (sau a fost șters). Creați angajatul / printați codul corect. |
| Scanare respinsă `DUPLICATE_SCAN` | Același angajat scanat de două ori în ~5 s — așteptați și scanați din nou. |
| Scanare respinsă `CLOCK_IN_TOO_EARLY` | Prea devreme: intrarea cea mai devreme = startul turei − minutele de early. |
| Scanare respinsă `CLOCK_OUT_NOT_ALLOWED` | Prea devreme pentru ieșire: ieșirea cea mai devreme = finalul turei − minutele de earliest-out. |
| Scannerul arată `Offline` | Verificați calea COM, baud, driverul și că niciun alt program nu a deschis portul. Aplicația reîncearcă la fiecare 5 s. |
| „Select a row first” | Apăsați întâi pe un rând din tabel, apoi pe buton. |
