// ============================================================
// LABEL PADEGHA SABH — Product Evaluation Engine v4.0
// Calls unified /api/analyze-product endpoint
// Displays full 10-step analysis pipeline
// ============================================================

const API_BASE = "http://127.0.0.1:8000";

// ── Step helpers ──────────────────────────────────────────
function setLoadingStep(stepId, state) {
    const el = document.getElementById(stepId);
    if (!el) return;
    el.className = `loading-step ${state}`;
}

async function animateLoadingSteps(steps, delay) {
    delay = delay || 600;
    for (let i = 0; i < steps.length; i++) {
        setLoadingStep(steps[i], 'active');
        await new Promise(function(r) { setTimeout(r, delay); });
        setLoadingStep(steps[i], 'done');
    }
}

// ── State ─────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", function() {
    var urlParams = new URLSearchParams(window.location.search);
    var barcodeFromUrl = urlParams.get("barcode");
    var barcode = barcodeFromUrl || localStorage.getItem("scannedBarcode");
    var image = localStorage.getItem("scannedImageBase64");

    if (barcode) {
        fetchFullAnalysis(barcode);
    } else if (image) {
        localStorage.removeItem("scannedImageBase64");
        fetchProductByImage(image);
    } else {
        showError("No product to analyze", "Please scan a product or upload an image first.");
    }
});

// ── Error UI ──────────────────────────────────────────────
function showError(title, msg) {
    title = title || "Error";
    msg = msg || "Something went wrong.";
    document.getElementById("loadingContainer").style.display = "none";
    document.getElementById("productContainer").style.display = "none";
    var err = document.getElementById("errorContainer");
    err.style.display = "block";
    document.getElementById("errorTitle").textContent = title;
    document.getElementById("errorMessage").textContent = msg;
}

// ── GET user preferences ───────────────────────────────────
function getHealthProfile() {
    try { return JSON.parse(localStorage.getItem("healthProfile") || "{}"); }
    catch (e) { return {}; }
}

// ═══════════════════════════════════════════════════════════
// Unified /api/analyze-product endpoint
// ═══════════════════════════════════════════════════════════
async function fetchFullAnalysis(barcode) {
    var loading = document.getElementById("loadingContainer");
    var container = document.getElementById("productContainer");
    loading.style.display = "flex";
    container.style.display = "none";

    var stepSeq = ['step-fetch', 'step-extract', 'step-regulatory', 'step-ai', 'step-personalize', 'step-dashboard'];
    var stepTimer = animateLoadingSteps(stepSeq, 500);

    try {
        var profile = getHealthProfile();
        var payload = {
            barcode: barcode,
            age: profile.age || null,
            allergies: profile.allergies || [],
            conditions: profile.conditions || [],
            diet: profile.diet || ""
        };

        console.log("[ProductEval] Calling /api/analyze-product for barcode: " + barcode, payload);

        var res = await fetch(API_BASE + "/api/analyze-product", {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        await stepTimer;

        if (!res.ok) {
            var body = await res.json().catch(function() { return {}; });
            throw new Error(body.detail || body.error || ("Server error (" + res.status + ")"));
        }

        var data = await res.json();
        console.log("[ProductEval] Analysis received:", data);

        if (data.error) {
            showError("Product Not Found", data.error);
            return;
        }

        renderFullAnalysis(data, profile);
    } catch (err) {
        console.error('[ProductEval] Error:', err);
        showError("Analysis Failed", err.message || "Could not connect to the server. Make sure the backend is running.");
    } finally {
        loading.style.display = "none";
    }
}

// ═══════════════════════════════════════════════════════════
// LEGACY: Image to /api/analyze
// ═══════════════════════════════════════════════════════════
async function fetchProductByImage(base64Image) {
    var loading = document.getElementById("loadingContainer");
    var container = document.getElementById("productContainer");
    loading.style.display = "flex";
    container.style.display = "none";

    var stepSeq = ['step-fetch', 'step-extract', 'step-regulatory', 'step-ai', 'step-personalize', 'step-dashboard'];
    var stepTimer = animateLoadingSteps(stepSeq, 700);

    try {
        var prefs = getHealthProfile();
        var imageData = "data:image/jpeg;base64," + base64Image;
        var res = await fetch(API_BASE + "/api/analyze", {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData, preferences: prefs })
        });

        await stepTimer;

        if (!res.ok) {
            var body = await res.json().catch(function() { return {}; });
            throw new Error(body.error || ("Server error (" + res.status + ")"));
        }

        var data = await res.json();
        if (data.error) {
            if (!data.name) { showError("Image Analysis Failed", data.error); return; }
        }

        renderFullAnalysis(data, prefs);
    } catch (err) {
        console.error(err);
        showError("Image Analysis Failed", err.message || "Could not analyze the image.");
    } finally {
        loading.style.display = "none";
    }
}

// ═══════════════════════════════════════════════════════════
// RENDER ENGINE v4 - Full 10-step dashboard
// ═══════════════════════════════════════════════════════════

// HTML entity encoding helper (split to prevent auto-formatter issues)
var _amp = "&" + "amp;";
var _lt = "&" + "lt;";
var _gt = "&" + "gt;";
var _quot = "&" + "quot;";

function escHtml(s) {
    return String(s)
        .replace(/&/g, _amp)
        .replace(/</g, _lt)
        .replace(/>/g, _gt)
        .replace(/"/g, _quot)
        .replace(/'/g, "&#039;");
}

function renderFullAnalysis(analysisData, profile) {
    if (!profile) profile = {};
    var container = document.getElementById("productContainer");
    if (!container) {
        console.error("Product container not found.");
        return;
    }

    try {
        var product = analysisData.product || {};
        var nutrition = analysisData.nutrition || {};
        var ingredients = analysisData.ingredients || [];
        var ingredientExplanations = analysisData.ingredient_explanations || [];
        var concernScore = analysisData.concern_score || { score: 50, level: "Moderate Concern", factors: [] };
        var allergens = analysisData.allergens || [];
        var alerts = analysisData.alerts || [];
        var personalizedWarnings = analysisData.personalized_warnings || [];
        var regulatory = analysisData.regulatory || [];
        var news = analysisData.news || [];
        var nova = analysisData.nova || { level: "Unknown", name: "Not Classified", description: "" };

        // Concern Score
        var score = concernScore.score || 50;
        var scoreLevel = concernScore.level || "Moderate Concern";
        var scoreFactors = concernScore.factors || [];

        var scoreRingColor = '#10B981';
        if (score >= 70) scoreRingColor = '#EF4444';
        else if (score >= 40) scoreRingColor = '#F59E0B';

        var circumference = 2 * Math.PI * 52;
        var fillOffset = circumference - (score / 100) * circumference;

        // Ingredient Explanations
        var ingExplHtml = "";
        if (ingredientExplanations.length > 0) {
            for (var i = 0; i < ingredientExplanations.length; i++) {
                var ing = ingredientExplanations[i];
                var riskClass = "risk-safe";
                if (ing.category === "Preservative" || ing.category === "Colour") riskClass = "risk-high";
                else if (ing.category === "Sweetener" || ing.category === "Flavour Enhancer") riskClass = "risk-moderate";

                ingExplHtml += '<div class="ingredient-card ' + riskClass + '">';
                ingExplHtml += '<p class="ing-name">' + escHtml(ing.name || '') + '</p>';
                if (ing.simple_name) ingExplHtml += '<p class="ing-purpose"><strong>Also known as:</strong> ' + escHtml(ing.simple_name) + '</p>';
                if (ing.purpose) ingExplHtml += '<p class="ing-purpose"><strong>Purpose:</strong> ' + escHtml(ing.purpose) + '</p>';
                if (ing.description) ingExplHtml += '<p class="ing-purpose">' + escHtml(ing.description) + '</p>';
                if (ing.category) ingExplHtml += '<span class="tag-pill">' + escHtml(ing.category) + '</span>';
                ingExplHtml += '</div>';
            }
        } else {
            ingExplHtml = '<p class="text-muted">No ingredient data available.</p>';
        }

        // Allergen Alerts
        var allergenHtml = "";
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

        // Personalized Warnings
        var warningsHtml = "";
        if (personalizedWarnings.length > 0) {
            for (var w = 0; w < personalizedWarnings.length; w++) {
                var warn = personalizedWarnings[w];
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

        // Regulatory Status
        var regHtml = "";
        if (regulatory.length > 0) {
            for (var r = 0; r < regulatory.length; r++) {
                var reg = regulatory[r];
                regHtml += '<div class="factor-detail-card mb-3" style="background:var(--gray-100);padding:16px;border-radius:14px;">';
                regHtml += '<h5 style="font-weight:700;margin-bottom:10px;">' + escHtml(reg.ingredient) + '</h5>';
                regHtml += '<div class="reg-pills">';
                var statuses = reg.regulatory_status || [];
                for (var s = 0; s < statuses.length; s++) {
                    var rs = statuses[s];
                    var cls = rs.status === 'Allowed' ? 'approved' : (rs.status === 'Banned' ? 'banned' : 'review');
                    var icon = rs.status === 'Allowed' ? 'check-circle-fill' : (rs.status === 'Banned' ? 'x-circle-fill' : 'exclamation-circle-fill');
                    regHtml += '<span class="reg-pill ' + cls + '"><i class="bi bi-' + icon + '"></i>' + escHtml(rs.country) + ' - ' + escHtml(rs.status) + '</span>';
                }
                regHtml += '</div>';
                if (reg.notes) {
                    regHtml += '<p class="text-muted small mt-2">' + escHtml(reg.notes) + '</p>';
                }
                regHtml += '</div>';
            }
        } else {
            regHtml = '<p class="text-muted">No verified regulatory information available for the detected ingredients.</p>';
        }

        // News / Recalls
        var newsHtml = "";
        if (news.length > 0) {
            for (var n = 0; n < news.length; n++) {
                var newsItem = news[n];
                newsHtml += '<div class="warning-card caution mb-2">';
                newsHtml += '<div class="warning-icon"><i class="bi bi-newspaper"></i></div>';
                newsHtml += '<div><div class="warning-title">' + escHtml(newsItem.title || 'News') + '</div>';
                newsHtml += '<p class="warning-desc">';
                if (newsItem.source) newsHtml += '<strong>Source:</strong> ' + escHtml(newsItem.source);
                if (newsItem.date) newsHtml += ' - ' + escHtml(newsItem.date);
                if (newsItem.link) newsHtml += '<br><a href="' + escHtml(newsItem.link) + '" target="_blank" style="color:var(--primary-emerald);">Read more</a>';
                newsHtml += '</p></div></div>';
            }
        } else {
            newsHtml = '<div class="alert alert-success"><i class="bi bi-shield-check-fill me-2"></i><strong>No recent recalls or safety notices</strong> found for this product.</div>';
        }

        // Nutrition
        var nutritionHtml = buildNutritionTable(nutrition);

        // Concern Factors
        var factorsHtml = "";
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
        var novaHtml = "";
        if (nova.level !== "Unknown") {
            novaHtml = '<span class="tag-pill" style="background:rgba(16,185,129,0.1);color:#059669;">NOVA ' + nova.level + ': ' + escHtml(nova.name) + '</span>';
        }

        // AI Summary — use backend field first, then generate client-side
        var aiSummary = analysisData.ai_summary || generateAISummary(product, nutrition, score, alerts);

        // BUILD THE FULL DASHBOARD
        var html = '';

        // Product Header
        html += '<div class="product-header-card fade-in mb-4">';
        html += '<div class="product-image-large">';
        if (product.image_url) {
            html += '<img src="' + escHtml(product.image_url) + '" alt="' + escHtml(product.name || '') + '" style="width:100%;height:100%;object-fit:cover;">';
        } else {
            html += '<div style="display:flex;align-items:center;justify-content:center;height:100%;background:var(--gray-100);border-radius:16px;"><i class="bi bi-box" style="font-size:5rem;color:var(--gray-300);"></i></div>';
        }
        html += '</div>';
        html += '<div class="product-header-info">';
        html += '<h1 class="product-title">' + escHtml(product.name || 'Unknown Product') + '</h1>';
        html += '<p class="product-brand-large" style="color:var(--gray-500);font-size:1.1rem;">' + escHtml(product.brand || 'Unknown Brand') + '</p>';
        html += '<div class="product-meta">';
        html += '<span><i class="bi bi-tag text-success"></i> ' + escHtml((product.categories || []).join(', ') || 'Food') + '</span>';
        html += '<span><i class="bi bi-box text-muted"></i> Source: ' + escHtml(product.source || 'OpenFoodFacts') + '</span>';
        html += novaHtml;
        html += '</div></div></div>';

        // Concern Score
        html += '<div class="factor-detail-card fade-in-up stagger-1">';
        html += '<div class="factor-header"><div class="factor-icon-lg"><i class="bi bi-speedometer2"></i></div>';
        html += '<div><h3>Concern Score</h3><p class="factor-subtitle">Rule-based risk assessment (0-100). Higher = More Concern.</p></div></div>';
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

        // Nutrition Facts
        html += '<div class="factor-detail-card fade-in-up stagger-2">';
        html += '<div class="factor-header"><div class="factor-icon-lg" style="background:linear-gradient(135deg,#06B6D4,#0891B2);"><i class="bi bi-bar-chart-fill"></i></div>';
        html += '<div><h3>Nutrition Facts</h3><p class="factor-subtitle">Per 100g serving</p></div></div>';
        html += '<div class="factor-body">' + nutritionHtml + '</div></div>';

        // Ingredient Breakdown
        html += '<div class="factor-detail-card fade-in-up stagger-3">';
        html += '<div class="factor-header"><div class="factor-icon-lg" style="background:linear-gradient(135deg,#3B82F6,#2563EB);"><i class="bi bi-clipboard-data"></i></div>';
        html += '<div><h3>Ingredient Breakdown</h3><p class="factor-subtitle">' + ingredients.length + ' ingredients detected</p></div></div>';
        html += '<div class="factor-body">' + ingExplHtml;
        html += '<hr style="margin:1rem 0;"><p class="text-muted small"><strong>Full ingredient list:</strong> ' + escHtml(ingredients.join(', ') || 'Not available') + '</p>';
        html += '</div></div>';

        // Allergen Alerts
        html += '<div class="factor-detail-card fade-in-up stagger-4" style="border-color:' + (allergens.length ? 'rgba(239,68,68,0.3)' : 'var(--gray-200)') + ';">';
        html += '<div class="factor-header" style="background:' + (allergens.length ? 'rgba(239,68,68,0.05)' : 'var(--light-gray)') + ';">';
        html += '<div class="factor-icon-lg" style="background:linear-gradient(135deg,#EF4444,#B91C1C);"><i class="bi bi-exclamation-triangle"></i></div>';
        html += '<div><h3>Allergen Alerts</h3><p class="factor-subtitle">Detected potential allergens in ingredient list</p></div></div>';
        html += '<div class="factor-body">' + allergenHtml + '</div></div>';

        // Personalized Warnings
        html += '<div class="factor-detail-card fade-in-up stagger-5" style="border-color:' + (personalizedWarnings.some(function(w) { return w.type === 'red'; }) ? 'rgba(239,68,68,0.3)' : 'var(--gray-200)') + ';">';
        html += '<div class="factor-header" style="background:' + (personalizedWarnings.some(function(w) { return w.type === 'red'; }) ? 'rgba(239,68,68,0.05)' : 'var(--light-gray)') + ';">';
        html += '<div class="factor-icon-lg" style="background:linear-gradient(135deg,#F59E0B,#D97706);"><i class="bi bi-person-exclamation"></i></div>';
        html += '<div><h3>Personalized Warnings</h3><p class="factor-subtitle">Based on your health profile</p></div></div>';
        html += '<div class="factor-body">' + warningsHtml + '</div></div>';

        // Regulatory Status
        html += '<div class="factor-detail-card fade-in-up stagger-6">';
        html += '<div class="factor-header"><div class="factor-icon-lg" style="background:linear-gradient(135deg,#8B5CF6,#7C3AED);"><i class="bi bi-globe-americas"></i></div>';
        html += '<div><h3>Global Regulatory Status</h3><p class="factor-subtitle">Cross-country compliance for detected ingredients</p></div></div>';
        html += '<div class="factor-body">' + regHtml + '</div></div>';

        // Safety Alerts & Recalls
        html += '<div class="factor-detail-card fade-in-up stagger-7">';
        html += '<div class="factor-header"><div class="factor-icon-lg" style="background:linear-gradient(135deg,#F59E0B,#D97706);"><i class="bi bi-megaphone-fill"></i></div>';
        html += '<div><h3>Safety Alerts & Recalls</h3><p class="factor-subtitle">Official recall notices and safety news</p></div></div>';
        html += '<div class="factor-body">' + newsHtml + '</div></div>';

        // AI Summary
        html += '<div class="factor-detail-card fade-in-up stagger-7">';
        html += '<div class="factor-header"><div class="factor-icon-lg" style="background:linear-gradient(135deg,#10B981,#059669);"><i class="bi bi-robot"></i></div>';
        html += '<div><h3>AI Summary</h3><p class="factor-subtitle">Simplified overview based on verified data</p></div></div>';
        html += '<div class="factor-body"><div style="background:var(--gray-100);border-radius:14px;padding:20px;line-height:1.7;">' + escHtml(aiSummary) + '</div></div></div>';

        // Decision Banner
        html += '<div class="decision-banner fade-in-up stagger-7">';
        html += '<h4>Your Decision Matters</h4>';
        html += '<p>Label Padegha Sabh provides transparent, data-driven insights - not a verdict. You are empowered to make the best choice for yourself.</p>';
        html += '</div>';

        // AI CTA
        html += '<div class="ai-cta-section fade-in-up stagger-7">';
        html += '<div class="ai-cta-text"><h3>Have questions? Ask the AI</h3>';
        html += '<p>Get deeper insights about this product\'s ingredients, health impacts, and alternatives.</p>';
        html += '<a href="ai-chat.html" class="btn mt-3" style="background:#fff;color:var(--primary-emerald);font-weight:700;border-radius:12px;padding:10px 24px;">';
        html += '<i class="bi bi-chat-dots-fill me-2"></i>Open AI Chat</a></div>';
        html += '<i class="bi bi-robot ai-cta-icon"></i></div>';

        container.innerHTML = html;
        container.style.display = "block";

        // Save context for AI chat
        try {
            localStorage.setItem("lps_ai_context", JSON.stringify({
                name: product.name,
                brand: product.brand,
                ingredients: ingredients,
                concern_score: score,
                allergens: alerts,
                nutrition: nutrition
            }));
        } catch (e) {}

    } catch (err) {
        console.error("Failed to render product dashboard", err);
        container.innerHTML = '<div class="error-card"><i class="bi bi-exclamation-circle"></i><h4>Analysis Preview Available</h4>';
        container.innerHTML += '<p class="text-muted">We received product information, but the full dashboard could not be rendered.</p>';
        container.innerHTML += '<div class="mt-3 text-start">';
        container.innerHTML += '<strong>' + escHtml((analysisData && analysisData.product && analysisData.product.name) || 'Unknown Product') + '</strong>';
        container.innerHTML += '<p class="text-muted mb-0">' + escHtml((analysisData && analysisData.ingredients || []).join(', ') || 'No details available.') + '</p>';
        container.innerHTML += '</div></div>';
        container.style.display = "block";
    }
}

// ═══════════════════════════════════════════════════════════
// AI Summary Generator (rule-based, no AI API needed)
// ═══════════════════════════════════════════════════════════
function generateAISummary(product, nutrition, score, alerts) {
    var name = product.name || "this product";
    var brand = product.brand || "";
    var scoreVal = score || 50;

    var summary = name;
    if (brand) summary += " by " + brand;
    summary += ". ";

    if (scoreVal <= 20) {
        summary += "This product has a low concern score, suggesting it may be a reasonable choice for most consumers. ";
    } else if (scoreVal <= 50) {
        summary += "This product has a moderate concern score. ";
    } else if (scoreVal <= 80) {
        summary += "This product has a high concern score. ";
    } else {
        summary += "This product has a very high concern score. ";
    }

    if (alerts && alerts.length > 0) {
        summary += "It contains potential allergens: " + alerts.join(', ') + ". ";
        summary += "If you have known allergies, please check the ingredient list carefully. ";
    }

    var sugar = nutrition.sugars_100g;
    var salt = nutrition.salt_100g;
    var fiber = nutrition.fiber_100g;

    if (sugar !== undefined) {
        if (sugar > 15) summary += "Sugar content is high at " + sugar + "g per 100g. ";
        else if (sugar > 5) summary += "Contains " + sugar + "g of sugar per 100g. ";
        else summary += "Sugar content is relatively low at " + sugar + "g per 100g. ";
    }

    if (salt !== undefined) {
        if (salt > 1.5) summary += "Sodium content is high at " + salt + "g per 100g. ";
        else if (salt > 0.5) summary += "Contains " + salt + "g of salt per 100g. ";
    }

    if (fiber !== undefined && fiber > 3) {
        summary += "Good source of dietary fiber (" + fiber + "g per 100g). ";
    }

    summary += "Always consider your personal dietary needs and consult healthcare professionals for personalized advice.";
    return summary;
}

// ═══════════════════════════════════════════════════════════
// Nutrition Table Builder
// ═══════════════════════════════════════════════════════════
function buildNutritionTable(nutrition) {
    var key_map = {
        'energy-kcal_100g': ['Calories (kcal)', 'kcal'],
        'energy_100g': ['Energy (kJ)', 'kJ'],
        'proteins_100g': ['Protein', 'g'],
        'carbohydrates_100g': ['Carbohydrates', 'g'],
        'sugars_100g': ['of which Sugars', 'g'],
        'fat_100g': ['Fat', 'g'],
        'saturated-fat_100g': ['Saturated Fat', 'g'],
        'fiber_100g': ['Dietary Fiber', 'g'],
        'sodium_100g': ['Sodium', 'g'],
        'salt_100g': ['Salt', 'g'],
        'calcium_100g': ['Calcium', 'mg'],
        'iron_100g': ['Iron', 'mg'],
    };

    var n = nutrition;
    if (Array.isArray(n)) {
        var obj = {};
        for (var i = 0; i < n.length; i++) {
            var item = n[i];
            var k = (item.nutrientName || '').toLowerCase().replace(/ /g, '_') + '_100g';
            obj[k] = item.amount;
        }
        n = obj;
    }

    var rows = '';
    var keys = Object.keys(key_map);
    for (var j = 0; j < keys.length; j++) {
        var key = keys[j];
        if (n[key] === undefined || n[key] === null) continue;
        var label = key_map[key][0];
        var unit = key_map[key][1];
        var val = parseFloat(n[key] || 0).toFixed(2);

        var lvlClass = '';
        if (key.indexOf('sugars') >= 0 && val > 15) lvlClass = 'nutriment-level-high';
        else if (key.indexOf('sugars') >= 0 && val > 5) lvlClass = 'nutriment-level-moderate';
        else if (key.indexOf('salt') >= 0 && val > 1.5) lvlClass = 'nutriment-level-high';
        else if (key.indexOf('salt') >= 0 && val > 0.5) lvlClass = 'nutriment-level-moderate';
        else if (key.indexOf('saturated') >= 0 && val > 5) lvlClass = 'nutriment-level-high';
        else if (key.indexOf('fiber') >= 0 && val > 3) lvlClass = 'nutriment-level-low';

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