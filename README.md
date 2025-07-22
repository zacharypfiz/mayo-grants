# Mayo Clinic Rochester Grant Analysis

## Overview
This project identifies optimal grant opportunities at Mayo Clinic Rochester for computational scientists and software engineers.

## Files
- `mayo_grants.csv` - Hiring-relevant Gold Tier grants
- `fetch_grants.py` - Script to fetch fresh data from NIH API
- `grant_types.txt` - Analysis of all grant types at Mayo Rochester
- `readme.md` - This documentation

## Usage
```bash
# Fetch latest grants data
uv run --with requests fetch_grants.py
```

## Grant Priority Tiers

### Gold Tier (Focus Here)
**Core Research:** R01, R35, R37, RF1  
**New PIs:** R00  
**Large Programs & Centers:** P01, P30, P50, U01, U19, U54, UF1, RC2, UH3  
**Resource & Data Hubs:** U24, U10, UL1 (excellent for engineers)

### Silver Tier (Investigate if Relevant)
**Exploratory Research:** R03, R21, R33, R61, UG3  
**Special Cases:** P20, R18, R56

### Bronze Tier (Avoid)
**Fellowships:** F30, F31, F32, F99  
**Career Development:** All K grants  
**Training:** T32, TL1  
**Non-Staff Funding:** R13, R25, R34, R38, R50, S10

## Timing Filters
The script automatically filters for grants with optimal hiring timing:
- **1.5+ years remaining** (plenty of budget left)
- **Started within last year** (fresh funding, likely hiring)

## Key Statistics
- **197 hiring-relevant grants** identified
- **$132,788,130 total funding** ($674,051 average per grant)
- **156 R01 grants** (79%) - independent researchers with hiring authority
- **7 P30/P50 center grants** - highest computational hiring probability

## Target Recommendations
1. **P30/P50 centers** - Often have computational cores
2. **Recent R01s** - Fresh budgets, new projects
3. **U24/U01 cooperatives** - Need technical infrastructure
4. **Search by keywords** in PROJECT_TITLE and PHR fields