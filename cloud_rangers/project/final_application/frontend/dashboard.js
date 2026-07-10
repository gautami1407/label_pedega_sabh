const API_URL = (typeof LPS_API_BASE !== 'undefined') ? LPS_API_BASE : 'http://localhost:8000/api';

async function apiFetch(path, options = {}) {
    if (typeof apiRequest === 'function') {
        return apiRequest(path, options);
    }
    const headers = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
    return fetch(`${API_URL}${path}`, { ...options, headers });
}

// Global Data Store
let currentProductData = null;

// ── Routing ──────────────────────────────────────────
function showScanSection() {
    window.location.href = 'barcodescanner.html';
}

function showHome() {
    document.getElementById('dashboard-home').style.display = 'block';
    document.getElementById('product-result').style.display = 'none';
}

function showProductResult() {
    document.getElementById('dashboard-home').style.display = 'none';
    document.getElementById('product-result').style.display = 'block';
}

// ── Fetch Product by Barcode ─────────────────────────
async function fetchProductData(barcode) {
    showLoadingState();
    try {
        const profileDataRaw = localStorage.getItem('healthProfile');
        let profileData = {};
        if (profileDataRaw) {
            try { profileData = JSON.parse(profileDataRaw); } catch (e) { }
        }

        const response = await apiFetch(`/product/${barcode}`, {
            method: 'POST',
            body: JSON.stringify({ preferences: profileData })
        });

        if (!response.ok) {
            const errBody = await response.json().catch(() => ({}));
            const errMsg = errBody.error || `Server error (${response.status})`;
            if (response.status === 404) {
                showErrorState(`Product not found: ${errMsg}. Try a known barcode like 3017620422003 (Nutella).`);
            } else {
                showErrorState(errMsg);
            }
            return;
        }

        const data = await response.json();
        if (data.error) {
            showErrorState(data.error);
            return;
        }

        data.barcode = barcode;
        currentProductData = data;
        localStorage.setItem('currentProductData', JSON.stringify(data));
        populateDashboard(data);
        showProductResult();
        performSearch(data.name || data.brand || '');

    } catch (error) {
        console.error('Error fetching product data:', error);
        showErrorState('Failed to analyze product: ' + error.message + '. Is api.py running on port 5000?');
    } finally {
        const loader = document.getElementById('loading-state');
        if (loader) loader.style.display = 'none';
    }
}

// ── Analyze Image via Gemini AI ──────────────────────
async function analyzeImage(imageDataURI) {
    showLoadingState();
    try {
        const profileDataRaw = localStorage.getItem('healthProfile');
        let profileData = {};
        if (profileDataRaw) {
            try { profileData = JSON.parse(profileDataRaw); } catch (e) { }
        }

        const response = await apiFetch('/analyze', {
            method: 'POST',
            body: JSON.stringify({
                image: imageDataURI,
                preferences: profileData
            })
        });

        if (!response.ok) throw new Error(`API Error: ${response.status}`);
        let data = await response.json();

        if (data.error && !data.name) {
            showErrorState('Image analysis failed: ' + data.error);
            return;
        }

        // If insights are embedded directly
        if (!data.dashboard_insights && data.concern_score !== undefined) {
            data = { ...data, dashboard_insights: data };
        }

        currentProductData = data;
        localStorage.setItem('currentProductData', JSON.stringify(data));
        populateDashboard(data);
        showProductResult();
    } catch (error) {
        console.error('Image analysis error:', error);
        showErrorState('Failed to analyze image: ' + error.message);
    } finally {
        const loader = document.getElementById('loading-state');
        if (loader) loader.style.display = 'none';
    }
}

// ── Loading / Error states ───────────────────────────
function showLoadingState() {
    document.getElementById('dashboard-home').style.display = 'none';
    document.getElementById('product-result').style.display = 'none';
    let loader = document.getElementById('loading-state');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'loading-state';
        loader.style.cssText = 'padding:4rem; text-align:center;';
        loader.innerHTML = `
            <div style="width:60px;height:60px;border:4px solid #e2e8f0;border-top-color:#10b981;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 1.5rem;"></div>
            <h3 style="font-weight:700;margin-bottom:0.5rem;">Analyzing Product...</h3>
            <p style="color:#64748b;">Fetching OpenFoodFacts data, cross-checking 1000+ additives, running AI analysis</p>
        `;
        const style = document.createElement('style');
        style.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
        document.head.appendChild(style);
        document.querySelector('.main-wrapper').appendChild(loader);
    }
    loader.style.display = 'block';
}

function showErrorState(msg) {
    let loader = document.getElementById('loading-state');
    if (loader) loader.style.display = 'none';
    document.getElementById('dashboard-home').style.display = 'block';
    document.getElementById('product-result').style.display = 'none';
    const errBanner = document.createElement('div');
    errBanner.style.cssText = 'background:#fef2f2;border:2px solid #fca5a5;border-radius:16px;padding:1rem 1.5rem;margin:1rem 0;color:#991b1b;font-weight:600;';
    errBanner.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i> ${msg} <button onclick="this.parentElement.remove()" style="float:right;background:none;border:none;font-size:1.2rem;cursor:pointer;">×</button>`;
    document.querySelector('.main-wrapper').prepend(errBanner);
}

// ═══════════════════════════════════════════════════════
// POPULATE DASHBOARD — Master render function
// ═══════════════════════════════════════════════════════
function populateDashboard(data) {
    console.log("LPS Intelligence Engine: Populating Dashboard...", data);

    const loader = document.getElementById('loading-state');
    if (loader) loader.style.display = 'none';
    if (!data) return;

    const insights = data.dashboard_insights || {};

    // 1. Banner
    document.getElementById('res-product-name').textContent = data.name || 'Unknown Product';
    document.getElementById('res-product-brand').textContent = `${data.brand || 'Unknown Brand'} • ${data.category || 'Unknown Category'}`;
    const imgEl = document.getElementById('res-product-img');
    imgEl.src = data.image || 'https://cdn-icons-png.flaticon.com/512/1046/1046857.png';

    const scanDateStr = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    const el_scanDate = document.getElementById('res-scan-date');
    if (el_scanDate) el_scanDate.textContent = scanDateStr;
    const el_batch = document.getElementById('res-batch');
    if (el_batch) el_batch.textContent = data.barcode || 'Image Scan';

    // 2. Profile Summary
    populateProfileSummary();

    // 3. OFF Scores
    populateOFFScores(data.scores || {});

    // 4. Regulatory Engine
    const lpsRegArray = (insights.global_regulatory_status) || data.regulatory?.csv_global_status || [];
    populateRegulatoryEngine(lpsRegArray);

    // 5. Concern Score (Factor 1)
    const finalScore = insights.concern_score || 0;
    const scoreValEl = document.getElementById('res-concern-score');
    if (scoreValEl) scoreValEl.textContent = finalScore;

    const ringPath = document.getElementById('score-circle-path');
    if (ringPath) {
        const color = finalScore > 70 ? '#ef4444' : finalScore > 40 ? '#f59e0b' : '#10b981';
        ringPath.setAttribute('stroke-dasharray', `${finalScore}, 100`);
        ringPath.style.stroke = color;
    }

    const riskLabelEl = document.getElementById('res-risk-level');
    if (riskLabelEl) {
        riskLabelEl.textContent = finalScore > 70 ? 'High Risk' : finalScore > 40 ? 'Moderate Risk' : 'Low Risk';
        riskLabelEl.style.color = finalScore > 70 ? '#ef4444' : finalScore > 40 ? '#f59e0b' : '#10b981';
    }

    // 6. Ingredient count (Factor 2)
    const ingredientList = insights.ingredient_purpose || [];
    const ingCountDisplay = document.getElementById('res-ing-count');
    if (ingCountDisplay) ingCountDisplay.textContent = ingredientList.length || '0';

    // 7. Banned Elsewhere (Factor 3)
    populateBannedSummary(lpsRegArray);

    // 8. Additive Context (Factor 4)
    populateAdditiveContext(insights.additive_context);

    // 9. Personal Warnings (Factor 5)
    populatePersonalWarnings(insights.personal_warnings || []);

    // 10. Flagged count
    const healthWarnings = insights.personal_warnings || [];
    const issuesBanner = document.getElementById('res-flagged-count');
    if (issuesBanner) {
        issuesBanner.innerHTML = `<i class="bi bi-exclamation-octagon-fill" style="color:${healthWarnings.length > 0 ? '#ef4444' : '#10b981'};"></i> <span>${healthWarnings.length} Intelligence Alerts</span>`;
    }
    const alertCountPill = document.getElementById('res-warning-count');
    if (alertCountPill) alertCountPill.textContent = `${healthWarnings.length} Alerts`;

    // 11. Nutrition Facts
    populateNutritionPanel(data.nutrition_analysis || {}, data.nutrition || {});

    // 12. Detailed Additives Table
    populateAdditiveDetails(data.detailed_additives || []);

    // 13. Healthier Alternatives
    populateAlternatives(insights.healthier_alternatives || []);

    // 14. Sustainability
    populateSustainability(data.sustainability || insights.sustainability || {});
}

// ── Profile Summary Bar ──────────────────────────────
function populateProfileSummary() {
    const el = document.getElementById('res-profile-summary');
    if (!el) return;

    const profileRaw = localStorage.getItem('healthProfile');
    if (!profileRaw) {
        el.innerHTML = `<i class="bi bi-person-exclamation" style="color:#f59e0b"></i> <span>No health profile configured — <a href="health-profile.html" style="color:var(--primary);font-weight:700;">Set up now</a> for personalized warnings</span>`;
        el.className = 'profile-summary-bar warning';
        return;
    }

    try {
        const p = JSON.parse(profileRaw);
        const pills = [];

        if (p.age) pills.push(`<span class="profile-pill">Age: ${p.age}</span>`);
        if (p.dietaryPreference && p.dietaryPreference !== 'other') pills.push(`<span class="profile-pill diet">${p.dietaryPreference}</span>`);
        if (p.allergies && p.allergies.length > 0 && p.allergies[0] !== 'none') {
            pills.push(`<span class="profile-pill allergy">Allergies: ${p.allergies.join(', ')}</span>`);
        }
        if (p.height && p.weight) {
            const bmi = (p.weight / ((p.height / 100) ** 2)).toFixed(1);
            pills.push(`<span class="profile-pill">BMI: ${bmi}</span>`);
        }

        el.innerHTML = `<i class="bi bi-person-check-fill" style="color:var(--primary)"></i> <span>Analysis personalized for: </span>${pills.join('')}`;
        el.className = 'profile-summary-bar active';
    } catch (e) {
        el.innerHTML = `<i class="bi bi-person-check-fill"></i> Profile active`;
        el.className = 'profile-summary-bar active';
    }
}

// ── OFF Scores ───────────────────────────────────────
function populateOFFScores(scores) {
    const nutriscoreColors = { a: '#1e8a3d', b: '#6dbb30', c: '#f5c623', d: '#e77e22', e: '#e63e12' };
    const novaColors = { 1: '#1e8a3d', 2: '#6dbb30', 3: '#f5c623', 4: '#e63e12' };
    const ecoscoreColors = { a: '#1e8a3d', b: '#6dbb30', c: '#f5c623', d: '#e77e22', e: '#e63e12' };

    // Nutri-Score
    const ns = (scores.nutriscore || '?').toString().toLowerCase();
    const nsEl = document.getElementById('res-nutriscore');
    if (nsEl) {
        nsEl.textContent = ns.toUpperCase();
        nsEl.style.background = nutriscoreColors[ns] || '#94a3b8';
        nsEl.style.color = '#fff';
    }
    const nsLabel = document.getElementById('res-nutriscore-label');
    if (nsLabel) nsLabel.textContent = scores.nutriscore_label || (ns !== '?' ? `Grade ${ns.toUpperCase()}` : 'Not available');

    // NOVA
    const nv = (scores.nova || '?').toString();
    const nvEl = document.getElementById('res-nova');
    if (nvEl) {
        nvEl.textContent = nv;
        nvEl.style.background = novaColors[nv] || '#94a3b8';
        nvEl.style.color = '#fff';
    }
    const nvLabel = document.getElementById('res-nova-label');
    if (nvLabel) nvLabel.textContent = scores.nova_label || `Group ${nv}`;

    // Eco-Score
    const es = (scores.ecoscore || '?').toString().toLowerCase();
    const esEl = document.getElementById('res-ecoscore');
    if (esEl) {
        esEl.textContent = es.toUpperCase();
        esEl.style.background = ecoscoreColors[es] || '#94a3b8';
        esEl.style.color = '#fff';
    }
    const esLabel = document.getElementById('res-ecoscore-label');
    if (esLabel) esLabel.textContent = scores.ecoscore_label || (es !== '?' ? `Grade ${es.toUpperCase()}` : 'Not assessed');
}

// ── Regulatory Engine Cards ──────────────────────────
function populateRegulatoryEngine(regArray) {
    const container = document.getElementById('res-regulatory-list');
    if (!container || !regArray.length) return;

    const agencyLogos = {
        'FSSAI': 'https://upload.wikimedia.org/wikipedia/en/thumb/5/52/FSSAI_logo.svg/320px-FSSAI_logo.svg.png',
        'FDA': 'https://logos-world.net/wp-content/uploads/2022/02/FDA-Logo.png',
        'EFSA': 'https://images.seeklogo.com/logo-png/46/1/efsa-logo-png_seeklogo-465873.png'
    };

    container.innerHTML = regArray.map(reg => {
        const countryText = reg.country || '';
        let agency = 'OTHER';
        if (countryText.includes('FSSAI')) agency = 'FSSAI';
        else if (countryText.includes('FDA')) agency = 'FDA';
        else if (countryText.includes('EFSA')) agency = 'EFSA';

        const logo = agencyLogos[agency] || '';
        const riskClass = reg.risk ? reg.risk.toLowerCase() : 'safe';
        const flagged = reg.flagged_additives || [];
        const flaggedHTML = flagged.length > 0
            ? `<div class="agency-flagged">${flagged.map(f => `<span class="flagged-tag">${f.additive} (${f.e_number})</span>`).join('')}</div>`
            : '';

        return `
            <div class="agency-card ${riskClass}">
                <div class="agency-logo-container">
                    <img src="${logo}" alt="${countryText}" onerror="this.src='https://cdn-icons-png.flaticon.com/512/2913/2913133.png'">
                </div>
                <div class="agency-name">${countryText}</div>
                <div class="agency-status-badge" style="color: ${riskClass === 'safe' ? '#10b981' : riskClass === 'caution' ? '#f59e0b' : '#ef4444'}">
                    ${reg.status}
                </div>
                ${flaggedHTML}
            </div>
        `;
    }).join('');
}

// ── Banned Summary ───────────────────────────────────
function populateBannedSummary(regArray) {
    const el = document.getElementById('res-banned-summary');
    if (!el) return;

    const alerts = regArray.filter(r => r.risk && r.risk.toLowerCase() === 'high');
    if (alerts.length === 0) {
        el.innerHTML = `<div class="reg-row"><span class="reg-country" style="color:#10b981;font-weight:700;"><i class="bi bi-check-circle-fill"></i> Globally Compliant</span></div>`;
    } else {
        el.innerHTML = alerts.map(r => {
            const flagged = (r.flagged_additives || []).map(f => f.additive).join(', ');
            return `
                <div class="reg-row" style="color:#ef4444;font-weight:700;margin-bottom:8px;">
                    <span class="reg-country"><i class="bi bi-x-circle-fill"></i> ${r.country}</span>
                    <span class="reg-status">${r.status}</span>
                </div>
                ${flagged ? `<div style="font-size:12px;color:#64748b;margin-bottom:8px;padding-left:24px;">Flagged: ${flagged}</div>` : ''}
            `;
        }).join('');
    }
}

// ── Additive Context Bars ────────────────────────────
function populateAdditiveContext(addsObj) {
    const el = document.getElementById('res-additive-context-list');
    if (!el) return;

    const adds = addsObj || { preservatives: 0, colorants: 0, flavors_msg: 0, stabilizers: 0 };
    const factorMax = 5;
    const addMap = [
        { label: 'Preservatives', val: adds.preservatives || 0, color: '#f59e0b' },
        { label: 'Colorants', val: adds.colorants || 0, color: '#ef4444' },
        { label: 'Flavors/MSG', val: adds.flavors_msg || 0, color: '#f59e0b' },
        { label: 'Stabilizers', val: adds.stabilizers || 0, color: '#10b981' },
    ];
    el.innerHTML = addMap.map(a => `
        <div class="additive-progress-row">
            <span class="additive-label">${a.label}</span>
            <div class="additive-bar-container">
                <div class="additive-bar" style="width:${Math.min(100, (a.val / factorMax) * 100)}%; background:${a.color};"></div>
            </div>
            <span style="font-size:13px;font-weight:700;min-width:16px;color:var(--text-main);text-align:right;">${a.val}</span>
        </div>
    `).join('');
}

// ── Personal Warnings ────────────────────────────────
function populatePersonalWarnings(warnings) {
    const el = document.getElementById('res-personal-warnings-list');
    if (!el) return;

    if (warnings.length === 0) {
        el.innerHTML = '<p class="subtitle" style="padding:12px 0;">No personal health violations detected. ✅</p>';
    } else {
        el.innerHTML = warnings.map(w => `
            <div class="warning-alert ${w.type || 'orange'}" style="display:flex;align-items:center;gap:16px;padding:16px;background:#f8fafc;border-radius:12px;margin-bottom:12px;border-left:4px solid ${w.type === 'red' ? '#ef4444' : '#f59e0b'}">
                <i class="bi bi-exclamation-triangle-fill" style="color:${w.type === 'red' ? '#ef4444' : '#f59e0b'};font-size:20px;"></i>
                <div style="flex:1;">
                    <h4 style="margin:0;font-size:15px;font-weight:700;">${w.title}</h4>
                    <p style="margin:4px 0 0;color:var(--text-muted);font-size:13px;">${w.description}</p>
                </div>
            </div>
        `).join('');
    }
}

// ── Nutrition Facts Panel ────────────────────────────
function populateNutritionPanel(analysis, rawNutrition) {
    const el = document.getElementById('res-nutrition-bars');
    if (!el) return;

    const nutrients = [
        { key: 'energy-kcal', label: 'Calories', unit: 'kcal', color: '#ef4444' },
        { key: 'fat', label: 'Fat', unit: 'g', color: '#f59e0b' },
        { key: 'saturated-fat', label: 'Saturated Fat', unit: 'g', color: '#ea580c' },
        { key: 'carbohydrates', label: 'Carbs', unit: 'g', color: '#0ea5e9' },
        { key: 'sugars', label: 'Sugars', unit: 'g', color: '#e63e12' },
        { key: 'fiber', label: 'Fiber', unit: 'g', color: '#10b981' },
        { key: 'proteins', label: 'Protein', unit: 'g', color: '#6366f1' },
        { key: 'salt', label: 'Salt', unit: 'g', color: '#64748b' },
    ];

    let html = '';
    let hasData = false;

    for (const n of nutrients) {
        const data = analysis[n.key];
        if (data) {
            hasData = true;
            const pct = Math.min(data.daily_pct, 100);
            const levelClass = data.level || 'low';
            html += `
                <div class="nutrition-bar-item">
                    <div class="nutrition-bar-header">
                        <span class="nutrition-bar-label">${n.label}</span>
                        <span class="nutrition-bar-value">${data.per_100g} ${n.unit}</span>
                    </div>
                    <div class="nutrition-bar-track">
                        <div class="nutrition-bar-fill ${levelClass}" style="width:${pct}%; background:${n.color};"></div>
                    </div>
                    <div class="nutrition-bar-pct">${data.daily_pct}% Daily Value</div>
                </div>
            `;
        }
    }

    if (!hasData) {
        // Fallback: show raw nutriments if available
        const fallbackKeys = ['energy-kcal_100g', 'fat_100g', 'carbohydrates_100g', 'sugars_100g', 'proteins_100g', 'salt_100g'];
        let fallbackHtml = '';
        for (const key of fallbackKeys) {
            if (rawNutrition[key] !== undefined) {
                hasData = true;
                const label = key.replace('_100g', '').replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                fallbackHtml += `<div class="nutrition-simple-row"><span>${label}</span><strong>${parseFloat(rawNutrition[key]).toFixed(1)}</strong></div>`;
            }
        }
        html = hasData ? fallbackHtml : '<p class="subtitle">No nutrition data available for this product</p>';
    }

    el.innerHTML = html;
}

// ── Detailed Additives Table ─────────────────────────
function populateAdditiveDetails(additives) {
    const el = document.getElementById('res-additives-table');
    if (!el) return;

    if (!additives || additives.length === 0) {
        el.innerHTML = '<p class="subtitle">No additives detected in this product ✅</p>';
        return;
    }

    const riskColors = { 'Low': '#10b981', 'Medium': '#f59e0b', 'High': '#ef4444' };

    let tableHTML = `
        <div class="additives-table-scroll">
        <table class="additives-table">
            <thead>
                <tr>
                    <th>E-Number</th>
                    <th>Additive Name</th>
                    <th>Risk Level</th>
                    <th>🇮🇳 India</th>
                    <th>🇺🇸 USA</th>
                    <th>🇪🇺 EU</th>
                    <th>Concern</th>
                </tr>
            </thead>
            <tbody>
    `;

    for (const add of additives) {
        const cs = add.country_status || {};
        const indiaStatus = cs['India'] || 'N/A';
        const usaStatus = cs['USA'] || 'N/A';
        const euStatus = cs['EU'] || 'N/A';
        const risk = add.risk_level || 'Low';

        const statusBadge = (s) => {
            const lower = s.toLowerCase();
            if (lower.includes('banned')) return `<span class="status-badge banned">${s}</span>`;
            if (lower.includes('permitted')) return `<span class="status-badge permitted">${s}</span>`;
            return `<span class="status-badge">${s}</span>`;
        };

        tableHTML += `
            <tr>
                <td><strong>${add.e_number || '--'}</strong></td>
                <td>${add.name}</td>
                <td><span class="risk-pill" style="background:${riskColors[risk] || '#94a3b8'}22;color:${riskColors[risk] || '#94a3b8'}">${risk}</span></td>
                <td>${statusBadge(indiaStatus)}</td>
                <td>${statusBadge(usaStatus)}</td>
                <td>${statusBadge(euStatus)}</td>
                <td style="font-size:12px;color:var(--text-muted);max-width:180px;">${add.reason || '—'}</td>
            </tr>
        `;
    }

    tableHTML += '</tbody></table></div>';
    el.innerHTML = tableHTML;
}

// ── Healthier Alternatives ───────────────────────────
function populateAlternatives(alternatives) {
    const el = document.getElementById('res-alternatives');
    if (!el) return;

    if (!alternatives || alternatives.length === 0) {
        el.innerHTML = '<p class="subtitle">No alternatives suggested</p>';
        return;
    }

    el.innerHTML = alternatives.map(alt => `
        <div class="alternative-card">
            <div class="alt-icon"><i class="bi bi-check-circle-fill"></i></div>
            <div class="alt-content">
                <h4>${alt.name}</h4>
                <p>${alt.description}</p>
                ${alt.benefit ? `<span class="alt-benefit"><i class="bi bi-star-fill"></i> ${alt.benefit}</span>` : ''}
            </div>
        </div>
    `).join('');
}

// ── Sustainability ───────────────────────────────────
function populateSustainability(sus) {
    const el = document.getElementById('res-sustainability');
    if (!el) return;

    if (!sus || Object.keys(sus).length === 0) {
        el.innerHTML = '<p class="subtitle">No sustainability data available</p>';
        return;
    }

    const ecoscoreColors = { a: '#1e8a3d', b: '#6dbb30', c: '#f5c623', d: '#e77e22', e: '#e63e12' };
    const esGrade = (sus.ecoscore || '?').toString().toLowerCase();
    const esColor = ecoscoreColors[esGrade] || '#94a3b8';

    let html = '<div class="sustainability-grid">';

    html += `
        <div class="sus-item">
            <div class="sus-icon" style="background:${esColor}22;color:${esColor}"><i class="bi bi-globe2"></i></div>
            <div><strong>Eco-Score</strong><br><span style="color:${esColor};font-weight:800;font-size:20px;">${esGrade.toUpperCase()}</span> <span class="subtitle">${sus.ecoscore_label || ''}</span></div>
        </div>
    `;

    if (sus.packaging) {
        html += `
            <div class="sus-item">
                <div class="sus-icon" style="background:#f0f9ff;color:#0ea5e9"><i class="bi bi-box-seam"></i></div>
                <div><strong>Packaging</strong><br><span class="subtitle">${sus.packaging}</span></div>
            </div>
        `;
    }

    if (sus.origins) {
        html += `
            <div class="sus-item">
                <div class="sus-icon" style="background:#fef3c7;color:#d97706"><i class="bi bi-geo-alt-fill"></i></div>
                <div><strong>Origins</strong><br><span class="subtitle">${sus.origins || 'Not specified'}</span></div>
            </div>
        `;
    }

    if (sus.carbon_footprint) {
        html += `
            <div class="sus-item">
                <div class="sus-icon" style="background:#ecfdf5;color:#059669"><i class="bi bi-cloud-fill"></i></div>
                <div><strong>Carbon Footprint</strong><br><span class="subtitle">${sus.carbon_footprint}</span></div>
            </div>
        `;
    }

    if (sus.tips && sus.tips.length > 0) {
        html += `
            <div class="sus-item" style="grid-column: span 2;">
                <div class="sus-icon" style="background:#f0fdf4;color:#10b981"><i class="bi bi-lightbulb-fill"></i></div>
                <div><strong>Tips</strong><br>${sus.tips.map(t => `<span class="subtitle">• ${t}</span>`).join('<br>')}</div>
            </div>
        `;
    }

    html += '</div>';
    el.innerHTML = html;
}

// ── Ingredient Modal ─────────────────────────────────
function openIngredientModal() {
    const modal = document.getElementById('ingredient-modal');
    if (!modal) return;
    const body = document.getElementById('ingredient-modal-body');

    if (!currentProductData) {
        body.innerHTML = '<p>No product loaded yet.</p>';
        modal.style.display = 'flex';
        return;
    }

    const insights = currentProductData.dashboard_insights || {};
    const ingredients = insights.ingredient_purpose || [];
    const fullIngText = currentProductData.ingredients || 'Not available.';

    if (ingredients.length === 0) {
        body.innerHTML = `<p class="subtitle">No AI-generated ingredient breakdown available.</p><p><strong>Full ingredients text:</strong> ${fullIngText}</p>`;
    } else {
        const riskColor = { 'Safe': '#10b981', 'Moderate': '#f59e0b', 'High': '#ef4444' };
        body.innerHTML = ingredients.map(ing => `
            <div style="padding:12px;border-radius:12px;border-left:4px solid ${riskColor[ing.risk_level] || '#94a3b8'};background:#f8fafc;margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <strong>${ing.name}</strong>
                    <span style="font-size:11px;padding:2px 10px;border-radius:50px;background:${riskColor[ing.risk_level] || '#94a3b8'}22;color:${riskColor[ing.risk_level] || '#94a3b8'};font-weight:700;">${ing.risk_level}</span>
                </div>
                <p style="margin:0;font-size:13px;color:#64748b;">${ing.purpose}</p>
            </div>`).join('') + `<hr><p class="subtitle"><strong>Full ingredients:</strong> ${fullIngText}</p>`;
    }
    modal.style.display = 'flex';
}

// ── News ─────────────────────────────────────────────
async function performSearch(query = '') {
    const grid = document.getElementById('news-grid');
    const resGrid = document.getElementById('res-news-grid');
    if (grid) grid.innerHTML = '<p class="subtitle">Loading news...</p>';
    if (resGrid) resGrid.innerHTML = '<p class="subtitle">Loading news...</p>';

    try {
        const response = await fetch(`${API_URL}/news?product=${encodeURIComponent(query)}`);
        const news = await response.json();
        updateNewsGrid(news);
    } catch (error) {
        console.error('Error fetching news:', error);
        if (grid) grid.innerHTML = '<p class="subtitle">Could not load news</p>';
        if (resGrid) resGrid.innerHTML = '<p class="subtitle">Could not load news</p>';
    }
}

function updateNewsGrid(news) {
    const grid = document.getElementById('news-grid');
    const resGrid = document.getElementById('res-news-grid');
    const FALLBACK_IMG = 'https://images.unsplash.com/photo-1606787366850-de6330128bfc?w=400&q=80';

    function badgeClass(badge) {
        if (!badge) return 'badge-research';
        const b = badge.toLowerCase();
        if (b.includes('recall')) return 'badge-recall';
        if (b.includes('health')) return 'badge-health';
        if (b.includes('regulation')) return 'badge-regulation';
        return 'badge-research';
    }

    const html = news.length === 0
        ? '<p style="padding: 20px; color: var(--text-muted);">No safety news found for this product.</p>'
        : news.map(article => {
            const thumb = article.thumbnail || FALLBACK_IMG;
            const badge = article.badge || 'Alert';
            return `
            <div class="news-card" style="cursor:pointer;flex-direction:column;padding:0;overflow:hidden;border-radius:16px;" onclick="window.open('${article.link}', '_blank')">
                <img src="${thumb}" onerror="this.src='${FALLBACK_IMG}'" alt="News" style="width:100%;height:110px;object-fit:cover;">
                <div class="news-content" style="padding:14px;">
                    <span class="badge ${badgeClass(badge)}" style="margin-bottom:8px;">${badge}</span>
                    <h4 style="font-size:13px;line-height:1.4;margin-bottom:6px;">${article.title}</h4>
                    <div class="news-meta">${article.source} • ${article.date}</div>
                </div>
            </div>`;
        }).join('');

    if (grid) grid.innerHTML = html;
    if (resGrid) resGrid.innerHTML = html;
}

// ── AI Chat ──────────────────────────────────────────
const chatTrigger = document.getElementById('chat-trigger');
const aiAssistant = document.getElementById('ai-assistant');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const chatBody = document.getElementById('chat-body');

function openAIChat() {
    if (aiAssistant) {
        aiAssistant.style.display = 'flex';
        if (chatTrigger) chatTrigger.style.display = 'none';
        const ctxPane = document.querySelector('.chat-context-pane');
        if (ctxPane && currentProductData) {
            ctxPane.innerHTML = `<i class="bi bi-info-circle-fill" style="color:var(--primary)"></i> Discussing: <strong>${currentProductData.name}</strong>`;
        }
    }
}

function closeAIChat() {
    if (aiAssistant) {
        aiAssistant.style.display = 'none';
        if (chatTrigger) chatTrigger.style.display = 'flex';
    }
}

if (chatTrigger) chatTrigger.addEventListener('click', openAIChat);

document.querySelectorAll('.chat-chip').forEach(chip => {
    chip.addEventListener('click', (e) => {
        if (chatInput) chatInput.value = e.target.textContent;
        sendMessage();
    });
});

async function sendMessage() {
    if (!chatInput) return;
    const text = chatInput.value.trim();
    if (!text) return;

    appendMessage(text, 'user');
    chatInput.value = '';

    const loadingId = 'loading-' + Date.now();
    appendMessage('...', 'ai', loadingId);

    try {
        const payload = {
            message: text,
            context: currentProductData
        };

        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        const loadingEl = document.getElementById(loadingId);

        if (data.error) {
            if (loadingEl) loadingEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill" style="color:red"></i> ${data.error}`;
        } else {
            if (loadingEl) {
                loadingEl.innerHTML = data.response
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\n/g, '<br/>');
            }
        }
        if (chatBody) chatBody.scrollTop = chatBody.scrollHeight;
    } catch (err) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.innerText = "Connection error. Please try again.";
    }
}

function appendMessage(text, sender, id = null) {
    if (!chatBody) return;
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-msg ${sender}-msg`;
    const icon = sender === 'user' ? 'bi-person' : 'bi-robot';
    msgDiv.innerHTML = `
        <div class="msg-avatar"><i class="bi ${icon}"></i></div>
        <div class="msg-bubble" ${id ? `id="${id}"` : ''}>${text}</div>
    `;
    chatBody.appendChild(msgDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

if (btnSend) btnSend.addEventListener('click', sendMessage);
if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
}

// ── Search bar ───────────────────────────────────────
const searchInput = document.querySelector('.search-container input');
if (searchInput) {
    searchInput.placeholder = 'Search by barcode (e.g. 3017620422003) or name...';
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && searchInput.value.trim() !== '') {
            const val = searchInput.value.trim();
            if (/^\d+$/.test(val)) {
                fetchProductData(val);
            } else {
                searchByName(val);
            }
        }
    });
}

async function searchByName(name) {
    showLoadingState();
    try {
        const url = `https://world.openfoodfacts.org/cgi/search.pl?search_terms=${encodeURIComponent(name)}&json=1&page_size=1&fields=code,product_name,brands`;
        const res = await fetch(url);
        const data = await res.json();
        const products = data.products || [];
        if (products.length > 0 && products[0].code) {
            fetchProductData(products[0].code);
        } else {
            showErrorState(`No product found for "${name}". Try using the barcode number instead.`);
        }
    } catch (err) {
        showErrorState('Search failed: ' + err.message);
    }
}

// ── Initialization ───────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const barcode = urlParams.get('barcode');

    if (barcode) {
        console.log("Analyzing scanned barcode:", barcode);
        fetchProductData(barcode);
    } else {
        performSearch('');
    }
});
