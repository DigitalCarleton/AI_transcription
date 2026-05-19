#!/usr/bin/env python3
import argparse
import csv
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def fetch_json(url: str, timeout: int = 30):
    req = Request(url, headers={"User-Agent": "new-transcribe-method/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_title_from_element_texts(element_texts):
    for et in element_texts or []:
        if et.get("element", {}).get("name") == "Title":
            return et.get("text")
    return None


def get_dc(item, field_name: str):
    for et in item.get("element_texts", []):
        if et.get("element", {}).get("name") == field_name:
            return et.get("text")
    return None


def parse_id_set(value: str):
    return {int(x.strip()) for x in value.split(",") if x.strip()}


def list_collections(api_base: str, max_pages: int = 200):
    all_collections = []
    for page in range(1, max_pages + 1):
        qs = urlencode({"page": page, "per_page": 100})
        rows = fetch_json(f"{api_base}/collections?{qs}")
        if not rows:
            break
        all_collections.extend(rows)
        time.sleep(0.12)
    return all_collections


def list_items(api_base: str, collection_id: int, per_page: int = 100, max_pages: int = 200):
    all_items = []
    for page in range(1, max_pages + 1):
        qs = urlencode({"collection": collection_id, "page": page, "per_page": per_page})
        rows = fetch_json(f"{api_base}/items?{qs}")
        if not rows:
            break
        all_items.extend(rows)
        time.sleep(0.12)
    return all_items


def list_files(api_base: str, item_id: int):
    return fetch_json(f"{api_base}/files?item={item_id}")


def pick_image_urls(files):
    urls = []
    for f in files or []:
        file_urls = f.get("file_urls", {})
        url = file_urls.get("fullsize") or file_urls.get("original")
        if url:
            urls.append(url)
    return urls


def write_collection_map_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as w:
        writer = csv.DictWriter(
            w,
            fieldnames=[
                "collection_id",
                "collection_title",
                "collection_web_url",
                "collection_api_url",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(
        description="Export Virtual Workhouse Omeka items into one JSONL file, plus a collection-title CSV."
    )
    p.add_argument("--api-base", default="https://virtualworkhouse.carleton.edu/api")
    p.add_argument("--exclude-collections", default="47", help="comma-separated collection IDs to exclude")
    p.add_argument("--out", required=True, help="main export JSONL path")
    p.add_argument(
        "--collection-map-out",
        default="",
        help="collection_id -> collection_title CSV path; default is beside --out",
    )
    p.add_argument("--max-items-per-collection", type=int, default=0, help="0 means no limit")
    args = p.parse_args()

    api_base = args.api_base.rstrip("/")
    exclude_ids = parse_id_set(args.exclude_collections)
    out_path = Path(args.out)
    default_stem = out_path.with_suffix("")
    collection_map_path = (
        Path(args.collection_map_out)
        if args.collection_map_out
        else default_stem.with_name(f"{default_stem.name}_collections.csv")
    )

    collections = list_collections(api_base)
    target_collections = [c for c in collections if c.get("id") not in exclude_ids]

    totals = {"collections": 0, "items": 0, "ready": 0, "skipped": 0}
    collection_map_rows = []
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as w:
        for col in target_collections:
            col_id = col.get("id")
            col_title = get_title_from_element_texts(col.get("element_texts", [])) or f"Untitled collection {col_id}"
            totals["collections"] += 1
            collection_map_rows.append({
                "collection_id": col_id,
                "collection_title": col_title,
                "collection_web_url": f"https://virtualworkhouse.carleton.edu/items/browse?collection={col_id}",
                "collection_api_url": col.get("url"),
            })

            items = list_items(api_base, col_id)
            if args.max_items_per_collection > 0:
                items = items[: args.max_items_per_collection]

            for item in items:
                totals["items"] += 1
                item_id = item.get("id")
                files_count = item.get("files", {}).get("count", 0)
                status = "ready"
                skip_reason = None
                image_urls = []

                if files_count and files_count > 0:
                    try:
                        image_urls = pick_image_urls(list_files(api_base, item_id))
                        if not image_urls:
                            status = "skipped_no_image_url"
                            skip_reason = "files exist but no fullsize/original image url"
                    except Exception as e:
                        status = "skipped_file_fetch_error"
                        skip_reason = str(e)
                else:
                    status = "skipped_no_image"
                    skip_reason = "files.count == 0"

                if status == "ready":
                    totals["ready"] += 1
                else:
                    totals["skipped"] += 1

                record = {
                    "collection_id": col_id,
                    "collection_title": col_title,
                    "item_id": item_id,
                    "item_web_url": f"https://virtualworkhouse.carleton.edu/items/show/{item_id}",
                    "item_api_url": item.get("url"),
                    "title": get_dc(item, "Title"),
                    "identifier": get_dc(item, "Identifier"),
                    "date": get_dc(item, "Date"),
                    "language": get_dc(item, "Language"),
                    "description": get_dc(item, "Description"),
                    "files_count": files_count,
                    "image_urls": image_urls,
                    "status": status,
                    "skip_reason": skip_reason,
                }
                w.write(json.dumps(record, ensure_ascii=False) + "\n")

    write_collection_map_csv(collection_map_path, collection_map_rows)
    print(json.dumps({
        "out": str(out_path),
        "collection_map_out": str(collection_map_path),
        **totals,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

# Usage:
# python export.py --out omeka_export.jsonl --collection-map-out collection_map.csv
#
# --api-base                  Omeka API address, default https://virtualworkhouse.carleton.edu/api
# --exclude-collections       excluded collection IDs, comma-separated, default 47
# --out                       main export JSONL save path, required
# --collection-map-out        collection-title mapping CSV save path, default auto-generated
# --max-items-per-collection  max items to fetch per collection, default 0 means no limit
