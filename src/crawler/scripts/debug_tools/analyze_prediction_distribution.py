# -*- coding: utf-8 -*-
"""
価格推定結果の予測値 vs 実際値（売出価格）残差・誤差分布分析スクリプト
"""
import os
import sys
import json
import numpy as np
import pandas as pd
import scipy.stats as stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_crawler_dir = os.path.dirname(_scripts_dir)
sys.path.insert(0, _crawler_dir)

import realestateSettings
realestateSettings.configure()

from django.apps import apps
from package.models.evaluation import PropertyEvaluation

COMPANIES = [
    "mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1", "mizuho",
    "odakyu", "afr", "sekisui", "daiwa", "totate", "athome", "homes", "seibu",
    "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim", "sumirin", "keio"
]

def analyze():
    print("Fetching actual prices from portal tables...")
    app_config = apps.get_app_config("package")
    url_to_price = {}
    
    for model in app_config.get_models():
        model_name = model.__name__.lower()
        if not any(model_name.startswith(c) for c in COMPANIES):
            continue
        field_names = [f.name for f in model._meta.get_fields()]
        if "pageUrl" in field_names:
            url_field = "pageUrl"
        elif "url" in field_names:
            url_field = "url"
        else:
            url_field = None
        if not url_field or "price" not in field_names:
            continue
        try:
            for row in model.objects.filter(price__isnull=False, price__gt=0).values(url_field, "price"):
                u = row.get(url_field)
                p = row.get("price")
                if u and p:
                    try:
                        p_val = float(p) / 10000.0
                        if p_val > 0:
                            url_to_price[u] = p_val
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            print(f"Warning: failed for {model.__name__}: {e}")
            
    print(f"Total properties with actual price indexed: {len(url_to_price):,}")
    
    print("Matching with PropertyEvaluation records...")
    eval_qs = PropertyEvaluation.objects.filter(first_stage_predicted_price__isnull=False)
    total_evals = eval_qs.count()
    print(f"Total PropertyEvaluation with predicted price: {total_evals:,}")
    
    data = []
    for ev in eval_qs.only("property_url", "company", "property_type", "first_stage_predicted_price"):
        act_p = url_to_price.get(ev.property_url)
        if not act_p:
            continue
        pred_p = float(ev.first_stage_predicted_price)
        if pred_p <= 0 or act_p <= 0:
            continue
            
        data.append({
            "url": ev.property_url,
            "company": ev.company,
            "property_type": ev.property_type,
            "actual_price": act_p,
            "pred_price": pred_p,
            "diff": pred_p - act_p,
            "pct_error": (pred_p - act_p) / act_p * 100.0,
            "abs_pct_error": abs(pred_p - act_p) / act_p * 100.0,
            "log_diff": np.log(pred_p) - np.log(act_p)
        })
        
    df = pd.DataFrame(data)
    print(f"Matched matched samples: {len(df):,}")
    if len(df) == 0:
        print("No matched samples found!")
        return

    # Basic Statistics
    log_diff = df["log_diff"].values
    pct_err = df["pct_error"].values
    abs_pct_err = df["abs_pct_error"].values
    
    mean_log_diff = float(np.mean(log_diff))
    std_log_diff = float(np.std(log_diff))
    median_log_diff = float(np.median(log_diff))
    skew_log_diff = float(stats.skew(log_diff))
    kurt_log_diff = float(stats.kurtosis(log_diff)) # excess kurtosis (normal=0)
    
    mean_pct_err = float(np.mean(pct_err))
    median_pct_err = float(np.median(pct_err))
    std_pct_err = float(np.std(pct_err))
    mape = float(np.mean(abs_pct_err))
    median_ape = float(np.median(abs_pct_err))
    
    # Normality test (D'Agostino and Pearson's test)
    _, p_val = stats.normaltest(log_diff)
    
    within_10pct = float(np.mean(abs_pct_err <= 10.0) * 100.0)
    within_20pct = float(np.mean(abs_pct_err <= 20.0) * 100.0)
    within_30pct = float(np.mean(abs_pct_err <= 30.0) * 100.0)
    
    stats_summary = {
        "sample_count": len(df),
        "log_diff": {
            "mean_bias": round(mean_log_diff, 4),
            "std": round(std_log_diff, 4),
            "median": round(median_log_diff, 4),
            "skewness": round(skew_log_diff, 4),
            "excess_kurtosis": round(kurt_log_diff, 4),
            "normality_test_p": float(p_val)
        },
        "pct_error": {
            "mean": round(mean_pct_err, 2),
            "median": round(median_pct_err, 2),
            "std": round(std_pct_err, 2),
            "mape": round(mape, 2),
            "median_ape": round(median_ape, 2)
        },
        "accuracy_bands": {
            "within_10pct": round(within_10pct, 2),
            "within_20pct": round(within_20pct, 2),
            "within_30pct": round(within_30pct, 2)
        }
    }
    
    print("\n================ STATISTICAL SUMMARY ================")
    print(json.dumps(stats_summary, indent=2, ensure_ascii=False))
    
    # By Property Type
    print("\n--- By Property Type ---")
    by_ptype = {}
    for pt, group in df.groupby("property_type"):
        if len(group) < 10:
            continue
        pt_mape = float(np.mean(group["abs_pct_error"]))
        pt_bias = float(np.mean(group["log_diff"]))
        pt_within20 = float(np.mean(group["abs_pct_error"] <= 20.0) * 100.0)
        by_ptype[pt] = {
            "count": len(group),
            "mape": round(pt_mape, 2),
            "log_bias": round(pt_bias, 4),
            "within_20pct": round(pt_within20, 2)
        }
        print(f"{pt:15s}: count={len(group):5d}, MAPE={pt_mape:5.2f}%, log_bias={pt_bias:+6.4f}, within_20%={pt_within20:5.1f}%")
        
    # Plotting
    print("\nGenerating plots...")
    fig = plt.figure(figsize=(18, 12))
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
    
    # 1. Log Residual Distribution vs Gaussian Curve
    ax1 = fig.add_subplot(2, 3, 1)
    # Filter reasonable bounds for display
    plot_log_diff = log_diff[(log_diff >= -1.0) & (log_diff <= 1.0)]
    ax1.hist(plot_log_diff, bins=60, density=True, alpha=0.6, color='#2b5c8f', edgecolor='black', linewidth=0.5, label='Actual Log Residuals')
    
    # Fit normal curve
    x_range = np.linspace(-1.0, 1.0, 300)
    norm_pdf = stats.norm.pdf(x_range, loc=mean_log_diff, scale=std_log_diff)
    ax1.plot(x_range, norm_pdf, 'r-', linewidth=2.5, label=f'Normal Fit (μ={mean_log_diff:+.3f}, σ={std_log_diff:.3f})')
    ax1.axvline(0, color='gray', linestyle='--', linewidth=1.2, label='Zero Error (Target)')
    ax1.axvline(mean_log_diff, color='red', linestyle=':', linewidth=1.5, label=f'Mean Bias ({mean_log_diff:+.3f})')
    ax1.set_title(f"1. Log Residual Distribution ln(Pred / Act)\nSkewness: {skew_log_diff:+.3f}, Kurtosis: {kurt_log_diff:+.3f}", fontsize=12, fontweight='bold')
    ax1.set_xlabel("ln(Predicted Price) - ln(Actual Price)")
    ax1.set_ylabel("Probability Density")
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(True, alpha=0.3)
    
    # 2. Percentage Error Distribution (-50% to +50%)
    ax2 = fig.add_subplot(2, 3, 2)
    plot_pct = pct_err[(pct_err >= -60) & (pct_err <= 60)]
    ax2.hist(plot_pct, bins=60, density=True, alpha=0.6, color='#1b7837', edgecolor='black', linewidth=0.5, label='Residual %')
    pct_x = np.linspace(-60, 60, 300)
    pct_norm = stats.norm.pdf(pct_x, loc=mean_pct_err, scale=std_pct_err)
    ax2.plot(pct_x, pct_norm, 'k--', linewidth=2.0, label=f'Normal Fit (μ={mean_pct_err:+.1f}%)')
    ax2.axvline(0, color='red', linestyle='-', linewidth=1.2, label='Zero Bias')
    ax2.axvline(median_pct_err, color='blue', linestyle=':', linewidth=1.5, label=f'Median Error: {median_pct_err:+.1f}%')
    ax2.set_title(f"2. Relative Percentage Error Distribution (%)\nMAPE: {mape:.1f}%, Median APE: {median_ape:.1f}%", fontsize=12, fontweight='bold')
    ax2.set_xlabel("Error Percentage: (Pred - Act) / Act * 100 (%)")
    ax2.set_ylabel("Density")
    ax2.legend(loc='upper right', fontsize=8)
    ax2.grid(True, alpha=0.3)
    
    # 3. Quantile-Quantile (Q-Q) Plot for Normality Check
    ax3 = fig.add_subplot(2, 3, 3)
    # Standardize sample
    std_resids = (plot_log_diff - np.mean(plot_log_diff)) / np.std(plot_log_diff)
    stats.probplot(std_resids, dist="norm", plot=ax3)
    ax3.set_title("3. Normal Q-Q Plot of Standardized Residuals\n(Straight red line = Perfect Normal Distribution)", fontsize=12, fontweight='bold')
    ax3.set_xlabel("Theoretical Normal Quantiles")
    ax3.set_ylabel("Sample Quantiles")
    ax3.grid(True, alpha=0.3)
    
    # 4. Actual vs Predicted Price Scatter Plot
    ax4 = fig.add_subplot(2, 3, 4)
    # Filter to under 30,000 万円 (3億円) for clear visual
    sub_df = df[(df["actual_price"] <= 20000) & (df["pred_price"] <= 20000)]
    if len(sub_df) > 5000:
        sub_sample = sub_df.sample(5000, random_state=42)
    else:
        sub_sample = sub_df
    ax4.scatter(sub_sample["actual_price"], sub_sample["pred_price"], alpha=0.25, color='#4575b4', s=12, edgecolors='none', label=f'Samples (N={len(sub_sample)})')
    max_val = max(sub_sample["actual_price"].max(), sub_sample["pred_price"].max())
    ax4.plot([0, max_val], [0, max_val], 'r-', linewidth=1.8, label='Ideal y = x')
    ax4.plot([0, max_val], [0, max_val * 1.15], 'r--', alpha=0.6, label='±15% Tolerance Band')
    ax4.plot([0, max_val], [0, max_val * 0.85], 'r--', alpha=0.6)
    ax4.set_title("4. Actual Price vs Predicted Price (万円)\nPoints close to diagonal = High Accuracy", fontsize=12, fontweight='bold')
    ax4.set_xlabel("Actual Price (万円)")
    ax4.set_ylabel("Predicted Price (万円)")
    ax4.legend(loc='upper left', fontsize=8)
    ax4.grid(True, alpha=0.3)
    
    # 5. Error Distribution by Major Property Types (Boxplot)
    ax5 = fig.add_subplot(2, 3, 5)
    top_ptypes = [pt for pt, count in df["property_type"].value_counts().items() if count >= 50][:5]
    box_data = [df[(df["property_type"] == pt) & (df["pct_error"] >= -50) & (df["pct_error"] <= 50)]["pct_error"] for pt in top_ptypes]
    bp = ax5.boxplot(box_data, patch_artist=True, showmeans=True)
    ax5.set_xticks(range(1, len(top_ptypes) + 1))
    ax5.set_xticklabels(top_ptypes)
    colors = ['#74add1', '#a6d96a', '#fdae61', '#f46d43', '#fee08b']
    for patch, color in zip(bp['boxes'], colors[:len(top_ptypes)]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax5.axhline(0, color='red', linestyle='--', linewidth=1)
    ax5.set_title("5. Percentage Error by Property Type\n(Symmetric box around 0 = Well Balanced)", fontsize=12, fontweight='bold')
    ax5.set_ylabel("Error %: (Pred - Act) / Act * 100 (%)")
    ax5.grid(True, alpha=0.3)
    
    # 6. Cumulative Accuracy Profile (% within threshold)
    ax6 = fig.add_subplot(2, 3, 6)
    thresholds = np.linspace(1, 50, 50)
    cum_acc = [np.mean(abs_pct_err <= th) * 100.0 for th in thresholds]
    ax6.plot(thresholds, cum_acc, 'b-', linewidth=2.5, label='Cumulative Accuracy')
    ax6.axvline(10, color='orange', linestyle=':', label=f'Within ±10%: {within_10pct:.1f}%')
    ax6.axvline(20, color='green', linestyle=':', label=f'Within ±20%: {within_20pct:.1f}%')
    ax6.axvline(30, color='purple', linestyle=':', label=f'Within ±30%: {within_30pct:.1f}%')
    ax6.set_title("6. Accuracy by Error Tolerance Threshold (%)\nFraction of predictions within ±X% error", fontsize=12, fontweight='bold')
    ax6.set_xlabel("Error Tolerance Threshold (±%)")
    ax6.set_ylabel("Properties within Threshold (%)")
    ax6.set_ylim(0, 100)
    ax6.legend(loc='lower right', fontsize=8)
    ax6.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_path = "/app/prediction_residuals_distribution.png"
    plt.savefig(output_path, dpi=150)
    print(f"\nPlot saved to: {output_path}")
    return df

if __name__ == "__main__":
    analyze()
