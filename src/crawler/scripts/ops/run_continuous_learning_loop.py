# -*- coding: utf-8 -*-
"""
MLモデル継続的学習・再評価・残差分析ループスクリプト
MLモデルの学習 ➔ 全件バルク再評価 ➔ 予測誤差・残差分布の分析 ➔ 外れ値監視 を一貫してループ実行します。
"""
import os
import sys
import time
import json
import logging
import subprocess
import shutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRAWLER_DIR = os.path.dirname(SCRIPTS_DIR)
PROJECT_DIR = os.path.dirname(CRAWLER_DIR)

def run_command(cmd, desc):
    logging.info(f"▶ [LOOP] {desc} 開始: {' '.join(cmd)}")
    t0 = time.time()
    env = os.environ.copy()
    env["PYTHONPATH"] = CRAWLER_DIR
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    elapsed = time.time() - t0
    if res.returncode == 0:
        logging.info(f"✔ [LOOP] {desc} 完了 (所要時間: {elapsed:.1f}秒)")
    else:
        logging.error(f"✘ [LOOP] {desc} 失敗 (終了コード: {res.returncode}):\n{res.stderr}\n{res.stdout}")
    return res

def execute_single_cycle(iteration=1, force_eval=True, train_model=False):
    logging.info(f"\n{'='*50}\n🔄 継続的改善サイクル #{iteration} 開始\n{'='*50}")
    
    # 0. モデル再学習 (指定時)
    if train_model:
        train_cmd = [sys.executable, os.path.join(CRAWLER_DIR, "package", "ml", "train.py")]
        run_command(train_cmd, "新特徴量によるMLモデル全件再学習")

    # 1. バルク再評価の実行
    eval_cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "ops", "run_bulk_ml_evaluation.py")]
    if force_eval:
        eval_cmd.append("--force")
    run_command(eval_cmd, "全件バルクML再評価")
    
    # 2. 予測残差・誤差分布分析の実行
    analyze_cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "debug_tools", "analyze_prediction_distribution.py")]
    res_analyze = run_command(analyze_cmd, "残差・誤差分布分析およびプロット生成")
    
    # 生成されたプロット画像をアーティファクトおよびルートへコピー
    src_png = os.path.join(SCRIPTS_DIR, "debug_tools", "prediction_residuals_distribution.png")
    dst_artifact = r"C:\Users\weare\.gemini\antigravity-ide\brain\6a365ac0-43d7-401e-aac6-d49373a5663f\prediction_residuals_distribution.png"
    if os.path.exists(src_png):
        try:
            shutil.copy2(src_png, dst_artifact)
            logging.info(f"✔ プロット画像をアーティファクトに同期: {dst_artifact}")
        except Exception as e:
            logging.warning(f"プロット画像のコピーに失敗: {e}")

    # 分析結果サマリーの標準出力
    if res_analyze.stdout:
        print("\n--- 最新の分析サマリー ---")
        lines = res_analyze.stdout.splitlines()
        summary_started = False
        for line in lines:
            if "STATISTICAL SUMMARY" in line:
                summary_started = True
            if summary_started:
                print(line)
                
    logging.info(f"✔ サイクル #{iteration} 完了")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Continuous ML Evaluation & Residual Analysis Loop")
    parser.add_argument("--once", action="store_true", help="1サイクルのみ実行して終了")
    parser.add_argument("--interval", type=int, default=300, help="サイクル間の待機秒数（デフォルト300秒）")
    args = parser.parse_args()
    
    iteration = 1
    while True:
        try:
            execute_single_cycle(iteration=iteration, force_eval=True)
        except Exception as e:
            logging.exception(f"サイクル #{iteration} で予期せぬ例外: {e}")
            
        if args.once:
            break
            
        logging.info(f"⏳ 次のサイクルまで {args.interval} 秒待機中... (Ctrl+C で中断)")
        time.sleep(args.interval)
        iteration += 1

if __name__ == "__main__":
    main()
