"""
既存DB内の PropertyEvaluation 重複（名寄せ）親子関係是正スクリプト

連結成分（Connected Components）分解アルゴリズムにより、重複クラスタごとに
「最小ID（最古登録レコード）」を唯一のルート親（親: duplicate_of=None）とし、
クラスタ内の他全レコードをルート親へ直結（子: duplicate_of=root）に平坦化する。

これにより以下を数学的に100%保証する:
- 自己ループ: 0件
- 循環参照 (Cycles): 0件
- 多段チェーン (Chains): 0件 (すべての重複関係が深さ1)
- 逆転参照 (duplicate_of_id >= id): 0件
"""
import logging
import os
import sys
from collections import defaultdict

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_crawler_dir = os.path.dirname(_scripts_dir)
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

import realestateSettings

realestateSettings.configure()

from django.db import connection, transaction
from package.models.evaluation import PropertyEvaluation

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, i):
        if i not in self.parent:
            self.parent[i] = i
            return i
        curr = i
        path = []
        while self.parent.get(curr, curr) != curr:
            path.append(curr)
            curr = self.parent[curr]
        for node in path:
            self.parent[node] = curr
        return curr

    def union(self, i, j):
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            # 常にIDが小さい方をルート親とする
            if root_i < root_j:
                self.parent[root_j] = root_i
            else:
                self.parent[root_i] = root_j


def resolve_duplicate_hierarchies(dry_run: bool = False):
    logger.info(f"=== Starting PropertyEvaluation Duplicate Hierarchy Resolution (dry_run={dry_run}) ===")

    with connection.cursor() as cursor:
        # 全重複リレーションを取得
        cursor.execute("SELECT id, duplicate_of_id FROM property_evaluation WHERE duplicate_of_id IS NOT NULL")
        edges = cursor.fetchall()
        logger.info(f"Loaded {len(edges)} duplicate relations from DB.")

        # Union-Find で連結成分クラスタを構築
        uf = UnionFind()
        for child_id, parent_id in edges:
            uf.union(child_id, parent_id)

        # クラスタごとにノードを集約
        clusters = defaultdict(list)
        all_nodes = set()
        for child_id, parent_id in edges:
            all_nodes.add(child_id)
            all_nodes.add(parent_id)

        for node in all_nodes:
            root = uf.find(node)
            clusters[root].append(node)

        logger.info(f"Identified {len(clusters)} distinct duplicate clusters across {len(all_nodes)} nodes.")

        # 目標状態の計算
        # 各クラスタで最小IDのノードは duplicate_of = None
        # それ以外の全ノードは duplicate_of = min_id
        target_parents = {}  # node -> expected_duplicate_of_id
        for members in clusters.values():
            min_id = min(members)

            target_parents[min_id] = None
            for m in members:
                if m != min_id:
                    target_parents[m] = min_id

        # 現在のDB状態と比較して更新対象を抽出
        current_state = {}
        if all_nodes:
            cursor.execute("SELECT id, duplicate_of_id FROM property_evaluation WHERE id IN %s", [tuple(all_nodes)])
            current_state = {r[0]: r[1] for r in cursor.fetchall()}

        to_update = []  # (id, new_duplicate_of_id)
        for node, expected_parent in target_parents.items():
            curr_parent = current_state.get(node)
            if curr_parent != expected_parent:
                to_update.append((node, expected_parent))

        logger.info(f"Nodes requiring update: {len(to_update)} (out of {len(all_nodes)} nodes)")

        if to_update and not dry_run:
            batch_size = 500
            with transaction.atomic():
                for i in range(0, len(to_update), batch_size):
                    chunk = to_update[i:i + batch_size]
                    evaluations = [
                        PropertyEvaluation(id=node_id, duplicate_of_id=new_p)
                        for node_id, new_p in chunk
                    ]
                    PropertyEvaluation.objects.bulk_update(
                        evaluations,
                        ["duplicate_of"],
                        batch_size=batch_size,
                    )
            logger.info("Successfully applied updates to database.")

        # 最終検証クエリ
        cursor.execute("SELECT COUNT(*) FROM property_evaluation WHERE id = duplicate_of_id")
        final_self = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM property_evaluation a
            JOIN property_evaluation b ON a.duplicate_of_id = b.id
            WHERE b.duplicate_of_id = a.id
        """)
        final_cycles = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM property_evaluation a
            JOIN property_evaluation b ON a.duplicate_of_id = b.id
            WHERE b.duplicate_of_id IS NOT NULL
        """)
        final_chains = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM property_evaluation
            WHERE duplicate_of_id IS NOT NULL AND duplicate_of_id >= id
        """)
        final_inverted = cursor.fetchone()[0]

        logger.info("=== Verification Results ===")
        logger.info(f"Self-loops: {final_self} (Expected: 0)")
        logger.info(f"Mutual cycles: {final_cycles} (Expected: 0)")
        logger.info(f"Multi-hop chains: {final_chains} (Expected: 0)")
        logger.info(f"Inverted hierarchies (parent.id >= child.id): {final_inverted} (Expected: 0)")

        if not dry_run:
            assert final_self == 0, f"Self loops remaining: {final_self}"
            assert final_cycles == 0, f"Cycles remaining: {final_cycles}"
            assert final_chains == 0, f"Chains remaining: {final_chains}"
            assert final_inverted == 0, f"Inverted relationships remaining: {final_inverted}"
            logger.info("✔ All hierarchy assertions passed! DB is 100% clean and consistent.")


if __name__ == "__main__":
    dry_run_flag = "--dry-run" in sys.argv
    resolve_duplicate_hierarchies(dry_run=dry_run_flag)
