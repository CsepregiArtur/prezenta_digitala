# Attendance Control — pagină wiki / web

Pagină de prezentare statică (HTML + CSS + JS, fără dependențe externe) pentru produsul
**Attendance Control**, cu capturi de ecran reale ale aplicației și descrieri pentru
fiecare funcție.

## Limbi — English / Română

Pagina este **bilingvă**, cu comutator în bara laterală:

- **Engleza este limba implicită** la prima deschidere.
- Comutarea se face din butoanele **English / Română** din stânga sus.
- Alegerea este reținută în `localStorage` și se reflectă în URL (`?lang=en` / `?lang=ro`).
- Poți forța o limbă direct din adresă: `index.html?lang=ro`.

## Deschidere

Deschide direct fișierul `index.html` în orice browser:

```powershell
start docs\index.html
```

Sau pornește un server local (recomandat, ca linkurile relative să fie servite corect):

```powershell
python -m http.server 8000 --directory docs
# apoi deschide http://localhost:8000/
```

## Conținut

| Fișier | Descriere |
| --- | --- |
| `index.html` | Pagina wiki completă (18 secțiuni, bilingvă) |
| `assets/wiki.css` | Stilizarea paginii (temă întunecată, responsive, print-friendly) |
| `assets/wiki.i18n.js` | Dicționarul de traduceri în **engleză** (limba implicită) |
| `assets/wiki.ro.js` | Dicționarul de traduceri în **română** |
| `assets/wiki.js` | Comutatorul de limbă + logica de aplicare |
| `screenshots/` | 20 de capturi de ecran reale, generate automat |
| `tools/capture_screenshots.py` | Generează toate capturile dintr-o bază demo |
| `tools/run_demo.py` | Pornește aplicația pe o bază demo izolată |

> Capturile de ecran arată interfața aplicației în română (capturate din aplicația reală),
> deci textele din imagini nu se schimbă odată cu comutatorul paginii.

## Structura paginii

1. Ce este Attendance Control
2. Funcționalități
3. Arhitectură
4. Ecranul de kiosk
5. Panoul administratorului
6. Galerie de ecrane (cu capturi reale)
7. Pornire rapidă
8. Schimburi
9. Rotirea săptămânală a schimburilor
10. Angajați & import din Excel/CSV
11. Coduri de bare
12. Scannere & terminale
13. Reguli de validare
14. Date, rapoarte și copii de siguranță
15. Instalare & construirea EXE
16. Depanare
17. Cum se refac capturile de ecran
18. Licență & contact

## Regenerarea capturilor de ecran

Capturile sunt generate dintr-o bază de date demonstrativă și **nu conțin date reale**.

```powershell
# toate capturile (necesită o sesiune Windows cu desktop)
.venv\Scripts\python.exe docs\tools\capture_screenshots.py

# doar anumite imagini
.venv\Scripts\python.exe docs\tools\capture_screenshots.py --only 03-dashboard

# explorează aplicația cu date demo
.venv\Scripts\python.exe docs\tools\run_demo.py --fresh
```

Scripturile lucrează exclusiv în `docs/.capture/` respectiv `.demo/`; fișierul de
producție `attendance.db` nu este atins niciodată.

---

© 2026 **Csepregi Artur**. Toate drepturile rezervate. · <https://csepregiartur.github.io>
