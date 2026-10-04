from django.db import models
from .base import MansionBaseModel, KodateBaseModel, TochiBaseModel

# --- Ietan (大成有楽不動産販売) ---
class IetanMansion(MansionBaseModel):
    class Meta:
        db_table = "crawled_ietan_mansion"

class IetanKodate(KodateBaseModel):
    class Meta:
        db_table = "crawled_ietan_kodate"

class IetanTochi(TochiBaseModel):
    class Meta:
        db_table = "crawled_ietan_tochi"


# --- Haseko (長谷工の仲介) ---
class HasekoMansion(MansionBaseModel):
    class Meta:
        db_table = "crawled_haseko_mansion"


# --- AdCast (アドキャスト) ---
class AdCastKodate(KodateBaseModel):
    class Meta:
        db_table = "crawled_adcast_kodate"

class AdCastTochi(TochiBaseModel):
    class Meta:
        db_table = "crawled_adcast_tochi"


# --- Toho House (東宝ハウス) ---
class TohoMansion(MansionBaseModel):
    class Meta:
        db_table = "crawled_toho_mansion"

class TohoKodate(KodateBaseModel):
    class Meta:
        db_table = "crawled_toho_kodate"

class TohoTochi(TochiBaseModel):
    class Meta:
        db_table = "crawled_toho_tochi"
