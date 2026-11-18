from package.validation.html_fuzzer import generate_fuzzed_html_cases


def test_generate_fuzzed_html_cases_produces_expected_variants():
    base_html = "<div class='card'><span class='price'>3,500万円</span><span class='type'>マンション</span></div>"
    cases = generate_fuzzed_html_cases(base_html, price_text="3,500万円")
    names = {c.name for c in cases}
    assert "missing_price" in names
    assert "whitespace_noise" in names
    assert "word_boundary_trap" in names
    missing = next(c for c in cases if c.name == "missing_price")
    assert "3,500万円" not in missing.html
