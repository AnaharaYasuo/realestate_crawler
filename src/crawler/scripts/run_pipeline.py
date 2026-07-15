# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import time
import logging
import datetime

# ロギング設定
log_dir = "/app/logs"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(log_dir, "pipeline.log"), encoding="utf-8")
    ]
)

def run_command(cmd, desc):
    logging.info(f"=== [START] {desc} ===")
    logging.info(f"Command: {' '.join(cmd)}")
    start_time = time.time()
    
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # リアルタイムで子プロセスの出力をログ化
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        # scheduler.logやtrain.logなどと競合しないよう、コンソールに出力
        print(line, end='', flush=True)
        
    proc.wait()
    elapsed = time.time() - start_time
    
    if proc.returncode != 0:
        logging.error(f"=== [FAILED] {desc} (Exit Code: {proc.returncode}, Time: {int(elapsed)}s) ===")
        raise RuntimeError(f"Step '{desc}' failed with exit code {proc.returncode}")
        
    logging.info(f"=== [SUCCESS] {desc} (Time: {int(elapsed)}s) ===")

def main():
    logging.info("=============================================================")
    logging.info("Starting REALESTATE CRAWLER & ML ESTIMATION PIPELINE")
    logging.info("=============================================================")
    
    try:
        # Step 1: 全件クローリング（2並列実行、PC負荷軽減）
        # ※CRAWL_COOLDOWN_SEC は本番パラメータの 180秒 を適用。
        # クローラー自体の物件数リミッター（CRAWLER_LIMIT）は空（上限なし全件）にするため env で指定なし。
        # ただし、全件クロールが非常に長引く場合を考慮し、呼び出し側はそのままキックします。
        run_command([
            sys.executable,
            "/app/src/crawler/scripts/run_all_crawlers.py",
            "--parallel=2"
        ], "Step 1/5: Parallel Crawling (All websites, all properties)")
        
        # Step 1.5 (2/5): 不正データ自動検証 & クレンジング & HTMLエラー監視
        run_command([
            sys.executable,
            "/app/src/crawler/scripts/validate_data.py"
        ], "Step 2/5: Scraping Data Validation & Automated Cleansing")
        
        # AI自己修復用のバグ指示書生成
        run_command([
            sys.executable,
            "/app/src/crawler/scripts/auto_heal_parsers.py"
        ], "Step 2.5/5: Auto-Heal Instruction Generation for AI Agent")
        
        # Step 2 (3/5): 最新データによるMLモデル再学習
        run_command([
            sys.executable,
            "/app/src/crawler/package/ml/train.py"
        ], "Step 3/5: ML Model Re-Training (LightGBM, XGBoost, CatBoost, RandomForest)")
        
        # Step 3 (4/5): 一括価格予測・投資シミュレーション評価のDB更新
        run_command([
            sys.executable,
            "/app/src/crawler/scripts/evaluate_all_properties.py"
        ], "Step 4/5: Batch Estimation & Investment Evaluation")
        
        # Step 4 (5/5): お宝物件のスクリーニング & Slack通知
        run_command([
            sys.executable,
            "/app/src/crawler/scripts/send_alerts.py"
        ], "Step 5/5: Slack Notification (Hot Property Recommendation)")
        
        logging.info("=============================================================")
        logging.info("PIPELINE COMPLETED SUCCESSFULLY! All steps finished.")
        logging.info("=============================================================")
        
    except Exception as e:
        logging.error(f"Pipeline crashed due to unhandled exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
