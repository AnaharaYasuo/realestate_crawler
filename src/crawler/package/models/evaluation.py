# -*- coding: utf-8 -*-
from django.db import models

class MunicipalPotential(models.Model):
    """
    自治体（市区町村）ごとのポテンシャル統計マスタ
    """
    prefecture = models.CharField(max_length=100, verbose_name="都道府県")
    city = models.CharField(max_length=100, verbose_name="市区町村")
    population_growth_rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="人口増減率（％）")
    average_income = models.IntegerField(verbose_name="1人あたり平均所得（千円）")

    class Meta:
        db_table = 'municipal_potential'
        unique_together = ('prefecture', 'city')
        verbose_name = "自治体ポテンシャルマスタ"
        verbose_name_plural = "自治体ポテンシャルマスタ"

    def __str__(self):
        return f"{self.prefecture}{self.city} (所得: {self.average_income}千円, 人口増減: {self.population_growth_rate}%)"


class StationPotential(models.Model):
    """
    駅ごとのポテンシャル統計マスタ
    """
    station_name = models.CharField(max_length=100, db_index=True, verbose_name="駅名")
    railway_line = models.CharField(max_length=100, verbose_name="路線名")
    passenger_volume = models.IntegerField(verbose_name="1日平均乗乗降客数")

    class Meta:
        db_table = 'station_potential'
        unique_together = ('station_name', 'railway_line')
        verbose_name = "駅ポテンシャルマスタ"
        verbose_name_plural = "駅ポテンシャルマスタ"

    def __str__(self):
        return f"{self.railway_line} {self.station_name}駅 (乗降客数: {self.passenger_volume}人/日)"


class PropertyEvaluation(models.Model):
    """
    物件共通評価モデル
    各社の物件テーブルに 1:1 またはポリモーフィックに紐づく評価・機械学習予測メタデータ
    """
    company = models.CharField(max_length=50, db_index=True, verbose_name="不動産会社コード")
    property_type = models.CharField(max_length=50, db_index=True, verbose_name="物件種別")
    property_id = models.IntegerField(db_index=True, verbose_name="元テーブルレコードID")
    property_url = models.CharField(max_length=500, unique=True, db_index=True, verbose_name="物件URL")

    # 一次スクリーニング（画像なし機械学習予測）
    first_stage_predicted_price = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="一次予測理論価格"
    )
    is_first_stage_passed = models.BooleanField(default=False, verbose_name="一次スクリーニング合格フラグ")

    # 二次スクリーニング（画像解析を含む精密機械学習予測）
    second_stage_predicted_price = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="二次予測理論価格"
    )
    interior_score = models.FloatField(null=True, blank=True, verbose_name="内装クオリティスコア (1.0-5.0)")
    layout_score = models.FloatField(null=True, blank=True, verbose_name="間取り評価スコア (1.0-5.0)")
    investment_score = models.FloatField(null=True, blank=True, verbose_name="投資価値スコア (0-100)")

    # 融資・収支シミュレーション評価項目
    estimated_sekisan_price = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="推定積算価格"
    )
    net_operating_income = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="ネット営業純利益 (NOI)"
    )
    debt_service = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="年間元利金返済額 (ADS)"
    )
    cash_flow = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="年間手残りキャッシュフロー"
    )
    dscr = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="債務サービスカバー率 (DSCR)"
    )
    coc_return = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="自己資金配当率 (CoC)"
    )
    sekisan_ratio = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="積算価格比率"
    )
    cashflow_score = models.FloatField(null=True, blank=True, verbose_name="キャッシュフロースコア (0-100)")
    finance_score = models.FloatField(null=True, blank=True, verbose_name="融資適合性スコア (0-100)")
    total_investment_score = models.FloatField(null=True, blank=True, verbose_name="総合投資スコア (0-100)")

    # 解析ステータス・制御
    analysis_status = models.CharField(
        max_length=30,
        default='pending',
        choices=[
            ('pending', '解析待ち'),
            ('processing', '解析中'),
            ('completed', '解析完了'),
            ('skipped_by_budget', '予算上限スキップ'),
            ('failed', '解析失敗')
        ],
        verbose_name="画像解析ステータス"
    )
    analyzed_at = models.DateTimeField(null=True, blank=True, verbose_name="解析実行日時")
    is_slack_notified = models.BooleanField(default=False, verbose_name="Slack通知済みフラグ")

    class Meta:
        db_table = 'property_evaluation'
        verbose_name = "物件評価データ"
        verbose_name_plural = "物件評価データ"

    def __str__(self):
        return f"[{self.company}/{self.property_type}] URL: {self.property_url} (一次合格: {self.is_first_stage_passed}, ステータス: {self.analysis_status})"


class PropertyImage(models.Model):
    """
    クレンジング済み物件画像モデル
    PropertyEvaluationに対して 1:N で紐づく
    """
    evaluation = models.ForeignKey(
        PropertyEvaluation,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name="物件評価"
    )
    image_url = models.CharField(max_length=1000, verbose_name="画像URL")
    local_path = models.CharField(max_length=500, null=True, blank=True, verbose_name="ローカル保存パス")
    category = models.CharField(
        max_length=50,
        choices=[
            ('layout', '間取り図'),
            ('exterior', '外観'),
            ('interior', '内装')
        ],
        verbose_name="画像カテゴリ"
    )
    is_cleaned = models.BooleanField(default=True, verbose_name="クレンジングフラグ")

    class Meta:
        db_table = 'property_image'
        verbose_name = "クレンジング画像"
        verbose_name_plural = "クレンジング画像"

    def __str__(self):
        return f"{self.category} - {self.image_url}"


class LandPricePotential(models.Model):
    """
    市区町村別の平均公示地価マスタ（地価・相場トレンドデータ）
    """
    prefecture = models.CharField(max_length=100, verbose_name="都道府県")
    city = models.CharField(max_length=100, verbose_name="市区町村")
    average_land_price = models.IntegerField(verbose_name="平均公示地価（円/㎡）")
    estimated_rosenka_price = models.IntegerField(null=True, blank=True, verbose_name="推定相続税路線価（円/㎡）")
    estimated_fixed_asset_price = models.IntegerField(null=True, blank=True, verbose_name="推定固定資産税評価価格（円/㎡）")
    land_use = models.CharField(
        max_length=50,
        choices=[
            ('residential', '住宅地'),
            ('commercial', '商業地')
        ],
        verbose_name="用途区分"
    )

    class Meta:
        db_table = 'land_price_potential'
        unique_together = ('prefecture', 'city', 'land_use')
        verbose_name = "平均地価マスタ"
        verbose_name_plural = "平均地価マスタ"

    def __str__(self):
        return f"{self.prefecture}{self.city} ({self.get_land_use_display()}: {self.average_land_price}円/㎡)"


class HazardMapPotential(models.Model):
    """
    市区町村ごとのハザードマップ（浸水・土砂災害リスク）統計マスタ
    """
    prefecture = models.CharField(max_length=100, verbose_name="都道府県")
    city = models.CharField(max_length=100, verbose_name="市区町村")
    flood_risk_level = models.IntegerField(default=0, verbose_name="浸水リスクレベル (0:低 - 4:極めて高)")
    landslide_risk_level = models.IntegerField(default=0, verbose_name="土砂災害リスクレベル (0:無 - 2:高)")

    class Meta:
        db_table = 'hazard_map_potential'
        unique_together = ('prefecture', 'city')
        verbose_name = "ハザードマップ統計マスタ"
        verbose_name_plural = "ハザードマップ統計マスタ"

    def __str__(self):
        return f"{self.prefecture}{self.city} (浸水: {self.flood_risk_level}, 土砂: {self.landslide_risk_level})"


class UrbanPlanningZonePotential(models.Model):
    """
    用途地域ごとの容積率・建ぺい率の上限規制マスタ
    """
    zone_name = models.CharField(max_length=100, unique=True, verbose_name="用途地域名")
    max_kenpei = models.IntegerField(verbose_name="上限建ぺい率（％）")
    max_youseki = models.IntegerField(verbose_name="上限容積率（％）")

    class Meta:
        db_table = 'urban_planning_zone_potential'
        verbose_name = "用途地域規制マスタ"
        verbose_name_plural = "用途地域規制マスタ"

    def __str__(self):
        return f"{self.zone_name} (建ぺい: {self.max_kenpei}%, 容積: {self.max_youseki}%)"

