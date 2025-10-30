"""
Enumerate unique labels and counts across CIC-IDS 2017/2018 CSV files.
Recurses subdirectories under the provided data directory.

Usage:
    python backend/scripts/list_labels.py --data-dir data
"""

import argparse
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

import pandas as pd


def find_csv_files(base_dir: Path) -> list[Path]:
    patterns = ["*.csv"]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(base_dir.rglob(pattern))
    return sorted(set(files))


def get_label_column(columns: list[str]) -> str | None:
    for col in columns:
        normalized = col.strip().lower()
        if normalized in {"label", "class"}:
            return col
        if col == " Label":
            return col
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, required=True, help="Path to data directory containing 2017/2018")
    args = parser.parse_args()

    base = Path(args.data_dir).resolve()
    if not base.exists():
        print(json.dumps({"error": f"data dir not found: {base}"}, indent=2))
        return 1

    all_counts: Counter[str] = Counter()
    per_file_counts: dict[str, dict[str, int]] = {}
    errors: list[dict[str, str]] = []

    for year in ("2017", "2018"):
        year_dir = base / year
        if not year_dir.exists():
            continue
        for csv_file in find_csv_files(year_dir):
            try:
                df = pd.read_csv(csv_file, low_memory=False)
                label_col = get_label_column(list(df.columns))
                if not label_col:
                    continue
                vals = df[label_col].dropna().astype(str).str.strip()
                counts = Counter(vals.tolist())
                all_counts.update(counts)
                per_file_counts[str(csv_file)] = {k: int(v) for k, v in counts.most_common()}
            except Exception as e:
                errors.append({"file": str(csv_file), "error": str(e)})

    result = {
        "unique_labels": sorted(all_counts.keys()),
        "num_labels": len(all_counts),
        "total_counts": {k: int(v) for k, v in all_counts.most_common()},
        "errors": errors[:10],
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


