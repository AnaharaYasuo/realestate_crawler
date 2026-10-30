#!/usr/bin/env python3
"""Scaffold generator for onboarding a new real estate site."""
import argparse
from pathlib import Path


def generate_scaffold(company: str, display_name: str, property_types: list[str], dry_run: bool = False) -> dict[str, str]:
    cap = "".join(part.capitalize() for part in company.split("_"))
    model_lines = [
        '"""Auto-scaffolded models for ' + display_name + '."""',
        "from package.models.base import (",
        "    InvestmentBaseModel,",
        "    KodateBaseModel,",
        "    MansionBaseModel,",
        "    TochiBaseModel,",
        ")",
        "",
    ]
    base_map = {
        "mansion": "MansionBaseModel",
        "kodate": "KodateBaseModel",
        "tochi": "TochiBaseModel",
        "investment": "InvestmentBaseModel",
        "invest_mansion": "InvestmentBaseModel",
        "invest_apartment": "InvestmentBaseModel",
        "invest_kodate": "InvestmentBaseModel",
    }
    for pt in property_types:
        if pt not in base_map:
            raise ValueError(f"Unsupported property type: {pt!r}. Allowed: {sorted(base_map)}")
        if pt == "investment":
            pt_cap = "Investment"
        elif pt.startswith("invest_"):
            suffix = "".join(part.capitalize() for part in pt.split("_")[1:])
            pt_cap = f"Investment{suffix}"
        else:
            pt_cap = "".join(part.capitalize() for part in pt.split("_"))
        base_cls = base_map[pt]
        model_lines.extend([
            f"class {cap}{pt_cap}({base_cls}):",
            "    class Meta:",
            f'        db_table = "{company}_{pt}"',
            "",
        ])
    result = {f"src/crawler/package/models/{company}.py": "\n".join(model_lines)}
    if not dry_run:
        root = Path(__file__).resolve().parents[4]
        for rel, content in result.items():
            target = root / rel
            if not target.exists():
                target.write_text(content, encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a new real estate crawler site.")
    parser.add_argument("--company", required=True, help="Company key (snake_case)")
    parser.add_argument("--display-name", required=True, help="Japanese display name")
    parser.add_argument("--types", default="mansion,kodate,tochi", help="Comma-separated property types")
    parser.add_argument("--dry-run", action="store_true", help="Print without writing files")
    args = parser.parse_args()
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    generated = generate_scaffold(args.company, args.display_name, types, dry_run=args.dry_run)
    for path in generated:
        print(f"Prepared: {path}")


if __name__ == "__main__":
    main()
