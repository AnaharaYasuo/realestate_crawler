"""
HTML Sanitizer for AI Prompt Injection & Token Reduction.
Strips scripts, styles, SVG, images, navbars, and excess whitespace to minimize token usage while preserving property data structure.
"""

from bs4 import BeautifulSoup


def sanitize_html_for_llm(html_content: str, max_length: int = 50000) -> str:
    """
    Sanitizes raw HTML into a dense structural representation suitable for LLM diagnosis.
    Removes script, style, SVG, noscript, header, footer, nav, iframe, and reduces tags to structural data.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove non-content and layout-bloat tags
    for tag in soup(["script", "style", "svg", "noscript", "header", "footer", "nav", "iframe", "link", "meta"]):
        tag.decompose()

    # Remove data: URIs, inline style attributes, and tracking attributes
    for el in soup.find_all(True):
        bad_attrs = [attr for attr in el.attrs if attr.startswith("on") or attr in ("style", "src", "srcset", "href")]
        for attr in bad_attrs:
            del el[attr]

    # Convert to clean string
    cleaned = str(soup)
    # Collapse consecutive whitespace
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    condensed = "\n".join(lines)

    if len(condensed) > max_length:
        condensed = condensed[:max_length] + "\n...[TRUNCATED FOR TOKEN LIMIT]"

    return condensed
