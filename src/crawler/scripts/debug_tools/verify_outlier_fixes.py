import setup_env
from django.apps import apps
from package.ml.predict import bulk_predict_first_stage

urls = [
    # 1万円・格安物件
    "https://toushi.homes.co.jp/bukkendetail/index/4588311/",
    "https://www.athome.co.jp/kodate/6976263844/",
    # 超高級豪邸
    "https://www.rehouse.co.jp/buy/kodate/bkdetail/FL2BPA03/",
    "https://toushi.homes.co.jp/bukkendetail/index/4587196/",
    # 超高級マンション
    "https://www.rehouse.co.jp/buy/mansion/bkdetail/FX6BDA13/",
    "https://www.stepon.co.jp/mansion/detail_947A3126/",
    # 格安リゾート・築古
    "https://www.athome.co.jp/mansion/1131476708/",
    "https://www.rehouse.co.jp/buy/mansion/bkdetail/FSJARA0A/"
]

app_config = apps.get_app_config("package")

for url in urls:
    for model in app_config.get_models():
        field_names = [f.name for f in model._meta.get_fields()]
        url_field = "pageUrl" if "pageUrl" in field_names else ("url" if "url" in field_names else None)
        if not url_field:
            continue
        obj = model.objects.filter(**{url_field: url}).order_by('-id').first()
        if obj:
            pred = bulk_predict_first_stage([obj])[0]
            act = float(obj.price) / 10000.0 if hasattr(obj, 'price') and obj.price else 0.0
            print(f"[{model.__name__}] Act: {act:,.0f}万 -> NewPred: {pred:,}万 | URL: {url}")
            break
