import sys
sys.path.insert(0, '.')
import setup_env
from django.apps import apps
from decimal import Decimal

models = [m for m in apps.get_models() if m._meta.app_label == 'package']

target_fields = [
    'tochikenri', 'rights', 'kenpei', 'youseki', 'youtoChiiki', 'hikiwatashi', 'genkyo',
    'douroHaba', 'douroMuki', 'douroKubun', 'setsumen', 'torihiki',
    'chikunengetsuStr', 'chikunengetsu', 'kanrihi', 'syuzenTsumitate',
    'soukosu', 'kaisu', 'kouzou', 'balconyMenseki', 'tyusyajo',
    'madori', 'senyuMenseki', 'tatemonoMenseki', 'tochiMenseki'
]

results = {}
for model in sorted(models, key=lambda m: m.__name__):
    name = model.__name__
    if name in ('PropertyEvaluation', 'PropertyEvaluationHistory', 'PropertyTypeCorrection', 'CrawlProgress', 'RecrawlQueue'):
        continue
    try:
        qs = list(model.objects.all().order_by('-id')[:100])
    except Exception as e:
        continue
    total = len(qs)
    if total == 0:
        continue
    
    missing_fields = {}
    for f in target_fields:
        if not hasattr(model, f):
            continue
        empty = 0
        for obj in qs:
            v = getattr(obj, f, None)
            if v is None or v == '' or v == Decimal(0) or v == 0:
                empty += 1
        pct = (empty / total) * 100
        if pct >= 40:
            missing_fields[f] = f"{pct:.0f}%"
    if missing_fields:
        results[name] = {'total': total, 'missing': missing_fields}

print("=== ALL MODELS MISSING SCAN RESULTS ===")
for k, v in results.items():
    print(f"{k} (n={v['total']}): {v['missing']}")
