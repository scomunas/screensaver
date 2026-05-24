// --- STATE CONFIGURATION ---
let slideshowInterval = null;
let isPlaying = true;
let currentLayer = 1; // 1 or 2
let idleTimer = null;

// Photo history cache for Prev/Next navigation
const photoHistory = [];
let historyIndex = -1;
const MAX_HISTORY = 50;

// Slideshow settings (default values)
const settings = {
    duration: 10000,        // 10s
    transition: 1000,       // 1s
    background: 'blurred',  // 'blurred' or 'black'
    showInfo: true,         // show EXIF/path overlay
    proxmoxUrl: 'http://localhost:9091',
    synologyUrl: 'http://localhost:9090'
};

// --- DOM ELEMENTS ---
const viewport = document.getElementById('screensaver-viewport');
const bgLayers = [document.getElementById('bg-layer-1'), document.getElementById('bg-layer-2')];
const fgLayers = [document.getElementById('fg-layer-1'), document.getElementById('fg-layer-2')];
const images = [document.getElementById('img-1'), document.getElementById('img-2')];

const clockEl = document.getElementById('digital-clock');
const dateEl = document.getElementById('digital-date');

const infoOverlay = document.getElementById('info-overlay');
const photoDirectory = document.getElementById('photo-directory');
const photoTitle = document.getElementById('photo-title');
const metadataStrip = document.getElementById('metadata-strip');
const exifStrip = document.getElementById('exif-strip');

// Metadata fields
const metaDateVal = document.querySelector('#meta-date .meta-val');
const metaResVal = document.querySelector('#meta-resolution .meta-val');
const exifCameraVal = document.querySelector('#exif-camera .exif-val');
const exifLensVal = document.querySelector('#exif-lens .exif-val');
const exifIsoVal = document.querySelector('#exif-iso .badge-val');
const exifApertureVal = document.querySelector('#exif-aperture .badge-val');
const exifShutterVal = document.querySelector('#exif-shutter .badge-val');
const exifFocalVal = document.querySelector('#exif-focal .badge-val');

// Controls
const controlPanel = document.getElementById('control-panel');
const btnPrev = document.getElementById('btn-prev');
const btnPlayPause = document.getElementById('btn-play-pause');
const btnNext = document.getElementById('btn-next');
const btnInfoToggle = document.getElementById('btn-info-toggle');
const btnSettingsToggle = document.getElementById('btn-settings-toggle');

// Settings Modal
const settingsModal = document.getElementById('settings-modal');
const btnSettingsClose = document.getElementById('btn-settings-close');
const selectDuration = document.getElementById('select-duration');
const selectTransition = document.getElementById('select-transition');
const toggleBackground = document.getElementById('toggle-background');
const inputProxmoxUrl = document.getElementById('input-proxmox-url');
const inputSynologyUrl = document.getElementById('input-synology-url');

// Scan components
const btnTriggerScan = document.getElementById('btn-trigger-scan');
const scanPathInput = document.getElementById('scan-path-input');
const scanApiKeyInput = document.getElementById('scan-api-key');
const scanStatusMsg = document.getElementById('scan-status-message');

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    initClock();
    initControlPanelAutoHide();
    
    // Initial fetch and start
    advanceSlideshow();
    startTimer();
    
    // Attach Event Listeners
    setupEventListeners();
});

// --- CLOCK AND DATE ---
function initClock() {
    const updateClock = () => {
        const now = new Date();
        
        // Time: HH:MM
        let hours = now.getHours().toString().padStart(2, '0');
        let minutes = now.getMinutes().toString().padStart(2, '0');
        clockEl.textContent = `${hours}:${minutes}`;
        
        // Date: Day of week, Month Day
        const options = { weekday: 'long', month: 'long', day: 'numeric' };
        dateEl.textContent = now.toLocaleDateString(undefined, options);
    };
    
    updateClock();
    setInterval(updateClock, 1000 * 30); // Update every 30 seconds
}

// --- SETTINGS MANAGEMENT ---
function loadSettings() {
    // Load from localStorage
    const savedDuration = localStorage.getItem('screensaver_duration');
    const savedTransition = localStorage.getItem('screensaver_transition');
    const savedBackground = localStorage.getItem('screensaver_background');
    const savedShowInfo = localStorage.getItem('screensaver_showinfo');
    const savedApiKey = localStorage.getItem('screensaver_api_key');
    const savedScanPath = localStorage.getItem('screensaver_scan_path');
    const savedProxmoxUrl = localStorage.getItem('screensaver_proxmox_url');
    const savedSynologyUrl = localStorage.getItem('screensaver_synology_url');

    if (savedDuration) settings.duration = parseInt(savedDuration);
    if (savedTransition) settings.transition = parseInt(savedTransition);
    if (savedBackground) settings.background = savedBackground;
    if (savedShowInfo) settings.showInfo = savedShowInfo === 'true';
    if (savedApiKey) scanApiKeyInput.value = savedApiKey;
    if (savedScanPath) scanPathInput.value = savedScanPath;
    if (savedProxmoxUrl) settings.proxmoxUrl = savedProxmoxUrl;
    if (savedSynologyUrl) settings.synologyUrl = savedSynologyUrl;

    // Apply values to dropdowns
    selectDuration.value = settings.duration;
    selectTransition.value = settings.transition;
    toggleBackground.value = settings.background;
    inputProxmoxUrl.value = settings.proxmoxUrl;
    inputSynologyUrl.value = settings.synologyUrl;
    
    if (settings.showInfo) {
        btnInfoToggle.classList.add('active');
        infoOverlay.classList.remove('info-hidden');
    } else {
        btnInfoToggle.classList.remove('active');
        infoOverlay.classList.add('info-hidden');
    }
    
    applyStyleSettings();
}

function applyStyleSettings() {
    // Apply transition speed CSS variable
    viewport.style.setProperty('--transition-speed', `${settings.transition}ms`);
    
    // Apply background style class
    if (settings.background === 'black') {
        viewport.classList.add('bg-black-mode');
    } else {
        viewport.classList.remove('bg-black-mode');
    }
}

function saveSetting(key, val) {
    localStorage.setItem(key, val);
}

// --- EVENT LISTENERS ---
function setupEventListeners() {
    // Media buttons
    btnPlayPause.addEventListener('click', togglePlayback);
    btnNext.addEventListener('click', () => {
        userTriggerAdvance(true);
    });
    btnPrev.addEventListener('click', () => {
        navigateHistory(-1);
    });
    btnInfoToggle.addEventListener('click', toggleInfoOverlay);
    
    // Settings modal triggers
    btnSettingsToggle.addEventListener('click', () => {
        settingsModal.classList.add('show');
        controlPanel.classList.add('keep-visible');
    });
    btnSettingsClose.addEventListener('click', () => {
        settingsModal.classList.remove('show');
        controlPanel.classList.remove('keep-visible');
        resetIdleTimer();
    });
    
    // Settings dropdown changes
    selectDuration.addEventListener('change', (e) => {
        settings.duration = parseInt(e.target.value);
        saveSetting('screensaver_duration', settings.duration);
        if (isPlaying) {
            stopTimer();
            startTimer();
        }
    });
    
    selectTransition.addEventListener('change', (e) => {
        settings.transition = parseInt(e.target.value);
        saveSetting('screensaver_transition', settings.transition);
        applyStyleSettings();
    });
    
    toggleBackground.addEventListener('change', (e) => {
        settings.background = e.target.value;
        saveSetting('screensaver_background', settings.background);
        applyStyleSettings();
    });

    inputProxmoxUrl.addEventListener('change', (e) => {
        settings.proxmoxUrl = e.target.value.trim();
        saveSetting('screensaver_proxmox_url', settings.proxmoxUrl);
    });

    inputSynologyUrl.addEventListener('change', (e) => {
        settings.synologyUrl = e.target.value.trim();
        saveSetting('screensaver_synology_url', settings.synologyUrl);
    });

    // Scanner actions
    btnTriggerScan.addEventListener('click', triggerLibraryScan);
    scanApiKeyInput.addEventListener('change', (e) => {
        saveSetting('screensaver_api_key', e.target.value);
    });
    scanPathInput.addEventListener('change', (e) => {
        saveSetting('screensaver_scan_path', e.target.value);
    });
}

// --- AUTO-HIDE CONTROLS PANEL ---
function initControlPanelAutoHide() {
    // Reset timer on activity
    const activityEvents = ['mousemove', 'mousedown', 'keydown', 'touchstart'];
    
    activityEvents.forEach(evt => {
        viewport.addEventListener(evt, resetIdleTimer);
    });
    
    resetIdleTimer();
}

function resetIdleTimer() {
    // Show controls on activity
    controlPanel.classList.remove('info-hidden'); // repurposing overlay hidden class
    
    // Don't auto-hide if settings modal is open
    if (settingsModal.classList.contains('show')) return;
    
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
        controlPanel.classList.add('info-hidden');
    }, 5000); // Hide after 5 seconds of inactivity
}

// --- TIMER CONTROL ---
function startTimer() {
    slideshowInterval = setInterval(advanceSlideshow, settings.duration);
}

function stopTimer() {
    clearInterval(slideshowInterval);
}

function togglePlayback() {
    isPlaying = !isPlaying;
    if (isPlaying) {
        btnPlayPause.innerHTML = '<i class="fa-solid fa-pause"></i>';
        startTimer();
        advanceSlideshow(); // Go immediately when playing
    } else {
        btnPlayPause.innerHTML = '<i class="fa-solid fa-play"></i>';
        stopTimer();
    }
    resetIdleTimer();
}

function toggleInfoOverlay() {
    settings.showInfo = !settings.showInfo;
    saveSetting('screensaver_showinfo', settings.showInfo);
    
    if (settings.showInfo) {
        btnInfoToggle.classList.add('active');
        infoOverlay.classList.remove('info-hidden');
    } else {
        btnInfoToggle.classList.remove('active');
        infoOverlay.classList.add('info-hidden');
    }
    resetIdleTimer();
}

// --- SLIDESHOW NAVIGATION ---
function userTriggerAdvance() {
    stopTimer();
    advanceSlideshow();
    if (isPlaying) {
        startTimer();
    }
    resetIdleTimer();
}

function navigateHistory(direction) {
    stopTimer();
    
    const targetIdx = historyIndex + direction;
    if (targetIdx >= 0 && targetIdx < photoHistory.length) {
        historyIndex = targetIdx;
        displayPhoto(photoHistory[historyIndex]);
    } else if (direction > 0) {
        // Go forward (fetch new)
        advanceSlideshow();
    }
    
    // Disable/Enable previous button state visually
    btnPrev.style.opacity = historyIndex <= 0 ? "0.4" : "1";
    btnPrev.style.pointerEvents = historyIndex <= 0 ? "none" : "auto";
    
    if (isPlaying) {
        startTimer();
    }
    resetIdleTimer();
}

async function advanceSlideshow() {
    // If we have history ahead of us, use that instead of fetching new
    if (historyIndex < photoHistory.length - 1) {
        historyIndex++;
        displayPhoto(photoHistory[historyIndex]);
        btnPrev.style.opacity = "1";
        btnPrev.style.pointerEvents = "auto";
        return;
    }

    // Otherwise, fetch a new random photo from the API
    try {
        const response = await fetch(`${settings.proxmoxUrl}/api/photos/random`);
        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }
        const photoData = await response.json();
        
        // Add to history list
        photoHistory.push(photoData);
        if (photoHistory.length > MAX_HISTORY) {
            photoHistory.shift(); // remove oldest
        }
        historyIndex = photoHistory.length - 1;
        
        // Update Prev button pointer states
        btnPrev.style.opacity = historyIndex <= 0 ? "0.4" : "1";
        btnPrev.style.pointerEvents = historyIndex <= 0 ? "none" : "auto";
        
        displayPhoto(photoData);
    } catch (error) {
        console.error("Failed to load random photo:", error);
        photoTitle.textContent = "Error loading photos from NAS";
        photoDirectory.textContent = "Error";
    }
}

// --- IMAGE PRELOADING & DISPLAY ---
function displayPhoto(photoData) {
    const nextLayer = currentLayer === 1 ? 2 : 1;
    const imgElement = images[nextLayer - 1];
    
    // Point image src to API
    const photoUrl = `${settings.synologyUrl}/api/photos/file/${photoData.id}`;
    
    // Preload image before switching layers
    const tempImg = new Image();
    tempImg.onload = () => {
        // Update sources once image is loaded in memory
        imgElement.src = photoUrl;
        
        // Update blurred background layer if enabled
        if (settings.background === 'blurred') {
            bgLayers[nextLayer - 1].style.backgroundImage = `url('${photoUrl}')`;
        }
        
        // Perform layer cross-fade
        bgLayers[currentLayer - 1].classList.remove('active');
        bgLayers[nextLayer - 1].classList.add('active');
        
        fgLayers[currentLayer - 1].classList.remove('active');
        fgLayers[nextLayer - 1].classList.add('active');
        
        // Update layer state
        currentLayer = nextLayer;
        
        // Update layout card EXIF values
        updateInfoCard(photoData);
    };
    
    tempImg.src = photoUrl;
}

// --- UPDATE METADATA CARD ---
function updateInfoCard(photoData) {
    // Set directory and title
    photoDirectory.textContent = photoData.directory;
    photoTitle.textContent = photoData.file_name;
    
    // Clean up older tags
    metadataStrip.classList.add('hidden');
    exifStrip.classList.add('hidden');
    
    // 1. Basic Metadata
    let hasMeta = false;
    
    if (photoData.date_taken) {
        const dateObj = new Date(photoData.date_taken);
        metaDateVal.textContent = dateObj.toLocaleDateString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
        hasMeta = true;
    } else {
        metaDateVal.parentElement.style.display = 'none';
    }
    
    if (photoData.width && photoData.height) {
        metaResVal.textContent = `${photoData.width} × ${photoData.height}`;
        metaResVal.parentElement.style.display = 'inline-flex';
        hasMeta = true;
    } else {
        metaResVal.parentElement.style.display = 'none';
    }
    
    if (hasMeta) {
        metadataStrip.classList.remove('hidden');
    }
    
    // 2. EXIF Stats
    let hasExif = false;
    
    // Camera Make/Model
    if (photoData.camera_model) {
        const make = photoData.camera_make ? photoData.camera_make.split(' ')[0] : '';
        const model = photoData.camera_model;
        // Avoid duplicate camera make words
        const cameraText = model.toLowerCase().startsWith(make.toLowerCase()) ? model : `${make} ${model}`;
        exifCameraVal.textContent = cameraText;
        exifCameraVal.parentElement.style.display = 'flex';
        hasExif = true;
    } else {
        exifCameraVal.parentElement.style.display = 'none';
    }
    
    // Lens Model
    if (photoData.lens_model) {
        exifLensVal.textContent = photoData.lens_model;
        exifLensVal.parentElement.style.display = 'flex';
        hasExif = true;
    } else {
        exifLensVal.parentElement.style.display = 'none';
    }
    
    // Badges strip (ISO, Aperture, Shutter speed, focal length)
    let hasBadges = false;
    
    if (photoData.iso) {
        exifIsoVal.textContent = photoData.iso;
        exifIsoVal.parentElement.style.display = 'flex';
        hasBadges = true;
    } else {
        exifIsoVal.parentElement.style.display = 'none';
    }
    
    if (photoData.f_number) {
        exifApertureVal.textContent = photoData.f_number;
        exifApertureVal.parentElement.style.display = 'flex';
        hasBadges = true;
    } else {
        exifApertureVal.parentElement.style.display = 'none';
    }
    
    if (photoData.exposure_time) {
        exifShutterVal.textContent = photoData.exposure_time;
        exifShutterVal.parentElement.style.display = 'flex';
        hasBadges = true;
    } else {
        exifShutterVal.parentElement.style.display = 'none';
    }
    
    if (photoData.focal_length) {
        exifFocalVal.textContent = Math.round(photoData.focal_length);
        exifFocalVal.parentElement.style.display = 'flex';
        hasBadges = true;
    } else {
        exifFocalVal.parentElement.style.display = 'none';
    }
    
    if (hasBadges || hasExif) {
        exifStrip.classList.remove('hidden');
    }
}

// --- SCANNING CONTROL ---
async function triggerLibraryScan() {
    const scanPath = scanPathInput.value.strip ? scanPathInput.value.strip() : scanPathInput.value.trim();
    const apiKey = scanApiKeyInput.value.strip ? scanApiKeyInput.value.strip() : scanApiKeyInput.value.trim();
    
    if (!scanPath) {
        showScanStatus("Please provide a valid scanning path.", "error");
        return;
    }
    
    if (!apiKey) {
        showScanStatus("An API Key is required to scan.", "error");
        return;
    }
    
    showScanStatus("Triggering scan...", "info");
    
    try {
        const response = await fetch(`${settings.synologyUrl}/api/scan`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': apiKey
            },
            body: JSON.stringify({ path: scanPath })
        });
        
        if (response.status === 403) {
            showScanStatus("Authentication failed: Invalid API Key.", "error");
            return;
        }
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Server error occurred");
        }
        
        const result = await response.json();
        showScanStatus(`Scan queued successfully! (Scan ID: ${result.scan_id.substring(0,8)}...)`, "success");
        
        // Wait and start displaying slideshow after a delay if first run
        setTimeout(() => {
            if (photoHistory.length === 0) {
                advanceSlideshow();
            }
        }, 3000);
        
    } catch (error) {
        console.error("Scanning request failed:", error);
        showScanStatus(`Scan failed: ${error.message}`, "error");
    }
}

function showScanStatus(message, type) {
    scanStatusMsg.textContent = message;
    scanStatusMsg.className = "scan-status-message"; // Reset
    if (type) {
        scanStatusMsg.classList.add(type);
    }
}
