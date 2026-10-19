# Windows-11-Fork von typesafe-computer-use: Arbeitsanweisung für Claude Code

Diese Datei ergänzt `AGENTS.md` und `VISION.md` und ersetzt sie nicht. `CLAUDE.md` lädt diese beiden schon über `@AGENTS.md` und `@VISION.md`. Damit diese Datei ebenfalls geladen wird, steht in `CLAUDE.md` zusätzlich die Zeile `@WINDOWS-FORK.md`. Bei Widerspruch gilt `AGENTS.md`, vor allem die Regel zur Kontrolle über den Rechner (Abschnitt 3).

## 1. Kontext

- Repo: Fork `kumal/typesafe-computer-use-win11` von `awlevin/typesafe-computer-use`. Der Fork gehört dem Nutzer. Hier darf frei aufgebaut werden, aber in kleinen, prüfbaren Schritten.
- Rechner: Windows 11 mit VS Code (Claude Code) und Visual Studio. Es gibt keinen Mac. Linux ist später denkbar.
- Ziel 1: Ein Computer-Use-Tool, das unter Windows 11 zuverlässig läuft und Windows-eigene Technik nutzt: UI Automation, `SendInput`, Windows.Media.Ocr.
- Ziel 2: Jev für schnelle Entscheidungen bei Browser-, GUI- und PC-Steuerung einsetzen.
- Ausblick (jetzt nicht anfangen, siehe Abschnitt 10): Das Tool soll später ein Baustein einer eigenen Windows-App werden.
- Sprache: Antworten an den Nutzer auf Deutsch. Code, Kommentare, Docstrings, Commit-Messages und Doku im Repo auf Englisch, wie im Upstream.

## 2. Was Jev ist

Jev ist TypeSafes gehostetes Entscheidungsmodell, also eine HTTP-API mit `TYPESAFE_API_KEY`. Es ist weder ein lokales Programm noch ein Protokoll. Es beantwortet typisierte Fragen (`Choice` über bis zu 255 Optionen) mit einer Wahrscheinlichkeitsverteilung und einer Konfidenz und generiert keinen Text. Das Projekt folgt daraus einem festen Prinzip (Details in `VISION.md`): Der Klassifikator wählt, Code bestimmt Fakten, das Schreibmodell schreibt nur Freitext. Alles, was ein Modell herleiten müsste (Datum, Fokus, saubere URL), wird in Code berechnet und als Zustand übergeben. Neue Logik gehört in diese Richtung, nicht ins Modell.

## 3. Regel Nr. 1: Den Rechner nie ohne Freigabe übernehmen

Das Tool steuert die echte Maus und Tastatur. Der Nutzer arbeitet oft gleichzeitig am selben Rechner. Frage vor jedem der folgenden Schritte nach, nenne den genauen Befehl und warte auf Zustimmung. Eine Zustimmung gilt nur für diesen einen Befehl:

- das Projekt auf diesem Rechner ausführen: `clicker`, `clicker-inspect`, `uv run python -m typesafe_computer_use ...` oder ein Skript, das `windows.py` importiert und aufruft
- alles, was die Maus bewegt, Tasten drückt, klickt, scrollt oder tippt (`SendInput`, `SetCursorPos`)
- Programme oder Fenster starten, aktivieren oder schließen sowie URLs und Dateien öffnen (`Start-Process`, `start`, `os.startfile`, `webbrowser.open`, `SetForegroundWindow`)
- einen Browser starten und alles, was per CDP mit einem Browser spricht
- Bildschirmaufnahmen jeder Art (`ImageGrab`)
- UI-Automation-Aktionen (`Invoke`, `SetValue`, `SetFocus`)
- Docker-Container außer der Sandbox und Anfragen an lokale Modellserver (Ollama, LM Studio)
- alles, was erhöhte Rechte braucht, zum Beispiel die OCR-Sprachpakete in Abschnitt 6. Das macht der Nutzer selbst.

Ohne Nachfrage erlaubt: `git`, `uv`, `ruff`, die Offline-Tests, `scripts/sandbox` (hat einen eigenen Rechner), normale CLI-Befehle wie `gh`. Befehle, die Cloud-Ressourcen anlegen oder löschen oder Geld kosten, brauchen ebenfalls ein Ja.

Wenn du Subagenten startest, gib ihnen diese Regel wörtlich mit.

Starte weder VS Code noch Claude Code mit Administratorrechten für dieses Projekt. Windows blockiert Eingaben eines Prozesses ohne Adminrechte in Fenster mit Adminrechten (UIPI) und meldet das nicht als Fehler.

## 4. Architektur in Kürze

Maßgeblich ist `docs/layout.md`. Das Wichtigste für Windows:

- `typesafe_computer_use/platform_adapter.py` wählt den Adapter: `windows.py` unter Windows, sonst `macos.py`. `Desktop` benennt, was beide bereitstellen.
- `windows.py` ist das einzige Modul, das `pywin32`, `uiautomation`, `winocr` und `SendInput` anfasst. Die reinen Regeln darin (Rollennamen, was als klickbar gilt, Prozess-zu-App-Zuordnung, Eingabeereignisse) sind einfache Funktionen und lassen sich ohne Windows testen.
- `ax_walk.py` ist der begrenzte Baumlauf durch den Accessibility-Tree, geteilt von beiden Adaptern. UI Automation wird dafür auf das gemeinsame `AX*`-Vokabular abgebildet (`CONTROL_TYPE_TO_ROLE`).
- `perception.py`, `decide.py`, `writer.py`, `actions.py`, `runner.py`, `report.py`: Wahrnehmung, die drei `Choice`-Fragen (Art der Aktion, Element, Seite), Schreibmodell, Aktionen, Schrittschleife, Run-Ordner.
- `browser/` ist ein optionales Backend über Chrome DevTools: DOM statt OCR, keine Bildschirmberechtigung. Es ist unabhängig vom Plattform-Adapter.
- `tests/` testet reine Logik. `tests/world.py` ist ein simulierter Computer, `tests/test_scenarios.py` hat Aufgaben steigender Schwierigkeit darauf.

Weitere Doku: `docs/how-a-step-works.md`, `docs/run-folder.md`, `docs/browser-backend.md`, `docs/writer-endpoints.md`, `docs/known-limits.md`, `docs/windows.md`.

## 5. Stand des Windows-Adapters

Laut `docs/windows.md` ist er experimentell und unter Windows ungetestet. Die CI prüft nur die reinen Regeln auf macOS und Linux. Behaupte also nie, etwas funktioniere unter Windows, solange es nicht auf dem Rechner des Nutzers gelaufen ist. Sage stattdessen, was du erwartest und was der Nutzer prüfen soll.

Unterschiede zu macOS:

- OCR liest nur Englisch (`OCR_LANGUAGE = "en"`) und liefert keine Konfidenz, jede Zeile gilt als sicher (`OCR_CONFIDENCE = 1.0`).
- Eine App ist ihr Prozess. `activate` vergleicht den Namen der ausführbaren Datei exakt (`notepad.exe`) oder einen bekannten Browser über den Produktnamen (`Google Chrome` ist `chrome.exe`). Fenstertitel zählen nie.
- Ein Klick liest die Mausposition zurück und bricht den Lauf ab, wenn der Zeiger das Ziel nicht erreicht hat (UAC-Abfrage, Sperrbildschirm).
- Die Browser-URL wird aus der Adressleiste gelesen. Chrome und Edge zeigen sie ohne Schema.
- Nur der primäre Monitor wird erfasst. "Zurück" ist Alt+Links statt Cmd+[.
- Per-Monitor-DPI-Awareness wird beim Import gesetzt, ein Bildschirmpunkt ist deshalb gleich einem Capture-Pixel (`display_scale` ist 1.0).
- Text wird als Unicode-Zeichen getippt, unabhängig vom Tastaturlayout.

## 6. Setup auf Windows 11 (PowerShell)

Voraussetzungen: `uv`, Python 3.12 oder neuer.

```powershell
git clone https://github.com/kumal/typesafe-computer-use-win11
cd typesafe-computer-use-win11
uv sync --python 3.12
Copy-Item .env.example .env   # TYPESAFE_API_KEY eintragen, nie committen
```

Einmalig, vom Nutzer selbst, in einer PowerShell als Administrator:

```powershell
Add-WindowsCapability -Online -Name "Language.OCR~~~en-US~0.0.1.0"
# Für deutsche Oberflächen zusätzlich (gleiches Namensmuster, nicht geprüft):
Add-WindowsCapability -Online -Name "Language.OCR~~~de-DE~0.0.1.0"
```

Umgebungsvariablen (`.env` im Repo-Root, von allen Einstiegspunkten gelesen):

| Variable | Pflicht | Zweck |
| --- | --- | --- |
| `TYPESAFE_API_KEY` | ja | jede Entscheidung |
| `ANTHROPIC_API_KEY` | nein | `type_text`, vom Schreibmodell vorgeschlagene URLs, Schlussantwort |
| `CLICKER_EMAIL` | nein | aktiviert die Aktion `type_email` |
| `CLICKER_BROWSER` | nein | Standard `Google Chrome` |

Andere Schreibmodelle (OpenAI-kompatible Endpunkte, LM Studio, Ollama) stehen in `docs/writer-endpoints.md`.

Upstream-Abgleich:

```powershell
git remote add upstream https://github.com/awlevin/typesafe-computer-use
git fetch upstream
git merge upstream/main
```

## 7. Befehle

Ohne Nachfrage erlaubt:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Nur mit Freigabe (Abschnitt 3):

```powershell
uv run clicker "<goal>"                  # Trockenlauf, ein Schritt, gibt nur aus
uv run clicker "<goal>" --act            # steuert den Rechner
uv run clicker-inspect "<goal>"          # Capture plus annotierter Screenshot
uv run python -m typesafe_computer_use ... # falls eine Richtlinie clicker.exe blockiert
```

Abbrechen: Strg+C im Terminal, oder die Maus in die obere linke Bildschirmecke schieben. Vor einem Lauf das Terminal leeren, denn sein Text ist OCR-Eingabe.

Jeder Lauf schreibt `runs/<Zeitstempel>/` mit `run.log`, `run.json`, Screenshots und den gesendeten Payloads. Das ist der bevorzugte Weg zur Fehleranalyse: Den Ordner offline lesen und, soweit freigegeben, einen gespeicherten Schritt per `--image` wieder abspielen. Die Ordner enthalten Bilder des echten Bildschirms. Nie committen, nie ungeprüft in Issues einfügen, und mit `.gitignore` abgleichen, ob `.env` und `runs/` ausgeschlossen sind.

## 8. Offene Aufgaben (nach Priorität)

Arbeite sie einzeln ab, je Aufgabe ein Commit. Der Nutzer macht zuerst den Trockenlauf auf seinem Rechner und liefert Log oder Run-Ordner. Aufgabe 1 hat Vorrang vor allem anderen.

1. **Ausgangslage klären.** Nach dem ersten echten Lauf `run.log` und `run.json` lesen und die tatsächlichen Fehler auflisten, bevor etwas geändert wird. Erst dann entscheiden, ob die Aufgaben 2 bis 7 nötig sind.
2. **Adressleiste in `browser_url()` erkennen.** Die Regex `(?i)address` trifft nur den englischen Namen. In deutschen Chrome- und Edge-Fenstern heißt das Feld meines Wissens "Adress- und Suchleiste", in Firefox "Suchen oder Adresse eingeben". Vorschlag: `(?i)add?ress`. Das Muster in eine Modulkonstante ziehen und mit einem reinen Test gegen diese drei Namen absichern. Das Ergebnis am echten Browser vom Nutzer prüfen lassen.
3. **OCR-Sprache konfigurierbar machen.** Den Wert von `OCR_LANGUAGE` über eine Umgebungsvariable überschreibbar machen. Namen und Stil an `config.py` anpassen. Der Standard bleibt `"en"`. In `docs/windows.md` dokumentieren, dass für jede Sprache das passende Sprachpaket installiert sein muss.
4. **Test-Guard für Windows-Aufrufe.** `tests/conftest.py` lässt jeden Aufruf scheitern, der den Rechner berührt. Prüfen, ob die Windows-Aufrufe abgedeckt sind: `SendInput`, `SetCursorPos`, `ImageGrab.grab`, `os.startfile`, `subprocess.Popen`, `webbrowser.open`, `SetForegroundWindow`, UI-Automation-Aktionen. Lücken im selben Commit schließen. Den Guard nie abschwächen.
5. **CI unter Windows.** In `.github/workflows` einen Job mit `windows-latest` ergänzen, der `ruff` und die reinen Tests ausführt und damit auch prüft, dass `windows.py` importierbar ist. Die bestehende CI bleibt unverändert.
6. **Adminrechte des Zielfensters erkennen.** Läuft das Zielfenster mit Adminrechten, endet der Lauf mit einer klaren Meldung, statt dass Klicks wirkungslos bleiben. Erst als kleiner Entwurf vorlegen, die Umsetzung braucht Windows-API-Kenntnis (Token-Elevation über `pywin32`).
7. **Fokuswechsel in `activate()`.** Windows verweigert `SetForegroundWindow` manchmal. Der Code prüft das bereits und gibt dann `False` zurück. Nur ändern, wenn es in echten Läufen auftritt.

Zurückgestellt, bis echte Läufe es verlangen: Lücken in `CONTROL_TYPE_TO_ROLE` (aktuell 15 Control-Typen), mehrere Monitore.

## 9. Arbeitsweise und Konventionen

- Windows-spezifischer Code gehört in `windows.py`, `docs/windows.md` und die Tests. Gemeinsame Module nie mit Windows-Importen belasten und nicht umformatieren. So bleibt der Abgleich mit dem Upstream einfach.
- Reine Regeln als einfache Funktionen schreiben, die ohne Windows testbar sind. Neue Aufrufe, die den Rechner berühren, werden im selben Commit in den Test-Guard aufgenommen.
- Der Adapter hat dieselben Funktionsnamen und Signaturen wie `macos.py` (siehe `Desktop` in `platform_adapter.py`).
- Python 3.12, `ruff` mit Zeilenlänge 130 und den Regeln `E, F, I, B, UP, SIM, RUF`. Abhängigkeiten sind exakt gepinnt (`==`). Neue Abhängigkeiten nur nach Rückfrage, danach `uv.lock` aktualisieren.
- Kleine Commits, Branches nach dem Muster `win11/<thema>`, kein Force-Push auf `main`. Details zu Pull Requests in `CONTRIBUTING.md`.
- Fehlerberichte an den Upstream enthalten den Run-Ordner, aber erst nach Durchsicht auf Privates.

Fertig ist eine Änderung, wenn `ruff check`, `ruff format --check` und `pytest -q` grün sind, `docs/windows.md` zum Verhalten passt und alles, was nur auf echtem Windows prüfbar ist, als Liste mit genauem Befehl an den Nutzer übergeben wurde.

## 10. Ausblick (nur auf ausdrücklichen Auftrag)

**Stand 19.10.2026:** Der Nutzer hat entschieden, Computer Use als eigenen C#-Kern in seinem Projekt AgentHub (`C:\DEV\VSCode\AgentHub`, Ordner `computer-use/`, Branch `feature/computer-use-core`) zu bauen, Windows zuerst, ohne MCP und ohne Unterprozess. Die Logik von Decider, Aktionen, Runner und Wahrnehmung sowie die Szenarien aus `tests/world.py` sind dorthin portiert (MIT, Urheber awlevin, Hinweis in `NOTICE.md` dort). Dieser Fork bleibt Referenz und Testvorlage. Änderungen hier ändern den C#-Kern nicht von selbst: Eine Verhaltensänderung im Fork (zum Beispiel die Verlaufszeilen in `actions.py`, die der Runner auswertet) muss bei Bedarf dort nachgezogen werden. Ein Abgleich mit dem Upstream ist für den C#-Kern nicht nötig.

Ältere Notiz (überholt):

- Einbindung als Werkzeug: entweder als Unterprozess (`clicker "<goal>" --act`, Ergebnis aus `runs/<Zeitstempel>/run.json`) oder als kleiner MCP-Server in Python mit einem Tool `computer_use(goal)`.
- Eigene App: Favorit ist Avalonia (C#/.NET) mit einem UI-freien Core, der als MCP-Host Server startet und deren Tools dem Modell anbietet. Der Nutzer lehnt Electron ab, und Tauri nutzt ebenfalls eine Webview. Cua wird nicht verwendet.
- Nichts davon ohne Auftrag beginnen und nichts in diesem Repo darauf vorbereiten.
