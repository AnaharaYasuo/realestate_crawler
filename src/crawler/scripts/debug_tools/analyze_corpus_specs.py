# -*- coding: utf-8 -*-
import json
from collections import Counter

with open('src/crawler/package/ml/logs/corpus_40_live_properties.json', encoding='utf-8') as f:
    corpus = json.load(f)

print(f"Total properties in corpus: {len(corpus)}")
types = Counter(f"{p['site']}_{p['property_type']}" for p in corpus)
print("Distribution:", dict(types))

# 1. specs キーの頻度
spec_keys = Counter()
# 2. features (特徴タグ) の頻度
feature_tags = Counter()
# 3. nuxt スニペットの頻度
nuxt_terms = Counter()

for p in corpus:
    for k in p['specs'].keys():
        spec_keys[k] += 1
    for f in p['features']:
        feature_tags[f] += 1
    for n in p.get('nuxt_extracted_snippets', []):
        nuxt_terms[n] += 1

print("\n--- TOP SPEC KEYS ACROSS ALL PROPERTIES ---")
for k, count in spec_keys.most_common(50):
    print(f"  {k}: {count}")

print("\n--- TOP FEATURE TAGS (EQUIPMENT & MERITS) ---")
for f, count in feature_tags.most_common(40):
    print(f"  {f}: {count}")

print("\n--- TOP NUXT KEYWORD SNIPPETS (SPEC & FACILITY) ---")
for n, count in nuxt_terms.most_common(40):
    print(f"  {n}: {count}")
