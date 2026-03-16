# Smart Skincare: Personalized Skincare Products Recommendation Tool

[![CI](https://github.com/JungmoonHa/Data515_SmartSkincare/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/JungmoonHa/Data515_SmartSkincare/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/JungmoonHa/Data515_SmartSkincare/graph/badge.svg)](https://codecov.io/gh/JungmoonHa/Data515_SmartSkincare)

Smart Skincare is an interactive recommendation tool that helps users find skincare products suited to their skin type. By analyzing ingredient compatibility across thousands of products, it provides personalized recommendations based on individual skin concerns.

**Try the app (deployed):** [https://jungmoonha.github.io/Data515_SmartSkincare/smart_skincare/templates/index.html](https://jungmoonha.github.io/Data515_SmartSkincare/smart_skincare/templates/index.html)

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
- [Documentation](#documentation)
- [Directory Summary](#directory-summary)
- [How to Use the App](#how-to-use-the-app)
- [Setting up the Virtual Environment](#setting-up-the-virtual-environment)
- [Continuous Integration](#continuous-integration)
- [Deploy on GitHub Pages](#deploy-on-github-pages)

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

The project is built using Python 3.10+. Dependencies are listed in `requirements.txt` and `pyproject.toml`. This project is licensed under the MIT License.

## Documentation

- **[Functional Specification](docs/functional_specification.md)** — project goals, user profiles, and functional requirements.
- **[Component Specification](docs/Component%20Specification.md)** — design and component interfaces.
- **[Technology Review](docs/technology_review/TECHNOLOGY_REVIEW.md)** — technology choices and review.

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

## How to Use the App

**Use the app in your browser (no install):** [https://jungmoonha.github.io/Data515_SmartSkincare/smart_skincare/templates/index.html](https://jungmoonha.github.io/Data515_SmartSkincare/smart_skincare/templates/index.html)

A step-by-step example of using the package (skin test → recommendations) is in the [Examples](Examples/README.md) folder.

## Setting up the Virtual Environment

We use a virtual environment so the team and reviewers can install the same dependencies and run tests and lint the same way.

1. **Clone the repository**
   ```bash
   git clone https://github.com/JungmoonHa/Data515_SmartSkincare.git
   cd Data515_SmartSkincare
   ```

2. **Create and activate a virtual environment**
   - **macOS/Linux:** `python3 -m venv .venv` then `source .venv/bin/activate`
   - **Windows (Command Prompt):** `python -m venv .venv` then `.venv\Scripts\activate.bat`
   - **Windows (PowerShell):** `python -m venv .venv` then `.venv\Scripts\Activate.ps1`

3. **Install the project and dev dependencies**
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

4. **Run tests**
   ```bash
   pytest smart_skincare/tests -v
   ```

5. **Run lint (Ruff)**
   ```bash
   ruff check smart_skincare/src
   ```

## Continuous Integration

CI runs on every push and pull request to `main` (see [Actions](https://github.com/JungmoonHa/Data515_SmartSkincare/actions/workflows/ci.yml)). It runs **Ruff** (lint), **pytest** (tests), and **pytest-cov** (coverage). Coverage is uploaded to **Codecov** when `CODECOV_TOKEN` is set. The badges at the top of this README report CI status and code coverage.

### Setting up Codecov (one-time)

1. Sign in at [codecov.io](https://codecov.io) with GitHub and add the repo **JungmoonHa/Data515_SmartSkincare**.
2. Copy the repository token from Codecov.
3. In the GitHub repo: **Settings** → **Secrets and variables** → **Actions** → **New repository secret** → Name: `CODECOV_TOKEN`, Value: (paste token).
4. After the next CI run, the coverage badge will update.

## Deploy on GitHub Pages

You can host the web app for free on **GitHub Pages** so anyone can use it from the browser.

### 1. Enable GitHub Pages

1. Open your repo on GitHub: `https://github.com/JungmoonHa/Data515_SmartSkincare`
2. Go to **Settings** → **Pages**
3. Under **Build and deployment** → **Source**, choose **Deploy from a branch**
4. Under **Branch**, select `main` and folder **/ (root)**, then **Save**

### 2. Open the deployed site

After a minute or two, the site will be available at:

**`https://jungmoonha.github.io/Data515_SmartSkincare/`**

The root URL may redirect to the app. Open the app directly at:

**`https://jungmoonha.github.io/Data515_SmartSkincare/smart_skincare/templates/index.html`**

### 3. (Optional) Generate full recommendation data

The repo includes a minimal `data/recommendations.csv` (header only) so the recommendation page loads. To show real product recommendations on the deployed site:

1. Clone the repo, install dependencies, and ensure cache files exist under `smart_skincare/cache/`.
2. From the project root, run:
   ```bash
   PYTHONPATH=smart_skincare/src python smart_skincare/src/recommend_mvp.py
   ```
   This writes `data/recommendations.csv`.
3. Commit the updated `data/recommendations.csv` and push. The next Pages deploy will show the full recommendations.

## Video Demonstration

Access the demo here for a detailed understanding of the flow of our project. [Video Download](docs/Demo_Recording.mov)
