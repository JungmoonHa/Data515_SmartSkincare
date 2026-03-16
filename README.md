# Smart Skincare: Personalized Skincare Products Recommendation Tool

[![CI](https://github.com/JungmoonHa/Data515_SmartSkincare/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/JungmoonHa/Data515_SmartSkincare/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/JungmoonHa/Data515_SmartSkincare/graph/badge.svg)](https://codecov.io/gh/JungmoonHa/Data515_SmartSkincare)

Smart Skincare is an interactive recommendation tool that helps users find skincare products suited to their skin type. By analyzing ingredient compatibility across thousands of products, it provides personalized recommendations based on individual skin concerns.

## Project Type
Interactive Data Analysis & Recommendation Tool

## Team Members
- DH Lee
- Emily Tran
- Jungmoon Ha
- Wonjoon Hwang

## Table of Contents
- [Key Features](#key-features)
- [Our Goal](#our-goal)
- [Data Sources](#data-sources)
- [Software Dependencies and License Information](#software-dependencies-and-license-information)
- [Directory Summary](#directory-summary)
- [Tutorial For Using the Tool](#tutorial-for-using-the-tool)

## Key Features

**Ingredient-Based Recommendations**
Analyzes thousands of skincare ingredients against a curated knowledge base to match products to a user's skin profile (dry, oily, sensitive, combination, pigmentation, wrinkle concerns).

**Interactive Web Dashboard**
Users input their skin type and concerns through a clean web interface and receive ranked product recommendations with explanations of key beneficial and cautionary ingredients.

**Review-Blended Scoring**
Recommendation scores incorporate real user review ratings, balancing ingredient compatibility with real-world product performance.

**Product Categorization**
Products are automatically categorized (moisturizer, serum, cleanser, sunscreen, etc.) to help users navigate results.

## Our Goal
To give users a data-driven tool that goes beyond generic "for dry skin" labels — surfacing products whose actual ingredient profiles match individual skin chemistry, backed by community review data.

## Data Sources

**1. Cosmetic Ingredients Dataset**
~1,500 skincare products including ingredient lists, product categories, and labeled skin types.
- https://www.kaggle.com/code/kingabzpro/cosmetics-ingredients
- https://www.kaggle.com/datasets/autumndyer/skincare-products-and-ingredients

**2. Sephora Skincare Products Dataset**
3,000+ Sephora products with ingredient lists, ratings, and product URLs.
- https://www.kaggle.com/code/natashamessier/sephora-data-analysis/input

**3. Paula's Choice Ingredient Dictionary**
Ingredient ratings (good/poor/etc.) used to score and penalize problematic ingredients during recommendation.

## Software Dependencies and License Information

The project is built using Python 3.10+. The frontend is a static web app (HTML/CSS/JS) served via Python's built-in HTTP server — no additional packages required to run the web app. The complete list of dependencies can be found in `requirements.txt`. This project is licensed under the MIT License.

## Directory Summary

```
.
├── data/                        # Raw and processed product/ingredient data
├── docs/                        # Project documents and notebooks
├── Examples/
│   └── example_images/          # Example screenshots of the tool
└── smart_skincare/
    ├── cache/                   # Prebuilt JSON caches (ingredient maps, KNN index, review stats)
    ├── scripts/                 # Preprocessing and pipeline scripts (one-time use)
    ├── src/                     # Core source code (recommendation engine)
    ├── static/                  # Frontend assets (JS, CSS, icons)
    │   └── Emily_Image_Icons/
    ├── templates/               # HTML pages (index, skin test, recommendations)
    └── tests/                   # Unit tests
```

## Tutorial For Using the Tool

### Step 1: Clone the Repository

```bash
git clone https://github.com/JungmoonHa/Data515_SmartSkincare.git
cd Data515_SmartSkincare
```

### Step 2: Run the Web App

```bash
python3 -m http.server 8000
```

Then open [http://localhost:8000/smart_skincare/templates/index.html](http://localhost:8000/smart_skincare/templates/index.html) in your browser.

### Step 3: (Optional) Run Tests

Install dependencies first:

```bash
pip install -r requirements.txt
```

Then run:

```bash
pytest src/smart_skincare -v
```

## Video Demonstration

Access the demo here for a detailed understanding of the flow of our project. [Video Download](docs/Demo_Recording.mov)
