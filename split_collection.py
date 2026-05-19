#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Split one Omeka export JSONL file into one JSONL file per collection_id.")
    p.add_argument("--in-jsonl", required=True, help="input JSONL produced by export.py")
    p.add_argument("--out-dir", required=True, help="directory for collection JSONL files")
    p.add_argument("--include-skipped", action="store_true", help="include records whose status is not ready")
    args = p.parse_args()

    src = Path(args.in_jsonl)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    handles = {}
    counts = defaultdict(int)
    skipped = 0

    try:
        with src.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if not args.include_skipped and rec.get("status") != "ready":
                    skipped += 1
                    continue

                collection_id = rec.get("collection_id")
                if collection_id is None:
                    collection_id = "unknown"
                out_path = out_dir / f"collection_{collection_id}.jsonl"

                if collection_id not in handles:
                    handles[collection_id] = out_path.open("w", encoding="utf-8")

                handles[collection_id].write(json.dumps(rec, ensure_ascii=False) + "\n")
                counts[str(collection_id)] += 1
    finally:
        for handle in handles.values():
            handle.close()

    print(json.dumps({
        "in_jsonl": str(src),
        "out_dir": str(out_dir),
        "collections": len(counts),
        "records": sum(counts.values()),
        "skipped_records": skipped,
        "counts": dict(sorted(counts.items(), key=lambda item: item[0])),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

# Usage:
# python split_collection.py --in-jsonl omeka_export.jsonl --out-dir collections
#
# --in-jsonl         input JSONL produced by export.py, required
# --out-dir          output directory for collection_*.jsonl files, required
# --include-skipped  include skipped/no-image records, default false
