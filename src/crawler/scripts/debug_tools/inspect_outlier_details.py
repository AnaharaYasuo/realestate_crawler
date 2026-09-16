import setup_env
from django.apps import apps
from package.models.evaluation import PropertyEvaluation

urls = [
    "https://toushi.homes.co.jp/bukkendetail/index/4588311/",
    "https://www.athome.co.jp/kodate/6976263844/",
    "https://www.rehouse.co.jp/buy/kodate/bkdetail/FL2BPA03/",
    "https://toushi.homes.co.jp/bukkendetail/index/4587196/",
    "https://www.rehouse.co.jp/buy/mansion/bkdetail/FX6BDA13/",
    "https://www.stepon.co.jp/mansion/detail_947A3126/",
    "https://www.athome.co.jp/mansion/1131476708/",
    "https://www.rehouse.co.jp/buy/mansion/bkdetail/FSJARA0A/"
]

app_config = apps.get_app_config("package")

for url in urls:
    print(f"\n==================================================")
    print(f"URL: {url}")
    ev = PropertyEvaluation.objects.filter(property_url=url).first()
    for model in app_config.get_models():
        field_names = [f.name for f in model._meta.get_fields()]
        url_field = "pageUrl" if "pageUrl" in field_names else ("url" if "url" in field_names else None)
        if not url_field:
            continue
        obj = model.objects.filter(**{url_field: url}).first()
        if obj:
            print(f"Model: {model.__name__} | EvPred: {ev.first_stage_predicted_price if ev else None}")
            for f in model._meta.get_fields():
                if f.name in ["id", "pageUrl", "url", "imageUrls", "images"]:
                    continue
                v = getattr(obj, f.name, None)
                if v is not None and str(v).strip() != "":
                    print(f"  {f.name}: {v}")
            break
