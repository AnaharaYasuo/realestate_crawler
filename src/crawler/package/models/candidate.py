# -*- coding: utf-8 -*-
from django.db import models


class CandidatePropertyUrl(models.Model):
    """
    未対応サイトの物件クローリング候補URLモデル
    ユーザーからのリクエスト回数(request_count)を集計し、優先開発対象を抽出する
    """
    url = models.CharField(max_length=500, unique=True, db_index=True, verbose_name="物件URL")
    domain = models.CharField(max_length=100, db_index=True, verbose_name="ドメイン")
    title = models.CharField(max_length=300, blank=True, default="", verbose_name="ページタイトル")
    matched_keywords = models.JSONField(default=list, verbose_name="検知された不動産キーワード")
    request_count = models.IntegerField(default=1, verbose_name="リクエスト要求回数")
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "未着手"),
            ("developing", "開発中"),
            ("rejected", "対象外"),
            ("implemented", "実装完了"),
        ],
        verbose_name="開発ステータス"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="初回要求日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="最終更新日時")

    class Meta:
        db_table = "candidate_property_url"
        verbose_name = "クローリング候補URL"
        verbose_name_plural = "クローリング候補URL一覧"

    def __str__(self):
        return f"{self.domain} ({self.request_count}回): {self.url}"
