from pydantic import BaseModel, Field, field_validator
from typing import Optional
from decimal import Decimal
from datetime import date

class PropertyDataSchema(BaseModel):
    """パース結果の中間データスキーマ（全物件共通）"""
    propertyName: str = Field(..., min_length=1)
    pageUrl: str = Field(..., min_length=1)
    priceStr: str
    price: int = Field(ge=0)
    address: str
    traffic: Optional[str] = None

    @field_validator('price')
    @classmethod
    def validate_price(cls, v):
        if v > 100_000_000_000:  # 1000億円
            raise ValueError('価格が異常に高額です')
        return v

class MansionDataSchema(PropertyDataSchema):
    """マンション物件のスキーマ"""
    senyuMensekiStr: Optional[str] = None
    senyuMenseki: Optional[Decimal] = Field(None, ge=0)
    chikunengetsuStr: Optional[str] = None
    chikunengetsu: Optional[date] = None
    kanrihiStr: Optional[str] = None
    kanrihi: Optional[int] = Field(None, ge=0)
    syuzenTsumitateStr: Optional[str] = None
    syuzenTsumitate: Optional[int] = Field(None, ge=0)
    madori: Optional[str] = None
    floorType: Optional[str] = None

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
    tochiMensekiStr: Optional[str] = None
    tochiMenseki: Optional[Decimal] = Field(None, ge=0)
    tatemonoMensekiStr: Optional[str] = None
    tatemonoMenseki: Optional[Decimal] = Field(None, ge=0)
    chikunengetsuStr: Optional[str] = None
    chikunengetsu: Optional[date] = None
    madori: Optional[str] = None
    kouzou: Optional[str] = None

class TochiDataSchema(PropertyDataSchema):
    """土地物件のスキーマ"""
    tochiMensekiStr: Optional[str] = None
    tochiMenseki: Optional[Decimal] = Field(None, ge=0)
    youto: Optional[str] = None
    kenpeiritsu: Optional[str] = None
    yousekritsu: Optional[str] = None
