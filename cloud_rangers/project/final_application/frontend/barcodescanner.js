window.addEventListener("DOMContentLoaded", startScanner);

function startScanner() {
    const codeReader = new ZXing.BrowserMultiFormatReader();
    const videoElement = document.getElementById("video");
    const statusText = document.getElementById("status");

    statusText.textContent = "Accessing camera...";

    codeReader.decodeFromVideoDevice(null, videoElement, async (result, err) => {
        if (result) {
            const barcode = result.getText();
            statusText.textContent = `✅ Barcode detected: ${barcode}`;

            codeReader.reset(); // stop camera after first successful scan

            // fetch the product and feed to product-eval-engine
            await fetchProductByBarcode(barcode);
        }

        if (err && !(err instanceof ZXing.NotFoundException)) {
            console.error(err);
        }
    });
}

// ============================================
// Fetch from OpenFoodFacts and feed to engine
// ============================================
async function fetchProductByBarcode(barcode) {
    const container = document.getElementById("productContainer");
    container.innerHTML = "Fetching product data...";

    try {
        const response = await fetch(
            `https://world.openfoodfacts.org/api/v0/product/${barcode}.json`
        );

        if (!response.ok) throw new Error("Network error");

        const data = await response.json();

        if (!data || data.status !== 1 || !data.product) {
            container.innerHTML = "<h3>❌ Product not found in OpenFoodFacts</h3>";
            return;
        }

        // Transform data
        const product = transformOpenFoodData(data.product);

        // Render product immediately
        renderDynamicProduct(product, null);

        // Optional: call AI analysis asynchronously
        analyzeIngredientsAI(product).then(aiData => {
            renderDynamicProduct(product, aiData); // update AI section
        });

        // Optional: fetch news asynchronously
        fetchNews(product.name);

    } catch (error) {
        console.error(error);
        container.innerHTML = "<h3>⚠️ Error fetching product data</h3>";
    }
}
