# マクロ時系列トレンド予測モデル & モメンタム特徴量仕様書 (Macro Time Series Forecaster)

## 1. 概要と背景 (Overview)

不動産相場は、低頻度（月次）かつマクロ経済環境（金利、不動産価格指数 REPI、日経平均、REIT指数、建設物価指数）に強い連動性を持ちます。
深層学習系（Transformer等）はデータ点数不足（過去10年で120点）により過学習のリスクが極めて高いため、本システムでは **「正則化多変量自己回帰 (Ridge Vector Autoregression) ＋ 指数平滑化モメンタム (Exponential Smoothing Momentum)」** による軽量・高精度な時系列分析モデルを採用します。

マクロ時系列モデルが算出した「過去変動モメンタム」および「将来3〜6ヶ月のトレンド予測値」を、個別物件推論モデル（LightGBM / XGBoost / CatBoost）の特徴量として注入することで、金利上昇や相場高騰の局面変化に即応する価格推定を実現します。

---

## 2. 時系列数理モデル (Mathematical Formulation)

### 2.1 状態ベクトル
各月 $t$ におけるマクロ指標ベクトル $X_t \in \mathbb{R}^k$:
$$X_t = \begin{bmatrix} \text{REPI}_{\text{mansion}, t} \\ \text{REPI}_{\text{kodate}, t} \\ \text{REPI}_{\text{tochi}, t} \\ \text{JGB}_{10y, t} \\ \text{Nikkei}_{225, t} \\ \text{REIT}_{t} \\ \text{ConstCost}_{t} \end{bmatrix}$$

### 2.2 正則化自己回帰モデル (Ridge VAR($p$))
過去 $p$ ヶ月（デフォルト $p=3$）のラグ値から、次月以降の指標を予測：
$$X_t = c + \sum_{i=1}^p A_i X_{t-i} + \epsilon_t$$
過学習防止のため、L2正則化（Ridge penalty $\lambda$）を適用して係数行列 $A_i$ を推定します。

### 2.3 モメンタム指標 (Momentum Features)
各時点 $t$ において、以下の変化率・差分指標を算出：
1. **REPI 3ヶ月・6ヶ月モメンタム**:
   $$\text{repi\_growth\_3m} = \frac{\text{REPI}_t - \text{REPI}_{t-3}}{\text{REPI}_{t-3}} \times 100$$
   $$\text{repi\_growth\_6m} = \frac{\text{REPI}_t - \text{REPI}_{t-6}}{\text{REPI}_{t-6}} \times 100$$
2. **10年国債利回り変動幅 (JGB Momentum)**:
   $$\text{jgb\_diff\_3m} = \text{JGB}_{10y, t} - \text{JGB}_{10y, t-3} \quad (\%)$$
3. **建設物価指数モメンタム**:
   $$\text{const\_cost\_growth\_6m} = \frac{\text{ConstCost}_t - \text{ConstCost}_{t-6}}{\text{ConstCost}_{t-6}} \times 100$$
4. **相場レジームスコア (Regime Score: -1.0 〜 +1.0)**:
   REPIの上昇トレンド、金利環境、REIT指数の合成スコア。

---

## 3. インターフェース仕様 (Class Interface)

```python
class MacroTrendForecaster:
    def fit(self, df_macro: pd.DataFrame):
        """DB上の MacroEconomicIndex 時系列データを学習"""
        pass

    def predict_future(self, steps: int = 6) -> pd.DataFrame:
        """将来 steps ヶ月先までのマクロ指標予測値を返却"""
        pass

    def get_features_for_month(self, year_month: str, ptype: str = "mansion") -> dict:
        """指定年月のモメンタムおよび予測トレンド特徴量辞書を返却"""
        pass
```

---

## 4. 組み込み先と運用サイクル

1. **学習時 (`train.py`)**:
   - `features.py` 経由で全学習データにマクロモメンタム特徴量を付与。
2. **推論時 (`predict.py`)**:
   - 物件の掲載年月（または最新年月）に基づき、最新の相場モメンタムと予測トレンドを特徴量としてリアルタイム注入。
3. **日次診断 (`run_daily_prediction_diagnostics.py`)**:
   - マクロモメンタムが急変した地域・種別でのズレを追跡監視。
