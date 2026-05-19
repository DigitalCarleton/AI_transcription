#!/usr/bin/env python3
import argparse
import html
import json
from pathlib import Path


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{
      font-family: Georgia, "Times New Roman", serif;
      line-height: 1.45;
      margin: 2rem;
      color: #222;
    }}
    main {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    table {{
      border-collapse: collapse;
      margin: 1rem 0;
      width: 100%;
    }}
    th, td {{
      border: 1px solid #999;
      padding: 0.35rem 0.5rem;
      vertical-align: top;
    }}
    h1, h2, h3 {{
      line-height: 1.15;
      margin: 0 0 0.35rem;
    }}
    h1 {{
      font-size: 1.45rem;
    }}
    h2 {{
      font-size: 1.25rem;
    }}
    h3 {{
      font-size: 1.1rem;
    }}
    strong {{
      font-weight: 700;
    }}
    em {{
      font-style: italic;
    }}
    .large {{
      font-size: 1.2em;
    }}
    .line {{
      min-height: 1.3em;
    }}
    .page-spread {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0;
      border: 1px solid #999;
    }}
    .page {{
      padding: 0.75rem;
      min-height: 30rem;
    }}
    .page + .page {{
      border-left: 1px solid #999;
    }}
    .main-text {{
      display: block;
    }}
    .margin-note {{
      color: #555;
      float: left;
      font-size: 0.8em;
      line-height: 1.25;
      margin: 0 0.75rem 0.5rem 0;
      max-width: 10rem;
    }}
    .bracket, .brace {{
      color: #7a2f00;
      font-weight: bold;
    }}
    .bracket-group {{
      align-items: stretch;
      display: flex;
      gap: 0.35rem;
      margin: 0.2rem 0;
    }}
    .bracket-mark {{
      align-items: center;
      color: #7a2f00;
      display: flex;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 3rem;
      line-height: 1;
      min-width: 1.1rem;
    }}
    .bracket-content {{
      flex: 1;
    }}
    .list-columns {{
      display: grid;
      gap: 1.5rem;
      grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
      margin: 0.35rem 0 0.75rem;
    }}
    .ruled-section {{
      border-bottom: 1px solid #999;
      border-top: 1px solid #999;
      margin: 0.5rem 0;
      padding: 0.4rem 0;
    }}
    hr {{
      border: 0;
      border-top: 1px solid #999;
      margin: 0.5rem 0;
    }}
    .unclear {{
      background: #fff3a3;
    }}
    .metadata {{
      color: #555;
      font-family: Arial, sans-serif;
      font-size: 0.9rem;
      margin-bottom: 1.5rem;
    }}
  </style>
</head>
<body>
<main>
  <h1>{heading}</h1>
  <div class="metadata">
    <div>record_id: {record_id}</div>
    <div>item_id: {item_id}</div>
    <div>collection: {collection}</div>
    <div>image: <a href="{image_url}">{image_url}</a></div>
    <div>item: <a href="{item_web_url}">{item_web_url}</a></div>
  </div>
  {transcription_html}
</main>
</body>
</html>
"""


def safe_filename(value):
    text = str(value or "unknown")
    safe = []
    for char in text:
        if char.isalnum() or char in ("-", "_"):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe).strip("_") or "unknown"


def write_html(out_dir: Path, rec):
    record_id = rec.get("record_id") or f'{rec.get("item_id", "unknown")}-image'
    title = rec.get("title") or record_id
    collection = rec.get("collection_title") or rec.get("collection_id") or ""
    transcription_html = rec.get("transcription_html") or ""

    page = HTML_TEMPLATE.format(
        title=html.escape(str(title)),
        heading=html.escape(str(title)),
        record_id=html.escape(str(record_id)),
        item_id=html.escape(str(rec.get("item_id", ""))),
        collection=html.escape(str(collection)),
        image_url=html.escape(str(rec.get("image_url", "")), quote=True),
        item_web_url=html.escape(str(rec.get("item_web_url", "")), quote=True),
        transcription_html=transcription_html,
    )

    out_path = out_dir / f"{safe_filename(record_id)}.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def strip_code_fence(text: str):
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def escape_inner_quotes(text: str):
    result = []
    in_string = False
    i = 0

    while i < len(text):
        char = text[i]

        if char == "\\":
            result.append(char)
            if i + 1 < len(text):
                result.append(text[i + 1])
                i += 2
                continue
            i += 1
            continue

        if char == '"':
            if not in_string:
                in_string = True
                result.append(char)
                i += 1
                continue

            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            next_char = text[j] if j < len(text) else ""

            if next_char in {":", ",", "}", "]", ""}:
                in_string = False
                result.append(char)
            else:
                result.append('\\"')
            i += 1
            continue

        result.append(char)
        i += 1

    return "".join(result)


def load_record(line: str, line_number: int, repair: bool):
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        if not repair:
            raise

    repaired = escape_inner_quotes(line)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        raise ValueError(f"Line {line_number} is not valid JSONL and automatic quote repair failed: {e}") from e


def load_records(path: Path, repair: bool):
    text = strip_code_fence(path.read_text(encoding="utf-8-sig"))
    stripped = text.strip()
    if not stripped:
        return []

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    records = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        records.append(load_record(line, line_number, repair))
    return records


def main():
    p = argparse.ArgumentParser(description="Convert Gemini transcription JSONL into one HTML file per record.")
    p.add_argument("--in-jsonl", required=True, help="Gemini returned JSONL file")
    p.add_argument("--out-dir", required=True, help="directory for HTML files")
    p.add_argument("--no-repair", action="store_true", help="disable automatic repair for unescaped quotes in Gemini output")
    args = p.parse_args()

    src = Path(args.in_jsonl)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for rec in load_records(src, repair=not args.no_repair):
        written.append(str(write_html(out_dir, rec)))

    print(json.dumps({
        "in_jsonl": str(src),
        "out_dir": str(out_dir),
        "html_files": len(written),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

# Usage:
# python jsonl_to_html.py --in-jsonl gemini_returned.jsonl --out-dir html_transcriptions
#
# --in-jsonl  Gemini returned JSONL file, required
# --out-dir   output directory for one HTML file per record, required
# --no-repair disable automatic repair for common unescaped quote problems
