# MDS-UPDRS Assessment Application

This document covers only the clinician-facing web application. The sensor-data training and machine-learning workflow is documented in [../ml/README.md](../ml/README.md).

## Purpose

The application records an MDS-UPDRS Part III-style clinical assessment and exports the assessment for local/server storage or Google Sheets synchronization.

## Main files

- [index.html](./index.html): assessment interface
- [data.js](./data.js): official-style Part III score-element definitions
- [app.js](./app.js): scoring, validation, save/reset, and export behavior
- [logs.html](./logs.html): local log review and exports
- [styles.css](./styles.css): application styling
- [../api/log.js](../api/log.js): server logging endpoint
- [google_apps_script.js](./google_apps_script.js): Google Sheets webhook
- [run_app.py](./run_app.py): local server launcher

## Assessment workflow

1. Open the application.
2. Enter optional patient metadata.
3. Record medication state, ON/OFF state, levodopa status, last dose timing, dyskinesia information, and optional Hoehn & Yahr stage.
4. Enter the 33 Part III score elements.
5. Rate each Part III scored element from 0 to 4, following the descriptions in the official MDS-UPDRS form.
6. Select `Done` to review the assessment result.
7. Select `Save Log & Start New Assessment`.
8. The application saves the record, shows a success message, clears the current responses, and returns to a new-assessment state.

Patient name, Patient ID, Session ID, and MDS-UPDRS number are optional. If identifiers are incomplete, records receive unique keys rather than being merged. When both Patient ID and Session ID are present, deduplication can use that pair.

## Local use

From the repository root, run:

```bash
python app/run_app.py
```

Then open `http://localhost:8080/index.html`.

## Storage and exports

The application supports:

- local/browser log storage
- server logging through [../api/log.js](../api/log.js)
- CSV and Excel export from the logs page
- Google Sheets synchronization through the Apps Script webhook

The app propagates optional metadata and clinical fields through summaries, local logs, server logs, CSV/Excel exports, and Google Sheets payloads.

## Google Sheets synchronization

1. Create a Google Sheet.
2. Open **Extensions → Apps Script**.
3. Paste the contents of [google_apps_script.js](./google_apps_script.js).
4. Deploy it as a Web app.
5. Configure access according to the deployment environment.
6. Copy the `/exec` URL.
7. Paste the URL into the application's Google Sheet Sync configuration.

Do not expose patient data or webhook URLs in public repositories. Use an access policy appropriate for the clinical environment.

## Clinical scope

The application is a data-entry and logging aid. It does not replace clinician examination, diagnosis, or official scoring guidance. The training notebook is separate and must not be used to infer clinical scores from this application's logs without validated labels and an approved evaluation protocol.

The current ML Random Forest result is documented in [../ml/README.md](../ml/README.md); it is exploratory and not clinically validated.
