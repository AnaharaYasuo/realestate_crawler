# -*- coding: utf-8 -*-
"""
ASTコードミューテーションエンジンの単体テスト (TDD)
"""
import ast
import os
import tempfile

from package.testing.mutation_engine import (
    ASTMutationEngine,
    MutationType,
    Mutant,
    MutationResult
)


SAMPLE_SOURCE_CODE = '''
def calculate_discount(price, is_special):
    if price > 10000 and is_special:
        return True
    return False
'''


def test_mutant_dataclass_properties():
    mutant = Mutant(
        file_path="dummy.py",
        line_number=3,
        mutation_type=MutationType.COMPARE_OP,
        original_source="price > 10000",
        mutated_source="price <= 10000",
        ast_node_str="Gt -> LtE"
    )
    assert mutant.file_path == "dummy.py"
    assert mutant.line_number == 3
    assert mutant.mutation_type == MutationType.COMPARE_OP
    assert mutant.ast_node_str == "Gt -> LtE"


def test_generate_compare_op_mutants():
    """比較演算子の反転変異（> -> <=, == -> != 等）が正しく生成されること"""
    engine = ASTMutationEngine()
    tree = ast.parse(SAMPLE_SOURCE_CODE)
    mutants = engine.generate_mutants_from_tree(tree, "sample.py")

    compare_mutants = [m for m in mutants if m.mutation_type == MutationType.COMPARE_OP]
    assert len(compare_mutants) >= 1
    gt_mutant = next(m for m in compare_mutants if ">" in m.original_source)
    assert "<=" in gt_mutant.mutated_source or "<" in gt_mutant.mutated_source


def test_generate_bool_op_mutants():
    """論理演算子の反転変異（and -> or）が正しく生成されること"""
    engine = ASTMutationEngine()
    tree = ast.parse(SAMPLE_SOURCE_CODE)
    mutants = engine.generate_mutants_from_tree(tree, "sample.py")

    bool_mutants = [m for m in mutants if m.mutation_type == MutationType.BOOL_OP]
    assert len(bool_mutants) >= 1
    assert any(" or " in m.mutated_source for m in bool_mutants)


def test_generate_return_value_mutants():
    """戻り値の破壊変異（return True -> return False 等）が正しく生成されること"""
    engine = ASTMutationEngine()
    tree = ast.parse(SAMPLE_SOURCE_CODE)
    mutants = engine.generate_mutants_from_tree(tree, "sample.py")

    return_mutants = [m for m in mutants if m.mutation_type == MutationType.RETURN_VALUE]
    assert len(return_mutants) >= 2
    assert any("return False" in m.mutated_source for m in return_mutants)


def test_apply_and_revert_mutant_file_safety():
    """変異適用とロールバックが完全に行われ、元ファイルが安全に維持されること"""
    engine = ASTMutationEngine()
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(SAMPLE_SOURCE_CODE)
        temp_path = f.name

    try:
        mutants = engine.generate_mutants_from_file(temp_path)
        assert len(mutants) > 0

        target_mutant = mutants[0]
        # 変異適用
        backup_content = engine.apply_mutant(target_mutant)
        with open(temp_path, 'r', encoding='utf-8') as f:
            mutated_code = f.read()
        assert mutated_code != SAMPLE_SOURCE_CODE

        # ロールバック
        engine.revert_mutant(target_mutant, backup_content)
        with open(temp_path, 'r', encoding='utf-8') as f:
            reverted_code = f.read()
        assert reverted_code == SAMPLE_SOURCE_CODE
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_mutation_result_summary():
    """MutationResultの集計とMutation Score（キル率）の計算が正確であること"""
    result = MutationResult(
        target="sample_module",
        total_mutants=10,
        killed_mutants=8,
        survived_mutants=2,
        errored_mutants=0,
        survived_details=[{"line": 5, "desc": "survived"}]
    )
    assert result.mutation_score == 80.0
    assert result.is_passed(threshold=75.0) is True
    assert result.is_passed(threshold=85.0) is False


def test_generate_mutants_max_limit():
    """max_mutantsの上限指定によりAST走査が早期終了し指定件数以下になること"""
    engine = ASTMutationEngine()
    tree = ast.parse(SAMPLE_SOURCE_CODE)
    all_mutants = engine.generate_mutants_from_tree(tree, "sample.py")
    assert len(all_mutants) >= 3

    limited_mutants = engine.generate_mutants_from_tree(tree, "sample.py", max_mutants=2)
    assert len(limited_mutants) == 2

