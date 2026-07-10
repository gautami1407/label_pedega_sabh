// ============================================================
// LABEL PADEGHA SABH — Barcode Scanner v3.0 (html5-qrcode)
// ============================================================

let html5QrCode = null;
let activeTab = 'camera';
let scanHandled = false;
let scannerRunning = false;

// ── Debug Logger ──────────────────────────────────────────
function logDebug(message, type = 'info') {
    const logEl = document.getElementById('debug-log');
    if (logEl) {
        logEl.style.display = 'block';
        const entry = document.createElement('div');
        entry.className = `log-entry log-${type}`;
        const ts = new Date().toLocaleTimeString();
        entry.textContent = `[${ts}] ${message}`;
        logEl.appendChild(entry);
        logEl.scrollTop = logEl.scrollHeight;
    }
    if (type === 'error') {
        console.error(`[BarcodeScanner] ${message}`);
    } else if (type === 'warn') {
        console.warn(`[BarcodeScanner] ${message}`);
    } else {
        console.log(`[BarcodeScanner] ${message}`);
    }
}

// ── DOM Ready ─────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    logDebug('Page loaded, initializing scanner...');
    initializeScannerUI();
    startScanner();
});

// ── UI Initialization ────────────────────────────────────
function initializeScannerUI() {
    document.querySelectorAll('.method-tab').forEach(button => {
        button.addEventListener('click', () => {
            switchTab(button.dataset.tab || 'camera');
        });
    });

    const manualInput = document.getElementById('manualBarcodeInput');
    if (manualInput) {
        manualInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                logDebug('Manual input Enter pressed');
                fetchDetectedBarcode();
            }
        });
    }

    const detectedInput = document.getElementById('detectedBarcodeInput');
    if (detectedInput) {
        detectedInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                logDebug('Detected input Enter pressed');
                fetchDetectedBarcode();
            }
        });
    }

    logDebug('UI initialized');
}

function resetDetectedBarcodeUI() {
    scanHandled = false;
    const detectedInput = document.getElementById('detectedBarcodeInput');
    const status = document.getElementById('scan-status');
    const rescanBtn = document.getElementById('rescanBtn');

    if (detectedInput) detectedInput.value = '';
    if (rescanBtn) rescanBtn.style.display = 'none';
    if (status) status.textContent = '🔍 Searching for barcode...';
    logDebug('UI reset for new scan');
}

function switchTab(tab) {
    activeTab = tab;
    logDebug(`Switching to tab: ${tab}`);

    document.querySelectorAll('.method-tab').forEach(tabButton => {
        tabButton.classList.toggle('active', tabButton.dataset.tab === tab);
    });

    document.querySelectorAll('.method-panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === `panel-${tab}`);
    });

    if (tab === 'camera') {
        resetDetectedBarcodeUI();
        startScanner();
    } else {
        stopScanner();
        if (tab === 'manual') {
            scanHandled = false;
        }
    }
}

// ═══════════════════════════════════════════════════════════
// HTML5-QRCODE SCANNER
// ═══════════════════════════════════════════════════════════

async function startScanner() {
    if (activeTab !== 'camera') {
        logDebug('Not on camera tab, skipping scanner start');
        return;
    }

    if (scannerRunning) {
        logDebug('Scanner already running');
        return;
    }

    const readerEl = document.getElementById('reader');
    if (!readerEl) {
        logDebug('Reader element not found', 'error');
        return;
    }

    // Check if html5-qrcode library loaded
    if (typeof Html5Qrcode === 'undefined') {
        logDebug('html5-qrcode library not loaded! Check internet connection.', 'error');
        const status = document.getElementById('scan-status');
        if (status) {
            status.textContent = '⚠️ Scanner library failed to load. Use manual entry.';
        }
        return;
    }

    logDebug('Initializing html5-qrcode scanner...');

    try {
        // Stop any previous scanner
        await stopScanner();

        html5QrCode = new Html5Qrcode("reader");
        logDebug('Html5Qrcode instance created');

        const config = {
            fps: 20,
            qrbox: { width: 300, height: 200 },
            aspectRatio: 1.333,
            formatsToSupport: [
                Html5QrcodeSupportedFormats.EAN_13,
                Html5QrcodeSupportedFormats.EAN_8,
                Html5QrcodeSupportedFormats.UPC_A,
                Html5QrcodeSupportedFormats.UPC_E,
                Html5QrcodeSupportedFormats.CODE_128,
                Html5QrcodeSupportedFormats.CODE_39,
                Html5QrcodeSupportedFormats.CODE_93,
                Html5QrcodeSupportedFormats.QR_CODE,
                Html5QrcodeSupportedFormats.DATA_MATRIX,
                Html5QrcodeSupportedFormats.ITF,
                Html5QrcodeSupportedFormats.CODABAR,
                Html5QrcodeSupportedFormats.RSS_14,
                Html5QrcodeSupportedFormats.RSS_EXPANDED
            ]
        };

        logDebug('Starting camera with config: fps=20, formats=all');

        await html5QrCode.start(
            { facingMode: "environment" },
            config,
            onScanSuccess,
            onScanFailure
        );

        scannerRunning = true;
        logDebug('✅ Camera started successfully - scanning live!', 'success');

        const status = document.getElementById('scan-status');
        if (status) {
            status.textContent = '📷 Camera ready — scanning live.';
        }

    } catch (error) {
        scannerRunning = false;
        logDebug(`Camera start failed: ${error.message}`, 'error');
        console.error('Full error:', error);

        const status = document.getElementById('scan-status');
        if (status) {
            if (error.message.includes('NotAllowedError')) {
                status.textContent = '⚠️ Camera access blocked. Allow camera access and refresh.';
            } else if (error.message.includes('NotFoundError')) {
                status.textContent = '⚠️ No camera found on this device.';
            } else {
                status.textContent = `⚠️ Camera error: ${error.message.substring(0, 50)}`;
            }
        }
    }
}

function onScanSuccess(decodedText, decodedResult) {
    logDebug(`✅ Barcode detected: ${decodedText}`, 'success');
    logDebug(`Result format: ${decodedResult?.result?.format || 'unknown'}`);

    handleBarcodeResult(decodedText);
}

function onScanFailure(error) {
    // Ignore "No barcode found" errors (they're normal)
    if (error && error.includes('NotFoundException')) {
        return;
    }
    if (error && error.includes('no scan')) {
        return;
    }
    // Only log non-standard scan failures
    if (error && !scanHandled) {
        logDebug(`Scan frame: ${error?.substring?.(0, 40) || 'processing...'}`, 'warn');
    }
}

async function stopScanner() {
    if (html5QrCode) {
        try {
            logDebug('Stopping scanner...');
            await html5QrCode.stop();
            html5QrCode.clear();
            logDebug('Scanner stopped');
        } catch (error) {
            logDebug(`Stop scanner warning: ${error.message}`, 'warn');
        }
        html5QrCode = null;
        scannerRunning = false;
    }

    // Also stop any legacy video elements
    const video = document.getElementById('video');
    if (video && video.srcObject) {
        try {
            const stream = video.srcObject;
            stream.getTracks().forEach(track => track.stop());
            video.pause();
            video.srcObject = null;
            logDebug('Legacy video stopped');
        } catch (e) {
            // ignore
        }
    }
}

// ═══════════════════════════════════════════════════════════
// BARCODE RESULT HANDLING
// ═══════════════════════════════════════════════════════════

function handleBarcodeResult(barcode) {
    const normalized = String(barcode || '').trim();
    if (!normalized) {
        logDebug('Empty barcode, ignoring', 'warn');
        return;
    }

    if (scanHandled) {
        logDebug(`Duplicate scan prevented: ${normalized}`);
        return;
    }

    scanHandled = true;
    logDebug(`🎯 Barcode captured: ${normalized}`, 'success');

    const status = document.getElementById('scan-status');
    const detectedInput = document.getElementById('detectedBarcodeInput');
    const manualInput = document.getElementById('manualBarcodeInput');
    const rescanBtn = document.getElementById('rescanBtn');

    if (status) {
        status.textContent = `✅ Barcode: ${normalized}`;
    }

    if (detectedInput) detectedInput.value = normalized;
    if (manualInput) manualInput.value = normalized;
    if (rescanBtn) rescanBtn.style.display = 'block';

    localStorage.setItem('scannedBarcode', normalized);
    logDebug(`Barcode saved to localStorage: ${normalized}`);

    // Stop scanning to save battery
    logDebug('Pausing scanner after detection...');
    stopScanner();

    // Auto-navigate after short delay so user can see the detected barcode
    logDebug('Auto-navigating to product-result in 800ms...');
    setTimeout(() => {
        window.location.href = `product-result.html?barcode=${encodeURIComponent(normalized)}`;
    }, 800);
}

function goWithBarcode() {
    fetchDetectedBarcode();
}

function getBarcodeValue() {
    // ── CRITICAL FIX (Bug #6): Prioritise the ACTIVE TAB's live input.
    // Previously, a stale localStorage value could silently override whatever
    // the user had just typed in the Manual tab.
    const detected = document.getElementById('detectedBarcodeInput')?.value?.trim();
    const manual   = document.getElementById('manualBarcodeInput')?.value?.trim();
    const stored   = localStorage.getItem('scannedBarcode')?.trim();

    // If the user is on the manual tab and has typed something, that wins.
    let value = '';
    if (activeTab === 'manual' && manual) {
        value = manual;
        logDebug(`getBarcodeValue: using manual input "${manual}"`);
        // Clear stale stored value so it doesn't interfere on the result page
        localStorage.removeItem('scannedBarcode');
    } else if (activeTab === 'camera' && detected) {
        value = detected;
        logDebug(`getBarcodeValue: using detected camera input "${detected}"`);
    } else {
        // Fallback chain: detected → manual → stored
        value = detected || manual || stored || '';
        logDebug(`getBarcodeValue: fallback chain -> detected="${detected}" manual="${manual}" stored="${stored}" -> "${value}"`);
    }
    return value;
}

function fetchDetectedBarcode() {
    const barcode = getBarcodeValue();
    logDebug(`fetchDetectedBarcode called — barcode: "${barcode}" (activeTab: ${activeTab})`);

    if (!barcode) {
        logDebug('No barcode to fetch — showing alert', 'warn');
        alert('Please scan a barcode or enter the number manually.');
        return;
    }

    // Log format check (informational only — don't block non-standard codes)
    if (/^[0-9]{8,14}$/.test(barcode)) {
        logDebug(`Barcode format: standard numeric (${barcode.length} digits)`, 'success');
    } else {
        logDebug(`Non-standard barcode format: "${barcode}" — proceeding anyway`, 'warn');
    }

    localStorage.setItem('scannedBarcode', barcode);
    const dest = `product-result.html?barcode=${encodeURIComponent(barcode)}`;
    logDebug(`✅ Navigating to: ${dest}`, 'success');
    window.location.href = dest;
}

function rescanBarcode() {
    logDebug('Rescan requested');
    resetDetectedBarcodeUI();
    startScanner();
}

function handleImageUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
        logDebug('No file selected for upload', 'warn');
        return;
    }

    logDebug(`Image uploaded: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`);

    const reader = new FileReader();
    reader.onload = () => {
        const base64Str = reader.result.split(',')[1];
        localStorage.setItem('scannedImageBase64', base64Str);
        localStorage.removeItem('scannedBarcode');
        logDebug('Image saved to localStorage, navigating to product-result.html');
        window.location.href = 'product-result.html';
    };
    reader.onerror = () => {
        logDebug('FileReader error reading image', 'error');
    };
    reader.readAsDataURL(file);
}

// ── Expose functions globally for onclick handlers ────────
window.switchTab = switchTab;
window.fetchDetectedBarcode = fetchDetectedBarcode;
window.rescanBarcode = rescanBarcode;
window.goWithBarcode = goWithBarcode;
window.handleImageUpload = handleImageUpload;