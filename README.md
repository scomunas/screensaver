# Synology & Proxmox Photo Screensaver (v0.0.4)

A modern, clean, and adaptive fullscreen media screensaver designed for Smart TVs. It uses a split architecture to keep files secure on your Synology NAS while running database and web operations on your Proxmox server, supporting both photos and videos natively.

```mermaid
graph TD
    subgraph Proxmox ["Proxmox Server"]
        FE["Frontend: Nginx"] -->|1. Fetch Random Metadata| BE["Backend: FastAPI"]
        BE -->|Query Meta| DB["PostgreSQL Database"]
    end
    subgraph Synology ["Synology NAS (Native Linux)"]
        FE -->|2. Stream Photo/Video File| SYN["Synology API: FastAPI"]
        SYN -->|Read File| Storage["NAS Disk Storage"]
        SYN -->|Read Path from DB| DB
        Scanner["manual_scan.py"] -->|Crawl & Index EXIF & Duration| DB
    end
```

---

## 📂 Project Structure

```text
/
├── docker-compose.yml          # Proxmox Compose (db, backend, frontend)
├── .env.example                # Template for environment variables
├── .gitignore                  # Git ignore rules
├── frontend/
│   ├── index.html              # Fullscreen screensaver structure
│   ├── style.css               # Glassmorphism styling and transitions
│   ├── app.js                  # Preloader, history queue, and clock engine
│   ├── generate-config.sh      # Container entrypoint helper (injects env variables)
│   └── Dockerfile              # Frontend Nginx container recipe
├── backend/
│   ├── main.py                 # Proxmox metadata API
│   ├── database.py             # Postgres schemas and connection helpers
│   ├── config.py               # Environment configuration
│   ├── requirements.txt        # Backend dependencies
│   └── Dockerfile              # Backend FastAPI container recipe
└── synology/
    ├── main.py                 # Synology file API and EXIF parser
    ├── manual_scan.py          # CLI directory scanner (updates Proxmox DB)
    ├── requirements.txt        # NAS Python requirements
    ├── Dockerfile              # NAS Agent container recipe (optional)
    └── docker-compose.yml      # NAS Agent Compose config (optional)
```

---

## 🚀 Deployment Guide

### Part 1: Proxmox Server Setup (Docker Stack)

1. Copy `.env.example` to `.env` in the root:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and set your credentials:
   - Make sure `DB_HOST` is the IP of your Proxmox server (so both backend and Synology can connect to it).
   - Set `BACKEND_PORT` (default: `9090`).
   - Set `SYNOLOGY_IP` to your Synology NAS IP and `SYNOLOGY_PORT` (default: `9090`).
3. Start the Docker stack on Proxmox:
   ```bash
   docker-compose up --build -d
   ```
   This will start:
   - **PostgreSQL Database** on port `5432`
   - **Backend API** on port `9090`
   - **Frontend UI (Nginx)** on port `8080` (access via `http://<proxmox_ip>:8080`)

---

### Part 2: Synology NAS Setup (Native Python)

The Synology agent runs directly on your NAS filesystem to scan directory structures natively.

1. Copy the `/synology` folder and your `.env` file to your Synology NAS.
2. Install Python 3 dependencies (including `hachoir` for video EXIF extraction and `pillow` / `pillow-heif` for image parsing) on the NAS:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the API service in the background on the NAS:
   ```bash
   python main.py
   ```
   This exposes the file-retrieval API on port `9092` of your NAS (e.g. `http://<synology_ip>:9092`).

---

## 🛠️ How to Scan your Photo Library

To sync your photos on the NAS into the Postgres database on Proxmox, use the CLI script on the NAS:

1. Connect to your Synology NAS over SSH.
2. Run the script and pass the path of your photo directory:
   ```bash
   python manual_scan.py /volume2/photo
   ```
This script will:
* Recursively scan `/volume2/photo`.
* Read image headers for dimensions (extremely fast).
* Parse EXIF details (Camera model, lens, exposure time, aperture, ISO, focal length).
* Upsert records into the Proxmox PostgreSQL database in batches.
* Purge records of any files that have been deleted from disk.

---

## 📺 Screensaver Features

- **Native Video Support**: Index and play `.mp4`, `.mov`, `.webm`, `.mpg`, `.mpeg`, and `.m4v` video files natively, pausing the slideshow transition automatically until the video finishes playing.
- **HTTP Range Requests**: Serves video files using standard partial content chunking, enabling progressive loading and playback without downloading the entire video file first.
- **Interactive Audio Volume Toggle**: A speaker icon button on the controls strip allows you to mute and unmute the screensaver globally (defaults to unmuted). The preference is maintained across slides.
- **Blurred Backdrop Scaling**: Portrait or narrow photos show a heavily blurred and darkened version of themselves in the background to prevent black letterbox bars (clears for video files).
- **TV Screen Protection**: Interactive controls automatically fade out after 5 seconds of inactivity to protect TV panels from burn-in.
- **History Queue**: The **Previous** and **Next** buttons let you navigate backward and forward through your recently viewed photos/videos.
- **EXIF & Video metadata Overlay**: Shows folder breadcrumbs, date taken, camera metrics, and lenses (or video duration and video icons). Click the **Eye icon** to toggle the clock and details card overlay for a completely clean view.
