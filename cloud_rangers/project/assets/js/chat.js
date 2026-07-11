// AI Chat JavaScript
// Handles chat interface, message sending, and simulated AI responses

document.addEventListener('DOMContentLoaded', function () {
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const chatMessages = document.getElementById('chatMessages');
    const typingIndicator = document.getElementById('typingIndicator');
    const sendBtn = document.getElementById('sendBtn');

    // Auto-resize textarea
    if (chatInput) {
        chatInput.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';

            // Enable/disable send button
            sendBtn.disabled = this.value.trim() === '';
        });

        // Initial state
        sendBtn.disabled = true;
    }

    // Handle form submission
    if (chatForm) {
        chatForm.addEventListener('submit', function (e) {
            e.preventDefault();
            sendMessage();
        });
    }

    // Handle Enter key (Shift+Enter for new line)
    if (chatInput) {
        chatInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (this.value.trim() !== '') {
                    sendMessage();
                }
            }
        });
    }
});

// Send message function
async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();

    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');

    // Clear input
    chatInput.value = '';
    chatInput.style.height = 'auto';
    document.getElementById('sendBtn').disabled = true;

    // Show typing indicator
    showTypingIndicator();

    // Simulate typing delay for realism
    await new Promise(r => setTimeout(r, 900 + Math.random() * 600));
    hideTypingIndicator();

    // 1. Try backend Gemini first
    let answered = false;
    try {
        let context = null;
        try { context = JSON.parse(localStorage.getItem("lps_ai_context") || "null"); } catch(e) {}
        const apiBase = (window.location.protocol === 'file:') ? 'http://127.0.0.1:8000' : window.location.origin;
        const res = await fetch(apiBase + '/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, context }),
            signal: AbortSignal.timeout(8000)
        });
        if (res.ok) {
            const data = await res.json();
            const reply = data.response || '';
            // Use the AI response if we got one
            if (reply && reply.trim()) {
                addMessage(reply, 'ai');
                answered = true;
            }
        } else if (res.status === 503) {
            // AI service not configured - fall back to local KB silently
            console.log('AI service not configured, using local knowledge base');
        }
    } catch(e) { 
        // backend unavailable — fall through to local KB
        console.log('Backend unavailable, using local knowledge base:', e);
    }

    // 2. Fallback: local knowledge base always answers
    if (!answered) {
        const reply = getLocalAnswer(message);
        addMessage(reply, 'ai');
    }
}

// Add message to chat
function addMessage(text, type) {
    const chatMessages = document.getElementById('chatMessages');
    const messageWrapper = document.createElement('div');
    messageWrapper.className = `message-wrapper ${type}-message`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = type === 'ai' ? '<i class="bi bi-robot"></i>' : '<i class="bi bi-person-fill"></i>';

    const content = document.createElement('div');
    content.className = 'message-content';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    // Convert line breaks to <br> and format text (simple markdown)
    const formattedText = formatMessageText(text);
    bubble.innerHTML = formattedText;

    const time = document.createElement('div');
    time.className = 'message-time';
    time.textContent = 'Just now';

    content.appendChild(bubble);
    content.appendChild(time);

    messageWrapper.appendChild(avatar);
    messageWrapper.appendChild(content);

    chatMessages.appendChild(messageWrapper);

    // Scroll to bottom
    scrollToBottom();
}

// Format message text
function formatMessageText(text) {
    if (!text) return "";

    // Headers (### text)
    text = text.replace(/^### (.*$)/gm, '<h4>$1</h4>');
    text = text.replace(/^## (.*$)/gm, '<h3>$1</h3>');
    text = text.replace(/^# (.*$)/gm, '<h2>$1</h2>');

    // Bold **text**
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Italics *text*
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Code blocks
    text = text.replace(/```([\s\S]*?)```/g, '<div class="code-block">$1</div>');
    text = text.replace(/`(.*?)`/g, '<code>$1</code>');

    // Convert URLs to links
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    text = text.replace(urlRegex, '<a href="$1" target="_blank" class="chat-link">$1</a>');

    // Convert numbered lists
    text = text.replace(/^\d+\.\s+(.*$)/gm, '<li>$1</li>');

    // Convert bullet points
    text = text.replace(/^[\-\*]\s+(.*$)/gm, '<li>$1</li>');

    // Wrap consecutive list items in <ul> or <ol> (simplified hack: just let browser render lists if styled properly, or use br)

    // Convert line breaks (excluding existing html block tags)
    text = text.replace(/\n\n/g, '<br><br>');
    text = text.replace(/(?<!<br>)\n(?!<br>)/g, '<br>');
    text = text.replace(/<br><li>/g, '<li>');
    text = text.replace(/<\/li><br>/g, '</li>');

    return text;
}

// Show typing indicator
function showTypingIndicator() {
    let typingIndicator = document.getElementById('typingIndicator');
    const chatMessages = document.getElementById('chatMessages');

    if (typingIndicator && chatMessages) {
        // Move it to the very bottom of the chat list so it scrolls naturally
        chatMessages.appendChild(typingIndicator);
        typingIndicator.style.display = 'block';
        scrollToBottom();
    }
}

// Hide typing indicator
function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.style.display = 'none';
    }
}

// Scroll chat to bottom
function scrollToBottom() {
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        setTimeout(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }, 100);
    }
}

// Quick message function
function sendQuickMessage(message) {
    const chatInput = document.getElementById('chatInput');
    chatInput.value = message;
    chatInput.dispatchEvent(new Event('input'));
    sendMessage();
}

// ══════════════════════════════════════════════════════════════
// LOCAL KNOWLEDGE BASE — answers food safety questions offline
// ══════════════════════════════════════════════════════════════
const KNOWLEDGE_BASE = [
  {
    keys: ['msg','monosodium glutamate','glutamate'],
    answer: `**Monosodium Glutamate (MSG)**\n\nMSG is a flavour enhancer that adds a savoury "umami" taste. It is **GRAS (Generally Recognized As Safe)** by the US FDA and approved by FSSAI, EFSA, and health authorities worldwide.\n\n**Key facts:**\n- Naturally occurs in tomatoes, parmesan cheese, and mushrooms\n- Contains 12% sodium — far less than table salt\n- No consistent scientific evidence links it to adverse effects at normal dietary levels\n- "Chinese Restaurant Syndrome" claims have not been confirmed in controlled studies\n\n**Who should limit it?** People on strict low-sodium diets should be mindful of total sodium intake from all sources.`
  },
  {
    keys: ['sodium benzoate','benzoate','e211'],
    answer: `**Sodium Benzoate (E211)**\n\nA synthetic preservative used to prevent bacteria and yeast growth in acidic foods and drinks.\n\n**Health concerns:**\n- When combined with **Vitamin C (ascorbic acid)**, it can form **benzene**, a known carcinogen\n- Approved by FDA, FSSAI, and EFSA at regulated levels\n- Some studies link it to hyperactivity in children when paired with certain artificial colours\n\n**Found in:** Fizzy drinks, fruit juices, pickles, salad dressings\n\n**Verdict:** Safe at permitted levels, but avoid products that combine it with Vitamin C.`
  },
  {
    keys: ['e number','e numbers','e-number','food additive','additives'],
    answer: `**E Numbers — What Do They Mean?**\n\nE numbers are codes for food additives approved for use in Europe (and internationally). They cover:\n\n| Range | Category |\n|-------|----------|\n| E100–E199 | Colours |\n| E200–E299 | Preservatives |\n| E300–E399 | Antioxidants & acidity regulators |\n| E400–E499 | Thickeners, stabilisers, emulsifiers |\n| E600–E699 | Flavour enhancers |\n| E900+ | Waxes, gases, sweeteners |\n\n**Not all E numbers are synthetic** — E300 is Vitamin C, E101 is Riboflavin (Vitamin B2), and E406 is Agar (seaweed).\n\nAlways check the specific E number if you have concerns.`
  },
  {
    keys: ['aspartame','sweetener','artificial sweetener','saccharin','sucralose'],
    answer: `**Artificial Sweeteners**\n\n**Aspartame (E951):** Zero-calorie sweetener ~200x sweeter than sugar. Approved by FDA & EFSA. In 2023, IARC classified it as "possibly carcinogenic" (Group 2B) — the same group as pickled vegetables. JECFA still considers it safe at the ADI. **Not suitable for people with phenylketonuria (PKU).**\n\n**Sucralose (E955):** Zero-calorie, 600x sweeter than sugar. Generally safe but some studies suggest it may affect gut bacteria at high doses.\n\n**Saccharin (E954):** Oldest artificial sweetener. Previously linked to bladder cancer in rats but NOT in humans. Approved globally.\n\n**Bottom line:** All approved sweeteners are safe at normal dietary intake. Moderation is key.`
  },
  {
    keys: ['palm oil','saturated fat','palmolein'],
    answer: `**Palm Oil**\n\nPalm oil is widely used in processed foods because it is cheap, stable at high temperatures, and naturally semi-solid.\n\n**Health concerns:**\n- Very high in saturated fat (~50%) — more than butter\n- High saturated fat intake is linked to raised LDL (bad) cholesterol\n- Palm oil is NOT the same as partially hydrogenated oil — it does NOT contain trans fats\n\n**Environmental concerns:**\n- Linked to deforestation and habitat loss in Indonesia and Malaysia\n- Look for RSPO-certified sustainable palm oil\n\n**Verdict:** Legal and approved everywhere. Consume in moderation as part of a balanced diet.`
  },
  {
    keys: ['gluten','celiac','wheat','wheat flour','maida'],
    answer: `**Gluten & Wheat**\n\nGluten is a protein found in wheat, barley, rye, and spelt.\n\n**Who needs to avoid it?**\n- **Celiac disease** (~1% of population): Gluten triggers immune damage to the small intestine. Must avoid completely.\n- **Non-celiac gluten sensitivity:** Symptoms without intestinal damage. Benefit from reduction.\n- **Wheat allergy:** Immune response to wheat proteins. Different from celiac disease.\n\n**Hidden sources:** Soy sauce, malt vinegar, some oats (cross-contamination), beer, many processed foods.\n\n**Maida (refined wheat flour):** Contains gluten AND has very low fiber and nutrients. High glycemic index — spikes blood sugar quickly.`
  },
  {
    keys: ['sugar','high sugar','added sugar','glucose syrup','fructose'],
    answer: `**Sugar in Food**\n\nThe WHO recommends limiting **free sugars** to less than **10% of total energy** (~50g/day for adults).\n\n**Types of sugar on labels:**\n- **Sucrose** — regular table sugar\n- **Glucose/Dextrose** — fast-absorbing, high GI\n- **Fructose** — fruit sugar; excess can stress the liver\n- **High Fructose Corn Syrup (HFCS)** — highly processed; linked to obesity and metabolic syndrome\n- **Invert sugar / Glucose syrup** — fast-absorbing sweeteners in confectionery\n\n**Health effects of excess sugar:**\n- Weight gain and obesity\n- Type 2 diabetes risk\n- Dental cavities\n- Fatty liver disease (HFCS)\n\n**Tip:** Ingredients are listed by weight — if sugar appears in the first 3 ingredients, the product is high in sugar.`
  },
  {
    keys: ['sodium','salt','high sodium','hypertension','blood pressure'],
    answer: `**Sodium / Salt**\n\nThe WHO recommends less than **5g of salt (2g sodium) per day** for adults.\n\n**Salt vs Sodium:**\n- Salt = Sodium + Chloride\n- 1g of salt = ~0.4g of sodium\n- To convert: Sodium (g) × 2.5 = Salt (g)\n\n**High sodium risks:**\n- Raises blood pressure (hypertension)\n- Increases risk of heart disease and stroke\n- Strains kidneys\n\n**Hidden sodium in foods:**\n- Instant noodles, chips, pickles, sauces, bread, processed meats, cheese\n\n**For hypertension patients:** A product with >1.5g salt per 100g is considered high. Target <0.3g per 100g for a low-salt food.`
  },
  {
    keys: ['tartrazine','yellow 5','red 40','allura red','food colour','artificial colour','food dye'],
    answer: `**Artificial Food Colours**\n\nCommon synthetic food dyes and their status:\n\n| Dye | E Number | Status |\n|-----|----------|--------|\n| Tartrazine (Yellow 5) | E102 | EU/UK: Warning label required |\n| Sunset Yellow (Yellow 6) | E110 | EU/UK: Warning label required |\n| Allura Red (Red 40) | E129 | EU/UK: Warning label required |\n| Brilliant Blue (Blue 1) | E133 | Banned in EU |\n\n**EU/UK requirement:** Products containing these dyes must carry the warning: *"may have an adverse effect on activity and attention in children."*\n\n**India (FSSAI):** All above are permitted. No warning label required.\n\n**USA (FDA):** All permitted. No special warning.\n\n**Verdict:** Avoid for young children. Prefer products using natural colours (curcumin, beta-carotene, beetroot).`
  },
  {
    keys: ['nova','ultra processed','ultra-processed','processed food','nova 4','nova group'],
    answer: `**NOVA Food Classification**\n\nNOVA classifies foods by degree of processing:\n\n| Group | Description | Examples |\n|-------|-------------|----------|\n| **1** | Unprocessed / Minimally processed | Fresh fruit, vegetables, plain milk, eggs |\n| **2** | Processed culinary ingredients | Oils, butter, sugar, salt, flour |\n| **3** | Processed foods | Canned vegetables, cheese, cured meats, bread |\n| **4** | Ultra-processed | Instant noodles, soft drinks, chips, packaged biscuits |\n\n**Ultra-processed foods (NOVA 4)** are linked to:\n- Higher obesity and diabetes risk\n- Increased cardiovascular disease\n- Poor gut microbiome health\n- Several large studies link high NOVA 4 intake to increased cancer risk\n\n**Rule of thumb:** If a product has ingredients you wouldn't find in a normal kitchen, it is likely NOVA 4.`
  },
  {
    keys: ['preservative','potassium sorbate','calcium propionate','bha','bht'],
    answer: `**Common Food Preservatives**\n\n**Potassium Sorbate (E202):**\nPrevents mould and yeast. Used in cheese, wine, yoghurt, dried fruits. Generally safe. Some people report mild skin sensitisation.\n\n**Calcium Propionate (E282):**\nPrevents mould in bread and baked goods. Generally safe. Some studies suggest links to behavioural changes in children (results inconclusive).\n\n**BHA (E320) & BHT (E321):**\nSynthetic antioxidants that prevent rancidity in fats. BHA is classified as a possible human carcinogen (IARC Group 2B). Both are restricted in EU and Japan. Approved in India and USA at low levels.\n\n**Tip:** Natural alternatives include Vitamin E (tocopherol) and rosemary extract — look for these on cleaner labels.`
  },
  {
    keys: ['allergen','allergy','milk allergy','nut allergy','peanut','soy','shellfish','egg allergy'],
    answer: `**The 14 Major Allergens (EU/UK)**\n\n1. 🥛 **Milk** (includes lactose, whey, casein)\n2. 🥚 **Eggs**\n3. 🌾 **Gluten** (wheat, barley, rye, oats)\n4. 🥜 **Peanuts**\n5. 🌰 **Tree nuts** (almonds, walnuts, cashews, etc.)\n6. 🐟 **Fish**\n7. 🦐 **Crustaceans** (shrimp, crab, lobster)\n8. 🐚 **Molluscs** (squid, mussels, oysters)\n9. 🫘 **Soy**\n10. 🌱 **Sesame**\n11. 🌿 **Mustard**\n12. 🥬 **Celery**\n13. 🍷 **Sulphites** (>10mg/kg)\n14. 🪲 **Lupin**\n\n**India (FSSAI):** Requires declaration of milk, egg, fish, shellfish, peanuts, tree nuts, wheat, soy, sesame.\n\n**Important:** Always read the full label. "May contain traces" warnings indicate shared production lines.`
  },
  {
    keys: ['diabetes','diabetic','blood sugar','glycemic','insulin'],
    answer: `**Food Guidance for Diabetes**\n\n**What to watch on labels:**\n- **Total sugars per 100g:** Aim for <5g (low), avoid >15g\n- **Total carbohydrates:** Impacts blood glucose\n- **Glycemic Index (GI):** Prefer low-GI foods (legumes, oats, most vegetables)\n- **Fiber content:** High fiber slows glucose absorption — aim for >3g/100g\n\n**Ingredients to avoid:**\n- Glucose syrup, maltodextrin, dextrose (fast-absorbing)\n- White maida/refined flour (high GI)\n- High fructose corn syrup\n\n**Better choices:**\n- Whole grain products\n- Products sweetened with stevia\n- High-fiber snacks\n\n⚠️ *This is general information only. Always consult your doctor or dietitian for personalised advice.*`
  },
  {
    keys: ['vegetarian','vegan','plant based','gelatin','gelatine','rennet'],
    answer: `**Vegetarian & Vegan Ingredient Checker**\n\n**Hidden animal-derived ingredients to watch:**\n\n| Ingredient | Source | Vegetarian? | Vegan? |\n|-----------|--------|-------------|--------|\n| Gelatin/Gelatine | Pig/Cow bones | ❌ No | ❌ No |\n| Rennet | Calf stomach | ❌ No (unless microbial) | ❌ No |\n| Carmine/Cochineal (E120) | Crushed insects | ❌ No | ❌ No |\n| Whey / Casein | Milk | ✅ Yes | ❌ No |\n| Honey | Bees | ✅ Yes | ❌ No |\n| Lactose | Milk | ✅ Yes | ❌ No |\n| Lard/Tallow | Animal fat | ❌ No | ❌ No |\n| Soy Lecithin | Soy plant | ✅ Yes | ✅ Yes |\n| Vitamin D3 | Sheep lanolin | ✅ Yes | ❌ No |\n\n**Tip:** Look for certifications like FSSAI Green Dot (vegetarian) or Vegan Society logo.`
  },
  {
    keys: ['fssai','food safety india','indian regulation','india food law'],
    answer: `**FSSAI — Food Safety and Standards Authority of India**\n\nFSSAI is India's apex food regulatory body under the Ministry of Health and Family Welfare.\n\n**Key regulations:**\n- **Food Safety and Standards Act, 2006** — main legislation\n- **FSS (Food Products Standards and Food Additives) Regulations, 2011** — permitted additives\n- **FSS (Labelling and Display) Regulations, 2020** — mandatory label information\n\n**Mandatory label requirements in India:**\n- Product name, net weight, MRP\n- Manufacturer name & address\n- Best before / expiry date\n- Batch number\n- FSSAI license number\n- Nutritional information (per 100g/100ml)\n- Allergen declaration\n- Vegetarian/Non-vegetarian dot symbol\n\n**Report unsafe food:** Call FSSAI helpline **1800-11-2100** (toll-free)`
  },
  {
    keys: ['nutriscore','nutri score','nutrition score','traffic light','health score'],
    answer: `**Nutri-Score — What It Means**\n\nNutri-Score is a front-of-pack nutrition label used in Europe that grades food from **A (healthiest)** to **E (least healthy)**.\n\n**How it's calculated:**\nPositive points (fiber, protein, fruit/veg content) minus negative points (sugar, saturated fat, sodium, calories).\n\n| Grade | Colour | Meaning |\n|-------|--------|----------|\n| A | Dark green | Excellent nutritional quality |\n| B | Light green | Good quality |\n| C | Yellow | Average |\n| D | Orange | Poor quality |\n| E | Red | Very poor quality |\n\n**Note:** Nutri-Score is not mandatory in India. Our Label Padegha Sabh concern score uses a similar principle but adds ingredient-level analysis, allergens, regulatory data, and personalized health profile matching.`
  },
  {
    keys: ['pregnancy','pregnant','prenatal'],
    answer: `**Food Safety During Pregnancy**\n\n**Foods to avoid completely:**\n- Raw/undercooked meat, fish, and eggs (Listeria, Salmonella risk)\n- High-mercury fish (shark, swordfish, king mackerel)\n- Unpasteurised dairy and juices\n- Soft cheeses (brie, camembert, blue cheese)\n- Deli meats unless heated until steaming\n- Raw sprouts\n\n**Limit:**\n- Caffeine: <200mg/day (≈1-2 cups of coffee)\n- Artificial colours (especially Southampton Six)\n- High-sodium foods (can worsen pregnancy hypertension)\n\n**Essential nutrients:**\n- **Folic acid (400mcg/day):** Prevents neural tube defects\n- **Iron:** Prevents anaemia\n- **Calcium & Vitamin D:** For baby's bones\n- **DHA (omega-3):** For brain development\n\n⚠️ *Always consult your doctor or gynecologist for personalised advice.*`
  },
  {
    keys: ['children','kids','child','baby','infant','hyperactivity'],
    answer: `**Food Safety for Children**\n\n**Ingredients to limit for children:**\n\n- **Artificial colours** (Tartrazine, Sunset Yellow, Allura Red, etc.): EU studies link them to hyperactivity. EU/UK require warning labels.\n- **High sugar**: Linked to tooth decay, obesity, and energy crashes\n- **Sodium**: Children have lower daily limits than adults\n- **Caffeine**: Not recommended for children under 12\n- **Aspartame**: Not recommended for phenylketonuric children\n\n**Daily sodium limits for children:**\n| Age | Max Salt/day |\n|-----|--------------|\n| 1–3 years | 2g |\n| 4–6 years | 3g |\n| 7–10 years | 5g |\n| 11+ years | 6g |\n\n**Better snack choices:** Fresh fruit, plain yoghurt, nuts (age-appropriate), whole grain crackers, homemade foods with known ingredients.`
  },
  {
    keys: ['trans fat','partially hydrogenated','hydrogenated oil','vanaspati'],
    answer: `**Trans Fats — Why They Are Dangerous**\n\nIndustrial trans fats are created by partially hydrogenating vegetable oils. They are one of the most harmful dietary fats.\n\n**Health effects:**\n- Raises LDL (bad) cholesterol\n- Lowers HDL (good) cholesterol\n- Strongly linked to heart disease, stroke, and Type 2 diabetes\n- WHO estimates 500,000 premature deaths annually from trans fat consumption\n\n**Global bans:**\n- **USA:** Banned since 2018\n- **EU:** Limited to 2g per 100g fat since 2021\n- **Canada, Australia, UK:** Effectively banned or severely restricted\n- **India (FSSAI):** Limited to **2% of total fats** since January 2022\n\n**How to spot it on labels:**\n- "Partially hydrogenated vegetable oil"\n- "Hydrogenated fat"\n- "Vanaspati"\n\nEven if a product claims "0g trans fat", it may legally contain up to 0.5g per serving in some countries.`
  },
  {
    keys: ['maggi','instant noodle','ramen'],
    answer: `**Maggi & Instant Noodles — Health Analysis**\n\n**Typical concerns:**\n- **Very High Sodium:** Most instant noodles contain 1.5–2.5g salt per 100g — close to the entire daily recommended intake in one serving\n- **Refined flour (maida):** Low fiber, high GI — causes rapid blood sugar spikes\n- **Palm oil:** High saturated fat content\n- **MSG (E621):** Flavour enhancer — safe for most people but adds to sodium load\n- **Artificial colours:** Some variants contain Sunset Yellow or Tartrazine\n- **NOVA Group 4:** Ultra-processed food\n\n**The 2015 Maggi controversy:**\nFSSAI ordered recall of Maggi noodles after tests found elevated lead levels and undeclared MSG. Nestle denied the findings. After legal battle, Maggi returned to shelves after passing safety tests.\n\n**Healthier tip:** If consuming instant noodles, discard most of the seasoning packet (main sodium source) and add fresh vegetables.`
  },
  {
    keys: ['cadbury','chocolate','cocoa','dark chocolate'],
    answer: `**Chocolate — Ingredients Decoded**\n\n**Common chocolate ingredients:**\n- **Cocoa mass/solids:** The actual cocoa bean content. Higher % = more antioxidants (flavanols)\n- **Cocoa butter:** Natural fat from cocoa beans. High in stearic acid (neutral on cholesterol)\n- **Sugar:** Often the first ingredient in milk chocolate\n- **Milk solids/milk powder:** Adds dairy allergen\n- **Soy lecithin (E322):** Emulsifier — contains soy allergen\n- **PGPR (E476):** Cheaper emulsifier used to reduce cocoa butter content\n- **Vanillin:** Synthetic vanilla flavouring (natural vanilla is far more expensive)\n- **Palm oil:** Some manufacturers add it to extend shelf life\n\n**India vs Global formulations:**\nCadbury India often uses PGPR (E476) instead of natural cocoa butter, and "milk solids minimum 22%" — lower cocoa content than EU-standard chocolate.\n\n**Dark chocolate benefit:** 70%+ dark chocolate contains significant flavanols with antioxidant properties.`
  },
  {
    keys: ['pringles','chips','crisps','potato chips','lays','lay\'s'],
    answer: `**Chips & Crisps — Health Analysis**\n\n**Typical nutritional profile (per 100g):**\n- Calories: 500–550 kcal\n- Fat: 30–35g (mostly from frying oil)\n- Saturated fat: 8–15g\n- Sodium: 1–2g (salt equivalent: 2.5–5g)\n- Carbohydrates: 50–55g\n\n**Key concerns:**\n- **High calorie density** — easy to overeat\n- **High sodium** — significant blood pressure impact\n- **Acrylamide** — naturally formed when starchy foods are cooked at high temperatures. Classified as a probable carcinogen. Present in all fried/baked chips.\n- **Palm oil** — high saturated fat (India-market Pringles use palm oil exclusively)\n- **Artificial flavours & colours** — some variants contain synthetic dyes\n\n**Pringles specifically:**\nContain dried potatoes, not whole potato slices. Only ~42% potato content — technically a "potato crisp" not a "potato chip" in some jurisdictions.\n\n**Healthier alternatives:** Air-popped popcorn, baked whole-grain crackers, roasted makhana (fox nuts).`
  }
];

/**
 * Find the best matching answer from the knowledge base.
 * Falls back to a context-aware or generic response.
 */
function getLocalAnswer(message) {
    const q = message.toLowerCase();

    // Check product context from last scan
    let ctx = null;
    try { ctx = JSON.parse(localStorage.getItem('lps_ai_context') || 'null'); } catch(e) {}

    // Try knowledge base match
    for (const entry of KNOWLEDGE_BASE) {
        if (entry.keys.some(k => q.includes(k))) {
            return entry.answer;
        }
    }

    // Context-aware answer if user scanned a product recently
    if (ctx && ctx.name) {
        const name = ctx.name;
        const score = ctx.concern_score;
        const allergens = (ctx.allergens || []).join(', ') || 'none detected';
        const ings = (ctx.ingredients || []).slice(0, 5).join(', ');

        if (q.includes('safe') || q.includes('healthy') || q.includes('good') || q.includes('bad') || q.includes('concern')) {
            return `**${name} — Safety Overview**\n\nBased on our analysis:\n- **Concern Score:** ${score}/100\n- **Allergens detected:** ${allergens}\n- **Key ingredients:** ${ings}\n\nA score above 50 indicates moderate-to-high concern. Review the full product analysis page for a detailed breakdown of all flagged ingredients, regulatory status across 8 countries, and personalized warnings based on your health profile.`;
        }
        if (q.includes('ingredient') || q.includes('what is in') || q.includes('contain')) {
            return `**Ingredients in ${name}:**\n\n${(ctx.ingredients || []).map((i, n) => `${n+1}. ${i}`).join('\n') || 'No ingredient data available.'}\n\nFor detailed explanations of each ingredient — including health notes, purpose, and regulatory status — check the Ingredient Breakdown section on the product analysis page.`;
        }
        if (q.includes('allergen') || q.includes('allergy')) {
            return `**Allergens in ${name}:**\n\n${allergens !== 'none detected' ? '⚠️ Contains: **' + allergens + '**' : '✅ No common allergens detected in the ingredient list.'}\n\nAlways check the physical product label as manufacturing processes may cause cross-contamination even when an allergen is not a direct ingredient.`;
        }
        return `**About ${name}:**\n\nThis product has a concern score of **${score}/100**. Key allergens: ${allergens}.\n\nYou can ask me specific questions like:\n- "Is it safe for diabetics?"\n- "What are the main ingredients?"\n- "Does it contain allergens?"\n- "Is MSG harmful?"\n- "What are artificial colours?"\n\nOr scan another product for a fresh analysis.`;
    }

    // Generic fallback
    const suggestions = [
        '"What is MSG?"',
        '"Is sodium benzoate safe?"',
        '"Explain E numbers"',
        '"What are artificial colours?"',
        '"Is this safe for diabetics?"',
        '"What are trans fats?"',
        '"Explain NOVA classification"',
    ];
    const random = suggestions[Math.floor(Math.random() * suggestions.length)];
    return `I'm your food safety assistant. I can answer questions about ingredients, additives, allergens, regulations, and help you understand product labels.\n\nTry asking something like ${random}\n\nOr scan a product first and I can give you specific insights about it.`;
}

// ── Legacy comment block
/*
    AI CHAT DATABASE INTEGRATION:
    
    In production, this chat would connect to:
    
    1. VECTOR DATABASE for RAG (Retrieval Augmented Generation):
       - Store embeddings of product information, ingredient data
       - Use for context-aware responses
       - Example: Pinecone, Weaviate, or PostgreSQL with pgvector
    
    2. PRODUCT CONTEXT:
       - If user asks about current product, fetch from session/URL params
       - Query product details, ingredients, compliance status
       - Provide specific answers based on actual product data
    
    3. USER PROFILE CONTEXT:
       - Include user allergies, preferences in AI prompts
       - Personalize warnings and recommendations
       - Query: SELECT * FROM user_health_profiles WHERE user_id = {id}
    
    4. KNOWLEDGE BASE:
       - Store in 'knowledge_articles' table
       - Categories: ingredients, additives, regulations, health concerns
       - Use for consistent, verified information
    
    5. CHAT HISTORY:
       - Store in 'chat_messages' table for context and user support
       - Schema: id, user_id, message, response, timestamp
    
    6. API INTEGRATION:
       - In production: Call Claude API or other LLM
       - Include system prompts with regulatory disclaimers
       - Example endpoint: /api/chat with streaming response
*/