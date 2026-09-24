# -*- coding: utf-8 -*-
"""
Swagger / OpenAPI 3.0 仕様書自動生成スクリプト
(src/crawler/scripts/generate_swagger_spec.py)

このスクリプトは、最新のモデルスキーマ・特徴量・推論API仕様を統合し、
docs/api/openapi.yaml を自動生成・同期します。

Usage:
    python src/crawler/scripts/generate_swagger_spec.py          # 仕様書を自動生成・更新
    python src/crawler/scripts/generate_swagger_spec.py --check  # 差分がないか検証 (CI用)
"""
import os
import sys
import yaml

MIME_APPLICATION_JSON = "application/json"
REF_INTERIOR_SCORE = "#/components/schemas/InteriorScore"
REF_LAYOUT_SCORE = "#/components/schemas/LayoutScore"
REF_SUCCESS_RESPONSE = "#/components/responses/SuccessResponse"
REF_ERROR_RESPONSE = "#/components/responses/ErrorResponse"
REF_COMMON_PROPERTY_DATA = "#/components/schemas/CommonPropertyData"
LABEL_SETUDO_MAGUCHI = "接道間口 (m)"
LABEL_ZENMEN_DOURO_FUKUIN = "前面道路幅員 (m)"

def get_openapi_spec_dict():
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Realestate Price Estimation API",
            "description": "不動産の基本情報および画像スコアをベースに、機械学習アンサンブルモデルを用いた推定理論価格（一次予測および二次予測）を算出するAPI。",
            "version": "1.0.0"
        },
        "servers": [
            {
                "url": "/",
                "description": "Current Host"
            },
            {
                "url": "http://localhost:8000",
                "description": "Local Development Server"
            }
        ],
        "security": [
            {
                "ApiKeyAuth": []
            }
        ],
        "paths": {
            "/api/evaluation/predict/mansion": {
                "post": {
                    "summary": "マンション推定価格予測を実行",
                    "description": "送信されたマンションデータをもとに価格推定を行います。周辺地価や地域統計情報は自動補完されます。",
                    "requestBody": {
                        "required": True,
                        "content": {
                            MIME_APPLICATION_JSON: {
                                "schema": {
                                    "type": "object",
                                    "required": ["property_data"],
                                    "properties": {
                                        "property_data": {
                                            "$ref": "#/components/schemas/MansionPropertyData"
                                        },
                                        "interior_score": {
                                            "$ref": REF_INTERIOR_SCORE
                                        },
                                        "layout_score": {
                                            "$ref": REF_LAYOUT_SCORE
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "$ref": REF_SUCCESS_RESPONSE
                        },
                        "400": {
                            "$ref": REF_ERROR_RESPONSE
                        },
                        "500": {
                            "$ref": REF_ERROR_RESPONSE
                        }
                    }
                }
            },
            "/api/evaluation/predict/kodate": {
                "post": {
                    "summary": "戸建推定価格予測を実行",
                    "description": "送信された戸建データをもとに価格推定を行います。",
                    "requestBody": {
                        "required": True,
                        "content": {
                            MIME_APPLICATION_JSON: {
                                "schema": {
                                    "type": "object",
                                    "required": ["property_data"],
                                    "properties": {
                                        "property_data": {
                                            "$ref": "#/components/schemas/KodatePropertyData"
                                        },
                                        "interior_score": {
                                            "$ref": REF_INTERIOR_SCORE
                                        },
                                        "layout_score": {
                                            "$ref": REF_LAYOUT_SCORE
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "$ref": REF_SUCCESS_RESPONSE
                        },
                        "400": {
                            "$ref": REF_ERROR_RESPONSE
                        },
                        "500": {
                            "$ref": REF_ERROR_RESPONSE
                        }
                    }
                }
            },
            "/api/evaluation/predict/apartment": {
                "post": {
                    "summary": "一棟アパート（投資用）推定価格予測を実行",
                    "description": "送信されたアパートデータをもとに価格推定を行います。収益還元用の年間賃料や利回りを含めることができます。",
                    "requestBody": {
                        "required": True,
                        "content": {
                            MIME_APPLICATION_JSON: {
                                "schema": {
                                    "type": "object",
                                    "required": ["property_data"],
                                    "properties": {
                                        "property_data": {
                                            "$ref": "#/components/schemas/ApartmentPropertyData"
                                        },
                                        "interior_score": {
                                            "$ref": REF_INTERIOR_SCORE
                                        },
                                        "layout_score": {
                                            "$ref": REF_LAYOUT_SCORE
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "$ref": REF_SUCCESS_RESPONSE
                        },
                        "400": {
                            "$ref": REF_ERROR_RESPONSE
                        },
                        "500": {
                            "$ref": REF_ERROR_RESPONSE
                        }
                    }
                }
            },
            "/api/evaluation/predict/tochi": {
                "post": {
                    "summary": "土地推定価格予測を実行",
                    "description": "送信された土地データをもとに価格推定を行います。",
                    "requestBody": {
                        "required": True,
                        "content": {
                            MIME_APPLICATION_JSON: {
                                "schema": {
                                    "type": "object",
                                    "required": ["property_data"],
                                    "properties": {
                                        "property_data": {
                                            "$ref": "#/components/schemas/TochiPropertyData"
                                        },
                                        "interior_score": {
                                            "$ref": REF_INTERIOR_SCORE
                                        },
                                        "layout_score": {
                                            "$ref": REF_LAYOUT_SCORE
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "$ref": REF_SUCCESS_RESPONSE
                        },
                        "400": {
                            "$ref": REF_ERROR_RESPONSE
                        },
                        "500": {
                            "$ref": REF_ERROR_RESPONSE
                        }
                    }
                }
            },
            "/api/evaluation/predict-by-url": {
                "post": {
                    "summary": "物件詳細URLから価格推定を実行",
                    "description": "不動産ポータル等の個別物件詳細URLをもとに、自動パースおよび機械学習アンサンブルモデルによる推定理論価格を算出します。3段階キャッシュ（推論キャッシュ、DB物件データ、リアルタイムクローリング）により高速応答します。",
                    "requestBody": {
                        "required": True,
                        "content": {
                            MIME_APPLICATION_JSON: {
                                "schema": {
                                    "type": "object",
                                    "required": ["url"],
                                    "properties": {
                                        "url": {
                                            "type": "string",
                                            "description": "不動産物件詳細ページのURL",
                                            "example": "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKPBAA05/"
                                        },
                                        "property_type": {
                                            "type": "string",
                                            "enum": ["mansion", "kodate", "tochi", "apartment"],
                                            "description": "物件種別の明示指定（省略時はURLまたはページ内容から自動判別）",
                                            "example": "mansion"
                                        },
                                        "force_refresh": {
                                            "type": "boolean",
                                            "default": False,
                                            "description": "true の場合、キャッシュをバイパスして強制再取得"
                                        },
                                        "interior_score": {
                                            "$ref": REF_INTERIOR_SCORE
                                        },
                                        "layout_score": {
                                            "$ref": REF_LAYOUT_SCORE
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "価格推定成功",
                            "content": {
                                MIME_APPLICATION_JSON: {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {
                                                "type": "boolean",
                                                "example": True
                                            },
                                            "url": {
                                                "type": "string",
                                                "example": "https://www.rehouse.co.jp/buy/mansion/bkdetail/FKPBAA05/"
                                            },
                                            "data_source": {
                                                "type": "string",
                                                "example": "evaluation_cache"
                                            },
                                            "site": {
                                                "type": "string",
                                                "example": "mitsui"
                                            },
                                            "property_type": {
                                                "type": "string",
                                                "example": "mansion"
                                            },
                                            "property_info": {
                                                "type": "object"
                                            },
                                            "prediction": {
                                                "type": "object",
                                                "properties": {
                                                    "first_stage_predicted_price": {
                                                        "type": "integer",
                                                        "example": 4850
                                                    },
                                                    "second_stage_predicted_price": {
                                                        "type": "integer",
                                                        "example": 4920
                                                    },
                                                    "price_gap": {
                                                        "type": "integer",
                                                        "example": 350
                                                    },
                                                    "divergence_ratio": {
                                                        "type": "number",
                                                        "example": 1.078
                                                    },
                                                    "is_bargain": {
                                                        "type": "boolean",
                                                        "example": False
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "400": {
                            "$ref": REF_ERROR_RESPONSE
                        },
                        "403": {
                            "$ref": REF_ERROR_RESPONSE
                        },
                        "410": {
                            "$ref": REF_ERROR_RESPONSE
                        },
                        "422": {
                            "$ref": REF_ERROR_RESPONSE
                        },
                        "429": {
                            "$ref": REF_ERROR_RESPONSE
                        },
                        "500": {
                            "$ref": REF_ERROR_RESPONSE
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "InteriorScore": {
                    "type": "number",
                    "description": "内装評価スコア (1.0〜5.0)。二次予測で使用。",
                    "default": 3.0,
                    "example": 4.2
                },
                "LayoutScore": {
                    "type": "number",
                    "description": "間取り評価スコア (1.0〜5.0)。二次予測で使用。",
                    "default": 3.0,
                    "example": 3.8
                },
                "CommonPropertyData": {
                    "type": "object",
                    "required": ["price", "address"],
                    "properties": {
                        "price": {
                            "type": "integer",
                            "description": "販売価格（円）。※必須",
                            "example": 45000000
                        },
                        "address": {
                            "type": "string",
                            "description": "物件の住所（市区町村地価・所得・ハザードマスタ自動引き当て用）。※必須",
                            "example": "東京都世田谷区桜丘1-1"
                        },
                        "address1": {
                            "type": "string",
                            "description": "都道府県名",
                            "example": "東京都"
                        },
                        "address2": {
                            "type": "string",
                            "description": "市区町村名",
                            "example": "世田谷区"
                        },
                        "station1": {
                            "type": "string",
                            "description": "最寄り駅名（駅ポテンシャル・乗降客数引き当て用）",
                            "example": "経堂"
                        },
                        "railway1": {
                            "type": "string",
                            "description": "最寄り沿線名",
                            "example": "小田急小田原線"
                        },
                        "railwayWalkMinute1": {
                            "type": "integer",
                            "description": "最寄り駅からの徒歩分数（分）。デフォルト 15 分",
                            "example": 8
                        },
                        "traffic": {
                            "type": "string",
                            "description": "交通テキスト（バス乗車分数や停歩が自動抽出されます）",
                            "example": "小田急線 経堂駅 徒歩8分"
                        },
                        "busStation1": {
                            "type": "string",
                            "description": "最寄りバス停名",
                            "example": "桜丘一丁目"
                        },
                        "busWalkMinute1": {
                            "type": "integer",
                            "description": "バス停徒歩分数（分）",
                            "example": 2
                        },
                        "chikunengetsuStr": {
                            "type": "string",
                            "description": "築年月（和暦・西暦どちらも可）",
                            "example": "平成15年10月"
                        },
                        "chikunen": {
                            "type": "number",
                            "description": "築年数（年）。chikunengetsuStrの代わりに数値を直接渡すことも可能",
                            "example": 21.0
                        },
                        "kouzou": {
                            "type": "string",
                            "description": "建物の構造（RC, SRC, 鉄骨造, 軽量鉄骨造, 木造など）",
                            "example": "RC"
                        },
                        "yousekiStr": {
                            "type": "string",
                            "description": "指定容積率（%不要。文字列。例: \"200\"）",
                            "example": "200"
                        },
                        "youseki": {
                            "type": "number",
                            "description": "指定容積率数値（%不要。例: 200）",
                            "example": 200
                        },
                        "kenpeiStr": {
                            "type": "string",
                            "description": "指定建ぺい率（%不要。文字列。例: \"60\"）",
                            "example": "60"
                        },
                        "kenpei": {
                            "type": "number",
                            "description": "指定建ぺい率数値（%不要。例: 60）",
                            "example": 60
                        },
                        "youtoChiiki": {
                            "type": "string",
                            "description": "用途地域（第一種住居地域、商業地域など）",
                            "example": "第一種低層住居専用地域"
                        },
                        "kuiki": {
                            "type": "string",
                            "description": "都市計画区域（市街化区域、市街化調整区域など）",
                            "example": "市街化区域"
                        },
                        "tochikenri": {
                            "type": "string",
                            "description": "土地権利形態（所有権、借地権、定期借地権、底地など。借地割合を自動補正）",
                            "example": "所有権"
                        },
                        "chimoku": {
                            "type": "string",
                            "description": "地目（宅地、畑、山林など）",
                            "example": "宅地"
                        },
                        "biko": {
                            "type": "string",
                            "description": "備考（再建築不可、市街化調整区域、定期借地、旗竿地などの判定キー）",
                            "example": "閑静な住宅街、日当たり良好"
                        }
                    }
                },
                "MansionPropertyData": {
                    "allOf": [
                        {"$ref": REF_COMMON_PROPERTY_DATA},
                        {
                            "type": "object",
                            "required": ["senyuMenseki"],
                            "properties": {
                                "senyuMenseki": {
                                    "type": "number",
                                    "description": "専有面積 (㎡)。※必須",
                                    "example": 72.5
                                },
                                "balconyMenseki": {
                                    "type": "number",
                                    "description": "バルコニー面積 (㎡)",
                                    "example": 11.2
                                },
                                "floorPlan": {
                                    "type": "string",
                                    "description": "間取り（3LDK, 2LDK, 1Kなど）",
                                    "example": "3LDK"
                                },
                                "shozaikai": {
                                    "type": "integer",
                                    "description": "所在階",
                                    "example": 5
                                },
                                "souKaisu": {
                                    "type": "integer",
                                    "description": "総階数",
                                    "example": 12
                                },
                                "muki": {
                                    "type": "string",
                                    "description": "主要採光方角（南, 南東, 東など）",
                                    "example": "南"
                                },
                                "kanrihi": {
                                    "type": "integer",
                                    "description": "月額管理費（円）",
                                    "example": 12000
                                },
                                "syuzenTsumitate": {
                                    "type": "integer",
                                    "description": "月額修繕積立金（円）",
                                    "example": 15000
                                },
                                "kanriKeitai": {
                                    "type": "string",
                                    "description": "管理形態（全部委託、日勤など）",
                                    "example": "全部委託"
                                }
                            }
                        }
                    ]
                },
                "KodatePropertyData": {
                    "allOf": [
                        {"$ref": REF_COMMON_PROPERTY_DATA},
                        {
                            "type": "object",
                            "required": ["tatemonoMenseki", "tochiMenseki"],
                            "properties": {
                                "tatemonoMenseki": {
                                    "type": "number",
                                    "description": "建物延床面積 (㎡)。※必須",
                                    "example": 95.0
                                },
                                "tochiMenseki": {
                                    "type": "number",
                                    "description": "土地有効面積 (㎡)。※必須",
                                    "example": 120.0
                                },
                                "floorPlan": {
                                    "type": "string",
                                    "description": "間取り（4LDK, 3LDKなど）",
                                    "example": "4LDK"
                                },
                                "maguchi": {
                                    "type": "number",
                                    "description": LABEL_SETUDO_MAGUCHI,
                                    "example": 7.2
                                },
                                "roadWidth": {
                                    "type": "number",
                                    "description": LABEL_ZENMEN_DOURO_FUKUIN,
                                    "example": 4.5
                                },
                                "roadDirection": {
                                    "type": "string",
                                    "description": "道路方角（南、北、東、西など）",
                                    "example": "南"
                                },
                                "roadType": {
                                    "type": "string",
                                    "description": "道路種別（公道、私道）",
                                    "example": "公道"
                                },
                                "roadStructure": {
                                    "type": "string",
                                    "description": "接道構造（角地、準角地、二方道路など）",
                                    "example": "角地"
                                },
                                "setsudou": {
                                    "type": "string",
                                    "description": "接道状況詳細テキスト (例: \"南側道路 幅員4.5m 公道\")",
                                    "example": "南側道路 幅員4.5m 公道"
                                },
                                "setback": {
                                    "type": "string",
                                    "description": "セットバック情報（例: \"要セットバック2.0㎡\"）",
                                    "example": "無"
                                }
                            }
                        }
                    ]
                },
                "ApartmentPropertyData": {
                    "allOf": [
                        {"$ref": REF_COMMON_PROPERTY_DATA},
                        {
                            "type": "object",
                            "required": ["tatemonoMenseki", "tochiMenseki", "grossYield", "annualRent"],
                            "properties": {
                                "tatemonoMenseki": {
                                    "type": "number",
                                    "description": "建物延床面積 (㎡)。※必須",
                                    "example": 220.0
                                },
                                "tochiMenseki": {
                                    "type": "number",
                                    "description": "土地面積 (㎡)。※必須",
                                    "example": 180.0
                                },
                                "grossYield": {
                                    "type": "number",
                                    "description": "表面利回り (%) ※収益価格特徴量。※必須",
                                    "example": 6.8
                                },
                                "annualRent": {
                                    "type": "integer",
                                    "description": "年間想定賃料（円） ※収益価格特徴量。※必須",
                                    "example": 8160000
                                },
                                "monthlyRent": {
                                    "type": "integer",
                                    "description": "月額想定賃料（円）",
                                    "example": 680000
                                },
                                "genkyo": {
                                    "type": "string",
                                    "description": "現況（満室賃貸中、一部空室など）",
                                    "example": "満室賃貸中"
                                },
                                "maguchi": {
                                    "type": "number",
                                    "description": LABEL_SETUDO_MAGUCHI,
                                    "example": 12.0
                                },
                                "roadWidth": {
                                    "type": "number",
                                    "description": LABEL_ZENMEN_DOURO_FUKUIN,
                                    "example": 5.0
                                },
                                "setsudou": {
                                    "type": "string",
                                    "description": "接道状況詳細テキスト",
                                    "example": "東側幅員5m公道"
                                }
                            }
                        }
                    ]
                },
                "TochiPropertyData": {
                    "allOf": [
                        {"$ref": REF_COMMON_PROPERTY_DATA},
                        {
                            "type": "object",
                            "required": ["tochiMenseki"],
                            "properties": {
                                "tochiMenseki": {
                                    "type": "number",
                                    "description": "土地面積 (㎡)。※必須",
                                    "example": 100.0
                                },
                                "maguchi": {
                                    "type": "number",
                                    "description": LABEL_SETUDO_MAGUCHI,
                                    "example": 6.5
                                },
                                "roadWidth": {
                                    "type": "number",
                                    "description": LABEL_ZENMEN_DOURO_FUKUIN,
                                    "example": 4.0
                                },
                                "roadDirection": {
                                    "type": "string",
                                    "description": "道路方角（南、北、東、西など）",
                                    "example": "北"
                                },
                                "roadType": {
                                    "type": "string",
                                    "description": "道路種別（公道、私道）",
                                    "example": "公道"
                                },
                                "roadStructure": {
                                    "type": "string",
                                    "description": "接道構造（角地、一方道路など）",
                                    "example": "一方"
                                },
                                "setsudou": {
                                    "type": "string",
                                    "description": "接道状況詳細テキスト",
                                    "example": "北側道路4m公道"
                                },
                                "setback": {
                                    "type": "string",
                                    "description": "セットバック情報（例: \"要セットバック2.0㎡\"）",
                                    "example": "無"
                                },
                                "is_furuya": {
                                    "type": "number",
                                    "description": "古家ありフラグ (1.0: あり, 0.0: なし)。未指定でも備考や現況から自動抽出",
                                    "example": 0.0
                                },
                                "has_demolition_condition": {
                                    "type": "number",
                                    "description": "更地渡し・解体条件フラグ (1.0: 売主解体更地渡し, 0.0: 買主負担解体)",
                                    "example": 0.0
                                },
                                "furuya_bldg_area": {
                                    "type": "number",
                                    "description": "古家建物延床面積 (㎡)",
                                    "example": 80.0
                                },
                                "kagechi_ratio": {
                                    "type": "number",
                                    "description": "かげ地割合 (0.0〜1.0)。旗竿地や不整形地ペナルティ計算用",
                                    "example": 0.0
                                }
                            }
                        }
                    ]
                }
            },
            "responses": {
                "SuccessResponse": {
                    "description": "推定成功",
                    "content": {
                        MIME_APPLICATION_JSON: {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {
                                        "type": "boolean",
                                        "example": True
                                    },
                                    "property_type": {
                                        "type": "string",
                                        "example": "mansion"
                                    },
                                    "first_stage_predicted_price": {
                                        "type": "integer",
                                        "description": "一次推定理論価格（万円）",
                                        "example": 4420
                                    },
                                    "second_stage_predicted_price": {
                                        "type": "integer",
                                        "description": "二次推定精密理論価格（万円）",
                                        "example": 4580
                                    },
                                    "message": {
                                        "type": "string",
                                        "example": "Estimation completed successfully"
                                    }
                                }
                            }
                        }
                    }
                },
                "ErrorResponse": {
                    "description": "エラー発生",
                    "content": {
                        MIME_APPLICATION_JSON: {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {
                                        "type": "boolean",
                                        "example": False
                                    },
                                    "message": {
                                        "type": "string",
                                        "example": "Missing or invalid JSON request body"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-KEY",
                    "description": "API Key authentication header"
                }
            }
        }
    }

def generate_yaml(output_path=None, check_only=False):
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    target_path = output_path or os.path.join(base_dir, "docs", "api", "openapi.yaml")

    spec = get_openapi_spec_dict()
    yaml_content = yaml.dump(spec, allow_unicode=True, sort_keys=False, width=120)

    if check_only:
        if not os.path.exists(target_path):
            print(f"Error: {target_path} does not exist.")
            return False
        with open(target_path, "r", encoding="utf-8") as f:
            existing_content = f.read()
        existing_data = yaml.safe_load(existing_content)
        new_data = yaml.safe_load(yaml_content)
        if existing_data != new_data:
            print(f"Error: {target_path} is out of date with generated specification.")
            return False
        print("Success: OpenAPI spec is up-to-date.")
        return True

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"Successfully generated OpenAPI specification at {target_path}")
    return True

if __name__ == "__main__":
    check_mode = "--check" in sys.argv
    success = generate_yaml(check_only=check_mode)
    if not success:
        sys.exit(1)
    sys.exit(0)
