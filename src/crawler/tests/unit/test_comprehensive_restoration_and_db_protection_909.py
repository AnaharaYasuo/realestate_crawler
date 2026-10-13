import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import realestateSettings
realestateSettings.configure()

from package.utils.db_safety import assert_production_db_safety, ProductionDatabaseModificationBlocked
from package.utils.data_validator import PropertyDataValidator
from package.models.athome import AthomeKodate


class TestComprehensiveRestorationAndDbProtection909:
    """Issue #909: 本番DBローカル保護・マイグレ整合性・バリデータ整合性テスト"""

    def test_production_db_safety_blocks_migrate_when_local(self, monkeypatch):
        """ローカル環境で本番DBを指定して migrate を実行しようとしたら必ずブロックされること"""
        from django.conf import settings
        monkeypatch.setitem(settings.DATABASES, "default", {
            "ENGINE": "django.db.backends.mysql",
            "HOST": "host.docker.internal",
            "PORT": "3307",
            "NAME": "real_estate"
        })
        monkeypatch.setenv("DB_HOST", "host.docker.internal")
        monkeypatch.setenv("DB_PORT", "3307")
        monkeypatch.setenv("DB_NAME", "real_estate")
        monkeypatch.delenv("IS_PRODUCTION_DEPLOYMENT", raising=False)

        # migrate コマンド実行時
        with pytest.raises(ProductionDatabaseModificationBlocked) as exc_info:
            assert_production_db_safety(command_name="migrate")
        assert "CRITICAL BLOCK" in str(exc_info.value)

        # makemigrations 実行時
        with pytest.raises(ProductionDatabaseModificationBlocked):
            assert_production_db_safety(command_name="makemigrations")

    def test_production_db_safety_allows_when_ci_deployment(self, monkeypatch):
        """CI/CDのデプロイパイプライン (IS_PRODUCTION_DEPLOYMENT=true) では許可されること"""
        from django.conf import settings
        monkeypatch.setitem(settings.DATABASES, "default", {
            "ENGINE": "django.db.backends.mysql",
            "HOST": "host.docker.internal",
            "PORT": "3307",
            "NAME": "real_estate"
        })
        monkeypatch.setenv("DB_HOST", "host.docker.internal")
        monkeypatch.setenv("DB_PORT", "3307")
        monkeypatch.setenv("DB_NAME", "real_estate")
        monkeypatch.setenv("IS_PRODUCTION_DEPLOYMENT", "true")

        # 例外が発生せず正常終了すること
        assert_production_db_safety(command_name="migrate")

    def test_production_db_safety_allows_read_commands(self, monkeypatch):
        """読み取り系やテスト系コマンドはローカルでもブロックされないこと"""
        monkeypatch.setenv("DB_HOST", "host.docker.internal")
        monkeypatch.setenv("DB_PORT", "3307")
        monkeypatch.setenv("DB_NAME", "real_estate")
        monkeypatch.delenv("IS_PRODUCTION_DEPLOYMENT", raising=False)

        # showmigrations や runserver は許可
        assert_production_db_safety(command_name="showmigrations")
        assert_production_db_safety(command_name="test")

    def test_data_validator_skips_missing_madori_age_for_models_without_fields(self):
        """モデル定義に madori / chikunengetsu が存在しないモデルでは欠損エラーにならないこと"""
        item = AthomeKodate()
        item.propertyName = "テスト戸建て"
        item.address = "東京都世田谷区1-1-1"
        item.traffic = "渋谷駅 徒歩10分"
        item.price = 50000000
        item.tochiMenseki = 100.0

        _, reasons = PropertyDataValidator.validate_property(item, "kodate")
        # 間取り・築年月の欠損エラーが含まれていないこと
        assert not any("間取りが未抽出" in r for r in reasons)
        assert not any("築年月が未抽出" in r for r in reasons)

    def test_data_validator_still_checks_madori_age_when_field_exists(self):
        """フィールドが存在するモデル（例: SumifuKodate）では空文字時に欠損エラーになること"""
        from package.models.sumifu import SumifuKodate
        item = SumifuKodate()
        item.propertyName = "テスト戸建て"
        item.address = "東京都世田谷区1-1-1"
        item.traffic = "渋谷駅 徒歩10分"
        item.price = 50000000
        item.tochiMenseki = 100.0
        item.madori = "" # 空

        _, reasons = PropertyDataValidator.validate_property(item, "kodate")
        assert any("間取りが未抽出" in r for r in reasons)

    def test_iter_unprocessed_chunks_safe_pagination(self, monkeypatch):
        """iter_unprocessed_chunks が PK ベースで安全にチャンク分割して yield すること"""
        from package.ml.evaluation.targets import iter_unprocessed_chunks

        # モックモデルオブジェクト
        class MockItem:
            def __init__(self, pk, url):
                self.pk = pk
                self.pageUrl = url

        items = [MockItem(i, f"https://example.com/prop/{i}") for i in range(1, 26)]

        class MockQuerySet:
            def __init__(self, data):
                self.data = data
            def filter(self, pk__gt=0):
                filtered = [x for x in self.data if x.pk > pk__gt]
                return MockQuerySet(filtered)
            def order_by(self, field):
                return self
            def __getitem__(self, sl):
                return self.data[sl]
            def __iter__(self):
                return iter(self.data)

        class MockModel:
            objects = MockQuerySet(items)

        # chunk_size=10 で分割走査
        chunks = list(iter_unprocessed_chunks(MockModel, existing_eval_map={}, chunk_size=10))
        assert len(chunks) == 3
        assert len(chunks[0][0]) == 10
        assert len(chunks[1][0]) == 10
        assert len(chunks[2][0]) == 5
        assert chunks[0][0][0].pk == 1
        assert chunks[2][0][-1].pk == 25
