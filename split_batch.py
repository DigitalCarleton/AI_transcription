#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def item_to_image_records(rec):
    image_urls = rec.get("image_urls") or []
    image_count = len(image_urls)
    for idx, image_url in enumerate(image_urls, start=1):
        yield {
            "record_id": f'{rec.get("item_id")}-image-{idx:03d}',
            "item_id": rec.get("item_id"),
            "item_web_url": rec.get("item_web_url"),
            "image_url": image_url,
            "image_index": idx,
            "image_count": image_count,
            "collection_id": rec.get("collection_id"),
            "collection_title": rec.get("collection_title"),
            "title": rec.get("title"),
            "identifier": rec.get("identifier"),
            "date": rec.get("date"),
            "language": rec.get("language"),
            "description": rec.get("description"),
        }


def write_batch(path: Path, records, output_format: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "jsonl":
        with path.open("w", encoding="utf-8") as w:
            for rec in records:
                w.write(json.dumps(rec, ensure_ascii=False) + "\n")
    else:
        with path.open("w", encoding="utf-8") as w:
            json.dump(records, w, ensure_ascii=False, indent=2)


def collection_name(path: Path):
    return path.stem.replace("collection_", "", 1)


def main():
    p = argparse.ArgumentParser(description="Split collection JSONL files into fixed-size image batches.")
    p.add_argument("--in-dir", required=True, help="directory containing collection_*.jsonl files")
    p.add_argument("--out-dir", required=True, help="directory for batch files")
    p.add_argument("--batch-size", type=int, default=5, help="image records per batch")
    p.add_argument("--format", choices=["jsonl", "json"], default="jsonl", help="batch output format")
    p.add_argument("--include-skipped", action="store_true", help="include records whose status is not ready")
    args = p.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    batch_size = max(1, args.batch_size)
    suffix = ".jsonl" if args.format == "jsonl" else ".json"

    total_batches = 0
    total_images = 0
    summaries = {}

    for collection_path in sorted(in_dir.glob("collection_*.jsonl")):
        collection_id = collection_name(collection_path)
        image_records = []

        for rec in iter_jsonl(collection_path):
            if not args.include_skipped and rec.get("status") != "ready":
                continue
            image_records.extend(item_to_image_records(rec))

        collection_batches = 0
        collection_out_dir = out_dir / f"collection_{collection_id}"
        for i in range(0, len(image_records), batch_size):
            batch = image_records[i:i + batch_size]
            collection_batches += 1
            batch_path = collection_out_dir / f"collection_{collection_id}_batch_{collection_batches:04d}{suffix}"
            write_batch(batch_path, batch, args.format)

        total_batches += collection_batches
        total_images += len(image_records)
        summaries[collection_id] = {
            "images": len(image_records),
            "batches": collection_batches,
        }

    print(json.dumps({
        "in_dir": str(in_dir),
        "out_dir": str(out_dir),
        "batch_size": batch_size,
        "format": args.format,
        "collections": len(summaries),
        "image_records": total_images,
        "batch_files": total_batches,
        "summary": summaries,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

# Usage:
# python split_batch.py --in-dir collections --out-dir batches --batch-size 5
#
# --in-dir           directory containing collection_*.jsonl files, required
# --out-dir          output directory for batch files, required
# --batch-size       image records per batch, default 5
# --format           batch output format, jsonl or json, default jsonl
# --include-skipped  include skipped/no-image item records, default false
