import setup_env
import os
import pandas as pd
from scripts.debug_tools.analyze_prediction_distribution import analyze

df = analyze()
if df is None or len(df) == 0:
    print("No data returned.")
    exit()

print(f"\nTotal samples: {len(df):,}")

# Kodate extreme outliers
kodate_df = df[df['property_type'] == 'kodate']
print(f"\n=== KODATE STATS (N={len(kodate_df):,}) ===")
print(f"Median pct_error: {kodate_df['pct_error'].median():.2f}%")
print(f"Mean log_diff: {kodate_df['log_diff'].mean():.4f}, Median log_diff: {kodate_df['log_diff'].median():.4f}")
print(f"MAPE: {kodate_df['abs_pct_error'].mean():.2f}%, Median APE: {kodate_df['abs_pct_error'].median():.2f}%")

print("\n--- KODATE WORST 10 OVER-PREDICTED ---")
worst_over = kodate_df.sort_values(by='pct_error', ascending=False).head(10)
for _, r in worst_over.iterrows():
    print(f"{r['company']} | Act: {int(r['actual_price']):,}万 | Pred: {int(r['pred_price']):,}万 | Err: +{r['pct_error']:.1f}% | URL: {r['url']}")

print("\n--- KODATE WORST 10 UNDER-PREDICTED ---")
worst_under = kodate_df.sort_values(by='pct_error', ascending=True).head(10)
for _, r in worst_under.iterrows():
    print(f"{r['company']} | Act: {int(r['actual_price']):,}万 | Pred: {int(r['pred_price']):,}万 | Err: {r['pct_error']:.1f}% | URL: {r['url']}")

# Mansion stats
mansion_df = df[df['property_type'] == 'mansion']
print(f"\n=== MANSION STATS (N={len(mansion_df):,}) ===")
print(f"Median pct_error: {mansion_df['pct_error'].median():.2f}%")
print(f"Mean log_diff: {mansion_df['log_diff'].mean():.4f}, Median log_diff: {mansion_df['log_diff'].median():.4f}")
print(f"MAPE: {mansion_df['abs_pct_error'].mean():.2f}%, Median APE: {mansion_df['abs_pct_error'].median():.2f}%")

print("\n--- MANSION WORST 10 OVER-PREDICTED ---")
m_over = mansion_df.sort_values(by='pct_error', ascending=False).head(10)
for _, r in m_over.iterrows():
    print(f"{r['company']} | Act: {int(r['actual_price']):,}万 | Pred: {int(r['pred_price']):,}万 | Err: +{r['pct_error']:.1f}% | URL: {r['url']}")

print("\n--- MANSION WORST 10 UNDER-PREDICTED ---")
m_under = mansion_df.sort_values(by='pct_error', ascending=True).head(10)
for _, r in m_under.iterrows():
    print(f"{r['company']} | Act: {int(r['actual_price']):,}万 | Pred: {int(r['pred_price']):,}万 | Err: {r['pct_error']:.1f}% | URL: {r['url']}")
