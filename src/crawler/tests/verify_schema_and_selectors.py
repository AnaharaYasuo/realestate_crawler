import os
import re
import sys
from bs4 import BeautifulSoup
import argparse

# Configuration
DOCS_DIR = os.environ.get("DOCS_DIR", "docs")
SCHEMA_FILE = os.path.join(DOCS_DIR, "detailed_design/database_schema.md")
SAMPLES_DIR = os.path.join(DOCS_DIR, "requirements/site_samples")
STRUCTURES_DIR = os.path.join(DOCS_DIR, "requirements/site_structures")

def parse_schema_coverage():
    """Checks if all sites and types are listed in database_schema.md"""
    print("\n[1] Checking Schema Completeness...")
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Simple check for headers
    required_sections = [
        "Sumifu", "Mitsui", "Tokyu", "Nomura", "Misawa"
    ]
    missing = []
    for site in required_sections:
        if site not in content:
            missing.append(site)
    
    if missing:
        print(f"FAILED: Missing schema definitions for: {missing}")
    else:
        print("PASS: All companies mentioned in schema.")

    # Check for investment types
    if "Investment" not in content:
         print("WARNING: 'Investment' section might be missing or named differently.")

def check_samples_existence():
    """Checks if site_samples contains expected files based on schema/targets"""
    print("\n[2] Checking Site Samples...")
    
    # Derived from targets we care about
    expected_files = [
        "sumifu_mansion_mock.html",
        "sumifu_investment_mansion_mock.html",
        "mitsui_mansion_mock.html",
        "mitsui_investment_mansion_mock.html",
        # "tokyu_mansion_mock.html", # Optional if we didn't fetch yet
        # "nomura_mansion_mock.html",
        # "misawa_mansion_mock.html"
    ]
    
    missing = []
    for f in expected_files:
        if not os.path.exists(os.path.join(SAMPLES_DIR, f)):
            missing.append(f)
            
    if missing:
        print(f"WARNING: Missing samples: {missing}")
    else:
        print("PASS: All key samples present.")

def verify_selectors_against_samples():
    """Parses site structure docs to extract selectors and verifies them against sample HTMLs"""
    print("\n[3] Verifying Selectors against Samples...")

    # Mapping samples to structure files (Simplified for this task)
    # Refine this mapping based on exact filenames
    mapping = {
        "site_structure_mitsui_rehouse.md": "mitsui_mansion_mock.html",
        "site_structure_mitsui_investment.md": "mitsui_investment_mansion_mock.html",
        "site_structure_sumifu.md": "sumifu_mansion_mock.html",
        "site_structure_sumifu_investment.md": "sumifu_investment_mansion_mock.html",
    }
    
    # Regex to find selectors in markdown tables or lists
    # Looking for pattern: `selector` or code block
    # This is a heuristic check.
    
    for struct_file, sample_file in mapping.items():
        struct_path = os.path.join(STRUCTURES_DIR, struct_file)
        sample_path = os.path.join(SAMPLES_DIR, sample_file)
        
        if not os.path.exists(struct_path):
            print(f"SKIP: Structure file not found: {struct_file}")
            continue
        if not os.path.exists(sample_path):
            print(f"SKIP: Sample file not found: {sample_file}")
            continue
            
        print(f"--- Verifying {struct_file} -> {sample_file} ---")
        
        with open(struct_path, "r", encoding="utf-8") as f:
            struct_content = f.read()
            
        with open(sample_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            
        # Extract potential selectors (simple backtick extraction for now)
        # We assume selectors are inside backticks `...` and likely contain classes/ids/tags
        potential_selectors = re.findall(r'`([^`]+)`', struct_content)
        
        valid_selectors = []
        for s in potential_selectors:
            # Filter unlikely selectors (e.g. database fields, plain text)
            if re.match(r'^[a-zA-Z0-9_]+$', s): continue # Skip single words likely field names
            if "TODO" in s: continue
            valid_selectors.append(s)
            
        print(f"Found {len(valid_selectors)} potential selectors to test.")
        
        passed = 0
        failed = 0
        
        for sel in valid_selectors:
            try:
                # Attempt to select
                elements = soup.select(sel)
                if elements:
                    passed += 1
                    # print(f"  OK: {sel} -> Found {len(elements)} items")
                else:
                    failed += 1
                    print(f"  FAIL: {sel} -> No elements found")
            except Exception as e:
                # Selection failed (invalid syntax or not a selector)
                # print(f"  SKIP: {sel} (Invalid syntax)")
                pass
                
        print(f"Result: {passed} Passed, {failed} Failed (or not found in sample)")

if __name__ == "__main__":
    parse_schema_coverage()
    check_samples_existence()
    verify_selectors_against_samples()
