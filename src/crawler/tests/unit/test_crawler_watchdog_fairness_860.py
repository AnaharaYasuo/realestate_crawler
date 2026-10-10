import unittest
from unittest.mock import MagicMock
from package.utils.crawler_watchdog import update_watchdog_progress


class TestCrawlerWatchdogFairness860(unittest.TestCase):
    """run_all_crawlers のウォッチドッグ監視が全ジョブ公平に更新されるかを検証 (Issue #860)"""

    def test_watchdog_loop_updates_all_eligible_jobs_without_break(self):
        """15秒以上経過した全ジョブが1回の監視ループで公平にチェックされること"""
        now = 1000.0

        # 3つのアクティブジョブをモック (proc, company, ptype, start_t, start_dt, last_act, prev_db_cnt, last_check_t)
        # ジョブ1: 20秒前にチェック (要チェック)
        # ジョブ2: 30秒前にチェック (要チェック)
        # ジョブ3: 5秒前にチェック (スキップ)
        p1 = MagicMock()
        p2 = MagicMock()
        p3 = MagicMock()

        active_processes = {
            1: (p1, "totate", "mansion", 900.0, None, 900.0, 10, 980.0),
            2: (p2, "sumai1", "kodate", 900.0, None, 900.0, 5, 970.0),
            3: (p3, "mitsui", "tochi", 900.0, None, 995.0, 20, 995.0),
        }

        # get_count_for_job をモックして件数増分を返す
        def fake_get_count(company, ptype, start_dt):
            if company == "totate":
                return 15, 0, 15  # 10 -> 15 (増加)
            elif company == "sumai1":
                return 8, 0, 8   # 5 -> 8 (増加)
            return 20, 0, 20

        # 本番の共有関数 update_watchdog_progress を呼び出してテスト
        update_watchdog_progress(active_processes, now, fake_get_count)

        # 検証: ジョブ1とジョブ2の双方で last_act が更新されていること (breakがあるとジョブ2が更新されない)
        self.assertEqual(active_processes[1][5], 1000.0, "Job 1 last_act must be updated to now")
        self.assertEqual(active_processes[2][5], 1000.0, "Job 2 last_act must be updated to now")
        # ジョブ3は15秒未満のため変更されないこと
        self.assertEqual(active_processes[3][5], 995.0, "Job 3 last_act must remain untouched")
