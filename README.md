# Running Dinner Pipeline

Dieses Paket organisiert ein Running Dinner aus einem LimeSurvey-JSON-Export. Es importiert die Daten, geocodiert Adressen, optimiert die Zuteilung, validiert den Plan und erzeugt E-Mail-Entwuerfe sowie interaktive Karten.

## Schnellstart fuer Empfaenger:innen

1. Den kompletten Ordner auf den eigenen Rechner kopieren.
2. Python 3.10 oder neuer installieren, falls noch nicht vorhanden.
3. Startdatei ausfuehren:
   - macOS: `start_app.command` doppelklicken.
   - macOS/Linux Terminal: `./start_app.sh`
   - Windows: `start_app.bat`
4. Die Web-App oeffnet sich unter `http://127.0.0.1:8765`.

Das Startskript erstellt automatisch eine lokale `.venv`, installiert `requirements.txt` und startet den Webserver. Fuer Geocoding und Routing wird eine Internetverbindung benoetigt.

## Sauberes Paket erstellen

Zum Versenden sollte nicht der Arbeitsordner direkt gezippt werden, weil darin lokale Umgebungen, alte Runs, Datenbanken und personenbezogene Eingabedaten liegen koennen.

Stattdessen:

```bash
python3 make_package.py
```

Das erzeugt ein ZIP in `dist/` und schliesst `.venv`, `data/input`, `data/intermediate`, `data/output`, `__pycache__` und `.DS_Store` aus. Die notwendigen Datenordner werden im ZIP leer angelegt, damit Empfaenger:innen direkt mit Uploads in der Web-App starten koennen.

## Web-App Workflow

In der Web-App kann ein neuer Run gestartet werden:

1. LimeSurvey-Datei hochladen: JSON, CSV oder XLSX.
2. Anzahl der Optimierungsversuche setzen, empfohlen: `5000`.
3. Optional ein Label vergeben.
4. Optional `Restgruppen mit einplanen` aktivieren, wenn bei einer nicht durch drei teilbaren Teamzahl keine Teams ausgeschlossen werden sollen.
5. Rahmeninformationen fuer diesen Run eintragen: Titel, Datum, Startzeit und weitere Hinweise auf Deutsch und optional Englisch. Treffpunkt/Abschlussort ist optional und kann leer bleiben.
6. Run starten.
7. Das Run-Detail oeffnet sich sofort und zeigt waehrend der Pipeline einen laufenden Status, einen Spinner und die letzten Log-Zeilen.
8. Validierung, Gesamtkarte, Teamkarten, E-Mail-Entwuerfe und ZIP-Download im Run-Detail pruefen.

## Importformate

Der Import unterstuetzt:

- JSON mit `responses`.
- CSV mit Kopfzeile.
- XLSX mit Kopfzeile im ersten Tabellenblatt.

Robust erkannt werden sowohl sichtbare LimeSurvey-Fragetexte als auch Spalten im Format `QCODE. Fragetext`, z.B. `G01Q08[SQ001]. Namen [Name 1]`. Fuer stabile Exporte sind Fragecodes/Variablencodes besser als reine Fragetexte.

Optional kann im Projektordner eine `field_mapping.json` liegen. Darin koennen projektspezifische Spaltennamen oder Fragecodes den internen Feldern zugeordnet werden:

```json
{
  "id": "id",
  "submitdate": "submitdate",
  "name1": "G01Q08[SQ001]",
  "name2": "G01Q08[SQ002]",
  "email1": "G01Q04[SQ001]",
  "street": "G01Q11[SQ001]"
}
```

Werte duerfen auch Listen sein, wenn mehrere Spaltennamen akzeptiert werden sollen.

## Run-Historie

Jede Ausfuehrung wird in einem eigenen Unterordner gespeichert:

```text
data/output/runs/<run_id>/
  manifest.json
  plan.json
  pipeline.log
  aggregated_map.html
  emails/
  maps/
```

Zusaetzlich pflegt das Paket:

```text
data/output/runs/index.json
data/output/runs/latest.json
data/output/runs/latest.txt
```

Damit kann die Web-App alte Runs referenzieren, vergleichen und wieder oeffnen. Ein Run wird nicht ueberschrieben; bei gleicher ID wird automatisch ein Suffix verwendet.

## CLI Workflow

Fortgeschrittene koennen die Pipeline direkt starten:

```bash
python3 main.py --input "data/input/DEINE_DATEI.json" --output "data/output" --trials 5000
```

Optional kann eine stabile Run-ID gesetzt werden:

```bash
python3 main.py --input "data/input/DEINE_DATEI.json" --run-id "probe-1" --trials 5000
```

Wenn bei einer nicht durch drei teilbaren Teamzahl keine Teams ausgeschlossen werden sollen:

```bash
python3 main.py --input "data/input/DEINE_DATEI.json" --trials 5000 --include-remainder-teams
```

Rahmeninformationen fuer die E-Mail-Entwuerfe koennen ebenfalls uebergeben werden:

```bash
python3 main.py \
  --input "data/input/DEINE_DATEI.json" \
  --event-title "Running Dinner Sommer 2026" \
  --event-date "2026-06-20" \
  --event-time "18:30" \
  --event-meeting-point "Abschluss ab 22:00 im Fachschaftsraum" \
  --event-meeting-point-en "Final meetup from 22:00 in the student council room" \
  --event-info "Bitte seid puenktlich bei den jeweiligen Stationen." \
  --event-info-en "Please arrive on time at each station."
```

Auch die CLI schreibt immer in `data/output/runs/<run_id>/`.

## Ergebnisse

- `emails/`: Individuelle E-Mail-Entwuerfe je Team, immer zweisprachig auf Deutsch und Englisch. Besuchsstationen nennen nur Gang, Adresse und Adresshinweise, keine Host-Namen, keine Telefonnummern und keine anderen Teamkontakte. Beim eigenen Gang werden Gastteams nur anonymisiert mit Ernaehrungs- und Allergiehinweisen aufgefuehrt.
- `maps/`: Interaktive HTML-Karten je Team. Die individuellen Karten nennen bei fremden Stationen nur Gang, Adresse und Adresshinweise, keine Gastgebernamen.
- `aggregated_map.html`: Gesamtuebersicht fuer die Orga.
- `plan.json`: Maschinenlesbarer Plan mit Hosts, Gaesten und Gaengen.
- `manifest.json`: Metadaten, Parameter, Status, Validierung und Artefaktpfade.
- `pipeline.log`: Ausgabe des Pipeline-Laufs, wenn der Run ueber die Web-App gestartet wurde.

## Hinweise und Grenzen

- Der echte E-Mail-Versand ist noch nicht scharf geschaltet. Die App verwaltet aktuell E-Mail-Entwuerfe. Fuer SMTP/Provider-Versand sollten Zugangsdaten, Absenderadresse, Testmodus und Versandprotokoll separat konfiguriert werden.
- Wenn die Teamzahl nicht durch drei teilbar ist, kuerzt der Optimizer standardmaessig die aktiven Teams auf das naechste Vielfache von drei. Wird `Restgruppen mit einplanen` bzw. `--include-remainder-teams` aktiviert, bleiben alle Teams aktiv; einzelne Stationen koennen dann aus 2 oder 4 Teams bestehen. Die gewaehlte Option steht im Manifest unter `include_remainder_teams`.
- Teams mit gleicher normalisierter Adresse werden als harte Konflikte behandelt und duerfen nie gemeinsam an einem Gang teilnehmen. Die Anzahl erkannter Konflikte steht im Manifest unter `same_address_conflicts`.
- Bei Adressen ohne brauchbare Hausnummer versucht der Import eine ungefaehre street-level Geocodierung. Solche Adressen sollten vor dem finalen Versand fachlich geprueft werden.
- Die Standard-LimeSurvey-Feldnamen und Fragecodes sind in `src/importer.py` gemappt. Aendert sich der Fragebogen stark, sollte `field_mapping.json` genutzt oder das Mapping erweitert werden.
- Geocoding-Ergebnisse werden in `data/intermediate/dinner.db` gecached.

## Fehlersuche

- `Imported 0 teams`: Feldnamen im JSON passen wahrscheinlich nicht zum Mapping in `src/importer.py`.
- `Geocoding failed`: Adresse pruefen; haeufige Schreibweisen werden bereits teilweise korrigiert.
- `Validation Failed`: Anzahl der Trials erhoehen, z.B. auf `10000`.
- Web-App startet nicht: im Terminalfenster die Fehlermeldung pruefen; meist fehlt Python oder Port `8765` ist bereits belegt. Alternativ mit `PORT=8766 ./start_app.sh` starten.
