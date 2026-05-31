# Changelog

All notable changes to this project will be documented in this file.

## [v0.0.4] - 2026-05-30

### Added
- **Native Video Support**: Expanded library scanner to index `.mp4`, `.mov`, `.webm`, `.mpg`, `.mpeg`, and `.m4v` files alongside photos, while explicitly excluding `.avi` files to prevent CPU-intensive server-side transcoding.
- **HTTP Range Request Support**: Serves video streaming files using standard range requests (via FastAPI's `FileResponse`), allowing instant progressive buffering in the browser without downloading the full video first.
- **Video EXIF Metadata Parsing**: Integrated `hachoir` parser to automatically retrieve video duration, width, height, and creation dates during crawler scans.
- **Responsive Video Engine Overlay**: Upgraded the frontend layers to include `<video>` containers alongside images, dynamically showing/hiding them depending on media type.
- **Synchronized Video Playback Logic**: Implemented automated slideshow transition pauses during active video playing, resuming and advancing only after the video ends (`onended` event) or if a safety fallback timeout is reached.
- **Smart Playback Controls**: Extended play/pause settings to pause/resume active video playback, and modified slideshow settings to prevent timer restarts while video media is playing.
- **Video Duration UI Details**: Dynamically adjusts glassmorphic info cards to show video camera icons and format duration times (`MM:SS` or `SSs`) next to resolutions.
- **Interactive Audio Volume Toggle**: Added a speaker control button (`btn-volume-toggle`) to the controls strip that is always visible (defaulting to unmuted/sound on). Toggling it sets a global session state (`isMuted`) so that all currently playing and subsequent videos respect the user's unmuted/muted preference.

### Changed
- **Parametric Video Extensions**: Added `VIDEO_EXTENSIONS` to `.env` and `.env.example` configurations to parse video file sweeps dynamically (defaults to `.mp4,.mov,.webm,.mpg,.mpeg,.m4v`), replacing hardcoded extensions in the crawler.

### Fixed
- **Large File Size Bug (Integer Out of Range)**: Upgraded `file_size` column data type from `INTEGER` to `BIGINT` in the database schema and created startup migrations. This fixes crashes during sweeps when indexing video files larger than 2.14 GB.

## [v0.0.3] - 2026-05-24

### Changed
- **Total IP and Port Parameterization**: Reordered `.env` and `.env.example` configurations to group database, frontend, backend, and Synology IP/Port variables.
- **Parametric Compose Layout**: Removed all hardcoded IP and port definitions inside root `docker-compose.yml` and `synology/docker-compose.yml`, driving container exposures and backend bindings dynamically from `.env`.
- **Database Connection Port Parameterization**: Updated psycopg2 DB configurations inside `backend/config.py` and `synology/main.py` to parse `DB_PORT` and pass it to connection handlers.
- **Port Naming Standardisation**: Unified port variables into explicit `BACKEND_PORT`, `SYNOLOGY_PORT`, `FRONTEND_PORT`, and `DB_PORT` overrides.
- **Directory Field Scope**: Configured the Synology scanner to save only the immediate parent folder name in the database `directory` field, rather than the complete relative path.
- **Removed Filename from UI**: Cleaned up the frontend glassmorphic information card by removing the large photo filename header.

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
