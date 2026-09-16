# -*- coding: utf-8 -*-
import os
import glob

api_dir = "/app/src/crawler/package/api"
files = glob.glob(os.path.join(api_dir, "*.py"))

for f in files:
    filename = os.path.basename(f)
    if filename in ["api.py", "middleware.py", "registry.py"]:
        continue
        
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()
        
    if "DETAIL_PARARELL_LIMIT = 1" in content:
        new_limit = 1 if filename == "athome.py" else 3
        new_content = content.replace("DETAIL_PARARELL_LIMIT = 1", f"DETAIL_PARARELL_LIMIT = {new_limit}")
        with open(f, "w", encoding="utf-8") as file:
            file.write(new_content)
        print(f"Updated {filename}: DETAIL_PARARELL_LIMIT = {new_limit}")
