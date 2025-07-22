import requests
import json
import csv
import time
from datetime import datetime

def fetch_abstract_by_title(project_title, pi_name="", fiscal_year=""):
    """Fetch project abstract using NIH Reporter API by searching project title"""
    url = "https://api.reporter.nih.gov/v2/projects/search"
    
    fields = [
        "ProjectTitle", "AbstractText", "PrincipalInvestigators", 
        "FiscalYear", "ProjectNum", "ActivityCode", "OrgName"
    ]
    
    # Try multiple search strategies based on API documentation
    search_strategies = []
    
    # Strategy 1: Advanced text search on project title
    if project_title.strip():
        search_strategies.append({
            "criteria": {
                "advanced_text_search": {
                    "operator": "and",
                    "search_field": "projecttitle",
                    "search_text": project_title.strip()
                },
                "org_names": ["MAYO"],
                "include_active_projects": True
            },
            "description": "Advanced text search on title + Mayo"
        })
    
    # Strategy 2: Search by PI name with wildcard (API supports this)
    if pi_name:
        # Handle multiple PIs separated by semicolon
        pi_names_list = []
        for name in pi_name.split(";"):
            name = name.strip()
            if name:
                name_parts = name.split()
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = name_parts[-1]
                    pi_names_list.append({"first_name": first_name, "last_name": last_name})
                elif len(name_parts) == 1:
                    pi_names_list.append({"any_name": name_parts[0]})
        
        if pi_names_list:
            strategy_criteria = {
                "pi_names": pi_names_list,
                "org_names": ["MAYO"],
                "include_active_projects": True
            }
            
            if fiscal_year and fiscal_year.isdigit():
                strategy_criteria["fiscal_years"] = [int(fiscal_year)]
            
            search_strategies.append({
                "criteria": strategy_criteria,
                "description": f"PI names + Mayo Clinic"
            })
    
    # Strategy 3: Text search with key terms from title
    if project_title.strip():
        # Extract key terms (longer words, remove common words)
        title_words = [word for word in project_title.split() 
                      if len(word) > 3 and word.lower() not in 
                      ['with', 'using', 'from', 'for', 'and', 'the', 'that', 'this', 'will', 'been', 'have']]
        
        if len(title_words) >= 2:
            key_terms = " ".join(title_words[:5])  # Use first 5 key terms
            search_strategies.append({
                "criteria": {
                    "advanced_text_search": {
                        "operator": "and",
                        "search_field": "projecttitle,abstracttext",
                        "search_text": key_terms
                    },
                    "org_names": ["MAYO"],
                    "include_active_projects": True
                },
                "description": f"Key terms search: {key_terms[:50]}..."
            })
    
    # Strategy 4: Organization + fiscal year + activity codes (for recent grants)
    if fiscal_year and fiscal_year.isdigit():
        search_strategies.append({
            "criteria": {
                "org_names": ["MAYO CLINIC ROCHESTER"],
                "fiscal_years": [int(fiscal_year)],
                "activity_codes": ["R01", "R37", "R35", "U01", "U24", "P01", "P30", "P50"],
                "include_active_projects": True
            },
            "description": f"Mayo + FY{fiscal_year} + activity codes"
        })
    
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    
    for strategy in search_strategies:
        payload = {
            "criteria": strategy["criteria"],
            "include_fields": fields,
            "offset": 0,
            "limit": 100,
            "use_relevance": True  # Use relevance scoring for better matches
        }
        
        try:
            time.sleep(0.5)  # Respect rate limiting
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            data = response.json()
            
            if "results" not in data or not data["results"]:
                continue
            
            projects = data["results"]
            
            # Look for best match using improved scoring
            best_match = None
            best_score = 0.0
            
            for project in projects:
                project_pi_names = []
                for pi in project.get("principal_investigators", []):
                    first = pi.get("first_name", "").strip()
                    last = pi.get("last_name", "").strip()
                    if first or last:
                        project_pi_names.append(f"{first} {last}".strip())
                
                project_pi_str = "; ".join(project_pi_names)
                project_title_from_api = project.get("project_title", "")
                
                # Calculate match score
                title_similarity = calculate_title_similarity(project_title, project_title_from_api)
                pi_match_score = calculate_pi_match_score(pi_name, project_pi_str)
                
                # Combined score with weights
                combined_score = (title_similarity * 0.7) + (pi_match_score * 0.3)
                
                if combined_score > best_score and combined_score > 0.3:  # Minimum threshold
                    best_score = combined_score
                    best_match = {
                        "title": project_title_from_api,
                        "abstract": project.get("abstract_text", ""),
                        "pi_names": project_pi_str,
                        "fiscal_year": project.get("fiscal_year", ""),
                        "project_num": project.get("full_project_num", ""),
                        "activity": project.get("activity_code", ""),
                        "org_name": project.get("organization", {}).get("name", ""),
                        "score": combined_score
                    }
            
            if best_match:
                print(f"    Found via {strategy['description']} (score: {best_match['score']:.2f})")
                return best_match
            
        except requests.exceptions.RequestException as e:
            print(f"    API request failed with {strategy['description']}: {e}")
            continue
    
    return None

def calculate_title_similarity(title1, title2):
    """Calculate similarity between two titles with improved algorithm"""
    if not title1 or not title2:
        return 0.0
    
    # Normalize titles
    title1_norm = title1.lower().strip()
    title2_norm = title2.lower().strip()
    
    # Exact match gets highest score
    if title1_norm == title2_norm:
        return 1.0
    
    # Word-based similarity
    words1 = set(title1_norm.split())
    words2 = set(title2_norm.split())
    
    # Remove common words
    common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 
                   'using', 'from', 'that', 'this', 'will', 'been', 'have', 'are', 'is', 'was', 'were'}
    words1 = words1 - common_words
    words2 = words2 - common_words
    
    if not words1 or not words2:
        return 0.0
    
    # Jaccard similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    jaccard = intersection / union if union > 0 else 0.0
    
    # Bonus for longer matches
    if intersection >= 3:
        jaccard += 0.1
    
    return min(jaccard, 1.0)

def calculate_pi_match_score(pi_name, project_pi_str):
    """Calculate PI name match score"""
    if not pi_name or not project_pi_str:
        return 0.0
    
    pi_parts = [name.strip().upper() for name in pi_name.split(";")]
    project_pi_upper = project_pi_str.upper()
    
    max_score = 0.0
    
    for pi_part in pi_parts:
        pi_words = pi_part.split()
        if not pi_words:
            continue
            
        # Check for last name match (most reliable)
        last_name = pi_words[-1]
        if len(last_name) > 2 and last_name in project_pi_upper:
            score = 0.8
            
            # Bonus for first name match too
            if len(pi_words) > 1:
                first_name = pi_words[0]
                if len(first_name) > 1 and first_name in project_pi_upper:
                    score = 1.0
            
            max_score = max(max_score, score)
    
    return max_score

def check_pi_match(pi_name, project_pi_str):
    """Check if PI names match (legacy function for compatibility)"""
    return calculate_pi_match_score(pi_name, project_pi_str) > 0.5

def read_targets_csv(filename):
    """Read targets from CSV file"""
    targets = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                targets.append({
                    "pi_names": row.get("PI_NAMEs", "").strip(),
                    "project_title": row.get("PROJECT_TITLE", "").strip(),
                    "fiscal_year": row.get("FY", "").strip(),
                    "activity": row.get("ACTIVITY", "").strip()
                })
    except FileNotFoundError:
        print(f"Error: {filename} not found")
        return []
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return []
    
    return targets

def save_abstracts_to_csv(abstracts_data, filename):
    """Save abstracts data to CSV file"""
    if not abstracts_data:
        print("No abstracts to save")
        return
    
    fieldnames = [
        "PI_NAMEs", "PROJECT_TITLE", "FISCAL_YEAR", "ACTIVITY", 
        "PROJECT_NUM", "ORG_NAME", "ABSTRACT", "FETCH_STATUS"
    ]
    
    with open(filename, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(abstracts_data)
    
    print(f"✓ Saved {len(abstracts_data)} project abstracts to {filename}")

def main():
    """Main function"""
    print("NIH Grant Abstract Fetcher")
    print("=" * 40)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    targets = read_targets_csv("targets.csv")
    if not targets:
        print("No targets found to process")
        return
    
    print(f"Found {len(targets)} projects to fetch abstracts for...")
    print()
    
    abstracts_data = []
    successful = 0
    failed = 0
    
    for i, target in enumerate(targets, 1):
        pi_names = target["pi_names"]
        title = target["project_title"]
        fy = target["fiscal_year"]
        activity = target["activity"]
        
        print(f"[{i}/{len(targets)}] Fetching: {title[:60]}...")
        
        result = fetch_abstract_by_title(title, pi_names, fy)
        
        if result and result.get("abstract"):
            abstracts_data.append({
                "PI_NAMEs": result["pi_names"],
                "PROJECT_TITLE": result["title"],
                "FISCAL_YEAR": result["fiscal_year"],
                "ACTIVITY": result["activity"],
                "PROJECT_NUM": result["project_num"],
                "ORG_NAME": result["org_name"],
                "ABSTRACT": result["abstract"],
                "FETCH_STATUS": "SUCCESS"
            })
            print(f"  ✓ Found abstract ({len(result['abstract'])} characters)")
            successful += 1
        else:
            abstracts_data.append({
                "PI_NAMEs": pi_names,
                "PROJECT_TITLE": title,
                "FISCAL_YEAR": fy,
                "ACTIVITY": activity,
                "PROJECT_NUM": "",
                "ORG_NAME": "",
                "ABSTRACT": "",
                "FETCH_STATUS": "NOT_FOUND"
            })
            print(f"  ✗ Abstract not found")
            failed += 1
    
    print()
    print(f"Summary: {successful} successful, {failed} failed")
    
    save_abstracts_to_csv(abstracts_data, "project_abstracts.csv")
    
    if successful > 0:
        print(f"\nSuccess! Abstracts saved to project_abstracts.csv")
        print("You can now review the abstracts to better understand each project's computational needs.")

if __name__ == "__main__":
    main() 