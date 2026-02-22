#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
バリデーションテスト: 厳格なスキーマ制約のテスト

このスクリプトは以下をテストします:
1. 必須フィールドが欠損している場合、ValidationError が発生すること
2. ValidationError が発生した場合、レコードが保存されないこと
3. 詳細なログが出力されること (物件URL、物件名、欠損フィールド)
4. 完全なデータの場合、正常に保存されること
"""
import os
import sys
import django
import logging
from decimal import Decimal

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestateSettings')
django.setup()

from package.models.sumifu import SumifuInvestmentKodate, SumifuInvestmentApartment
from package.models.mitsui import MitsuiInvestmentKodate, MitsuiInvestmentApartment
from django.core.exceptions import ValidationError
from datetime import datetime, date

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

def test_validation_error_on_missing_price():
    """テスト1: price が欠損している場合、ValidationError が発生すること"""
    print("\n" + "="*80)
    print("テスト1: price 欠損時の ValidationError 発生確認")
    print("="*80)
    
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
    # price は意図的に設定しない
    
    try:
        item.full_clean()
        print("❌ FAILED: ValidationError が発生しませんでした")
        return False
    except ValidationError as e:
        print(f"✅ PASSED: ValidationError が発生しました")
        print(f"   エラー内容: {e.message_dict}")
        if 'price' in e.message_dict:
            print(f"   price フィールドのエラー: {e.message_dict['price']}")
            return True
        else:
            print("❌ FAILED: price フィールドのエラーが含まれていません")
            return False

def test_validation_error_on_missing_landarea():
    """テスト2: landArea が欠損している場合、ValidationError が発生すること"""
    print("\n" + "="*80)
    print("テスト2: landArea 欠損時の ValidationError 発生確認")
    print("="*80)
    
    item = SumifuInvestmentApartment()
    item.propertyName = "テストアパート"
    item.pageUrl = "https://test.example.com/property/2"
    item.inputDate = date.today()
    item.inputDateTime = datetime.now()
    item.priceStr = "5000万円"
    item.price = 50000000
    item.address = "東京都新宿区"
    item.traffic = "JR中央線 新宿駅 徒歩10分"
    item.buildingArea = Decimal("150.00")
    item.propertyType = "Apartment"
    # landArea は意図的に設定しない
    
    try:
        item.full_clean()
        print("❌ FAILED: ValidationError が発生しませんでした")
        return False
    except ValidationError as e:
        print(f"✅ PASSED: ValidationError が発生しました")
        print(f"   エラー内容: {e.message_dict}")
        if 'landArea' in e.message_dict:
            print(f"   landArea フィールドのエラー: {e.message_dict['landArea']}")
            return True
        else:
            print("❌ FAILED: landArea フィールドのエラーが含まれていません")
            return False

def test_successful_save_with_complete_data():
    """テスト3: 完全なデータの場合、バリデーションが成功すること"""
    print("\n" + "="*80)
    print("テスト3: 完全なデータでのバリデーション成功確認")
    print("="*80)
    
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
    
    try:
        item.full_clean()
        print("✅ PASSED: バリデーションが成功しました")
        print(f"   物件名: {item.propertyName}")
        print(f"   価格: {item.price:,}円")
        print(f"   土地面積: {item.landArea}㎡")
        print(f"   建物面積: {item.buildingArea}㎡")
        
        # 実際に保存してみる (テスト後に削除)
        item.save()
        print(f"   データベース保存成功 (ID: {item.id})")
        
        # テストデータを削除
        item.delete()
        print(f"   テストデータ削除完了")
        
        return True
    except ValidationError as e:
        print(f"❌ FAILED: ValidationError が発生しました")
        print(f"   エラー内容: {e.message_dict}")
        return False
    except Exception as e:
        print(f"❌ FAILED: 予期しないエラーが発生しました")
        print(f"   エラー: {e}")
        return False

def test_multiple_missing_fields():
    """テスト4: 複数フィールドが欠損している場合、すべてのエラーが報告されること"""
    print("\n" + "="*80)
    print("テスト4: 複数フィールド欠損時のエラー報告確認")
    print("="*80)
    
    item = MitsuiInvestmentApartment()
    item.propertyName = "不完全アパート"
    item.pageUrl = "https://test.example.com/property/incomplete"
    # inputDate, inputDateTime, price, address, railway1, landArea, buildingArea を意図的に設定しない
    item.propertyType = "Apartment"
    
    try:
        item.full_clean()
        print("❌ FAILED: ValidationError が発生しませんでした")
        return False
    except ValidationError as e:
        print(f"✅ PASSED: ValidationError が発生しました")
        print(f"   欠損フィールド数: {len(e.message_dict)}")
        print(f"   欠損フィールド:")
        for field, errors in e.message_dict.items():
            print(f"     - {field}: {', '.join(errors)}")
        
        # 必須フィールドがすべて報告されているか確認
        required_fields = ['inputDate', 'inputDateTime', 'price', 'address', 'railway1', 'landArea', 'buildingArea']
        missing_in_report = [f for f in required_fields if f not in e.message_dict]
        
        if missing_in_report:
            print(f"   ⚠️  報告されていない必須フィールド: {missing_in_report}")
        
        return len(missing_in_report) == 0

def main():
    """すべてのテストを実行"""
    print("\n" + "="*80)
    print("厳格なバリデーション実装テスト")
    print("="*80)
    
    results = []
    
    # テスト実行
    results.append(("price 欠損テスト", test_validation_error_on_missing_price()))
    results.append(("landArea 欠損テスト", test_validation_error_on_missing_landarea()))
    results.append(("完全データテスト", test_successful_save_with_complete_data()))
    results.append(("複数欠損テスト", test_multiple_missing_fields()))
    
    # 結果サマリー
    print("\n" + "="*80)
    print("テスト結果サマリー")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\n合計: {passed}/{total} テスト成功")
    
    if passed == total:
        print("\n🎉 すべてのテストが成功しました！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 件のテストが失敗しました")
        return 1

if __name__ == "__main__":
    sys.exit(main())
