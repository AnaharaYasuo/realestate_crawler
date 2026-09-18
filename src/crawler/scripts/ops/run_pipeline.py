# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import time
import logging

# ロギング設定
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
log_dir = os.path.join(_project_root, "logs")
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
    if proc.stdout is not None:
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
    import argparse
    parser = argparse.ArgumentParser(description="Real Estate Pipeline")
    parser.add_argument("--skip-portals", action="store_true", help="Skip large portal sites (homes, athome)")
    args = parser.parse_args()

    logging.info("=============================================================")
    logging.info(f"Starting REALESTATE CRAWLER & ML ESTIMATION PIPELINE (skip_portals={args.skip_portals})")
    logging.info("=============================================================")
    
    current_dir = os.path.dirname(os.path.abspath(__file__)) # .../scripts/ops
    scripts_dir = os.path.dirname(current_dir)              # .../scripts
    crawler_dir = os.path.dirname(scripts_dir)              # .../crawler
    project_root = os.path.dirname(os.path.dirname(crawler_dir)) # root
    
    debug_tools_dir = os.path.join(scripts_dir, "debug_tools")
    maintenance_dir = os.path.join(scripts_dir, "maintenance")
    ops_dir = current_dir

    failed_slack_file = os.path.join(crawler_dir, "failed_slack_notifications.json")
    # 起動前に過去のエラーログをクリア
    if os.path.exists(failed_slack_file):
        try:
            os.remove(failed_slack_file)
        except Exception:
            pass
            
    try:
        # Step 0: Slack Connection Pre-flight Check
        run_command([
            sys.executable,
            os.path.join(debug_tools_dir, "check_slack_connection.py")
        ], "Step 0/5: Slack Connection Pre-flight Check")

        # Step 0.5: Database Schema Migration (テーブル未初期化・マイグレーション自動反映)
        run_command([
            sys.executable,
            os.path.join(crawler_dir, "manage.py"),
            "migrate",
            "--noinput"
        ], "Step 0.5/5: Database Schema Migration")

        # Step 1: クローリング（並列実行）
        crawl_cmd = [sys.executable, os.path.join(ops_dir, "run_all_crawlers.py")]
        if args.skip_portals:
            crawl_cmd.append("--skip-portals")
        run_command(crawl_cmd, f"Step 1/5: Parallel Crawling{' [Skip Portals]' if args.skip_portals else ''}")
        
        # Step 1.5 (2/5): 不正データ自動検証 & クレンジング & HTMLエラー監視
        run_command([
            sys.executable,
            os.path.join(maintenance_dir, "validate_data.py")
        ], "Step 2/5: Scraping Data Validation & Automated Cleansing")
        
        # AI自己修復用のバグ指示書生成
        run_command([
            sys.executable,
            os.path.join(debug_tools_dir, "auto_heal_parsers.py")
        ], "Step 2.5/5: Auto-Heal Instruction Generation for AI Agent")
        
        # Step 2 (3/5): 最新データによるMLモデル再学習
        run_command([
            sys.executable,
            os.path.join(crawler_dir, "package", "ml", "train.py")
        ], "Step 3/5: ML Model Re-Training (LightGBM, XGBoost, CatBoost, RandomForest)")
        
        # Step 3 (4/5): 一括価格予測・投資シミュレーション評価のDB更新 (バルクML推論)
        eval_cmd = [sys.executable, os.path.join(ops_dir, "run_bulk_ml_evaluation.py")]
        if args.skip_portals:
            eval_cmd.append("--skip-portals")
        run_command(eval_cmd, f"Step 4/5: Batch Estimation & Investment Evaluation{' [Skip Portals]' if args.skip_portals else ''}")
        
        # Step 4 (5/5): お宝物件のスクリーニング & Slack通知
        run_command([
            sys.executable,
            os.path.join(ops_dir, "send_recommendations.py")
        ], "Step 5/5: Slack Notification (Hot Property Recommendation)")

        
        # パイプライン全体におけるSlack送信不達チェック
        if os.path.exists(failed_slack_file):
            import json
            try:
                with open(failed_slack_file, "r", encoding="utf-8") as f:
                    failed_msgs = json.load(f)
                if failed_msgs:
                    logging.critical(f"❌ 【深刻なエラー】 パイプライン中に送信されるべき Slack メッセージが不達となっています（計 {len(failed_msgs)} 件）。")
                    for m in failed_msgs:
                        logging.critical(f"  - [{m['timestamp']}] Channel: {m['channel']} | Error: {m['error']} | Preview: {m['message_preview']}")
                    raise RuntimeError("Pipeline finished but some Slack notifications were not delivered successfully.")
            except Exception as fe:
                if isinstance(fe, RuntimeError):
                    raise fe
                    
        logging.info("=============================================================")
        logging.info("PIPELINE COMPLETED SUCCESSFULLY! All steps finished.")
        logging.info("=============================================================")
        
    except Exception as e:
        logging.error(f"Pipeline crashed due to unhandled exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
