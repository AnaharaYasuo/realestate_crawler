# -*- coding: utf-8 -*-
"""
中心値から著しく外れた物件（極端な残差外れ値）の高速要因調査スクリプト
"""
import os
import sys
import json
import numpy as np
import pandas as pd

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_crawler_dir = os.path.dirname(_scripts_dir)
sys.path.insert(0, _crawler_dir)

import realestateSettings
realestateSettings.configure()

from django.apps import apps
from package.models.evaluation import PropertyEvaluation

COMPANIES = [
    "mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1", "mizuho",
    "odakyu", "afr", "sekisui", "daiwa", "totate", "athome", "homes", "seibu",
    "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim", "sumirin", "keio"
]

def investigate():
    print("1. Indexing (url, price) across models...", flush=True)
    app_config = apps.get_app_config("package")
    url_to_price = {}
    url_to_model = {}
    
    for model in app_config.get_models():
        model_name = model.__name__.lower()
        if not any(model_name.startswith(c) for c in COMPANIES):
            continue
        field_names = [f.name for f in model._meta.get_fields()]
        if "pageUrl" in field_names:
            url_field = "pageUrl"
        elif "url" in field_names:
            url_field = "url"
        else:
            url_field = None
        if not url_field or "price" not in field_names:
            continue
        try:
            for row in model.objects.filter(price__isnull=False, price__gt=0).values(url_field, "price"):
                u = row.get(url_field)
                p = row.get("price")
                if u and p:
                    try:
                        p_val = float(p) / 10000.0
                        if p_val > 0:
                            url_to_price[u] = p_val
                            url_to_model[u] = model
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass
            
    print(f"Indexed {len(url_to_price):,} property prices.", flush=True)
    
    print("2. Matching with PropertyEvaluation...", flush=True)
    candidates = []
    eval_qs = PropertyEvaluation.objects.filter(first_stage_predicted_price__isnull=False).only(
        "property_url", "company", "property_type", "first_stage_predicted_price"
    )
    for ev in eval_qs:
        act_p = url_to_price.get(ev.property_url)
        if not act_p:
            continue
        pred_p = float(ev.first_stage_predicted_price)
        if pred_p <= 0 or act_p <= 0:
            continue
        ratio = pred_p / act_p
        candidates.append({
            "url": ev.property_url,
            "company": ev.company,
            "property_type": ev.property_type,
            "actual_price": act_p,
            "pred_price": pred_p,
            "diff": pred_p - act_p,
            "ratio": ratio,
            "log_diff": np.log(pred_p) - np.log(act_p)
        })
        
    df = pd.DataFrame(candidates)
    print(f"Total matched: {len(df):,}", flush=True)
    
    top_over = df.sort_values(by="ratio", ascending=False).head(15)
    top_under = df.sort_values(by="ratio", ascending=True).head(15)
    
    def fetch_full_details(url):
        model = url_to_model.get(url)
        if not model:
            return {}
        field_names = [f.name for f in model._meta.get_fields()]
        if "pageUrl" in field_names:
            url_field = "pageUrl"
        elif "url" in field_names:
            url_field = "url"
        else:
            url_field = None
        try:
            item = model.objects.filter(**{url_field: url}).first()
            if not item:
                return {}
            return {
                "model": model.__name__,
                "address": getattr(item, "address", "") or getattr(item, "location", ""),
                "layout": getattr(item, "layout", "") or getattr(item, "madori", ""),
                "area": getattr(item, "area", None) or getattr(item, "senyuMenseki", None) or getattr(item, "tochiMenseki", None) or getattr(item, "tatemonoMenseki", None),
                "building_area": getattr(item, "tatemonoMenseki", None) or getattr(item, "nobeyukaMenseki", None),
                "land_area": getattr(item, "tochiMenseki", None),
                "built_year": getattr(item, "builtYear", None) or getattr(item, "chikunen", None) or getattr(item, "buildDate", None),
                "structure": getattr(item, "structure", "") or getattr(item, "kouzou", ""),
                "rights": getattr(item, "rights", "") or getattr(item, "kenri", ""),
                "saikenchiku": getattr(item, "saikenchiku", "") or getattr(item, "saikenchikuFuka", ""),
                "remarks": getattr(item, "remarks", "") or getattr(item, "bikou", "") or getattr(item, "description", "") or getattr(item, "setsumei", ""),
                "bcr": getattr(item, "kenpeiRitsu", None),
                "far": getattr(item, "yousekiRitsu", None),
                "traffic": getattr(item, "traffic", "") or getattr(item, "koutsu", "")
            }
        except Exception:
            return {}
            
    print("\n================ TOP 15 OVERPREDICTED (PRED >> ACTUAL) ================", flush=True)
    for rank, (_, row) in enumerate(top_over.iterrows(), 1):
        inf = fetch_full_details(row["url"])
        print(f"\n[OVER #{rank}] Ratio: {row['ratio']:.2f}x (Pred: {row['pred_price']:,.0f}万 vs Act: {row['actual_price']:,.0f}万, Diff: +{row['diff']:,.0f}万)", flush=True)
        print(f"  Type: {row['property_type']} ({inf.get('model', 'N/A')}) | URL: {row['url']}", flush=True)
        print(f"  Addr: {inf.get('address')} | Layout: {inf.get('layout')} | Built: {inf.get('built_year')} | Struct: {inf.get('structure')}", flush=True)
        print(f"  Area: {inf.get('area')} | BldgArea: {inf.get('building_area')} | LandArea: {inf.get('land_area')}", flush=True)
        print(f"  Rights: {inf.get('rights')} | Saikenchiku: {inf.get('saikenchiku')}", flush=True)
        print(f"  BCR: {inf.get('bcr')}% | FAR: {inf.get('far')}% | Traffic: {inf.get('traffic')}", flush=True)
        remarks_snip = (inf.get('remarks', '')[:140] + "...") if inf.get('remarks') else "None"
        print(f"  Remarks: {remarks_snip}", flush=True)
        
    print("\n================ TOP 15 UNDERPREDICTED (PRED << ACTUAL) ================", flush=True)
    for rank, (_, row) in enumerate(top_under.iterrows(), 1):
        inf = fetch_full_details(row["url"])
        print(f"\n[UNDER #{rank}] Ratio: {row['ratio']:.2f}x (Pred: {row['pred_price']:,.0f}万 vs Act: {row['actual_price']:,.0f}万, Diff: {row['diff']:,.0f}万)", flush=True)
        print(f"  Type: {row['property_type']} ({inf.get('model', 'N/A')}) | URL: {row['url']}", flush=True)
        print(f"  Addr: {inf.get('address')} | Layout: {inf.get('layout')} | Built: {inf.get('built_year')} | Struct: {inf.get('structure')}", flush=True)
        print(f"  Area: {inf.get('area')} | BldgArea: {inf.get('building_area')} | LandArea: {inf.get('land_area')}", flush=True)
        print(f"  Rights: {inf.get('rights')} | Saikenchiku: {inf.get('saikenchiku')}", flush=True)
        print(f"  BCR: {inf.get('bcr')}% | FAR: {inf.get('far')}% | Traffic: {inf.get('traffic')}", flush=True)
        remarks_snip = (inf.get('remarks', '')[:140] + "...") if inf.get('remarks') else "None"
        print(f"  Remarks: {remarks_snip}", flush=True)

if __name__ == "__main__":
    investigate()
