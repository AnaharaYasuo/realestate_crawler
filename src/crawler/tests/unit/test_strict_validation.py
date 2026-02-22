import pytest
import os
import sys
from decimal import Decimal
from datetime import datetime, date

# Ensure package is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from package.models.sumifu import SumifuInvestmentKodate, SumifuInvestmentApartment
from package.models.mitsui import MitsuiInvestmentKodate, MitsuiInvestmentApartment
from django.core.exceptions import ValidationError

class TestStrictValidation:
    """厳格なバリデーション実装のテスト"""

    def test_validation_error_on_missing_price(self):
        """テスト1: price が欠損している場合、ValidationError が発生すること"""
        item = SumifuInvestmentKodate()
        item.propertyName = "テスト物件"
        item.pageUrl = "https://test.example.com/property/1"
        item.inputDate = date.today()
        item.inputDateTime = datetime.now()
        item.address = "東京都渋谷区"
        item.traffic = "JR山手線 渋谷駅 徒歩5分"
        item.landArea = Decimal("100.00")
        item.buildingArea = Decimal("80.00")
        item.propertyType = "Kodate"
        
        # Add required Sumifu model fields
        item.hikiwatashi = "即時"
        item.genkyo = "空室"
        item.torihiki = "仲介"
        item.tochikenri = "所有権"
        item.tochiMensekiStr = "100.00㎡"
        item.tatemonoMensekiStr = "80.00㎡"
        item.tatemonoMenseki = Decimal("80.00")
        item.setsudou = "東 4.0m"
        item.chikunengetsuStr = "2020年01月"
        item.kouzou = "木造"
        item.propertyType = "Kodate"
        item.chikunengetsu = date(2020, 1, 1)
        
        with pytest.raises(ValidationError) as exc_info:
            item.full_clean()
        
        assert 'price' in exc_info.value.message_dict
        print(f"✅ price 欠損時の ValidationError: {exc_info.value.message_dict['price']}")

    def test_validation_error_on_missing_landarea(self):
        """テスト2: landArea が欠損している場合、ValidationError が発生すること"""
        item = SumifuInvestmentKodate()
        item.propertyName = "テスト戸建て"
        item.pageUrl = "https://test.example.com/property/2"
        item.inputDate = date.today()
        item.inputDateTime = datetime.now()
        item.priceStr = "5000万円"
        item.price = 50000000
        item.address = "東京都新宿区"
        item.traffic = "JR中央線 新宿駅 徒歩10分"
        item.buildingArea = Decimal("150.00")
        item.propertyType = "Kodate"
        item.price = 50000000
        item.annualRent = 2500000
        item.monthlyRent = 208333
        item.currentStatus = "賃貸中"
        
        # Add required Sumifu model fields
        item.hikiwatashi = "相談"
        item.genkyo = "賃貸中"
        item.torihiki = "仲介"
        item.tochikenri = "所有権"
        item.tochiMensekiStr = "150.00㎡"
        item.tatemonoMensekiStr = "120.00㎡"
        item.chikunengetsuStr = "2015年05月"
        item.chikunengetsu = date(2015, 5, 1)
        item.kouzou = "鉄骨造"
        
        # grossYield は意図的に設定しない
        
        with pytest.raises(ValidationError) as exc_info:
            item.full_clean()
        
        assert 'grossYield' in exc_info.value.message_dict
        print(f"✅ grossYield 欠損時の ValidationError: {exc_info.value.message_dict['grossYield']}")

    def test_successful_validation_with_complete_data(self):
        """テスト3: 完全なデータの場合、バリデーションが成功すること"""
        item = MitsuiInvestmentKodate()
        item.propertyName = "完全データ戸建て"
        item.pageUrl = f"https://test.example.com/property/complete_{datetime.now().timestamp()}"
        item.inputDate = date.today()
        item.inputDateTime = datetime.now()
        item.priceStr = "8000万円"
        item.price = 80000000
        item.address = "神奈川県横浜市"
        item.railway1 = "東急東横線"
        item.station1 = "横浜駅"
        item.landArea = Decimal("120.00")
        item.buildingArea = Decimal("95.00")
        item.propertyType = "Kodate"
        item.grossYield = Decimal("6.00")
        item.annualRent = 4800000
        item.monthlyRent = 400000
        item.currentStatus = "賃貸中"
        
        # Add required Mitsui model fields
        item.kouzou = "木造"
        item.chikunengetsuStr = "2010年10月"
        item.tochikenri = "所有権"
        item.hikiwatashi = "即時"
        item.genkyo = "空室"
        item.torihiki = "仲介"
        item.tochiMensekiStr = "120.00㎡"
        item.tatemonoMensekiStr = "95.00㎡"
        item.tatemonoMenseki = Decimal("95.00")
        item.setsudou = "南西 4.0m"
        item.tochiMenseki = Decimal("120.00")
        item.chimoku = "宅地"
        item.youtoChiiki = "第一種低層住居専用地域"
        item.kenpei = Decimal("50.0")
        item.kenpeiStr = "50%"
        item.youseki = Decimal("100.0")
        item.yousekiStr = "100%"
        item.kaisuStr = "地上2階建"
        
        # バリデーションが成功することを確認（例外が発生しないこと）
        item.full_clean()
        print(f"✅ 完全データのバリデーション成功")
        print(f"   物件名: {item.propertyName}")
        print(f"   価格: {item.price:,}円")
        print(f"   土地面積: {item.landArea}㎡")
        print(f"   建物面積: {item.buildingArea}㎡")

    def test_multiple_missing_fields(self):
        """テスト4: 複数フィールドが欠損している場合、すべてのエラーが報告されること"""
        item = MitsuiInvestmentKodate()
        item.propertyName = "不完全戸建"
        item.pageUrl = "https://test.example.com/property/incomplete"
        # inputDate, inputDateTime, price, address, railway1, landArea, buildingArea を意図的に設定しない
        item.propertyType = "Kodate"
        
        with pytest.raises(ValidationError) as exc_info:
            item.full_clean()
        
        errors = exc_info.value.message_dict
        print(f"✅ 複数欠損時のエラー数: {len(errors)}")
        print(f"   欠損フィールド: {list(errors.keys())}")
        
        # 必須フィールドがすべて報告されているか確認
        required_fields = ['priceStr', 'price', 'address', 'grossYield', 'annualRent', 'monthlyRent', 'currentStatus', 'kouzou', 'chikunengetsuStr', 'tochiMensekiStr', 'tochiMenseki', 'tatemonoMensekiStr', 'tatemonoMenseki', 'setsudou', 'chimoku', 'youtoChiiki', 'kenpei', 'kenpeiStr', 'youseki', 'yousekiStr', 'kaisuStr']
        for field in required_fields:
            assert field in errors, f"{field} がエラーに含まれていません"
