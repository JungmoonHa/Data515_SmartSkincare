# Functional Specification

## Background
The goal of this project is to build a web-based skincare recommendation and ingredient analysis platform that helps users find products tailored to their specific skin type.

The system uses a structured skincare product database that includes:
- Ingredient information
- Product details
- Brand data
- Labels indicating which skin types each product is suitable for

### Project Goals
- Provide personalized skincare product recommendations  
- Enable ingredient transparency and detailed analysis  
- Support users in making informed skincare decisions  
- Allow users to save and compare preferred products  

---

## User Profiles

### 1) General Skincare Consumer
- Basic understanding of skincare  
- Knows their skin type (dry, oily, combination, sensitive, etc.)  
- No programming knowledge  
- Wants personalized product recommendations  

### 2) Skincare Enthusiast
- Moderate knowledge of ingredients  
- Interested in ingredient-level transparency  
- Wants to analyze and compare products  

### 3) Developer
- Maintains the software  
- Ensures the data sources are updated  

---

## Data Sources

---

## Use Cases

## Use Case 1: Personalized Product Recommendation
**User:** General Skincare Consumer  
**Objective:** Find skincare products suitable for a specific skin type and review detailed ingredient information before making a decision.

### Use-Case Flow
1. **System:** Prompts the user to select their skin type.  
2. **User:** Selects a skin type (e.g., dry, oily, combination, sensitive).  
3. **System:** Filters the product database and displays recommended products suitable for the selected skin type.  
4. **User:** Applies additional filters such as:
   - Product category  
   - Brand  
   - Price range  
   - Ingredient exclusions  
5. **System:** Updates and displays filtered product results dynamically.  
6. **User:** Selects a specific product.  
7. **System:** Retrieves and displays detailed product information, including:
   - Full ingredient list  
   - Ingredient functions  
   - Skin-type compatibility explanation  
8. **User:** Likes or saves the product.  
9. **System:** Adds the selected product to the user's saved items list.  

---

## Use Case 2: Ingredient Transparency & Product Comparison
**User:** Skincare Enthusiast  
**Objective:** Help the user understand ingredients and compare products before choosing one.  
**Before starting:** The user has at least one product open or selected.

### Use-Case Flow
1. **User:** Searches for a product by name or browses by category.  
2. **System:** Shows matching products.  
3. **User:** Clicks a product to view details.  
4. **System:** Shows ingredient info, including:
   - Full (cleaned) ingredient list  
   - Ingredients that are good for the user’s skin type  
   - Ingredients that may be irritating or not recommended  
   - What each key ingredient does (function/benefit)  
5. **User:** Clicks **Compare** and selects a second product.  
6. **System:** Displays a side-by-side comparison with:
   - Shared ingredients (overlap)  
   - Ingredients unique to each product  
   - Skin-type suitability for each product  
   - Rating or recommendation score (if available)  
7. **User:** Reviews the comparison.  
8. **System:** Explains why one product is recommended (based on the ingredient scoring rules/model).  

---

## Component Specification
