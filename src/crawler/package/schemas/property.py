from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from datetime import date

class PropertyDataSchema(BaseModel):
    """パース結果の中間データスキーマ（全物件共通）"""
    propertyName: str = Field(..., min_length=1)
    pageUrl: str = Field(..., min_length=1)
    priceStr: str
    price: int = Field(ge=0)
    address: str
    traffic: str | None = None

    @field_validator('price')
    @classmethod
    def validate_price(cls, v):
        if v > 100_000_000_000:  # 1000億円
            raise ValueError('価格が異常に高額です')
        return v

class MansionDataSchema(PropertyDataSchema):
    """マンション物件のスキーマ"""
    senyuMensekiStr: str | None = None
    senyuMenseki: Decimal | None = Field(None, ge=0)
    chikunengetsuStr: str | None = None
    chikunengetsu: date | None = None
    kanrihiStr: str | None = None
    kanrihi: int | None = Field(None, ge=0)
    syuzenTsumitateStr: str | None = None
    syuzenTsumitate: int | None = Field(None, ge=0)
    madori: str | None = None
    floorType: str | None = None

    @field_validator('senyuMenseki')
    @classmethod
    def validate_menseki(cls, v):
        if v is not None and v <= 0:
            raise ValueError('面積は正の値である必要があります')
        if v is not None and v > 10000:
            raise ValueError('面積が異常に大きいです')
        return v

class KodateDataSchema(PropertyDataSchema):
    """戸建て物件のスキーマ"""
    tochiMensekiStr: str | None = None
    tochiMenseki: Decimal | None = Field(None, ge=0)
    tatemonoMensekiStr: str | None = None
    tatemonoMenseki: Decimal | None = Field(None, ge=0)
    chikunengetsuStr: str | None = None
    chikunengetsu: date | None = None
    madori: str | None = None
    kouzou: str | None = None

class TochiDataSchema(PropertyDataSchema):
    """土地物件のスキーマ"""
    tochiMensekiStr: str | None = None
    tochiMenseki: Decimal | None = Field(None, ge=0)
    youto: str | None = None
    kenpeiritsu: str | None = None
    yousekritsu: str | None = None
