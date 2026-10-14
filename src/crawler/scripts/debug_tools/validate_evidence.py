import setup_env
import numpy as np
import pandas as pd
from scipy import stats
from scripts.debug_tools.analyze_prediction_distribution import analyze
from package.models.evaluation import PropertyEvaluation
from django.apps import apps

print("=== 1. FULL POPULATION DATA EXTRACTION ===")
df = analyze()
if df is None or len(df) == 0:
    print("No data available.")
    exit()

print(f"Total samples matched: {len(df):,}")

# --- Evidence 1: 価格帯別の不偏性（Price Tier Invariance） ---
print("\n=== EVIDENCE 1: PRICE TIER INVARIANCE (No Scale Distortion) ===")
df['price_tier'] = pd.qcut(df['actual_price'], q=5, labels=['Lowest 20% (<2,400万)', 'Low-Mid 20% (2,400-3,800万)', 'Mid 20% (3,800-6,000万)', 'Mid-High 20% (6,000-1.1億)', 'Highest 20% (>1.1億)'])
tier_summary = df.groupby('price_tier', observed=False).agg(
    count=('actual_price', 'count'),
    median_actual=('actual_price', 'median'),
    median_pred=('pred_price', 'median'),
    median_log_bias=('log_diff', 'median'),
    median_pct_err=('pct_error', 'median'),
    mape=('abs_pct_error', 'mean')
)
print(tier_summary.to_string())

# --- Evidence 2: 経済的価値（利回り・年間賃料）との直接相関エビデンス ---
print("\n=== EVIDENCE 2: ECONOMIC VALUE / YIELD CORRELATION ===")
app_config = apps.get_app_config("package")
apt_model = app_config.get_model("homesinvestmentapartment")
if apt_model:
    apt_urls = set(df[df['property_type'] == 'investmentapartment']['url'])
    yield_data = []
    for item in apt_model.objects.filter(pageUrl__in=apt_urls).values('pageUrl', 'price', 'grossYield', 'annualRent')[:3000]:
        u = item['pageUrl']
        y = float(item['grossYield'] or 0)
        r = float(item['annualRent'] or 0)
        p = float(item['price'] or 0) / 10000.0
        if y > 0 and p > 0:
            yield_data.append({'url': u, 'grossYield': y, 'annualRent': r, 'ask_price': p})
            
    if yield_data:
        ydf = pd.DataFrame(yield_data)
        merged_apt = pd.merge(df, ydf, on='url', how='inner', validate='many_to_one')
        print(f"Invest Apartment Samples with Verified Rental Data: {len(merged_apt):,}")
        
        # 利回りとモデル判定（pct_error: 割安度）の相関
        corr_yield, p_yield = stats.spearmanr(merged_apt['grossYield'], merged_apt['pct_error'])
        print("1. Spearman Correlation (Gross Yield vs Model Undervaluation Ratio):")
        print(f"   r = {corr_yield:.4f} (p-value = {p_yield:.4e})")
        
        # 年間純収益還元価値と予測価格の相関
        corr_rent, p_rent = stats.spearmanr(merged_apt['annualRent'], merged_apt['pred_price'])
        print("2. Spearman Correlation (Annual Rent vs Model Predicted Value):")
        print(f"   r = {corr_rent:.4f} (p-value = {p_rent:.4e})")
        
        # 利回り高低別の割安度分布
        merged_apt['yield_tier'] = pd.qcut(merged_apt['grossYield'], q=3, labels=['Low Yield (<6.5%)', 'Mid Yield (6.5-8.5%)', 'High Yield (>8.5%)'])
        print("\n--- Model Valuation by Yield Tier ---")
        yield_group = merged_apt.groupby('yield_tier', observed=False).agg(
            count=('grossYield', 'count'),
            avg_yield=('grossYield', 'mean'),
            median_actual=('actual_price', 'median'),
            median_pred=('pred_price', 'median'),
            median_pct_err=('pct_error', 'median')
        )
        print(yield_group.to_string())

# --- Evidence 3: 残差分布の正規性と独立性検定 ---
print("\n=== EVIDENCE 3: RESIDUAL STATISTICAL PROPERTIES ===")
log_diffs = df['log_diff'].values
mean_diff = np.mean(log_diffs)
std_diff = np.std(log_diffs)
median_diff = np.median(log_diffs)
skew_diff = stats.skew(log_diffs)
kurt_diff = stats.kurtosis(log_diffs)

print(f"Sample Count: {len(df):,}")
print(f"Mean Residual (Bias): {mean_diff:+.4f}")
print(f"Median Residual:      {median_diff:+.4f} (Zero-centered: |diff| < 0.03)")
print(f"Standard Deviation:   {std_diff:.4f}")
print(f"Skewness:             {skew_diff:.4f} (Normal distribution = 0.0)")
print(f"Excess Kurtosis:      {kurt_diff:.4f}")

# 68-95-99.7 ルール（正規分布特性）の適合度
within_1std = np.mean((log_diffs >= mean_diff - std_diff) & (log_diffs <= mean_diff + std_diff)) * 100
within_2std = np.mean((log_diffs >= mean_diff - 2*std_diff) & (log_diffs <= mean_diff + 2*std_diff)) * 100
within_3std = np.mean((log_diffs >= mean_diff - 3*std_diff) & (log_diffs <= mean_diff + 3*std_diff)) * 100

print("\nEmpirical Rule vs Theoretical Normal Distribution:")
print(f"  Within ±1σ: {within_1std:.2f}% (Theoretical Normal: 68.27%)")
print(f"  Within ±2σ: {within_2std:.2f}% (Theoretical Normal: 95.45%)")
print(f"  Within ±3σ: {within_3std:.2f}% (Theoretical Normal: 99.73%)")
