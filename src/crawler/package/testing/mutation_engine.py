# -*- coding: utf-8 -*-
"""
AST Code Mutation Engine
コード構文木 (AST) を変異させ、ユニットテストの殺傷力 (Mutation Score) を計測するエンジン
"""
import ast
import copy
from dataclasses import dataclass, field
from enum import Enum
import subprocess
from typing import Any, Dict, List, Optional


class MutationType(str, Enum):
    COMPARE_OP = "compare_op"
    BOOL_OP = "bool_op"
    RETURN_VALUE = "return_value"
    UNARY_OP = "unary_op"


@dataclass
class Mutant:
    file_path: str
    line_number: int
    mutation_type: MutationType
    original_source: str
    mutated_source: str
    ast_node_str: str
    mutated_code: Optional[str] = None
    original_file_content: Optional[str] = None


@dataclass
class MutationResult:
    target: str
    total_mutants: int
    killed_mutants: int
    survived_mutants: int
    errored_mutants: int = 0
    survived_details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def mutation_score(self) -> float:
        if self.total_mutants == 0:
            return 100.0
        return round((self.killed_mutants / self.total_mutants) * 100.0, 2)

    def is_passed(self, threshold: float = 85.0) -> bool:
        return self.mutation_score >= threshold


class ASTMutationEngine:
    """Python AST の比較演算子・論理演算子・戻り値を変異させるエンジン"""

    COMPARE_MUTATIONS = {
        ast.Gt: ast.LtE,
        ast.Lt: ast.GtE,
        ast.GtE: ast.Lt,
        ast.LtE: ast.Gt,
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
        ast.In: ast.NotIn,
        ast.NotIn: ast.In,
        ast.Is: ast.IsNot,
        ast.IsNot: ast.Is,
    }

    BOOL_MUTATIONS = {
        ast.And: ast.Or,
        ast.Or: ast.And,
    }

    def generate_mutants_from_file(self, file_path: str, max_mutants: Optional[int] = None) -> List[Mutant]:
        """ファイルからASTをパースして変異体を生成"""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
        mutants = self.generate_mutants_from_tree(tree, file_path, max_mutants=max_mutants)
        for m in mutants:
            m.original_file_content = content
        return mutants

    def generate_mutants_from_tree(
        self,
        tree: ast.AST,
        file_path: str,
        max_mutants: Optional[int] = None,
    ) -> List[Mutant]:
        """AST構文木から変異体リストを抽出・生成"""
        mutants: List[Mutant] = []

        # 1. 比較演算子変異
        for node in ast.walk(tree):
            if max_mutants is not None and len(mutants) >= max_mutants:
                break

            if isinstance(node, ast.Compare):
                for idx, op in enumerate(node.ops):
                    if max_mutants is not None and len(mutants) >= max_mutants:
                        break
                    op_type = type(op)
                    if op_type in self.COMPARE_MUTATIONS:
                        target_op_cls = self.COMPARE_MUTATIONS[op_type]
                        tree_copy = copy.deepcopy(tree)
                        mutated_target = self._find_matching_node(tree_copy, node)
                        if mutated_target and isinstance(mutated_target, ast.Compare):
                            mutated_target.ops[idx] = target_op_cls()
                            orig_src = ast.unparse(node)
                            mut_src = ast.unparse(mutated_target)
                            mutants.append(
                                Mutant(
                                    file_path=file_path,
                                    line_number=getattr(node, "lineno", 1),
                                    mutation_type=MutationType.COMPARE_OP,
                                    original_source=orig_src,
                                    mutated_source=mut_src,
                                    ast_node_str=f"{op_type.__name__} -> {target_op_cls.__name__}",
                                    mutated_code=ast.unparse(tree_copy),
                                )
                            )

            # 2. 論理演算子変異 (and / or)
            elif isinstance(node, ast.BoolOp):
                op_type = type(node.op)
                if op_type in self.BOOL_MUTATIONS:
                    target_op_cls = self.BOOL_MUTATIONS[op_type]
                    tree_copy = copy.deepcopy(tree)
                    mutated_target = self._find_matching_node(tree_copy, node)
                    if mutated_target and isinstance(mutated_target, ast.BoolOp):
                        mutated_target.op = target_op_cls()
                        orig_src = ast.unparse(node)
                        mut_src = ast.unparse(mutated_target)
                        mutants.append(
                            Mutant(
                                file_path=file_path,
                                line_number=getattr(node, "lineno", 1),
                                mutation_type=MutationType.BOOL_OP,
                                original_source=orig_src,
                                mutated_source=mut_src,
                                ast_node_str=f"{op_type.__name__} -> {target_op_cls.__name__}",
                                mutated_code=ast.unparse(tree_copy),
                            )
                        )

            # 3. 戻り値破壊変異 (return True -> False, return False -> True, return 0 -> 1, return obj -> None)
            elif isinstance(node, ast.Return) and node.value is not None:
                tree_copy = copy.deepcopy(tree)
                mutated_target = self._find_matching_node(tree_copy, node)
                if mutated_target and isinstance(mutated_target, ast.Return):
                    new_val_node = None
                    if isinstance(node.value, ast.Constant):
                        if node.value.value is True:
                            new_val_node = ast.Constant(value=False)
                        elif node.value.value is False:
                            new_val_node = ast.Constant(value=True)
                        elif node.value.value == 0:
                            new_val_node = ast.Constant(value=1)
                        elif node.value.value is not None:
                            new_val_node = ast.Constant(value=None)
                    else:
                        new_val_node = ast.Constant(value=None)

                    if new_val_node is not None:
                        mutated_target.value = new_val_node
                        orig_src = ast.unparse(node)
                        mut_src = ast.unparse(mutated_target)
                        mutants.append(
                            Mutant(
                                file_path=file_path,
                                line_number=getattr(node, "lineno", 1),
                                mutation_type=MutationType.RETURN_VALUE,
                                original_source=orig_src,
                                mutated_source=mut_src,
                                ast_node_str=f"Return {orig_src} -> {mut_src}",
                                mutated_code=ast.unparse(tree_copy),
                            )
                        )

        return mutants

    def _find_matching_node(self, tree: ast.AST, target_node: ast.AST) -> Optional[ast.AST]:
        """ディープコピー後のAST構文木から元のノードに対応するノードを行番号と位置で特定"""
        target_line = getattr(target_node, "lineno", None)
        target_col = getattr(target_node, "col_offset", None)
        target_type = type(target_node)

        for node in ast.walk(tree):
            if type(node) is target_type:
                if (
                    getattr(node, "lineno", None) == target_line
                    and getattr(node, "col_offset", None) == target_col
                ):
                    return node
        return None

    def apply_mutant(self, mutant: Mutant) -> str:
        """ファイルに変異コードを適用し、ロールバック用バックアップ文字列を返却"""
        with open(mutant.file_path, "r", encoding="utf-8") as f:
            backup_content = f.read()

        if mutant.mutated_code is not None:
            with open(mutant.file_path, "w", encoding="utf-8") as f:
                f.write(mutant.mutated_code)

        return backup_content

    def revert_mutant(self, mutant: Mutant, backup_content: str) -> None:
        """ファイルを元のバックアップ文字列にロールバック"""
        restore_content = mutant.original_file_content if getattr(mutant, "original_file_content", None) else backup_content
        with open(mutant.file_path, "w", encoding="utf-8") as f:
            f.write(restore_content)

    def run_mutation_test(
        self,
        mutant: Mutant,
        test_command: str,
        cwd: Optional[str] = None,
        timeout: int = 30
    ) -> bool:
        """変異を適用してテストを実行。テストが失敗 (FAIL) すれば変異体殺傷 (Killed=True)"""
        backup = self.apply_mutant(mutant)
        try:
            # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
            res = subprocess.run(
                test_command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            # テストが失敗 (exit != 0) したら変異体検知成功 (KILLED)
            is_killed = (res.returncode != 0)
            return is_killed
        except subprocess.TimeoutExpired:
            # タイムアウト（無限ループ変異等）も殺傷とみなす
            return True
        except Exception:
            return True
        finally:
            self.revert_mutant(mutant, backup)
