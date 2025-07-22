import requests
import json
import csv
import time
from datetime import datetime

def is_hiring_relevant(project):
    """
    Check if grant has optimal timing for hiring:
    - 1.5+ years remaining OR started within last year
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
        
        if years_remaining >= 1.5:
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
            "activity_codes": gold_tier_types,
            "exclude_subprojects": True
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
    print("Filter: 1.5+ years remaining OR started within last year")
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
            if years_remaining >= 1.5:
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

def update_readme(stats):
    """Update README with current statistics"""
    if not stats:
        return
    
    # Read current README
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print("README.md not found, skipping update")
        return
    
    # Update statistics section
    new_stats = f"""## Key Statistics
- **{stats['total_grants']} hiring-relevant grants** identified
- **${stats['total_funding']:,.0f} total funding** (${stats['avg_funding']:,.0f} average per grant)
- **{stats['r01_count']} R01 grants** ({stats['r01_count']/stats['total_grants']*100:.0f}%) - independent researchers with hiring authority
- **{stats['center_grants']} P30/P50 center grants** - highest computational hiring probability"""
    
    # Replace the existing Key Statistics section
    import re
    pattern = r"## Key Statistics.*?(?=## [A-Z]|\Z)"
    if re.search(pattern, content, re.DOTALL):
        updated_content = re.sub(pattern, new_stats + "\n\n", content, flags=re.DOTALL)
    else:
        # If section doesn't exist, add it before Target Recommendations
        target_pattern = r"(## Target Recommendations)"
        updated_content = re.sub(target_pattern, f"{new_stats}\n\n\\1", content)
    
    # Write back to file
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated_content)
    
    print("✓ Updated README.md with current statistics")

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
        return {}
    
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
    
    # Return stats for README update
    return {
        "total_grants": len(projects),
        "total_funding": total_funding,
        "avg_funding": total_funding / len(projects) if len(projects) > 0 else 0,
        "top_grant_types": sorted(activity_counts.items(), key=lambda x: x[1], reverse=True)[:3],
        "r01_count": activity_counts.get("R01", 0),
        "center_grants": activity_counts.get("P30", 0) + activity_counts.get("P50", 0)
    }

def deduplicate_by_project_title(projects):
    """Keep only the most recent fiscal year for each unique project title"""
    print(f"\nDeduplicating {len(projects)} projects by title...")
    
    title_groups = {}
    for project in projects:
        title = project.get("PROJECT_TITLE", "").strip()
        if not title:
            continue
        
        fy = project.get("FY", "").strip()
        if not fy or not fy.isdigit():
            continue
        
        fy_int = int(fy)
        
        if title not in title_groups:
            title_groups[title] = []
        title_groups[title].append((fy_int, project))
    
    deduplicated = []
    duplicates_removed = 0
    
    for title, project_list in title_groups.items():
        project_list.sort(key=lambda x: x[0], reverse=True)
        most_recent_fy, most_recent_project = project_list[0]
        deduplicated.append(most_recent_project)
        
        if len(project_list) > 1:
            duplicates_removed += len(project_list) - 1
            pi = most_recent_project.get("PI_NAMEs", "").split(';')[0].strip()
            activity = most_recent_project.get("ACTIVITY", "")
            print(f"  Kept FY{most_recent_fy} for: {activity} - {pi[:25]} - {title[:50]}...")
    
    print(f"Removed {duplicates_removed} duplicates, kept {len(deduplicated)} unique projects")
    return deduplicated

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
    
    deduplicated_processed = deduplicate_by_project_title(processed)
    save_to_csv(deduplicated_processed, "mayo_grants.csv")
    stats = analyze_results(deduplicated_processed)
    update_readme(stats)
    
    print(f"\nSuccess! {len(deduplicated_processed)} hiring-relevant grants saved to mayo_grants.csv")

if __name__ == "__main__":
    main() 