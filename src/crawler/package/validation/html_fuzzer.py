"""Specification fuzzing helper for parser HTML boundary/anomaly cases (Chapter 5.6)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FuzzedHtmlCase:
    name: str
    html: str


def generate_fuzzed_html_cases(base_html: str, price_text: str = "") -> list[FuzzedHtmlCase]:
    """Synthesize anomaly and boundary HTML variants from a normal sample."""
    cases: list[FuzzedHtmlCase] = []
    missing_html = base_html.replace(price_text, "") if price_text else base_html
    cases.append(FuzzedHtmlCase(name="missing_price", html=missing_html))

    noisy_html = base_html.replace(">", ">\n\u3000", 1)
    cases.append(FuzzedHtmlCase(name="whitespace_noise", html=noisy_html))

    trap_html = f"{base_html}<!-- unit-entry community-apart -->"
    cases.append(FuzzedHtmlCase(name="word_boundary_trap", html=trap_html))
    return cases
