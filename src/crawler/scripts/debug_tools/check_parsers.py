import os

parser_dir = "/app/src/crawler/package/parser"
files = [f for f in os.listdir(parser_dir) if f.endswith(".py") and f != "__init__.py" and f != "baseParser.py"]

results = []
for file in sorted(files):
    path = os.path.join(parser_dir, file)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check if file has assignments or references to kenpei, youseki, railwayWalkMinute1Str / railwayWalkMinute1
    has_kenpei = "kenpei" in content
    has_youseki = "youseki" in content
    has_walk_str = "railwayWalkMinute1Str" in content or "railwayWalkMinute1" in content
    
    results.append({
        "file": file,
        "kenpei": has_kenpei,
        "youseki": has_youseki,
        "walk": has_walk_str
    })

print(f"{'Parser File':<25} | {'Kenpei':<6} | {'Youseki':<7} | {'Walk':<5}")
print("-" * 55)
for r in results:
    print(f"{r['file']:<25} | {str(r['kenpei']):<6} | {str(r['youseki']):<7} | {str(r['walk']):<5}")
