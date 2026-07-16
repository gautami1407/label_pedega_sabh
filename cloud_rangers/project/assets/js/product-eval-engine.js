// ============================================================
// LABEL PADEGHA SABH — Consumer Decision Platform v7.0
// Purpose: Help shoppers decide "Should I buy this?"
// Shopper-first design with Purchase Decision focus
// ============================================================

const API = (window.location.protocol === 'file:') ? 'http://127.0.0.1:8000' : '';

function log(m, t) { t=t||'info'; var p='[LPS] '; t==='error'?console.error(p+m):t==='warn'?console.warn(p+m):console.log(p+m); }

// ── HTML Escape ──
var _amp='&'+'amp;',_lt='&'+'lt;',_gt='&'+'gt;',_quot='&'+'quot;';
function esc(s){return String(s||'').replace(/&/g,_amp).replace(/</g,_lt).replace(/>/g,_gt).replace(/"/g,_quot).replace(/'/g,'&#039');}

// ── Bootstrap ──
window.addEventListener('DOMContentLoaded',function(){
    var u=new URLSearchParams(window.location.search);
    var bc=u.get('barcode')||localStorage.getItem('scannedBarcode');
    var img=localStorage.getItem('scannedImageBase64');
    if(bc){log('Scanning: '+bc);fetchFullAnalysis(bc);}
    else if(img){localStorage.removeItem('scannedImageBase64');fetchProductByImage(img);}
    else showError('No product','Scan a product or upload an image first.');
});

function showError(t,m){
    var l=document.getElementById('loadingContainer'),c=document.getElementById('productContainer'),e=document.getElementById('errorContainer');
    if(l)l.style.display='none';if(c)c.style.display='none';
    if(e){e.style.display='block';
        var tt=document.getElementById('errorTitle'),mm=document.getElementById('errorMessage');
        if(tt)tt.textContent=t||'Error';if(mm)mm.textContent=m||'Something went wrong.';
    }
}

function getProfile(){try{return JSON.parse(localStorage.getItem('healthProfile')||'{}');}catch(e){return{};}}

// ── Fetch ──
async function fetchFullAnalysis(barcode){
    var l=document.getElementById('loadingContainer'),c=document.getElementById('productContainer');
    if(l)l.style.display='flex';if(c)c.style.display='none';
    try{
        var p=getProfile();
        var r=await fetch(API+'/api/analyze-product',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({barcode:barcode,age:p.age||null,allergies:p.allergies||[],conditions:p.conditions||[],diet:p.diet||''})});
        var d=await r.json();
        if(!r.ok)throw new Error((d&&(d.detail||d.error))||'Server error');
        if(d.error){showError('Not Found',d.error);return;}
        if(l)l.style.display='none';
        renderAnalysis(d,getProfile());
    }catch(e){
        if(l)l.style.display='none';
        if(e.message.indexOf('Failed to fetch')>=0)showError('Cannot Connect','Start the backend: cd backend && python app.py');
        else showError('Analysis Failed',e.message);
    }
}

async function fetchProductByImage(img){
    var l=document.getElementById('loadingContainer'),c=document.getElementById('productContainer');
    if(l)l.style.display='flex';if(c)c.style.display='none';
    try{
        var r=await fetch(API+'/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:'data:image/jpeg;base64,'+img,preferences:getProfile()})});
        var d=await r.json();
        if(!r.ok)throw new Error((d&&(d.error||d.detail))||'Server error');
        if(d.error&&!d.name){showError('Image Failed',d.error);return;}
        if(l)l.style.display='none';renderAnalysis(d,getProfile());
    }catch(e){if(l)l.style.display='none';showError('Image Failed',e.message);}
}

// ── MAIN RENDER ENGINE (Consumer-First) ──
function renderAnalysis(d,profile){
    if(!profile)profile={};
    window.ad=d; window.ar=d.additive_regulatory_report||[];
    var c=document.getElementById('productContainer');if(!c)return;
    try{
        var p=d.product||{},nut=d.nutrition||{},ings=d.ingredients||[],ie=d.ingredient_explanations||[];
        var cs=d.concern_score||{score:50,level:'Moderate',factors:[]},score=cs.score||50,level=cs.level||'Moderate';
        var al=d.allergens||[],alerts=d.alerts||[],pw=d.personalized_warnings||[],regs=d.regulatory||[],news=d.news||[];
        var nova=d.nova||{level:'Unknown',name:'',description:''};
        var factors=cs.factors||[];
        
        // Build product summary badges
        var productBadges = buildProductBadges(p, ings, nut);
        
        // Purchase Decision - shopper first
        var purchaseDecision = getPurchaseDecision(score, level, factors, ings, nut, regs);
        
        // Health dashboard data
        var healthDashboard = buildHealthDashboard(nut, ings, score);
        
        // Build HTML
        var html='';
        
        // ═══════════════════════════════════════════════
        // 1. PRODUCT SUMMARY
        // ═══════════════════════════════════════════════
        html+='<div class="section-card">';
        html+='<div class="sec-header"><i class="bi bi-box-seam"></i> <span>Product Summary</span></div>';
        html+='<div class="sec-body expanded">';
        html+='<div class="product-meta-grid">';
        html+='<div class="product-meta-item"><div class="product-meta-label">Product</div><div class="product-meta-value">'+esc(p.name||'Unknown')+'</div></div>';
        html+='<div class="product-meta-item"><div class="product-meta-label">Brand</div><div class="product-meta-value">'+esc(p.brand||'Unknown')+'</div></div>';
        html+='<div class="product-meta-item"><div class="product-meta-label">Category</div><div class="product-meta-value">'+esc(p.categories? (Array.isArray(p.categories)? p.categories.join(', '): p.categories): 'Unknown')+'</div></div>';
        html+='<div class="product-meta-item"><div class="product-meta-label">Barcode</div><div class="product-meta-value">'+esc(barcode||'Unknown')+'</div></div>';
        html+='<div class="product-meta-item"><div class="product-meta-label">Source</div><div class="product-meta-value">'+esc(p.source||'OpenFoodFacts')+'</div></div>';
        if(p.manufacturer){
            html+='<div class="product-meta-item"><div class="product-meta-label">Manufacturer</div><div class="product-meta-value">'+esc(p.manufacturer)+'</div></div>';
        }
        if(p.origin){
            html+='<div class="product-meta-item"><div class="product-meta-label">Origin</div><div class="product-meta-value">'+esc(p.origin)+'</div></div>';
        }
        html+='</div>';
        // Product badges row
        if(productBadges.length){
            html+='<div style="margin-top:12px;">'+productBadges.join('')+'</div>';
        }
        html+='</div></div>';
        
        // ═══════════════════════════════════════════════
        // 2. PURCHASE DECISION (MOST IMPORTANT)
        // ═══════════════════════════════════════════════
        html+='<div class="section-card" style="border:2px solid '+(purchaseDecision.class==='recommended'?'#a7f3d0':purchaseDecision.class==='occasional'?'#fde68a':purchaseDecision.class==='limit'?'#fed7aa':'#fecaca')+'">';
        html+='<div class="sec-header"><i class="bi bi-cart-check"></i> <span>Purchase Decision</span></div>';
        html+='<div class="sec-body expanded">';
        html+='<div class="purchase-badge '+purchaseDecision.class+'"><i class="bi '+purchaseDecision.icon+'"></i> <span>'+esc(purchaseDecision.text)+'</span></div>';
        html+='<div class="purchase-reasons">';
        for(var i=0;i<purchaseDecision.reasons.length;i++){
            var r=purchaseDecision.reasons[i];
            html+='<div class="reason-item '+r.type+'"><i class="bi '+r.icon+'"></i> <span>'+esc(r.text)+'</span></div>';
        }
        html+='</div>';
        // Who should avoid
        if(purchaseDecision.audience.length){
            html+='<div class="audience-warning"><h6><i class="bi bi-exclamation-triangle"></i> Who should avoid this product?</h6><ul>';
            for(var j=0;j<purchaseDecision.audience.length;j++){
                html+='<li>'+esc(purchaseDecision.audience[j])+'</li>';
            }
            html+='</ul></div>';
        }
        html+='<div class="dec-final"><i class="bi bi-info-circle-fill"></i> '+esc(purchaseDecision.summary)+'</div>';
        html+='</div></div>';
        
        // ═══════════════════════════════════════════════
        // 3. HEALTH SCORE DASHBOARD
        // ═══════════════════════════════════════════════
        html+='<div class="section-card">';
        html+='<div class="sec-header"><i class="bi bi-heart-pulse"></i> <span>Health Score Dashboard</span></div>';
        html+='<div class="sec-body expanded">';
        html+='<div class="health-dashboard">'+healthDashboard+'</div>';
        html+='</div></div>';
        
        // ═══════════════════════════════════════════════
        // 4. INGREDIENT INTELLIGENCE
        // ═══════════════════════════════════════════════
        // Deduplicate ingredients
        var ingMap={};var ingDedup=[];
        for(var k=0;k<ie.length;k++){
            var ig=ie[k];var key=ig.name.toLowerCase().trim();
            if(!ingMap[key]){ingMap[key]={name:ig.name,simple:ig.simple_name||'',purpose:ig.purpose||'',desc:ig.description||'',cat:ig.category||'',source:ig.source||'',ins_e:ig.ins_e||'',health_info:ig.health_info||''};ingDedup.push(ingMap[key]);}
            else{if(ig.simple_name&&!ingMap[key].simple)ingMap[key].simple=ig.simple_name;if(ig.source==='additives'||ig.source==='both')ingMap[key].source=ig.source;}
        }
        
        html+='<div class="section-card">';
        html+='<div class="sec-header" onclick="toggleSection(this)"><i class="bi bi-list-check"></i> <span>Ingredient Intelligence ('+ingDedup.length+')</span><i class="bi bi-chevron-down sec-chevron"></i></div>';
        html+='<div class="sec-body expanded">';
        
        if(ingDedup.length){
            for(var m=0;m<ingDedup.length;m++){
                var ing=ingDedup[m];
                var rClass='safe';var rIcon='🟢';
                var cat=(ing.cat||'').toLowerCase();
                if(cat==='preservative'||cat==='colour'||cat==='artificial colour'){rClass='high';rIcon='🔴';}
                else if(cat==='sweetener'||cat==='flavour enhancer'){rClass='warning';rIcon='🟡';}
                
                // Get additive details if available
                var additiveInfo = getAdditiveInfoForIngredient(ing.name);
                
                html+='<div class="ingredient-knowledge-card" id="ingCard'+m+'" onclick="toggleIngredientCard('+m+')">';
                html+='<div class="ingredient-card-header">';
                html+='<div><span class="ingredient-name">'+esc(ing.name)+'</span>';
                if(ing.simple)html+='<span class="ingredient-category-badge">'+esc(ing.simple)+'</span>';
                html+='</div>';
                html+='<span class="ingredient-category-badge">'+esc(ing.cat||'Unknown')+'</span>';
                html+='</div>';
                html+='<div class="ingredient-card-body" id="ingBody'+m+'">';
                if(additiveInfo){
                    html+='<div class="ingredient-info-row"><span class="ingredient-info-label">INS/E Number</span><span class="ingredient-info-value">'+esc(additiveInfo.ins_no||'Data Not Available')+'</span></div>';
                    html+='<div class="ingredient-info-row"><span class="ingredient-info-label">Why Added</span><span class="ingredient-info-value">'+esc(additiveInfo.purpose||'Data Not Available')+'</span></div>';
                    html+='<div class="ingredient-info-row"><span class="ingredient-info-label">Where Used</span><span class="ingredient-info-value">'+esc(additiveInfo.found_in||additiveInfo.food_category||'Data Not Available')+'</span></div>';
                    html+='<div class="ingredient-info-row"><span class="ingredient-info-label">Health Impact</span><span class="ingredient-info-value">'+esc(additiveInfo.health_considerations||additiveInfo.scientific_notes||'Data Not Available')+'</span></div>';
                    html+='<div class="ingredient-info-row"><span class="ingredient-info-label">Daily Intake</span><span class="ingredient-info-value">'+esc(additiveInfo.adi||'Data Not Available')+'</span></div>';
                }else{
                    html+='<div class="ingredient-info-row"><span class="ingredient-info-label">Purpose</span><span class="ingredient-info-value">'+esc(ing.purpose||'No verified public information available.')+'</span></div>';
                    html+='<div class="ingredient-info-row"><span class="ingredient-info-label">Health Info</span><span class="ingredient-info-value">'+esc(ing.desc||'No verified public information available.')+'</span></div>';
                }
                html+='</div>';
                html+='</div>';
            }
        }else{
            html+='<div class="note-empty">No ingredient details available.</div>';
        }
        html+='</div></div>';
        
        // ═══════════════════════════════════════════════
        // 5. RELATED PRODUCTS
        // ═══════════════════════════════════════════════
        if(d.related_products && d.related_products.length){
            html+=buildRelatedProductsSection(d.related_products, score);
        }
        
        // ═══════════════════════════════════════════════
        // 6. SMART PRODUCT COMPARISON
        // ═══════════════════════════════════════════════
        html+='<div class="section-card">';
        html+='<div class="sec-header" onclick="openComparisonModal()"><i class="bi bi-arrows-angle-contract"></i> <span>Compare with Other Products</span><i class="bi bi-chevron-right"></i></div>';
        html+='<div class="sec-body expanded">';
        html+='<p class="text-muted small">Enter another barcode to compare side-by-side.</p>';
        html+='<div style="display:flex;gap:10px;max-width:400px"><input type="text" id="compareBarcodeInput" class="form-control" placeholder="Enter barcode to compare"><button class="btn btn-sm btn-primary" onclick="initiateComparison()"><i class="bi bi-arrow-right"></i></button></div>';
        html+='</div></div>';
        
        // ═══════════════════════════════════════════════
        // 7. GLOBAL REGULATORY DASHBOARD
        // ═══════════════════════════════════════════════
        html+='<div class="section-card">';
        html+='<div class="sec-header" onclick="openRegulatoryModal()"><i class="bi bi-globe2"></i> <span>Global Regulatory Comparison</span><i class="bi bi-chevron-right"></i></div>';
        html+='<div class="sec-body expanded">';
        html+='<div class="regulatory-dashboard" id="regulatoryDashboard">'+buildRegulatoryDashboard(regs)+'</div>';
        html+='</div></div>';
        
        // ═══════════════════════════════════════════════
        // 8. FOOD SAFETY NEWS
        // ═══════════════════════════════════════════════
        html+='<div class="section-card">';
        html+='<div class="sec-header" onclick="toggleSection(this)"><i class="bi bi-newspaper"></i> <span>Food Safety News</span><i class="bi bi-chevron-down sec-chevron"></i></div>';
        html+='<div class="sec-body expanded">';
        html+='<div class="news-categories" id="newsCategories">'+buildNewsCategories(news)+'</div>';
        html+='<div id="newsContent">'+newsHtml(news, 'all')+'</div>';
        html+='</div></div>';
        
        // ═══════════════════════════════════════════════
        // 9. PERSONALIZED HEALTH INSIGHTS
        // ═══════════════════════════════════════════════
        var healthInsights = buildHealthInsights(profile, nut, ings);
        if(healthInsights.length){
            html+='<div class="section-card">';
            html+='<div class="sec-header"><i class="bi bi-person-heart"></i> <span>Personalized Health Insights</span></div>';
            html+='<div class="sec-body expanded">';
            for(var n=0;n<healthInsights.length;n++){
                html+='<div class="health-insight"><div class="health-insight-title">'+esc(healthInsights[n].title)+'</div><div class="health-insight-desc">'+esc(healthInsights[n].desc)+'</div></div>';
            }
            html+='</div></div>';
        }
        
        // ═══════════════════════════════════════════════
        // 10. BETTER ALTERNATIVES
        // ═══════════════════════════════════════════════
        if(d.better_alternatives && d.better_alternatives.length){
            html+='<div class="section-card">';
            html+='<div class="sec-header"><i class="bi bi-arrow-left-right"></i> <span>Better Alternatives</span></div>';
            html+='<div class="sec-body expanded alternatives-grid" id="alternativesGrid">'+buildAlternativesCards(d.better_alternatives, score)+'</div>';
            html+='</div></div>';
        }else{
            // Show placeholder with find alternatives button
            html+='<div class="section-card">';
            html+='<div class="sec-header"><i class="bi bi-arrow-left-right"></i> <span>Better Alternatives</span></div>';
            html+='<div class="sec-body expanded alternatives-grid">';
            html+='<p class="text-muted small">Find healthier alternatives based on your preferences.</p>';
            html+='<button class="btn btn-outline-primary find-alternatives-btn" onclick="findAlternatives()"><i class="bi bi-search"></i> Find Alternatives</button>';
            html+='</div></div>';
        }
        
        // ═══════════════════════════════════════════════
        // 11. SCIENTIFIC REFERENCES
        // ═══════════════════════════════════════════════
        if(d.scientific_references && d.scientific_references.length){
            html+='<div class="section-card">';
            html+='<div class="sec-header" onclick="toggleSection(this)"><i class="bi bi-book"></i> <span>Scientific References</span><i class="bi bi-chevron-down sec-chevron"></i></div>';
            html+='<div class="sec-body expanded"><div class="reference-list">'+buildReferences(d.scientific_references)+'</div></div></div>';
        }
        
        // ── AI Chat CTA ──
        html+='<div class="chat-cta"><div><h3>🤖 Ask the AI</h3><p>Get personalized answers about this product.</p></div><a href="ai-chat.html" class="chat-btn"><i class="bi bi-chat-dots"></i> Ask AI</a></div>';
        
        c.innerHTML=html;
        c.style.display='block';
        log('Consumer UI rendered');
        
        try{localStorage.setItem('lps_ai_context',JSON.stringify({name:p.name,brand:p.brand,ingredients:ings,concern_score:score,allergens:alerts,nutrition:nut}));}catch(e){}
    }catch(e){log('Render error: '+e.message,'error');console.error(e);
        c.innerHTML='<div style="text-align:center;padding:60px 20px;"><i class="bi bi-exclamation-circle" style="font-size:3rem;color:#ef4444;"></i><h3 style="margin:16px 0 8px;">Analysis Available</h3><p style="color:#64748b;">'+esc((d&&d.product&&d.product.name)||'Product')+'</p></div>';c.style.display='block';}
}

// ── HELPER FUNCTIONS ──

function buildProductBadges(p, ingredients, nutrition){
    var badges=[];
    var nova=p.nova_group;
    if(nova==4||nova=='4'||nova==='Unknown'){
        badges.push('<div class="product-badge badge-ultra-processed"><i class="bi bi-lightning"></i><span>Ultra Processed</span></div>');
    }
    var sugar=parseFloat(nutrition.sugars_100g||0);
    if(sugar>15){
        badges.push('<div class="product-badge badge-high-sugar"><i class="bi bi-exclamation-triangle"></i><span>High Sugar</span></div>');
    }
    var salt=parseFloat(nutrition.salt_100g||0);
    if(salt>1.5){
        badges.push('<div class="product-badge badge-high-sodium"><i class="bi bi-exclamation-triangle"></i><span>High Sodium</span></div>');
    }
    var ingText=ingredients.join(' ').toLowerCase();
    var artChems=['e102','e110','e129','e133','e150d'];
    var hasArtificial=false;
    for(var i=0;i<artChems.length;i++){
        if(ingText.indexOf(artChems[i])>=0){hasArtificial=true;break;}
    }
    if(hasArtificial){
        badges.push('<div class="product-badge badge-artificial"><i class="bi bi-palette"></i><span>Artificial Colours</span></div>');
    }
    if(p.allergens && p.allergens.length){
        badges.push('<div class="product-badge badge-allergens"><i class="bi bi-exclamation-triangle"></i><span>Contains Allergens</span></div>');
    }
    return badges;
}

function getPurchaseDecision(score, level, factors, ingredients, nutrition, regulatory){
    var result={class:'recommended',text:'Recommended',icon:'bi-check-circle-fill',reasons:[],audience:[],summary:''};
    
    if(score<=30){
        result.class='recommended';
        result.text='Recommended';
        result.icon='bi-check-circle-fill';
    }else if(score<=50){
        result.class='occasional';
        result.text='Occasional Consumption';
        result.icon='bi-exclamation-circle-fill';
    }else if(score<=70){
        result.class='limit';
        result.text='Limit Consumption';
        result.icon='bi-exclamation-triangle-fill';
    }else{
        result.class='not-recommended';
        result.text='Not Recommended';
        result.icon='bi-x-circle-fill';
    }
    
    // Build reasons
    var sugar=nutrition.sugars_100g||0;
    var salt=nutrition.salt_100g||0;
    
    if(sugar>15){
        result.reasons.push({type:'negative',icon:'bi-x-circle',text:'Very high sugar ('+sugar+'g/100g)'});
        result.audience.push('People with diabetes');
        result.audience.push('Those limiting sugar intake');
    }else if(sugar>5&&sugar<=15){
        result.reasons.push({type:'warning',icon:'bi-exclamation-circle',text:'Moderate sugar ('+sugar+'g/100g)'});
    }
    
    if(salt>1.5){
        result.reasons.push({type:'negative',icon:'bi-x-circle',text:'High sodium ('+salt+'g/100g)'});
        result.audience.push('People with hypertension');
    }
    
    // Check for artificial additives
    var ingText=ingredients.join(' ').toLowerCase();
    var artCount=0;
    var artChems=['e102','e110','e129','e133','e150d'];
    for(var i=0;i<artChems.length;i++){
        if(ingText.indexOf(artChems[i])>=0)artCount++;
    }
    if(artCount>0){
        result.reasons.push({type:'negative',icon:'bi-x-circle',text:'Contains '+artCount+' artificial additives'});
        result.audience.push('Children (may affect attention)');
    }
    
    // Check for banned ingredients
    for(var j=0;j<regulatory.length;j++){
        var ss=regulatory[j].regulatory_status||[];
        for(var k=0;k<ss.length;k++){
            if(ss[k].status==='Banned'){
                result.reasons.push({type:'negative',icon:'bi-x-circle',text:regulatory[j].ingredient+' banned in '+ss[k].country});
                break;
            }
        }
    }
    
    // Build summary
    if(score<=30){
        result.summary='This product appears to be a reasonable choice based on available data. Always check labels for personal dietary needs.';
    }else if(score<=50){
        result.summary='This product is acceptable for occasional consumption. Consider portion control and healthier alternatives for regular use.';
    }else if(score<=70){
        result.summary='This product has significant concerns. Consider choosing alternatives with fewer additives and better nutrition.';
    }else{
        result.summary='This product has high concern levels. We recommend avoiding it and looking for healthier alternatives.';
    }
    
    // Remove duplicate audience items
    result.audience = [...new Set(result.audience)];
    
    return result;
}

function buildHealthDashboard(nutrition, ingredients, score){
    var sugar=parseFloat(nutrition.sugars_100g||0);
    var salt=parseFloat(nutrition.salt_100g||0);
    var satFat=parseFloat(nutrition['saturated-fat_100g']||0);
    var fiber=parseFloat(nutrition.fiber_100g||0);
    
    var sugarRisk = getRiskLevel(sugar, 5, 15, 25);
    var sodiumRisk = getRiskLevel(salt, 0.3, 1.5, 2);
    var fatQuality = getFateQuality(satFat);
    var additiveLoad = getAdditiveRisk(ingredients);
    
    return ''+
        '<div class="gauge-card">'+
            '<svg class="gauge-svg" viewBox="0 0 100 100">'+
                '<circle cx="50" cy="50" r="42" stroke="#e2e8f0" stroke-width="10" fill="none"></circle>'+
                '<circle cx="50" cy="50" r="42" stroke="#ef4444" stroke-width="10" fill="none" stroke-dasharray="264" stroke-dashoffset="'+getDashOffset(sugarRisk.val)+'" style="transform: rotate(-90deg); transition: stroke-dashoffset 1.5s;"></circle>'+
            '</svg>'+
            '<div class="gauge-label">Sugar Risk</div>'+
            '<div class="gauge-value">'+sugar+'g</div>'+
        '</div>'+
        '<div class="gauge-card">'+
            '<svg class="gauge-svg" viewBox="0 0 100 100">'+
                '<circle cx="50" cy="50" r="42" stroke="#e2e8f0" stroke-width="10" fill="none"></circle>'+
                '<circle cx="50" cy="50" r="42" stroke="'+getRiskColor(sodiumRisk.color)+'" stroke-width="10" fill="none" stroke-dasharray="264" stroke-dashoffset="'+getDashOffset(sodiumRisk.val)+'" style="transform: rotate(-90deg); transition: stroke-dashoffset 1.5s;"></circle>'+
            '</svg>'+
            '<div class="gauge-label">Sodium Risk</div>'+
            '<div class="gauge-value">'+salt+'g</div>'+
        '</div>'+
        '<div class="gauge-card">'+
            '<svg class="gauge-svg" viewBox="0 0 100 100">'+
                '<circle cx="50" cy="50" r="42" stroke="#e2e8f0" stroke-width="10" fill="none"></circle>'+
                '<circle cx="50" cy="50" r="42" stroke="'+fatQuality.color+'" stroke-width="10" fill="none" stroke-dasharray="264" stroke-dashoffset="'+getDashOffset(fatQuality.val)+'" style="transform: rotate(-90deg); transition: stroke-dashoffset 1.5s;"></circle>'+
            '</svg>'+
            '<div class="gauge-label">Fat Quality</div>'+
            '<div class="gauge-value">'+satFat+'g</div>'+
        '</div>'+
        '<div class="gauge-card">'+
            '<svg class="gauge-svg" viewBox="0 0 100 100">'+
                '<circle cx="50" cy="50" r="42" stroke="#e2e8f0" stroke-width="10" fill="none"></circle>'+
                '<circle cx="50" cy="50" r="42" stroke="'+getRiskColor(additiveLoad.color)+'" stroke-width="10" fill="none" stroke-dasharray="264" stroke-dashoffset="'+getDashOffset(additiveLoad.val)+'" style="transform: rotate(-90deg); transition: stroke-dashoffset 1.5s;"></circle>'+
            '</svg>'+
            '<div class="gauge-label">Additive Load</div>'+
            '<div class="gauge-value">'+additiveLoad.text+'</div>'+
        '</div>';
}

function getRiskLevel(val, low, med, high){
    var result={val:20,color:'green'};
    if(val>high){result.val=100;color='red';}
    else if(val>med){result.val=65;color='orange';}
    else if(val>low){result.val=40;color='yellow';}
    return result;
}

function getFateQuality(satFat){
    return {val: satFat>10?90:satFat>5?60:satFat>2?30:10, color: satFat>10?'#ef4444':satFat>5?'#f59e0b':'#10b981'};
}

function getAdditiveRisk(ingredients){
    var ingText=ingredients.join(' ').toLowerCase();
    var artChems=['e102','e110','e129','e133','e150d','e250','e320','e321','e951','e950'];
    var count=0;
    for(var i=0;i<artChems.length;i++){
        if(ingText.indexOf(artChems[i])>=0)count++;
    }
    return {val: Math.min(100, count*25), color: count>2?'red':count>0?'orange':'green', text: count+' additives'};
}

function getDashOffset(risk){
    var circumference=264;
    var offset=circumference-(circumference*risk/100);
    return offset;
}

function getRiskColor(color){
    var colors={green:'#10b981', yellow:'#f59e0b', orange:'#f97316', red:'#ef4444'};
    return colors[color]||'#64748b';
}

function getAdditiveInfoForIngredient(name){
    var additives=window.ar||[];
    for(var i=0;i<additives.length;i++){
        if(additives[i].name.toLowerCase()===name.toLowerCase()){
            return additives[i];
        }
    }
    return null;
}

function buildRelatedProductsSection(products, currentScore){
    var html='<div class="related-products-section">';
    html+='<div class="alternatives-header"><h3 class="alternatives-title">Customers Also Compare</h3><span class="product-badge badge-ultra-processed">'+products.length+' products</span></div>';
    html+='<div class="related-products-grid">';
    for(var i=0;i<Math.min(products.length,4);i++){
        var p=products[i];
        var pScore=p.health_score||50;
        var pClass='limit';
        if(pScore<=30)pClass='recommended';
        else if(pScore<=50)pClass='occasional';
        html+='<div class="related-product-card" onclick="scanRelatedProduct(\''+esc(p.barcode)+'\')">';
        if(pClass==='recommended' && currentScore>pScore){
            html+='<span class="healthiest-badge">Healthiest</span>';
        }
        html+='<div class="related-product-name">'+esc(p.name)+'</div>';
        html+='<div class="related-product-score '+('related-product-'+pClass)+'">'+pScore+'</div>';
        html+='<div style="font-size:10px;color:#94a3b8;margin-top:4px;">'+esc(p.brand)+'</div>';
        html+='</div>';
    }
    html+='</div></div>';
    return html;
}

function buildRegulatoryDashboard(regulatory){
    var countries=[
        {flag:'🇮🇳', name:'India (FSSAI)', key:'India (FSSAI)'},
        {flag:'🇺🇸', name:'USA (FDA)', key:'USA (FDA)'},
        {flag:'🇪🇺', name:'European Union', key:'European Union (EFSA)'},
        {flag:'🇬🇧', name:'UK', key:'United Kingdom'},
        {flag:'🇨🇦', name:'Canada', key:'Canada'},
        {flag:'🇦🇺', name:'Australia/NZ', key:'Australia / New Zealand'}
    ];
    var html='';
    for(var i=0;i<countries.length;i++){
        var c=countries[i];
        var status='—';
        var statusClass='allowed';
        for(var j=0;j<regulatory.length;j++){
            var ss=regulatory[j].regulatory_status||[];
            for(var k=0;k<ss.length;k++){
                if(ss[k].country.indexOf(c.key)>=0){
                    status=ss[k].status;
                    if(status==='Allowed')statusClass='allowed';
                    else if(status==='Restricted')statusClass='restricted';
                    else statusClass='banned';
                    break;
                }
            }
        }
        html+='<div class="country-reg-card" onclick="showCountryReg(\''+c.key+'\')"><div class="country-flag">'+c.flag+'</div><div class="country-name">'+c.name+'</div><div class="country-status '+statusClass+'">'+status+'</div></div>';
    }
    return html;
}

function buildNewsCategories(news){
    if(!news||!news.length)return '';
    var hasRecall=news.some(n=>n.category==='recall' || (n.title&&n.title.toLowerCase().includes('recall')));
    var hasReg=news.some(n=>n.category==='regulation' || (n.title&&n.title.toLowerCase().includes('banned')));
    var hasStudy=news.some(n=>n.category==='study');
    return ''+
        '<div class="news-category-tab active" data-cat="all" onclick="filterNews(\'all\')">All ('+news.length+')</div>'+
        '<div class="news-category-tab" data-cat="recalls" onclick="filterNews(\'recalls\')">Recalls</div>'+
        '<div class="news-category-tab" data-cat="regulatory" onclick="filterNews(\'regulatory\')">Regulatory</div>'+
        '<div class="news-category-tab" data-cat="studies" onclick="filterNews(\'studies\')">Studies</div>';
}

function buildAlternativesCards(alternatives, currentScore){
    var html='';
    for(var i=0;i<alternatives.length;i++){
        var alt=alternatives[i];
        html+='<div class="alternative-card">';
        html+='<h4 style="font-size:16px;font-weight:700;margin-bottom:4px;">'+esc(alt.name)+'</h4>';
        html+='<p style="font-size:12px;color:#64748b;margin-bottom:8px;">'+esc(alt.brand)+'</p>';
        html+='<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">';
        html+='<span style="font-size:24px;font-weight:800;color:#059669;">'+alt.health_score+'</span>';
        html+='<span style="font-size:12px;color:#64748b;">vs '+currentScore+' (current)</span>';
        html+='</div>';
        html+='<div class="alternative-reason"><strong>Why better:</strong> '+esc(alt.why_better)+'</div>';
        html+='</div>';
    }
    return html;
}

function buildHealthInsights(profile, nutrition, ingredients){
    var insights=[];
    if(!profile)return insights;
    
    var conditions=(profile.conditions||[]).map(c=>c.toLowerCase());
    var age=parseInt(profile.age||0);
    
    if(conditions.some(c=>c.includes('diabet'))){
        var sugar=parseFloat(nutrition.sugars_100g||0);
        var whoLimit=25; // WHO recommends <25g sugar per day
        var dailyPercent=(sugar/whoLimit)*100;
        insights.push({
            title:'Sugar Alert (Diabetes)',
            desc: sugar+'g sugar per 100g = '+Math.round(dailyPercent*4)+'% of WHO daily limit for a 100g serving'
        });
    }
    
    if(conditions.some(c=>c.includes('hypertension'))||conditions.some(c=>c.includes('blood pressure'))){
        var salt=parseFloat(nutrition.salt_100g||0);
        insights.push({
            title:'Sodium Alert (Hypertension)',
            desc: 'Contains '+salt+'g salt per 100g. Consider products with <0.3g for better blood pressure control.'
        });
    }
    
    if(age && age < 12){
        insights.push({
            title:'Child Safety Note',
            desc: 'Artificial colors in this product may affect attention in children. Consider dye-free alternatives.'
        });
    }
    
    if(conditions.some(c=>c.includes('pregnan'))){
        insights.push({
            title:'Pregnancy Caution',
            desc: 'Please consult your healthcare provider about artificial additives and caffeine content.'
        });
    }
    
    return insights;
}

function buildReferences(refs){
    var html='';
    for(var i=0;i<refs.length;i++){
        html+='<div class="reference-item"><i class="bi bi-link-45deg" style="color:#059669;font-size:16px;"></i> <a href="'+esc(refs[i].link)+'" target="_blank">'+esc(refs[i].title)+'</a></div>';
    }
    return html;
}

// ── Utility Functions ──

function toggleSection(h){
    var b=h.parentNode.querySelector('.sec-body');
    var ch=h.querySelector('.sec-chevron');
    if(!b)return;
    if(b.classList.contains('expanded')){
        b.classList.remove('expanded');
        if(ch)ch.className='bi bi-chevron-right sec-chevron';
    }else{
        b.classList.add('expanded');
        if(ch)ch.className='bi bi-chevron-down sec-chevron';
    }
}

function toggleIngredientCard(idx){
    var body=document.getElementById('ingBody'+idx);
    if(body)body.classList.toggle('expanded');
}

function starsFromScore(s){var n=Math.round((100-s)/20);n=Math.max(0,Math.min(5,n));var h='';for(var i=0;i<5;i++)h+=i<n?'⭐':'☆';return h;}

function nutritionTable(nut){
    var km={'energy-kcal_100g':['Calories','kcal'],'proteins_100g':['Protein','g'],'carbohydrates_100g':['Carbs','g'],'sugars_100g':['Sugars','g'],'fat_100g':['Fat','g'],'saturated-fat_100g':['Sat.Fat','g'],'fiber_100g':['Fiber','g'],'salt_100g':['Salt','g']};
    var n=nut;if(Array.isArray(n)){var o={};for(var i=0;i<n.length;i++){var k=(n[i].nutrientName||'').toLowerCase().replace(/ /g,'_')+'_100g';o[k]=n[i].amount;}n=o;}
    var rows='';var keys=Object.keys(km);
    for(var j=0;j<keys.length;j++){var key=keys[j];if(n[key]===undefined||n[key]===null)continue;var label=km[key][0],unit=km[key][1];var val=parseFloat(n[key]||0).toFixed(1);
    var cls='';if(key.indexOf('sugars')>=0&&val>15)cls='high';else if(key.indexOf('sugars')>=0&&val>5)cls='mod';else if(key.indexOf('salt')>=0&&val>1.5)cls='high';else if(key.indexOf('salt')>=0&&val>0.5)cls='mod';else if(key.indexOf('saturated')>=0&&val>5)cls='high';else if(key.indexOf('fiber')>=0&&val>3)cls='low';
    rows+='<div class="nut-row"><span class="nut-key">'+label+'</span><span class="nut-val '+cls+'">'+val+' '+unit+'</span></div>';}
    return rows?'<div class="nut-table">'+rows+'</div>':'<div class="note-empty">No nutrition data available.</div>';
}

function newsHtml(news, category){
    if(!news||!news.length)return'<div class="note-good"><i class="bi bi-shield-check"></i> No recent recalls or safety notices for this product.</div>';
    var filtered=news;
    if(category&&category!=='all'){
        filtered=news.filter(n=>{
            if(category==='recalls')return n.category==='recall'||(n.title&&n.title.toLowerCase().includes('recall'));
            if(category==='regulatory')return n.category==='regulation'||(n.title&&n.title.toLowerCase().includes('banned'));
            if(category==='studies')return n.category==='study';
            return true;
        });
    }
    if(!filtered.length)return'<div class="note-good"><i class="bi bi-shield-check"></i> No news in this category.</div>';
    var h='<div class="news-list">';
    for(var i=0;i<filtered.length;i++){var n=filtered[i];
    h+='<div class="news-item" onclick="window.open(\''+esc(n.link)+'\',\'_blank\')">';
    h+='<div class="ns-source">'+esc(n.source||'News')+'</div>';
    h+='<div class="ns-title">'+esc(n.title||'')+'</div>';
    h+='<div class="ns-date">'+esc(n.date||'')+'</div></div>';}
    h+='</div>';return h;
}

function genAI(p,nut,score,alerts){
    var n=p.name||'this product',b=p.brand||'',sv=score||50;
    var s=n;if(b)s+=' by '+b;s+='. ';
    if(sv<=20)s+='Low concern — reasonable choice. ';
    else if(sv<=50)s+='Moderate concern — check labels. ';
    else if(sv<=80)s+='High concern — consider alternatives. ';
    else s+='Very high concern — avoid if possible. ';
    if(alerts&&alerts.length)s+='Allergens: '+alerts.join(', ')+'. ';
    var sugar=nut.sugars_100g,salt=nut.salt_100g,fiber=nut.fiber_100g;
    if(sugar>15)s+='High sugar ('+sugar+'g/100g). ';
    else if(sugar>5)s+=sugar+'g sugar/100g. ';
    if(salt>1.5)s+='High sodium ('+salt+'g/100g). ';
    if(fiber>3)s+='Good fiber ('+fiber+'g/100g). ';
    s+='Always read labels and consult professionals.';
    return s;
}

// ── Global Functions ──

window.toggleIngredientCard=toggleIngredientCard;
window.filterNews=function(cat){
    var news=window.ad.news||[];
    document.getElementById('newsContent').innerHTML=newsHtml(news, cat);
    document.querySelectorAll('.news-category-tab').forEach(function(el){
        el.classList.toggle('active', el.dataset.cat===cat);
    });
};

window.scanRelatedProduct=function(barcode){
    localStorage.setItem('scannedBarcode', barcode);
    window.location.href='product-result.html';
};

window.initiateComparison=function(){
    var barcode=document.getElementById('compareBarcodeInput').value;
    if(barcode&&barcode.length>8){
        var current=window.ad.barcode;
        localStorage.setItem('comparisonProducts', JSON.stringify([current, barcode]));
        alert('Comparison will be shown after loading both products.');
    }
};

window.findAlternatives=function(){
    var barcode=window.ad.barcode;
    if(barcode){
        fetch(API+'/api/alternatives?barcode='+barcode).then(r=>r.json()).then(d=>{
            if(d.alternatives){
                window.ad.better_alternatives=d.alternatives;
                document.getElementById('alternativesGrid').innerHTML=buildAlternativesCards(d.alternatives, window.ad.concern_score.score);
            }
        }).catch(e=>console.error(e));
    }
};

// ── Legacy Functions Preserved ──

function calcCountryScore(regs,country){
    if(!regs||!regs.length)return 85;var total=0,count=0;
    for(var i=0;i<regs.length;i++){var ss=regs[i].regulatory_status||[];
    for(var j=0;j<ss.length;j++){if(ss[j].country&&ss[j].country.toLowerCase().indexOf(country.toLowerCase())>=0){
    if(ss[j].status==='Allowed')total+=100;else if(ss[j].status==='Restricted')total+=50;else if(ss[j].status==='Banned')total+=0;else total+=80;count++;}}}
    return count?Math.round(total/count):85;
}

function buildRegSummary(regs){
    if(!regs||!regs.length)return '<p class="text-muted" style="font-size:13px;">No verified regulatory information available.</p>';
    var h='';var totalAllowed=0,totalRestricted=0,totalBanned=0;
    for(var i=0;i<regs.length;i++){var ss=regs[i].regulatory_status||[];
    for(var j=0;j<ss.length;j++){if(ss[j].status==='Allowed')totalAllowed++;else if(ss[j].status==='Restricted')totalRestricted++;else if(ss[j].status==='Banned')totalBanned++;}}
    h+='<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px;">';
    h+='<div style="display:flex;align-items:center;gap:6px;background:rgba(16,185,129,0.1);padding:6px 12px;border-radius:50px;font-size:12px;font-weight:600;color:#047857;"><i class="bi bi-check-circle-fill"></i> '+totalAllowed+' Allowed</div>';
    h+='<div style="display:flex;align-items:center;gap:6px;background:rgba(245,158,11,0.1);padding:6px 12px;border-radius:50px;font-size:12px;font-weight:600;color:#b45309;"><i class="bi bi-exclamation-circle-fill"></i> '+totalRestricted+' Restricted</div>';
    h+='<div style="display:flex;align-items:center;gap:6px;background:rgba(239,68,68,0.1);padding:6px 12px;border-radius:50px;font-size:12px;font-weight:600;color:#b91c1c;"><i class="bi bi-x-circle-fill"></i> '+totalBanned+' Banned</div>';
    h+='</div>';
    if(totalBanned>0){h+='<div style="background:rgba(239,68,68,0.08);border-left:3px solid #ef4444;padding:12px;border-radius:8px;font-size:13px;color:#7f1d1d;">';for(var i=0;i<regs.length;i++){var ss=regs[i].regulatory_status||[];for(var j=0;j<ss.length;j++){if(ss[j].status==='Banned')h+='<div><strong>'+esc(regs[i].ingredient)+'</strong> banned in '+esc(ss[j].country)+'</div>';}}h+='</div>';}
    return h;
}

function showIngModal(idx){
    var data=window.ad;if(!data||!data.ingredient_explanations||!data.ingredient_explanations[idx])return;
    var ing=data.ingredient_explanations[idx];
    var body=document.getElementById('ingredientDetailModalBody');if(!body)return;
    var additive=(data.additive_regulatory_report||[]).find(function(a){return a.name.toLowerCase()===ing.name.toLowerCase()||(ing.simple_name&&a.name.toLowerCase()===ing.simple_name.toLowerCase())||ing.name.toLowerCase().includes(a.name.toLowerCase());});
    var h='';
    h+='<div class="ing-modal-header"><h4>'+esc(ing.name||'')+'</h4>';
    if(ing.simple_name)h+='<p class="text-muted" style="font-size:13px;">Also called: '+esc(ing.simple_name)+'</p>';
    if(ing.ins_e)h+='<p class="text-muted" style="font-size:13px;">Code: '+esc(ing.ins_e)+'</p>';
    h+='</div>';
    var badgeClass='#10B981';if(ing.category==='Preservative'||ing.category==='Colour')badgeClass='#ef4444';else if(ing.category==='Sweetener'||ing.category==='Flavour Enhancer')badgeClass='#d97706';
    if(ing.category)h+='<div style="display:inline-block;padding:4px 12px;border-radius:50px;font-size:11px;font-weight:600;background:'+badgeClass+'22;color:'+badgeClass+';margin-bottom:12px;">'+esc(ing.category)+'</div>';
    if(additive)h+='<div style="display:inline-block;padding:4px 12px;border-radius:50px;font-size:11px;font-weight:600;background:#6366f122;color:#4338ca;margin-left:6px;">INS '+esc(additive.ins_no)+'</div>';

    if(ing.purpose)h+='<div style="margin:12px 0;"><strong style="font-size:13px;">What it does:</strong><p style="font-size:13px;color:#64748b;margin:4px 0 0;">'+esc(ing.purpose)+'</p></div>';
    if(ing.description)h+='<div style="margin:12px 0;"><strong style="font-size:13px;">Health Information:</strong><p style="font-size:13px;color:#64748b;margin:4px 0 0;line-height:1.6;">'+esc(ing.description)+'</p></div>';

    if(additive){
        h+='<hr style="margin:16px 0;"><strong style="font-size:13px;">Country Regulations:</strong>';
        var keys=Object.keys(additive.countries);
        for(var k=0;k<keys.length;k++){var c=keys[k],ci=additive.countries[c];
        var sb='#10B981';if(ci.status==='Banned')sb='#ef4444';else if(ci.status==='Restricted')sb='#d97706';
        h+='<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #f1f5f9;font-size:13px;"><span>'+esc(c)+'</span><span style="color:'+sb+';font-weight:600;">'+esc(ci.status)+'</span></div>';}
    }
    if(!ing.purpose&&!ing.description&&!additive)h+='<p class="text-muted" style="font-size:13px;">No detailed information available for this ingredient.</p>';
    body.innerHTML=h;
    var modal=new bootstrap.Modal(document.getElementById('ingredientDetailModal'));modal.show();
}

function openCountryModal(){
    var tc=document.getElementById('foodRegulationsTabContent');
    if(tc)tc.innerHTML=buildRegSummary(window.ad.regulatory||[]);
    renderAdditiveReport();
    var me=document.getElementById('regulatoryBottomSheet');
    var m=bootstrap.Modal.getInstance(me);if(!m)m=new bootstrap.Modal(me);m.show();
}

window.exportPage=function(type){
    if(type==='print'){window.print();return;}
    var w=window.open('','_blank');
    var h='<html><head><title>Product Report - Label Padegha Sabh</title>';
    h+='<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">';
    h+='<style>body{font-family:"Outfit",sans-serif;padding:40px;color:#333;}h1{font-weight:800;}';
    h+='table{width:100%;border-collapse:collapse;font-size:13px;}td,th{padding:8px 12px;border-bottom:1px solid #eee;}';
    h+='.section{margin:20px 0;padding:15px;border:1px solid #ddd;border-radius:12px;}</style></head><body onload="window.print()">';
    h+='<h1>Product Intelligence Report</h1>';
    var d=window.ad;if(d&&d.product){h+='<p><strong>'+esc(d.product.name)+'</strong> by '+esc(d.product.brand)+'</p>';h+='<p>Concern Score: '+(d.concern_score?d.concern_score.score:'N/A')+'/100</p>';}
    h+='<hr>';if(d&&d.ingredients){h+='<div class="section"><h3>Ingredients</h3><p>'+esc(d.ingredients.join(', '))+'</p></div>';}
    if(d&&d.allergens&&d.allergens.length){h+='<div class="section"><h3>Allergens</h3>';for(var a=0;a<d.allergens.length;a++)h+=esc(d.allergens[a].allergen)+', ';h+='</div>';}
    h+='<hr><p style="font-size:12px;color:#999;">Label Padegha Sabh</p></body></html>';
    w.document.write(h);w.document.close();
};