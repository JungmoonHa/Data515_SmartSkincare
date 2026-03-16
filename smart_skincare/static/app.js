/* Pagination variables */
let currentPage = 1;
const productsPerPage = 25;
let allRecommendations = [];

/* Get results from skin test */
const params = new URLSearchParams(window.location.search);
const name = params.get("firstName") || "";
const age = params.get("age") || "";
const skinType = params.get("skinType") || "";

const concernsParam = params.get("concerns") || "";
let concerns = concernsParam ? concernsParam.split(",") : [];

/* Remove Dry & Oily concerns automatically */
concerns = concerns.filter(c => c !== "Dry" && c !== "Oily");

const profileSummary = document.getElementById("profileSummary");

/* Show user profile summary */
function updateProfileSummary(){
let parts = [];

if(name) parts.push(name);
if(age) parts.push(`Age ${age}`);
if(skinType) parts.push(skinType);
if(concerns.length) parts.push(`Concerns: ${concerns.join(", ")}`);

profileSummary.textContent = parts.join(" • ");
}
updateProfileSummary();

/* Load dataset */
async function loadProducts(){
try {
const response = await fetch("../../data/recommendations.csv");
if (!response.ok) {
console.warn("recommendations.csv not found (run recommendation script locally to generate)");
return [];
}
const csv = await response.text();
const parsed = Papa.parse(csv,{
header:true,
skipEmptyLines:true
});
const products = (parsed.data || []).map(row => ({
brand: row["brand"],
name: row["name"],
score: parseFloat(row["score"]) || 0,
beneficial: row["beneficial_ingredients"],
caution: row["caution_ingredients"],
ingredients: row["ingredients_parsed"],
image: row["image_url"],
category: row["category"]
}));
return products;
} catch (e) {
console.warn("Could not load recommendations.csv:", e);
return [];
}
}

/* Filter by category */
function filterByCategory(products){
const categorySelect = document.getElementById("categoryFilter");
if(!categorySelect) return products;

const category = categorySelect.value;
if(category === "all") return products;

return products.filter(p => p.category === category);
}

/* Recommendation logic */
function recommendProducts(products){
let filtered = [...products];

if(concerns.includes("Sensitive")){
filtered = filtered.filter(p =>
!p.ingredients?.toLowerCase().includes("fragrance")
);
}

if(concerns.includes("Pigmentation")){
filtered = filtered.filter(p =>
p.ingredients?.toLowerCase().includes("vitamin c") ||
p.ingredients?.toLowerCase().includes("niacinamide") ||
p.ingredients?.toLowerCase().includes("alpha arbutin")
);
}

if(concerns.includes("Wrinkles")){
filtered = filtered.filter(p =>
p.ingredients?.toLowerCase().includes("retinol") ||
p.ingredients?.toLowerCase().includes("peptide") ||
p.ingredients?.toLowerCase().includes("vitamin c")
);
}

if(filtered.length === 0){
console.log("No matches found. Using fallback products.");
filtered = products.slice(0,200);
}

filtered.sort((a,b)=>b.score - a.score);
return filtered;
}

/* Render products */
function renderProducts(products){
const grid = document.querySelector(".recommendations-grid");
const topProduct = document.getElementById("topProduct");
const pagination = document.getElementById("pagination");

grid.innerHTML = "";
topProduct.innerHTML = "";

if(products.length === 0) {
grid.innerHTML = "<p class=\"empty-message\">No recommendation data yet. Run the recommendation script locally to generate <code>data/recommendations.csv</code>, then commit and redeploy.</p>";
return;
}

const start = (currentPage - 1) * productsPerPage;
const end = start + productsPerPage;
const pageProducts = products.slice(start,end);

/* Top match */
const best = pageProducts[0];

topProduct.innerHTML = `
<div class="product-card">
<div class="product-top">
<div class="score-badge">${best.score.toFixed(1)}</div>
<div class="product-image">
<img src="${best.image}" alt="${best.name}"
onerror="this.src='images/default-product.png'">
</div>
</div>

<div class="product-info">
<div class="brand-name">${best.brand}</div>
<h4 class="product-title">${best.name}</h4>

<div class="ingredient-tags">
<button class="tag good toggle-btn">⭐ Beneficial Ingredients</button>
<div class="ingredient-desc hidden">
${best.beneficial || "No beneficial ingredient data"}
</div>

<button class="tag caution toggle-btn">⚠️ Caution Ingredients</button>
<div class="ingredient-desc hidden">
${best.caution ? best.caution.split(",").map(i => `<div>• ${i.trim()}</div>`).join("") : "No caution ingredient data"}
</div>
</div>
</div>
</div>`;

/* Other products */
pageProducts.slice(1).forEach(p=>{
grid.innerHTML += `
<div class="product-card">
<div class="product-top">
<div class="score-badge">${p.score.toFixed(1)}</div>
<div class="product-image">
<img src="${p.image}" alt="${p.name}"
onerror="this.src='images/default-product.png'">
</div>
</div>

<div class="product-info">
<div class="brand-name">${p.brand}</div>
<h4 class="product-title">${p.name}</h4>

<div class="ingredient-tags">
<button class="tag good toggle-btn">⭐ Beneficial Ingredients</button>
<div class="ingredient-desc hidden">
${p.beneficial || "No beneficial ingredient data"}
</div>

<button class="tag caution toggle-btn">⚠️ Caution Ingredients</button>
<div class="ingredient-desc hidden">
${p.caution ? p.caution.split(",").map(i => `<div>• ${i.trim()}</div>`).join("") : "No caution ingredient data"}
</div>
</div>
</div>
</div>`;
});

/* Pagination */
pagination.innerHTML = `
<button id="prevPage">⬅ Previous</button>
<span>Page ${currentPage}</span>
<button id="nextPage">Next ➡</button>
`;

document.getElementById("prevPage").onclick = ()=>{
if(currentPage > 1){
currentPage--;
renderProducts(allRecommendations);
}
};

document.getElementById("nextPage").onclick = ()=>{
if(currentPage * productsPerPage < allRecommendations.length){
currentPage++;
renderProducts(allRecommendations);
}
};
}

/* Toggle ingredient descriptions */
document.addEventListener("click",function(e){
if(e.target.classList.contains("toggle-btn")){
const desc = e.target.nextElementSibling;
desc.classList.toggle("hidden");
}
});

/* Run recommendation system */
async function init(){
if(!skinType) return;

let products = await loadProducts();
console.log("Loaded products:", products.length);

products = filterByCategory(products);
allRecommendations = recommendProducts(products);

console.log("Recommendations:", allRecommendations.length);

currentPage = 1;
renderProducts(allRecommendations);
}

init();

/* Re-run when category changes */
const categoryFilter = document.getElementById("categoryFilter");

if(categoryFilter){
categoryFilter.addEventListener("change",init);
}
