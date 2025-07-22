import requests
import json
import csv
import time
from datetime import datetime

def is_hiring_relevant(project):
    """
    Check if grant has optimal timing for hiring:
    - 2+ years remaining OR started within last year
    """
    try:
        today = datetime.now()
        project_start_str = project.get("project_start_date", "")
        project_end_str = project.get("project_end_date", "")
        
        if not project_end_str:
            fy = project.get("fiscal_year", "")
            return fy in [2024, 2025]
        
        project_end = datetime.strptime(project_end_str[:10], '%Y-%m-%d')
        years_remaining = (project_end - today).days / 365.25
        
        if years_remaining >= 2.0:
            return True
        
        if project_start_str:
            project_start = datetime.strptime(project_start_str[:10], '%Y-%m-%d')
            years_since_start = (today - project_start).days / 365.25
            if years_since_start <= 1.0:
                return True
        
        return False
        
    except (ValueError, TypeError):
        fy = project.get("fiscal_year", "")
        return fy in [2024, 2025]

def fetch_mayo_grants():
    """Fetch Mayo Rochester grants from NIH API"""
    url = "https://api.reporter.nih.gov/v2/projects/search"
    
    fields = [
        "PrincipalInvestigators", "OrgName", "OrgCity", "OrgState",
        "ProjectTitle", "PublicHealthRelevance", "SpendingCategories",
        "FiscalYear", "SupportYear", "ProjectStartDate", "ProjectEndDate",
        "AwardAmount", "ActivityCode", "ApplicationTypeCode", "ProjectNum"
    ]
    
    gold_tier_types = [
        "R01", "R35", "R37", "RF1", "R00",
        "P01", "P30", "P50", "U01", "U19", "U54", "UF1", "RC2", "UH3",
        "U24", "U10", "UL1"
    ]
    
    payload = {
        "criteria": {
            "org_names_exact_match": ["MAYO CLINIC ROCHESTER"],
            "include_active_projects": True,
            "fiscal_years": [2022, 2023, 2024, 2025],
            "activity_codes": gold_tier_types
        },
        "include_fields": fields,
        "offset": 0,
        "limit": 500,
        "sort_field": "FiscalYear",
        "sort_order": "desc"
    }
    
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    all_projects = []
    offset = 0
    
    print("Fetching Mayo Rochester grants...")
    print(f"Grant types: {', '.join(gold_tier_types)}")
    print("Filter: 2+ years remaining OR started within last year")
    print("=" * 60)
    
    while True:
        payload["offset"] = offset
        
        try:
            print(f"Requesting projects {offset + 1} to {offset + 500}...")
            time.sleep(1)
            
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            data = response.json()
            
            if "results" not in data:
                break
                
            projects = data["results"]
            if not projects:
                break
            
            all_projects.extend(projects)
            print(f"✓ Fetched {len(projects)} projects (Total: {len(all_projects)})")
            
            if len(projects) < 500:
                break
            offset += 500
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            break
    
    return all_projects

def process_projects(projects):
    """Process and filter projects for hiring relevance"""
    processed = []
    filtered_count = 0
    
    print(f"\nApplying timing filters to {len(projects)} projects...")
    
    for project in projects:
        if is_hiring_relevant(project):
            processed_project = {
                "PI_NAMEs": extract_pi_names(project.get("principal_investigators", [])),
                "ORG_NAME": project.get("organization", {}).get("name", ""),
                "ORG_CITY": project.get("organization", {}).get("city", ""),
                "ORG_STATE": project.get("organization", {}).get("state", ""),
                "PROJECT_TITLE": project.get("project_title", ""),
                "PHR": project.get("phr", ""),
                "NIH_SPENDING_CATS": extract_spending_categories(project.get("spending_categories", [])),
                "FY": str(project.get("fiscal_year", "")).strip(),
                "SUPPORT_YEAR": str(project.get("support_year", "")).strip(),
                "PROJECT_START": project.get("project_start_date", ""),
                "PROJECT_END": project.get("project_end_date", ""),
                "TOTAL_COST": str(project.get("award_amount", "")).strip(),
                "ACTIVITY": project.get("activity_code", ""),
                "APPLICATION_TYPE": str(project.get("application_type_code", "")).strip(),
                "FULL_PROJECT_NUM": project.get("full_project_num", "")
            }
            processed.append(processed_project)
            filtered_count += 1
            
            if filtered_count <= 5:
                timing = get_timing_reason(project)
                pi = processed_project["PI_NAMEs"].split(';')[0].strip()
                activity = processed_project["ACTIVITY"]
                title = processed_project["PROJECT_TITLE"][:40]
                print(f"✓ {activity} - {timing}: {pi[:20]} - {title}...")
    
    print(f"\nFilter results: {filtered_count}/{len(projects)} grants kept ({filtered_count/len(projects)*100:.1f}%)")
    return processed

def get_timing_reason(project):
    """Get reason why project passed timing filter"""
    try:
        today = datetime.now()
        project_end_str = project.get("project_end_date", "")
        project_start_str = project.get("project_start_date", "")
        
        if project_end_str:
            project_end = datetime.strptime(project_end_str[:10], '%Y-%m-%d')
            years_remaining = (project_end - today).days / 365.25
            if years_remaining >= 2.0:
                return f"{years_remaining:.1f}y remaining"
        
        if project_start_str:
            project_start = datetime.strptime(project_start_str[:10], '%Y-%m-%d')
            years_since_start = (today - project_start).days / 365.25
            if years_since_start <= 1.0:
                return f"Started {years_since_start:.1f}y ago"
        
        return "Recent FY"
    except (ValueError, TypeError):
        return "Recent FY"

def extract_pi_names(pi_list):
    """Extract PI names from API response"""
    if not pi_list:
        return ""
    
    names = []
    for pi in pi_list:
        first = pi.get("first_name", "").strip()
        last = pi.get("last_name", "").strip()
        if first or last:
            names.append(f"{first} {last}".strip())
    
    return "; ".join(names)

def extract_spending_categories(categories):
    """Extract spending categories from API response"""
    if not categories:
        return ""
    
    cat_names = []
    for cat in categories:
        if isinstance(cat, dict):
            name = cat.get("name", "").strip()
            if name:
                cat_names.append(name)
        elif isinstance(cat, str):
            cat_names.append(cat.strip())
    
    return "; ".join(cat_names)

def save_to_csv(projects, filename):
    """Save projects to CSV file"""
    if not projects:
        print("No projects to save")
        return
    
    fieldnames = [
        "PI_NAMEs", "ORG_NAME", "ORG_CITY", "ORG_STATE",
        "PROJECT_TITLE", "PHR", "NIH_SPENDING_CATS",
        "FY", "SUPPORT_YEAR", "PROJECT_START", "PROJECT_END",
        "TOTAL_COST", "ACTIVITY", "APPLICATION_TYPE", "FULL_PROJECT_NUM"
    ]
    
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(projects)
    
    print(f"✓ Saved {len(projects)} projects to {filename}")

def analyze_results(projects):
    """Analyze and display grant statistics"""
    if not projects:
        return
    
    print(f"\nGrant Analysis:")
    print("=" * 40)
    print(f"Total hiring-relevant grants: {len(projects)}")
    
    activity_counts = {}
    fiscal_years = {}
    total_funding = 0
    
    for project in projects:
        activity = project.get("ACTIVITY", "").strip()
        fy = project.get("FY", "").strip()
        cost_str = project.get("TOTAL_COST", "").strip()
        
        if activity:
            activity_counts[activity] = activity_counts.get(activity, 0) + 1
        if fy:
            fiscal_years[fy] = fiscal_years.get(fy, 0) + 1
        
        if cost_str and cost_str.replace('.', '').replace(',', '').isdigit():
            total_funding += float(cost_str.replace(',', ''))
    
    print(f"\nGrant Types:")
    for activity, count in sorted(activity_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {activity:4s}: {count:3d} grants")
    
    print(f"\nFiscal Years:")
    for fy, count in sorted(fiscal_years.items(), reverse=True):
        print(f"  FY{fy}: {count:3d} grants")
    
    if total_funding > 0:
        print(f"\nFunding: ${total_funding:,.0f} total, ${total_funding/len(projects):,.0f} average")

def main():
    """Main function"""
    print("Mayo Rochester - Hiring-Relevant Gold Tier Grants")
    print("=" * 50)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    projects = fetch_mayo_grants()
    if not projects:
        print("No projects found")
        return
    
    processed = process_projects(projects)
    if not processed:
        print("No projects passed filters")
        return
    
    save_to_csv(processed, "mayo_grants.csv")
    analyze_results(processed)
    
    print(f"\nSuccess! {len(processed)} hiring-relevant grants saved to mayo_grants.csv")

if __name__ == "__main__":
    main() 