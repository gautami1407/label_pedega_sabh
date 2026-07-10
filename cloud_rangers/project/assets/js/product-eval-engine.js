// ============================================================
// LABEL PADEGHA SABH — Product Evaluation Engine v4.1
// FIXED: API_BASE conflict, double res.json(), stepTimer race,
//        loading state management, comprehensive debug logging
// ============================================================

// ── CRITICAL FIX (Bug #2): Use a unique name to avoid `const` redeclaration
// conflict with the `const API_BASE` already declared in app.js.
// Both files are loaded on product-result.html — a duplicate `const`
// declaration is a SyntaxError that kills ALL JS on the page.
const EVAL_API_BASE = (window.location.protocol === 'file:') ? 'http://127.0.0.1:8000' : '';

// ── Debug Logger ──────────────────────────────────────────
function evalLog(message, type) {
    type = type || 'info';
    var prefix = '[ProductEval] ';
    if (type === 'error')   console.error(prefix + message);
    else if (type === 'warn') console.warn(prefix + message);
    else                    console.log(prefix + message);
}

// ── Step helpers ──────────────────────────────────────────
function setLoadingStep(stepId, state) {
    var el = document.getElementById(stepId);
    if (!el) return;
    el.className = 'loading-step ' + state;
}

function animateLoadingSteps(steps, delay) {
    delay = delay || 600;
    return (async function() {
        for (var i = 0; i < steps.length; i++) {
            setLoadingStep(steps[i], 'active');
            await new Promise(function(r) { setTimeout(r, delay); });
            setLoadingStep(steps[i], 'done');
        }
    })();
}

// ── State ─────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', function() {
    var urlParams  = new URLSearchParams(window.location.search);
    var barcodeFromUrl = urlParams.get('barcode');
    var barcode = barcodeFromUrl || localStorage.getItem('scannedBarcode');
    var image   = localStorage.getItem('scannedImageBase64');

    evalLog('🚀 DOMContentLoaded — barcode="' + barcode + '" image=' + !!image);

    if (barcode) {
        evalLog('Starting barcode analysis: ' + barcode);
        fetchFullAnalysis(barcode);
    } else if (image) {
        evalLog('Starting image analysis');
        localStorage.removeItem('scannedImageBase64');
        fetchProductByImage(image);
    } else {
        evalLog('No product data found — showing error', 'warn');
        showError('No product to analyze', 'Please scan a product or upload an image first.');
    }
});

// ── Error UI ──────────────────────────────────────────────
function showError(title, msg) {
    title = title || 'Error';
    msg   = msg   || 'Something went wrong.';
    evalLog('❌ showError: ' + title + ' — ' + msg, 'error');
    document.getElementById('loadingContainer').style.display = 'none';
    document.getElementById('productContainer').style.display = 'none';
    var err = document.getElementById('errorContainer');
    err.style.display = 'block';
    document.getElementById('errorTitle').textContent   = title;
    document.getElementById('errorMessage').textContent = msg;
}

// ── GET user preferences ───────────────────────────────────
function getHealthProfile() {
    try { return JSON.parse(localStorage.getItem('healthProfile') || '{}'); }
    catch (e) { return {}; }
}

// ═══════════════════════════════════════════════════════════
// Unified /api/analyze-product endpoint
// ═══════════════════════════════════════════════════════════
async function fetchFullAnalysis(barcode) {
    var loading   = document.getElementById('loadingContainer');
    var container = document.getElementById('productContainer');
    loading.style.display   = 'flex';
    container.style.display = 'none';

    var stepSeq = ['step-fetch', 'step-extract', 'step-regulatory', 'step-ai', 'step-personalize', 'step-dashboard'];

    // ── CRITICAL FIX (Bug #5): Run step animation concurrently — don't await it
    // before the fetch. This prevents a 3-second deadlock if the API is fast.
    var stepTimer = animateLoadingSteps(stepSeq, 500);

    var data = null;

    try {
        var profile = getHealthProfile();
        var payload = {
            barcode:    barcode,
            age:        profile.age        || null,
            allergies:  profile.allergies  || [],
            conditions: profile.conditions || [],
            diet:       profile.diet       || ''
        };

        evalLog('📡 Sending POST /api/analyze-product  barcode=' + barcode);
        evalLog('   payload: ' + JSON.stringify(payload));

        var res = await fetch(EVAL_API_BASE + '/api/analyze-product', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload)
        });

        evalLog('✅ API response received — HTTP ' + res.status + ' ' + res.statusText);

        // ── CRITICAL FIX (Bug #3): Read the response body EXACTLY ONCE.
        // Previously the code called res.json() inside the !res.ok branch AND
        // again outside it, causing "body stream already consumed" TypeError.
        data = await res.json();
        evalLog('✅ Response JSON parsed successfully');
        evalLog('   Keys: ' + Object.keys(data).join(', '));

        if (!res.ok) {
            // Backend returned a non-2xx status — extract message from either field
            var errMsg = (data && (data.detail || data.error)) || ('Server error (' + res.status + ')');
            evalLog('❌ Non-OK status: ' + errMsg, 'error');
            throw new Error(errMsg);
        }

        // Backend may return 200 + {"error": "..."} for product-not-found
        if (data.error) {
            evalLog('❌ Product not found: ' + data.error, 'warn');
            showError('Product Not Found', data.error);
            return;
        }

    } catch (err) {
        evalLog('❌ Fetch/parse failed: ' + err.message, 'error');
        // ── CRITICAL FIX (Bug #4): Always hide loading in the error path
        loading.style.display = 'none';
        if (err.message && err.message.includes('Failed to fetch')) {
            showError(
                'Cannot Connect to Backend',
                'Make sure the Python backend is running: cd backend && uvicorn app:app --reload  (port 8000)'
            );
        } else {
            showError('Analysis Failed', err.message || 'Could not connect to the server.');
        }
        return;
    }

    // ── CRITICAL FIX (Bug #4): Hide loading BEFORE rendering so the product
    // cards are not covered by the spinner overlay.
    loading.style.display = 'none';

    evalLog('🎨 Calling renderFullAnalysis...');
    renderFullAnalysis(data, getHealthProfile());

    // Let the step animation finish in the background (it's already running)
    stepTimer.catch(function() {});
}

// ═══════════════════════════════════════════════════════════
// LEGACY: Image to /api/analyze
// ═══════════════════════════════════════════════════════════
async function fetchProductByImage(base64Image) {
    var loading   = document.getElementById('loadingContainer');
    var container = document.getElementById('productContainer');
    loading.style.display   = 'flex';
    container.style.display = 'none';

    var stepSeq   = ['step-fetch', 'step-extract', 'step-regulatory', 'step-ai', 'step-personalize', 'step-dashboard'];
    var stepTimer = animateLoadingSteps(stepSeq, 700);

    var data = null;

    try {
        var prefs     = getHealthProfile();
        var imageData = 'data:image/jpeg;base64,' + base64Image;

        evalLog('📡 Sending POST /api/analyze (image)');

        var res = await fetch(EVAL_API_BASE + '/api/analyze', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ image: imageData, preferences: prefs })
        });

        evalLog('✅ Image API response — HTTP ' + res.status);
        data = await res.json();   // read once
        evalLog('✅ Image response JSON parsed');

        if (!res.ok) {
            var errMsg = (data && (data.error || data.detail)) || ('Server error (' + res.status + ')');
            throw new Error(errMsg);
        }

        if (data.error && !data.name) {
            showError('Image Analysis Failed', data.error);
            loading.style.display = 'none';
            return;
        }

    } catch (err) {
        evalLog('❌ Image fetch failed: ' + err.message, 'error');
        loading.style.display = 'none';
        showError('Image Analysis Failed', err.message || 'Could not analyze the image.');
        return;
    }

    loading.style.display = 'none';
    renderFullAnalysis(data, getHealthProfile());
    stepTimer.catch(function() {});
}

// ═══════════════════════════════════════════════════════════
// RENDER ENGINE v4.1 — Full dashboard
// ═══════════════════════════════════════════════════════════

// HTML entity encoding helper
var _amp  = '&' + 'amp;';
var _lt   = '&' + 'lt;';
var _gt   = '&' + 'gt;';
var _quot = '&' + 'quot;';

function escHtml(s) {
    return String(s)
        .replace(/&/g, _amp)
        .replace(/</g, _lt)
        .replace(/>/g, _gt)
        .replace(/"/g, _quot)
        .replace(/'/g, '&#039;');
}

function renderFullAnalysis(analysisData, profile) {
    if (!profile) profile = {};
    evalLog('🎨 renderFullAnalysis — product: ' + (analysisData.product && analysisData.product.name));

    var container = document.getElementById('productContainer');
    if (!container) {
        evalLog('❌ productContainer element not found!', 'error');
        return;
    }

    try {
        var product                = analysisData.product                || {};
        var nutrition              = analysisData.nutrition              || {};
        var ingredients            = analysisData.ingredients            || [];
        var ingredientExplanations = analysisData.ingredient_explanations|| [];
        var concernScore           = analysisData.concern_score          || { score: 50, level: 'Moderate Concern', factors: [] };
        var allergens              = analysisData.allergens              || [];
        var alerts                 = analysisData.alerts                 || [];
        var personalizedWarnings   = analysisData.personalized_warnings  || [];
        var regulatory             = analysisData.regulatory             || [];
        var news                   = analysisData.news                   || [];
        var nova                   = analysisData.nova                   || { level: 'Unknown', name: 'Not Classified', description: '' };

        evalLog('📊 Data summary:');
        evalLog('   product.name   = ' + product.name);
        evalLog('   ingredients    = ' + ingredients.length);
        evalLog('   allergens      = ' + allergens.length);
        evalLog('   regulatory     = ' + regulatory.length);
        evalLog('   concern_score  = ' + concernScore.score);
        evalLog('   news items     = ' + news.length);

        // Concern Score
        var score       = concernScore.score  || 50;
        var scoreLevel  = concernScore.level  || 'Moderate Concern';
        var scoreFactors= concernScore.factors || [];

        var scoreRingColor = '#10B981';
        if (score >= 70) scoreRingColor = '#EF4444';
        else if (score >= 40) scoreRingColor = '#F59E0B';

        var circumference = 2 * Math.PI * 52;
        var fillOffset    = circumference - (score / 100) * circumference;

        // ── Factor 3: Ingredient Explanations ──
        var ingExplHtml = '';
        if (ingredientExplanations.length > 0) {
            for (var i = 0; i < ingredientExplanations.length; i++) {
                var ing      = ingredientExplanations[i];
                var riskClass= 'risk-safe';
                if (ing.category === 'Preservative' || ing.category === 'Colour') riskClass = 'risk-high';
                else if (ing.category === 'Sweetener' || ing.category === 'Flavour Enhancer') riskClass = 'risk-moderate';

                ingExplHtml += '<div class="ingredient-card ' + riskClass + '">';
                ingExplHtml += '<p class="ing-name">' + escHtml(ing.name || '') + '</p>';
                if (ing.simple_name) ingExplHtml += '<p class="ing-purpose"><strong>Also known as:</strong> ' + escHtml(ing.simple_name) + '</p>';
                if (ing.purpose)     ingExplHtml += '<p class="ing-purpose"><strong>Purpose:</strong> ' + escHtml(ing.purpose) + '</p>';
                if (ing.description) ingExplHtml += '<p class="ing-purpose">' + escHtml(ing.description) + '</p>';
                if (ing.category)    ingExplHtml += '<span class="tag-pill">' + escHtml(ing.category) + '</span>';
                ingExplHtml += '</div>';
            }
        } else {
            ingExplHtml = '<p class="text-muted">No ingredient data available.</p>';
        }

        // ── Factor 4: Allergen Alerts ──
        var allergenHtml = '';
        if (allergens.length > 0) {
            for (var a = 0; a < allergens.length; a++) {
                var al = allergens[a];
                allergenHtml += '<div class="warning-card danger mb-2">';
                allergenHtml += '<div class="warning-icon"><i class="bi bi-exclamation-triangle-fill"></i></div>';
                allergenHtml += '<div><div class="warning-title">Contains ' + escHtml(al.allergen || '') + '</div>';
                allergenHtml += '<p class="warning-desc">Found in: ' + escHtml(al.found_in || '') + '</p></div></div>';
            }
        } else {
            allergenHtml = '<div class="alert alert-success"><i class="bi bi-check-circle-fill me-2"></i><strong>No common allergens detected</strong> in the ingredient list.</div>';
        }

        // ── Factor 5: Personalized Warnings ──
        var warningsHtml = '';
        if (personalizedWarnings.length > 0) {
            for (var w = 0; w < personalizedWarnings.length; w++) {
                var warn  = personalizedWarnings[w];
                var wType = warn.type === 'red' ? 'danger' : 'caution';
                var wIcon = warn.type === 'red' ? 'exclamation-triangle-fill' : 'exclamation-circle-fill';
                warningsHtml += '<div class="warning-card ' + wType + '">';
                warningsHtml += '<div class="warning-icon"><i class="bi bi-' + wIcon + '"></i></div>';
                warningsHtml += '<div><div class="warning-title">' + escHtml(warn.title || 'Warning') + '</div>';
                warningsHtml += '<p class="warning-desc">' + escHtml(warn.description || '') + '</p></div></div>';
            }
        } else {
            warningsHtml = '<div class="alert alert-success"><i class="bi bi-check-circle-fill me-2"></i><strong>No personalized warnings</strong> based on your health profile.</div>';
        }

        // ── Factor 6: Regulatory Status ──
        var regHtml = '';
        if (regulatory.length > 0) {
            for (var r = 0; r < regulatory.length; r++) {
                var reg = regulatory[r];
                regHtml += '<div class="factor-detail-card mb-3" style="background:var(--gray-100);padding:16px;border-radius:14px;">';
                regHtml += '<h5 style="font-weight:700;margin-bottom:10px;">' + escHtml(reg.ingredient) + '</h5>';
                regHtml += '<div class="reg-pills">';
                var statuses = reg.regulatory_status || [];
                for (var s = 0; s < statuses.length; s++) {
                    var rs  = statuses[s];
                    var cls = rs.status === 'Allowed' ? 'approved' : (rs.status === 'Banned' ? 'banned' : 'review');
                    var icon= rs.status === 'Allowed' ? 'check-circle-fill' : (rs.status === 'Banned' ? 'x-circle-fill' : 'exclamation-circle-fill');
                    regHtml += '<span class="reg-pill ' + cls + '"><i class="bi bi-' + icon + '"></i> ' + escHtml(rs.country) + ' — ' + escHtml(rs.status) + '</span>';
                }
                regHtml += '</div>';
                if (reg.notes) regHtml += '<p class="text-muted small mt-2">' + escHtml(reg.notes) + '</p>';
                regHtml += '</div>';
            }
        } else {
            regHtml = '<p class="text-muted">No verified regulatory information available for the detected ingredients.</p>';
        }

        // News / Recalls
        var newsHtml = '';
        if (news.length > 0) {
            for (var n = 0; n < news.length; n++) {
                var newsItem = news[n];
                newsHtml += '<div class="warning-card caution mb-2">';
                newsHtml += '<div class="warning-icon"><i class="bi bi-newspaper"></i></div>';
                newsHtml += '<div><div class="warning-title">' + escHtml(newsItem.title || 'News') + '</div>';
                newsHtml += '<p class="warning-desc">';
                if (newsItem.source) newsHtml += '<strong>Source:</strong> ' + escHtml(newsItem.source);
                if (newsItem.date)   newsHtml += ' - ' + escHtml(newsItem.date);
                if (newsItem.link)   newsHtml += '<br><a href="' + escHtml(newsItem.link) + '" target="_blank" style="color:var(--primary-emerald);">Read more</a>';
                newsHtml += '</p></div></div>';
            }
        } else {
            newsHtml = '<div class="alert alert-success"><i class="bi bi-shield-check-fill me-2"></i><strong>No recent recalls or safety notices</strong> found for this product.</div>';
        }

        // Nutrition table
        var nutritionHtml = buildNutritionTable(nutrition);

        // Concern Factors list
        var factorsHtml = '';
        if (scoreFactors.length > 0) {
            factorsHtml = '<ul style="margin:0;padding-left:20px;">';
            for (var f = 0; f < scoreFactors.length; f++) {
                factorsHtml += '<li style="color:var(--gray-700);margin-bottom:4px;">' + escHtml(scoreFactors[f]) + '</li>';
            }
            factorsHtml += '</ul>';
        } else {
            factorsHtml = '<p class="text-muted small">No specific concern factors identified.</p>';
        }

        // NOVA
        var novaHtml = '';
        if (nova.level !== 'Unknown') {
            novaHtml = '<span class="tag-pill" style="background:rgba(16,185,129,0.1);color:#059669;">NOVA ' + nova.level + ': ' + escHtml(nova.name) + '</span>';
        }

        // AI Summary
        var aiSummary = analysisData.ai_summary || generateAISummary(product, nutrition, score, alerts);

        // ════════════════════════════════════════════════
        // BUILD THE FULL DASHBOARD — 6 Factor Cards
        // ════════════════════════════════════════════════
        var html = '';

        // ── Product Header Card ──
        html += '<div class="product-header-card fade-in mb-4">';
        html += '<div class="product-image-large">';
        if (product.image_url) {
            html += '<img src="' + escHtml(product.image_url) + '" alt="' + escHtml(product.name || '') + '" style="width:100%;height:100%;object-fit:cover;" onerror="this.style.display=\'none\'">';
        } else {
            html += '<div style="display:flex;align-items:center;justify-content:center;height:100%;background:var(--gray-100);border-radius:16px;"><i class="bi bi-box" style="font-size:5rem;color:var(--gray-300);"></i></div>';
        }
        html += '</div>';
        html += '<div class="product-header-info">';
        html += '<h1 class="product-title">' + escHtml(product.name || 'Unknown Product') + '</h1>';
        html += '<p class="product-brand-large" style="color:var(--gray-500);font-size:1.1rem;">' + escHtml(product.brand || 'Unknown Brand') + '</p>';
        html += '<div class="product-meta">';
        html += '<span><i class="bi bi-tag text-success"></i> ' + escHtml((Array.isArray(product.categories) ? product.categories.join(', ') : product.categories) || 'Food') + '</span>';
        html += '<span><i class="bi bi-database text-muted"></i> Source: ' + escHtml(product.source || 'OpenFoodFacts') + '</span>';
        html += novaHtml;
        html += '</div>';
        if (product.health_note)     html += '<div class="mt-2 p-2" style="background:rgba(16,185,129,0.08);border-radius:10px;font-size:13px;color:#065f46;"><i class="bi bi-heart-pulse me-1"></i>' + escHtml(product.health_note) + '</div>';
        if (product.key_differences) html += '<div class="mt-2 p-2" style="background:rgba(59,130,246,0.08);border-radius:10px;font-size:13px;color:#1e40af;"><i class="bi bi-info-circle me-1"></i><strong>India vs Global:</strong> ' + escHtml(product.key_differences) + '</div>';
        if (product.consumer_note)   html += '<div class="mt-2 p-2" style="background:rgba(245,158,11,0.08);border-radius:10px;font-size:13px;color:#92400e;"><i class="bi bi-lightbulb me-1"></i>' + escHtml(product.consumer_note) + '</div>';
        html += '</div></div>';

        // ── Factor 1: Concern Score ──
        html += '<div class="factor-detail-card fade-in-up stagger-1">';
        html += '<div class="factor-header"><div class="factor-icon-lg"><i class="bi bi-speedometer2"></i></div>';
        html += '<div><h3>Concern Score</h3><p class="factor-subtitle">Rule-based risk assessment (0–100). Higher = More Concern.</p></div></div>';
        html += '<div class="factor-body">';
        html += '<div class="concern-score-block">';
        html += '<div class="score-ring-container">';
        html += '<svg class="score-ring-svg" width="120" height="120" viewBox="0 0 120 120">';
        html += '<circle class="score-ring-bg" cx="60" cy="60" r="52"/>';
        html += '<circle class="score-ring-fill" cx="60" cy="60" r="52" stroke="' + scoreRingColor + '" stroke-dasharray="' + circumference + '" stroke-dashoffset="' + fillOffset + '"/>';
        html += '</svg>';
        html += '<div class="score-ring-text"><span class="score-ring-num" style="color:' + scoreRingColor + ';">' + score + '</span><span class="score-ring-label">/ 100</span></div>';
        html += '</div>';
        html += '<div class="score-description" style="flex:1;">';
        html += '<h4 style="font-size:1.2rem;font-weight:700;margin-bottom:8px;color:' + scoreRingColor + ';">' + escHtml(scoreLevel) + '</h4>';
        html += '<div class="progress-bar-custom mb-3" style="height:10px;"><div class="progress-fill" style="width:' + score + '%;background:' + scoreRingColor + ';"></div></div>';
        html += '<p class="text-muted small" style="font-weight:600;margin-bottom:6px;">Contributing factors:</p>';
        html += factorsHtml;
        html += '</div></div></div></div>';

        // ── Factor 2: Nutrition Facts ──
        html += '<div class="factor-detail-card fade-in-up stagger-2">';
        html += '<div class="factor-header"><div class="factor-icon-lg" style="background:linear-gradient(135deg,#06B6D4,#0891B2);"><i class="bi bi-bar-chart-fill"></i></div>';
        html += '<div><h3>Nutrition Facts</h3><p class="factor-subtitle">Per 100g serving</p></div></div>';
        html += '<div class="factor-body">' + nutritionHtml + '</div></div>';

        // ── Factor 3: Ingredient Breakdown ──
        html += '<div class="factor-detail-card fade-in-up stagger-3">';
        html += '<div class="factor-header"><div class="factor-icon-lg" style="background:linear-gradient(135deg,#3B82F6,#2563EB);"><i class="bi bi-clipboard-data"></i></div>';
        html += '<div><h3>Ingredient Breakdown</h3><p class="factor-subtitle">' + ingredients.length + ' ingredients detected</p></div></div>';
        html += '<div class="factor-body">' + ingExplHtml;
        html += '<hr style="margin:1rem 0;"><p class="text-muted small"><strong>Full ingredient list:</strong> ' + escHtml(ingredients.join(', ') || 'Not available') + '</p>';
        html += '</div></div>';

        // ── Factor 4: Allergen Alerts ──
        html += '<div class="factor-detail-card fade-in-up stagger-4" style="border-color:' + (allergens.length ? 'rgba(239,68,68,0.3)' : 'var(--gray-200)') + ';">';
        html += '<div class="factor-header" style="background:' + (allergens.length ? 'rgba(239,68,68,0.05)' : 'var(--light-gray)') + ';">';
        html += '<div class="factor-icon-lg" style="background:linear-gradient(135deg,#EF4444,#B91C1C);"><i class="bi bi-exclamation-triangle"></i></div>';
        html += '<div><h3>Allergen Alerts</h3><p class="factor-subtitle">Detected potential allergens in ingredient list</p></div></div>';
        html += '<div class="factor-body">' + allergenHtml + '</div></div>';

        // ── Factor 5: Personalized Warnings ──
        var hasRedWarning = personalizedWarnings.some(function(w) { return w.type === 'red'; });
        html += '<div class="factor-detail-card fade-in-up stagger-5" style="border-color:' + (hasRedWarning ? 'rgba(239,68,68,0.3)' : 'var(--gray-200)') + ';">';
        html += '<div class="factor-header" style="background:' + (hasRedWarning ? 'rgba(239,68,68,0.05)' : 'var(--light-gray)') + ';">';
        html += '<div class="factor-icon-lg" style="background:linear-gradient(135deg,#F59E0B,#D97706);"><i class="bi bi-person-exclamation"></i></div>';
        html += '<div><h3>Personalized Warnings</h3><p class="factor-subtitle">Based on your health profile</p></div></div>';
        html += '<div class="factor-body">' + warningsHtml + '</div></div>';

        // ── Factor 6: Global Regulatory Status ──
        html += '<div class="factor-detail-card fade-in-up stagger-6">';
        html += '<div class="factor-header"><div class="factor-icon-lg" style="background:linear-gradient(135deg,#8B5CF6,#7C3AED);"><i class="bi bi-globe-americas"></i></div>';
        html += '<div><h3>Global Regulatory Status</h3><p class="factor-subtitle">Cross-country compliance for detected ingredients</p></div></div>';
        html += '<div class="factor-body">' + regHtml + '</div></div>';

        // ── Safety Alerts & Recalls ──
        html += '<div class="factor-detail-card fade-in-up stagger-7">';
        html += '<div class="factor-header"><div class="factor-icon-lg" style="background:linear-gradient(135deg,#F59E0B,#D97706);"><i class="bi bi-megaphone-fill"></i></div>';
        html += '<div><h3>Safety Alerts &amp; Recalls</h3><p class="factor-subtitle">Official recall notices and safety news</p></div></div>';
        html += '<div class="factor-body">' + newsHtml + '</div></div>';

        // ── AI Summary ──
        html += '<div class="factor-detail-card fade-in-up stagger-7">';
        html += '<div class="factor-header"><div class="factor-icon-lg" style="background:linear-gradient(135deg,#10B981,#059669);"><i class="bi bi-robot"></i></div>';
        html += '<div><h3>AI Summary</h3><p class="factor-subtitle">Simplified overview based on verified data</p></div></div>';
        html += '<div class="factor-body"><div style="background:var(--gray-100);border-radius:14px;padding:20px;line-height:1.7;">' + escHtml(aiSummary) + '</div></div></div>';

        // ── Decision Banner ──
        html += '<div class="decision-banner fade-in-up stagger-7">';
        html += '<h4>Your Decision Matters</h4>';
        html += '<p>Label Padegha Sabh provides transparent, data-driven insights — not a verdict. You are empowered to make the best choice for yourself.</p>';
        html += '</div>';

        // ── AI CTA ──
        html += '<div class="ai-cta-section fade-in-up stagger-7">';
        html += '<div class="ai-cta-text"><h3>Have questions? Ask the AI</h3>';
        html += '<p>Get deeper insights about this product\'s ingredients, health impacts, and alternatives.</p>';
        html += '<a href="ai-chat.html" class="btn mt-3" style="background:#fff;color:var(--primary-emerald);font-weight:700;border-radius:12px;padding:10px 24px;">';
        html += '<i class="bi bi-chat-dots-fill me-2"></i>Open AI Chat</a></div>';
        html += '<i class="bi bi-robot ai-cta-icon"></i></div>';

        container.innerHTML = html;
        container.style.display = 'block';

        evalLog('✅ UI updated — all 6 factor cards rendered successfully', 'info');

        // Save context for AI chat
        try {
            localStorage.setItem('lps_ai_context', JSON.stringify({
                name:         product.name,
                brand:        product.brand,
                ingredients:  ingredients,
                concern_score:score,
                allergens:    alerts,
                nutrition:    nutrition
            }));
        } catch (e) {}

    } catch (err) {
        evalLog('❌ renderFullAnalysis crashed: ' + err.message, 'error');
        console.error('[ProductEval] Render error detail:', err);
        container.innerHTML  = '<div class="error-card"><i class="bi bi-exclamation-circle"></i><h4>Analysis Preview Available</h4>';
        container.innerHTML += '<p class="text-muted">We received product information, but the full dashboard could not be rendered.</p>';
        container.innerHTML += '<div class="mt-3 text-start">';
        container.innerHTML += '<strong>' + escHtml((analysisData && analysisData.product && analysisData.product.name) || 'Unknown Product') + '</strong>';
        container.innerHTML += '<p class="text-muted mb-0">' + escHtml((analysisData && analysisData.ingredients || []).join(', ') || 'No details available.') + '</p>';
        container.innerHTML += '</div></div>';
        container.style.display = 'block';
    }
}

// ═══════════════════════════════════════════════════════════
// AI Summary Generator (rule-based fallback, no API needed)
// ═══════════════════════════════════════════════════════════
function generateAISummary(product, nutrition, score, alerts) {
    var name     = product.name  || 'this product';
    var brand    = product.brand || '';
    var scoreVal = score || 50;

    var summary = name;
    if (brand) summary += ' by ' + brand;
    summary += '. ';

    if (scoreVal <= 20)      summary += 'This product has a low concern score, suggesting it may be a reasonable choice for most consumers. ';
    else if (scoreVal <= 50) summary += 'This product has a moderate concern score. ';
    else if (scoreVal <= 80) summary += 'This product has a high concern score. ';
    else                     summary += 'This product has a very high concern score. ';

    if (alerts && alerts.length > 0) {
        summary += 'It contains potential allergens: ' + alerts.join(', ') + '. ';
        summary += 'If you have known allergies, please check the ingredient list carefully. ';
    }

    var sugar = nutrition.sugars_100g;
    var salt  = nutrition.salt_100g;
    var fiber = nutrition.fiber_100g;

    if (sugar !== undefined) {
        if (sugar > 15)     summary += 'Sugar content is high at ' + sugar + 'g per 100g. ';
        else if (sugar > 5) summary += 'Contains ' + sugar + 'g of sugar per 100g. ';
        else                summary += 'Sugar content is relatively low at ' + sugar + 'g per 100g. ';
    }
    if (salt !== undefined) {
        if (salt > 1.5)     summary += 'Sodium content is high at ' + salt + 'g per 100g. ';
        else if (salt > 0.5)summary += 'Contains ' + salt + 'g of salt per 100g. ';
    }
    if (fiber !== undefined && fiber > 3) {
        summary += 'Good source of dietary fiber (' + fiber + 'g per 100g). ';
    }

    summary += 'Always consider your personal dietary needs and consult healthcare professionals for personalized advice.';
    return summary;
}

// ═══════════════════════════════════════════════════════════
// Nutrition Table Builder
// ═══════════════════════════════════════════════════════════
function buildNutritionTable(nutrition) {
    var key_map = {
        'energy-kcal_100g':    ['Calories (kcal)', 'kcal'],
        'energy_100g':         ['Energy (kJ)',      'kJ'],
        'proteins_100g':       ['Protein',          'g'],
        'carbohydrates_100g':  ['Carbohydrates',    'g'],
        'sugars_100g':         ['of which Sugars',  'g'],
        'fat_100g':            ['Fat',              'g'],
        'saturated-fat_100g':  ['Saturated Fat',    'g'],
        'fiber_100g':          ['Dietary Fiber',    'g'],
        'sodium_100g':         ['Sodium',           'g'],
        'salt_100g':           ['Salt',             'g'],
        'calcium_100g':        ['Calcium',          'mg'],
        'iron_100g':           ['Iron',             'mg'],
    };

    var n = nutrition;
    if (Array.isArray(n)) {
        var obj = {};
        for (var i = 0; i < n.length; i++) {
            var item = n[i];
            var k    = (item.nutrientName || '').toLowerCase().replace(/ /g, '_') + '_100g';
            obj[k]   = item.amount;
        }
        n = obj;
    }

    var rows = '';
    var keys = Object.keys(key_map);
    for (var j = 0; j < keys.length; j++) {
        var key = keys[j];
        if (n[key] === undefined || n[key] === null) continue;
        var label = key_map[key][0];
        var unit  = key_map[key][1];
        var val   = parseFloat(n[key] || 0).toFixed(2);

        var lvlClass = '';
        if      (key.indexOf('sugars')    >= 0 && val > 15)  lvlClass = 'nutriment-level-high';
        else if (key.indexOf('sugars')    >= 0 && val > 5)   lvlClass = 'nutriment-level-moderate';
        else if (key.indexOf('salt')      >= 0 && val > 1.5) lvlClass = 'nutriment-level-high';
        else if (key.indexOf('salt')      >= 0 && val > 0.5) lvlClass = 'nutriment-level-moderate';
        else if (key.indexOf('saturated') >= 0 && val > 5)   lvlClass = 'nutriment-level-high';
        else if (key.indexOf('fiber')     >= 0 && val > 3)   lvlClass = 'nutriment-level-low';

        rows += '<div class="nutriment-row">';
        rows += '<span class="nutriment-key">' + label + '</span>';
        rows += '<span class="nutriment-val ' + lvlClass + '">' + val + ' ' + unit + '</span>';
        rows += '</div>';
    }

    if (rows.length === 0) {
        return '<p class="text-muted">No nutrition data available for this product.</p>';
    }
    return '<div class="nutriment-table">' + rows + '</div>';
}