# Changelog

All notable changes to this project will be documented in this file.

## [v0.0.3] - 2026-05-24

### Changed
- **Total IP and Port Parameterization**: Reordered `.env` and `.env.example` configurations to group database, frontend, backend, and Synology IP/Port variables.
- **Parametric Compose Layout**: Removed all hardcoded IP and port definitions inside root `docker-compose.yml` and `synology/docker-compose.yml`, driving container exposures and backend bindings dynamically from `.env`.
- **Database Connection Port Parameterization**: Updated psycopg2 DB configurations inside `backend/config.py` and `synology/main.py` to parse `DB_PORT` and pass it to connection handlers.
- **Port Naming Standardisation**: Unified port variables into explicit `BACKEND_PORT`, `SYNOLOGY_PORT`, `FRONTEND_PORT`, and `DB_PORT` overrides.

## [v0.0.2] - 2026-05-24 (Initial Release)

### Added
- **Split Proxmox & Synology Architecture**: Separated logic into Nginx frontend, FastAPI metadata API, and standalone Python NAS scanner.
- **Dynamic Config Ingestion**: Nginx entrypoint dynamically builds and exposes backend and Synology IPs from the Proxmox host `.env` file to the static web client.
- **Consolidated Synology Agent**: Merged crawler, DB connection pooling, EXIF metadata parser, and HTTP stream server into a single file ([synology/main.py](file:///c:/CSDrive/Documentos/Desarrollo/screensaver/synology/main.py)).
- **Manual CLI Scan Helper**: Added [synology/manual_scan.py](file:///c:/CSDrive/Documentos/Desarrollo/screensaver/synology/manual_scan.py) to trigger database catalog scans from the NAS command line.
- **EXIF Metadata Scanners**: Scans and saves camera manufacturer, camera model, lens model, exposure time, aperture, ISO, focal length, and width/height dimensions.
- **Dynamic HEIC-to-JPEG Conversion**: Automatically detects `.heic` images and converts them in memory on-the-fly when streaming to TV browsers.
- **Glassmorphism Screensaver UI**: High-end translucent detail cards, customizable slide durations, transition speeds, and blurred background scaling.
- **Burn-In Protection**: Auto-hiding interactive navigation control panels.
- **Slideshow History Queue**: Caches recently viewed images to make "Previous" and "Next" controls fully functional.
- **Git Rules**: Added [.gitignore](file:///c:/CSDrive/Documentos/Desarrollo/screensaver/.gitignore) for security.
