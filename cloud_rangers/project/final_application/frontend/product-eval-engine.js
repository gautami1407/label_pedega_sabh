// ============================================
// AUTH CHECK
// ============================================
if (localStorage.getItem("isLoggedIn") !== "true") {
    window.location.href = "login.html";
}

// ============================================
// TRANSFORM OPEN FOOD FACTS DATA
// ============================================
function transformOpenFoodData(product) {
    return {
        name: product.product_name || "Unknown Product",
        brand: product.brands || "Unknown Brand",
        image: product.image_url || "",
        ingredientsText: product.ingredients_text || "Not available",
        ingredientsList: product.ingredients ? product.ingredients.map(i => i.text).filter(Boolean) : [],
        nutriments: product.nutriments || {},
        nutriscore: product.nutriscore_grade || "unknown",
        additives: product.additives_tags || [],
        allergens: product.allergens || "",
        risks: product.risks || [],
        health_score: product.health_score || 0
    };
}

// ============================================
// MAIN LOAD
// ============================================
window.addEventListener("DOMContentLoaded", () => {
    const storedProduct = localStorage.getItem("openFoodProduct");
    if (storedProduct) {
        const rawProduct = JSON.parse(storedProduct);
        processProduct(rawProduct);
        localStorage.removeItem("openFoodProduct");
    }

    // Setup barcode scanning
    setupBarcodeScan();
});

// ============================================
// BARCODE SCAN SETUP
// ============================================
function setupBarcodeScan() {
    const barcodeInput = document.getElementById("barcode-input");
    const fetchBtn = document.getElementById("fetch-barcode-btn");

    if (!barcodeInput || !fetchBtn) return;

    const barcodeHandler = async () => {
        const barcode = barcodeInput.value.trim();
        if (!barcode) return showError("Please enter a barcode.");
        await fetchProductByBarcode(barcode);
    };

    fetchBtn.addEventListener("click", barcodeHandler);
    barcodeInput.addEventListener("keypress", e => {
        if (e.key === "Enter") barcodeHandler();
    });
}

// ============================================
// FETCH PRODUCT BY BARCODE
// ============================================
async function fetchProductByBarcode(barcode) {
    const loading = document.getElementById("loadingContainer");
    const container = document.getElementById("productContainer");

    if (loading) loading.style.display = "block";
    if (container) container.style.display = "none";
    container.innerHTML = '';

    try {
        const response = await fetch(`https://world.openfoodfacts.org/api/v0/product/${barcode}.json`);
        if (!response.ok) throw new Error(`Network response was not OK (${response.status})`);
        const data = await response.json();

        if (!data || data.status !== 1 || !data.product) {
            return showError("Product not found in OpenFoodFacts.");
        }

        processProduct(data.product);

    } catch (err) {
        console.error("Error fetching data:", err);
        showError("Error fetching product from OpenFoodFacts. Check your internet or barcode.");
    } finally {
        if (loading) loading.style.display = "none";
    }
}

// ============================================
// PROCESS PRODUCT (Render + AI + News)
// ============================================
async function processProduct(rawProduct) {
    const product = transformOpenFoodData(rawProduct);

    // AI analysis
    const aiAnalysis = await analyzeIngredientsAI(product);

    // Render product
    renderDynamicProduct(product, aiAnalysis);

    // Fetch news
    fetchNews(product.name);
}

// ============================================
// AI INGREDIENT ANALYZER
// ============================================
async function analyzeIngredientsAI(product) {
    if (!product.ingredientsList || product.ingredientsList.length === 0) return null;

    try {
        const response = await fetch("http://127.0.0.1:8000/analyze-ingredients", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ingredients: product.ingredientsList })
        });
        return await response.json();
    } catch (err) {
        console.error("AI Analysis Error:", err);
        return null;
    }
}

// ============================================
// RENDER PRODUCT
// ============================================
function renderDynamicProduct(product, aiAnalysis) {
    const container = document.getElementById("productContainer");
    const loading = document.getElementById("loadingContainer");

    if (loading) loading.style.display = "none";
    if (container) container.style.display = "block";

    container.innerHTML = generateProductHTML(product, aiAnalysis);
}

// ============================================
// GENERATE PRODUCT HTML
// ============================================
function generateProductHTML(product, aiAnalysis) {
    const concernData = calculateConcern(product);

    let aiHTML = "";
    if (aiAnalysis) {
        aiHTML = `<div class="info-card">
            <h3>🤖 AI Ingredient Analysis</h3>
            ${aiAnalysis.overall_health_risk ? `<p><strong>Overall Risk:</strong> ${aiAnalysis.overall_health_risk}</p>` : ""}
            ${aiAnalysis.high_risk_ingredients?.length ? `<p><strong>High Risk Ingredients:</strong> ${aiAnalysis.high_risk_ingredients.join(", ")}</p>` : ""}
            ${aiAnalysis.comments?.length ? `<ul>${aiAnalysis.comments.map(c => `<li>${c}</li>`).join("")}</ul>` : ""}
        </div>`;
    }

    return `
        <div class="product-wrapper">

            <div class="product-header-card">
                <div class="product-left">
                    ${product.image ? `<img src="${product.image}" class="product-img">` : `<div class="product-placeholder">📦</div>`}
                </div>
                <div class="product-right">
                    <h1>${product.name}</h1>
                    <p>${product.brand}</p>
                    <div class="concern-badge ${concernData.level}">
                        ${concernData.label} • Score ${concernData.score}/100
                    </div>
                </div>
            </div>

            <div class="product-grid">
                <div class="info-card">
                    <h3>Ingredients</h3>
                    ${product.ingredientsList.length ? `<ul>${product.ingredientsList.map(i => `<li>${i}</li>`).join("")}</ul>` : `<p>${product.ingredientsText}</p>`}
                </div>

                <div class="info-card">
                    <h3>Nutrition (per 100g)</h3>
                    <p><strong>Energy:</strong> ${product.nutriments["energy-kcal_100g"] || "N/A"} kcal</p>
                    <p><strong>Sugar:</strong> ${product.nutriments.sugars_100g || "N/A"} g</p>
                    <p><strong>Fat:</strong> ${product.nutriments.fat_100g || "N/A"} g</p>
                    <p><strong>Salt:</strong> ${product.nutriments.salt_100g || "N/A"} g</p>
                </div>

                <div class="info-card">
                    <h3>Additives</h3>
                    ${product.additives.length ? `<ul>${product.additives.map(a => `<li>${a}</li>`).join("")}</ul>` : `<p>No additives reported</p>`}
                </div>

                <div class="info-card">
                    <h3>Allergens</h3>
                    ${product.allergens ? `<p>${product.allergens}</p>` : `<p>No allergens reported</p>`}
                </div>

                ${aiHTML}
            </div>

            <div class="footer-note">Data sourced live from OpenFoodFacts.</div>
        </div>
    `;
}

// ============================================
// CALCULATE CONCERN SCORE
// ============================================
function calculateConcern(product) {
    let score = 100;
    const nutriScores = { "e": 40, "d": 25, "c": 10 };
    score -= nutriScores[product.nutriscore] || 0;
    if (product.additives.length > 5) score -= 20;
    if (product.ingredientsText.toLowerCase().includes("palm oil")) score -= 10;
    score = Math.max(0, score);

    if (score >= 80) return { score, level: "low", label: "Low Concern" };
    if (score >= 50) return { score, level: "moderate", label: "Moderate Concern" };
    return { score, level: "high", label: "High Concern" };
}

// ============================================
// SHOW ERROR
// ============================================
function showError(message) {
    const container = document.getElementById("productContainer");
    const loading = document.getElementById("loadingContainer");

    if (loading) loading.style.display = "none";
    if (container) container.style.display = "block";

    container.innerHTML = `
        <div style="text-align:center;padding:5rem 2rem;">
            <h2>Product Not Found</h2>
            <p>${message}</p>
            <a href="dashboard.html" class="back-btn">Return to Dashboard</a>
        </div>
    `;
}

// ============================================
// FETCH PRODUCT SAFETY NEWS
// ============================================
async function fetchNews(productName) {
    try {
        const res = await fetch("http://127.0.0.1:8000/news", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ product_name: productName })
        });
        const data = await res.json();
        displayNews(data.news || []);
    } catch (err) {
        console.error(err);
        displayNews([]);
    }
}

function displayNews(newsList) {
    const container = document.getElementById("news-section");
    container.innerHTML = "";

    if (!newsList.length) {
        container.innerHTML = `<p>No recent safety alerts found for this product.</p>`;
        return;
    }

    newsList.forEach(n => {
        container.innerHTML += `<div class="news-card">
            <img src="${n.thumbnail || 'https://images.unsplash.com/photo-1606787366850-de6330128bfc?w=800&q=80'}" class="news-image"/>
            <div>
                <div>${n.source || "Unknown"} • ${n.date || "Unknown"}</div>
                <div>${n.title}</div>
                <a href="${n.link}" target="_blank">Read More</a>
            </div>
        </div>`;
    });
}
