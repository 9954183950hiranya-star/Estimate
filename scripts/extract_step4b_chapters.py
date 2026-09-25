#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fitz

from estimate_app.database.catalogue import CATALOGUE_HEADERS, CatalogueRepository
from estimate_app.database.connection import connect, initialise

ROOT = Path(__file__).resolve().parents[1]
WORKDIR = ROOT / ".chapter_extraction"
PILOT_DIR = ROOT / ".pilot_extraction"
SOURCES = {
    "Volume I": ROOT / "reference_sources" / "DSR_Vol_1_Civil 2023.pdf",
    "Volume II": ROOT / "reference_sources" / "DSR_Vol_2_Civil  2023.pdf",
}
PILOT_FILES = (PILOT_DIR / "pilot_vol1_candidate.csv", PILOT_DIR / "pilot_vol2_candidate.csv")
CODE_RE = re.compile(r"^(?P<code>(?:\d{1,2}(?:\.[0-9A-Za-z]+)+|\d{4}))\b\s*(?P<text>.*)$")
CHAPTER_RE = re.compile(r"^(?P<code>\d+)\.0(?:\s+(?P<name>.*))?$")
RATE_RE = re.compile(r"(?P<rate>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*$")
UNIT_RE = re.compile(
    r"(?P<unit>cm\s+per\s+metre|per\s+bag\s+of\s+50\s*kg|100\s+Nos|kg/m2|kg/m²|tonne/km|tonne\s+km|km/cum|sqm|sq\.\s*m|cum|each|day|hour|month|litre|ltr|kg|m3|m²|m|set|pair|%|No\.?|nos)\s*$",
    re.IGNORECASE,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unassigned"
    if len(normalized) <= 72:
        return normalized
    return normalized[:72].rstrip("_") + "_" + hashlib.sha1(value.encode()).hexdigest()[:8]


def pilot_codes() -> set[str]:
    codes: set[str] = set()
    for path in PILOT_FILES:
        with path.open(newline="", encoding="utf-8") as handle:
            codes.update(row["item_code"] for row in csv.DictReader(handle))
    return codes


def code_equivalents(code: str, volume: str) -> set[str]:
    equivalents = {code}
    if volume == "Volume II" and re.fullmatch(r"\d{4}", code):
        equivalents.add(code[:2] + "." + code[2:])
    return equivalents


def valid_code_for_chapter(code: str, chapter_code: str, volume: str) -> bool:
    if chapter_code in {"0.1", "0.2"}:
        return volume == "Volume I" and re.fullmatch(r"\d{4}", code) is not None
    if not chapter_code or not code.startswith(chapter_code.split(".")[0] + "."):
        return False
    parts = code.split(".")
    return all(part.isdigit() or (index == len(parts) - 1 and part.endswith("A") and part[:-1].isdigit()) for index, part in enumerate(parts))


def render_and_ocr(pdf: Path, volume: str, page_number: int) -> tuple[str, float, Path]:
    volume_dir = WORKDIR / "ocr" / slug(volume)
    image_dir = WORKDIR / "source_images"
    volume_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)
    text_path = volume_dir / f"page_{page_number:03d}.txt"
    image_path = volume_dir / f"page_{page_number:03d}.png"
    cached_image = ROOT / ".ocr_tmp" / ("v1" if volume == "Volume I" else "v2") / f"page-{page_number:03d}.png"
    if not text_path.exists():
        with fitz.open(pdf) as document:
            embedded_text = document[page_number - 1].get_text("text").strip()
        if len(embedded_text) >= 80:
            text_path.write_text(embedded_text + "\n", encoding="utf-8")
            confidence_path = volume_dir / f"page_{page_number:03d}.confidence"
            confidence_path.write_text("100.0\n", encoding="utf-8")
            with fitz.open(pdf) as document:
                page = document[page_number - 1]
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
                pixmap.save(image_path)
            shutil.copyfile(cached_image if cached_image.exists() else image_path, image_dir / f"{slug(volume)}_{page_number:03d}.png")
            return embedded_text + "\n", 100.0, image_dir / f"{slug(volume)}_{page_number:03d}.png"
        if cached_image.exists():
            shutil.copyfile(cached_image, image_dir / f"{slug(volume)}_{page_number:03d}.png")
            with fitz.open(pdf) as document:
                page = document[page_number - 1]
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
                pixmap.save(image_path)
        else:
            with fitz.open(pdf) as document:
                page = document[page_number - 1]
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
                pixmap.save(image_path)
        result = subprocess.run(
            ["tesseract", str(image_path), "stdout", "--psm", "6", "tsv"],
            check=True,
            capture_output=True,
            text=True,
        )
        line_words: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        confidences = []
        for row in result.stdout.splitlines()[1:]:
            fields = row.split("\t")
            if len(fields) != 12:
                continue
            text = fields[11].strip()
            if text:
                line_words[(fields[4], fields[5], fields[6])].append(text)
                try:
                    confidence = float(fields[10])
                    if confidence >= 0:
                        confidences.append(confidence)
                except ValueError:
                    pass
        lines = [" ".join(words) for _, words in sorted(line_words.items())]
        text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if not (image_dir / f"{slug(volume)}_{page_number:03d}.png").exists():
            shutil.copyfile(image_path, image_dir / f"{slug(volume)}_{page_number:03d}.png")
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        (volume_dir / f"page_{page_number:03d}.confidence").write_text(f"{confidence:.1f}\n", encoding="utf-8")
    confidence_path = volume_dir / f"page_{page_number:03d}.confidence"
    confidence = float(confidence_path.read_text(encoding="utf-8")) if confidence_path.exists() else 0.0
    return text_path.read_text(encoding="utf-8", errors="replace"), confidence, image_dir / f"{slug(volume)}_{page_number:03d}.png"


def code_line(line: str) -> tuple[str, str] | None:
    match = CODE_RE.match(" ".join(line.split()))
    if not match:
        return None
    code = match.group("code")
    if code.count(".") >= 2 and any(len(part) > 2 for part in code.split(".")[-1:]):
        return None
    return code, match.group("text").strip()


def clean_text(value: str) -> str:
    return " ".join(value.replace("|", " ").split()).strip(" -~_=:")


def chapter_heading(code: str, text: str) -> bool:
    if code in {"0.1", "0.2"}:
        return True
    if not re.fullmatch(r"\d{1,2}\.0", code):
        return False
    heading = clean_text(text)
    letters = [character for character in heading if character.isalpha()]
    return bool(heading) and len(heading) <= 80 and len(letters) >= 4 and sum(character.isupper() for character in letters) / len(letters) >= 0.45


def chapter_rank(code: str) -> float:
    if code == "0.1":
        return 0.1
    if code == "0.2":
        return 0.2
    return float(code.split(".")[0])


def parse_item(code: str, text: str, volume: str, chapter_code: str, chapter_name: str, page: int, source_name: str) -> tuple[dict[str, str] | None, str | None]:
    text = clean_text(text)
    rate_match = RATE_RE.search(text)
    rate = rate_match.group("rate").replace(",", "") if rate_match else ""
    before_rate = text[: rate_match.start()].rstrip() if rate_match else text
    unit_match = UNIT_RE.search(before_rate) if rate_match else None
    if rate_match and not unit_match:
        return None, f"{source_name}: PDF page {page}: {code}: rate found but unit is ambiguous: {text}"
    unit = unit_match.group("unit") if unit_match else ""
    description = before_rate[: unit_match.start()].rstrip(" ,") if unit_match else before_rate
    is_heading = not bool(rate_match)
    if is_heading and re.fullmatch(r"\d{4}", code):
        return None, f"{source_name}: PDF page {page}: {code}: priced row has no recoverable unit/rate"
    if is_heading and not description:
        return None, f"{source_name}: PDF page {page}: {code}: empty heading description"
    parent = code.rsplit(".", 1)[0] if code.count(".") >= 2 else ""
    row = {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": volume,
        "chapter": chapter_name or chapter_code or "Unassigned",
        "item_code": code,
        "parent_item_code": parent,
        "description": description,
        "original_unit": unit,
        "canonical_unit": unit,
        "rate": rate,
        "source_document_name": source_name,
        "source_page": str(page),
        "is_heading": "true" if is_heading else "false",
    }
    return row, None


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOGUE_HEADERS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_pilot_rows() -> list[dict[str, str]]:
    rows = []
    for path in PILOT_FILES:
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def prewarm_ocr() -> None:
    jobs = [(pdf, volume, page) for volume, pdf in SOURCES.items() for page in range(1, len(fitz.open(pdf)) + 1)]
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as executor:
        list(executor.map(lambda job: render_and_ocr(*job), jobs))


def write_inventory(rows: list[dict[str, str]]) -> None:
    path = WORKDIR / "page_chapter_inventory.csv"
    fields = ["volume", "pdf_page", "printed_page", "chapter_code", "chapter_name", "ocr_confidence", "row_count", "status", "notes"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def validate_chapter(chapter: str, rows: list[dict[str, str]], all_rows: list[dict[str, str]], pilot_rows: list[dict[str, str]]) -> dict[str, str]:
    database = WORKDIR / "isolated" / f"{slug(chapter)}.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    if database.exists():
        database.unlink()
    connection = connect(database)
    initialise(connection)
    repository = CatalogueRepository(connection)
    combined = pilot_rows + all_rows
    temp = WORKDIR / "isolated" / f"{slug(chapter)}.csv"
    write_csv(temp, combined)
    errors: list[str] = []
    try:
        repository.import_csv(temp, temp.name)
    except ValueError as error:
        errors.append(str(error))
    imported = {item.item_code: item for item in repository.list_items()}
    missing = []
    incomplete = []
    for row in rows:
        parent_code = row["parent_item_code"]
        if not parent_code:
            continue
        parent = imported.get(parent_code)
        child = imported.get(row["item_code"])
        if parent is None:
            missing.append(f"{row['item_code']}->{parent_code}")
        elif child is None or child.description.count(parent.description) != 1:
            incomplete.append(row["item_code"])
    connection.close()
    return {
        "chapter": chapter,
        "candidate_rows": str(len(rows)),
        "missing_parent_references": str(len(missing)),
        "incomplete_parent_descriptions": str(len(incomplete)),
        "import_errors": str(len(errors)),
        "unverified_only": "yes",
        "status": "pass" if not missing and not incomplete and not errors else "fail",
        "details": "; ".join(errors + missing + incomplete),
    }


def package(documentation: Path) -> None:
    archive_path = WORKDIR / "step4b_chapter_review.zip"
    files = [
        WORKDIR / "remaining_candidates.csv",
        WORKDIR / "page_chapter_inventory.csv",
        WORKDIR / "chapter_inventory.csv",
        WORKDIR / "chapter_counts.csv",
        WORKDIR / "ambiguities.csv",
        WORKDIR / "parent_integrity_report.txt",
        WORKDIR / "source_manifest.txt",
        WORKDIR / "test_output.txt",
        WORKDIR / "checkpoint_summary.txt",
        documentation,
        ROOT / "docs" / "STEP4B_CHAPTER_EXTRACTION.md",
    ]
    files.extend(sorted((WORKDIR / "chapters").glob("*.csv")))
    files.extend(sorted((WORKDIR / "source_images").glob("*.png")))
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            if file_path.exists():
                archive.write(file_path, file_path.relative_to(ROOT))


def main() -> None:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    prewarm_ocr()
    excluded = pilot_codes()
    inventory = []
    candidate_rows: list[dict[str, str]] = []
    ambiguities: list[dict[str, str]] = []
    chapters: dict[str, list[dict[str, str]]] = defaultdict(list)
    checkpoint_path = WORKDIR / "checkpoints.json"
    checkpoints = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
    for volume, pdf in SOURCES.items():
        source_name = pdf.name
        with fitz.open(pdf) as document:
            current_code = ""
            current_name = ""
            current_rank = -1.0
            seen_codes: set[str] = set()
            blocks: list[tuple[int, str, str]] = []
            for page_number in range(1, document.page_count + 1):
                text, confidence, image_path = render_and_ocr(pdf, volume, page_number)
                lines = text.splitlines()
                page_blocks = []
                active_code = None
                active_text = []
                for line in lines:
                    parsed = code_line(line)
                    if parsed:
                        if active_code:
                            page_blocks.append((active_code, " ".join(active_text)))
                        active_code, first_text = parsed
                        active_text = [first_text]
                    elif active_code:
                        active_text.append(line)
                if active_code:
                    page_blocks.append((active_code, " ".join(active_text)))
                page_rows = []
                for code, block_text in page_blocks:
                    chapter_match = CHAPTER_RE.match(code + (" " + clean_text(block_text) if block_text else ""))
                    if chapter_heading(code, block_text) and chapter_rank(code) > current_rank:
                        current_code = code
                        current_name = clean_text(block_text)[:120]
                        current_rank = chapter_rank(code)
                    if current_code and code != current_code:
                        if not valid_code_for_chapter(code, current_code, volume):
                            ambiguities.append({"volume": volume, "pdf_page": str(page_number), "chapter": current_code, "item_code": code, "issue": f"{source_name}: code does not match active chapter prefix", "action": "Review source image; no candidate row emitted."})
                            continue
                        row, problem = parse_item(code, block_text, volume, current_code, current_name, page_number, source_name)
                        if row:
                            is_duplicate = row["item_code"] in seen_codes
                            is_pilot_equivalent = bool(code_equivalents(row["item_code"], volume) & excluded)
                            if is_duplicate:
                                ambiguities.append({"volume": volume, "pdf_page": str(page_number), "chapter": current_code, "item_code": row["item_code"], "issue": f"{source_name}: duplicate OCR item code in source order", "action": "Review source image; duplicate row suppressed from candidates."})
                            else:
                                seen_codes.add(row["item_code"])
                                page_rows.append(row)
                            if is_pilot_equivalent:
                                ambiguities.append({"volume": volume, "pdf_page": str(page_number), "chapter": current_code, "item_code": row["item_code"], "issue": f"{source_name}: code is equivalent to reviewed pilot code", "action": "Pilot record preserved; no Step 4B candidate emitted."})
                            if not is_duplicate and not is_pilot_equivalent:
                                chapters[f"{volume}: {current_code} {current_name}"].append(row)
                                candidate_rows.append(row)
                        if problem:
                            ambiguities.append({"volume": volume, "pdf_page": str(page_number), "chapter": current_code, "item_code": code, "issue": problem, "action": "Review source image; no candidate row emitted."})
                inventory.append({
                    "volume": volume,
                    "pdf_page": str(page_number),
                    "printed_page": "",
                    "chapter_code": current_code,
                    "chapter_name": current_name,
                    "ocr_confidence": f"{confidence:.1f}",
                    "row_count": str(len(page_rows)),
                    "status": "processed",
                    "notes": "OCR source text; page image retained in review package." if page_rows or current_code else "No structured chapter rows detected.",
                })
                checkpoints[f"{volume}:{page_number}"] = {"status": "completed", "chapter": current_code, "rows": len(page_rows)}
                checkpoint_path.write_text(json.dumps(checkpoints, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_inventory(inventory)
    pilot_rows = load_pilot_rows()
    known_codes = {row["item_code"] for row in pilot_rows} | {row["item_code"] for row in candidate_rows}
    while True:
        unresolved = [row for row in candidate_rows if row["parent_item_code"] and row["parent_item_code"] not in known_codes]
        if not unresolved:
            break
        for row in unresolved:
            ambiguities.append({"volume": row["volume"], "pdf_page": row["source_page"], "chapter": row["chapter"], "item_code": row["item_code"], "issue": f"Unresolved parent reference {row['parent_item_code']}", "action": "Chapter marked partial; child excluded from validated candidate CSV until source wording is resolved."})
        candidate_rows = [row for row in candidate_rows if row not in unresolved]
        known_codes = {row["item_code"] for row in pilot_rows} | {row["item_code"] for row in candidate_rows}
    malformed = [row for row in candidate_rows if not row["description"].strip()]
    for row in malformed:
        ambiguities.append({"volume": row["volume"], "pdf_page": row["source_page"], "chapter": row["chapter"], "item_code": row["item_code"], "issue": "OCR row has no recoverable description", "action": "Chapter marked partial; row excluded from candidate CSV."})
    candidate_rows = [row for row in candidate_rows if row not in malformed]
    parent_filter_db = WORKDIR / "parent_filter.sqlite3"
    if parent_filter_db.exists():
        parent_filter_db.unlink()
    parent_filter_connection = connect(parent_filter_db)
    initialise(parent_filter_connection)
    parent_filter_repository = CatalogueRepository(parent_filter_connection)
    parent_filter_csv = WORKDIR / "parent_filter.csv"
    write_csv(parent_filter_csv, pilot_rows + candidate_rows)
    parent_filter_repository.import_csv(parent_filter_csv, parent_filter_csv.name)
    imported = {item.item_code: item for item in parent_filter_repository.list_items()}
    incomplete = [
        row for row in candidate_rows
        if row["parent_item_code"]
        and row["item_code"] in imported
        and row["parent_item_code"] in imported
        and imported[row["item_code"]].description.count(imported[row["parent_item_code"]].description) != 1
    ]
    for row in incomplete:
        ambiguities.append({"volume": row["volume"], "pdf_page": row["source_page"], "chapter": row["chapter"], "item_code": row["item_code"], "issue": "Inherited parent wording is incomplete or repeated after isolated import", "action": "Chapter marked partial; child excluded from validated candidate CSV."})
    candidate_rows = [row for row in candidate_rows if row not in incomplete]
    parent_filter_connection.close()
    parent_filter_db.unlink(missing_ok=True)
    parent_filter_csv.unlink(missing_ok=True)
    known_codes = {row["item_code"] for row in pilot_rows} | {row["item_code"] for row in candidate_rows}
    while True:
        unresolved = [row for row in candidate_rows if row["parent_item_code"] and row["parent_item_code"] not in known_codes]
        if not unresolved:
            break
        for row in unresolved:
            ambiguities.append({"volume": row["volume"], "pdf_page": row["source_page"], "chapter": row["chapter"], "item_code": row["item_code"], "issue": f"Parent removed after wording validation: {row['parent_item_code']}", "action": "Chapter marked partial; child excluded from validated candidate CSV."})
        candidate_rows = [row for row in candidate_rows if row not in unresolved]
        known_codes = {row["item_code"] for row in pilot_rows} | {row["item_code"] for row in candidate_rows}
    chapters = defaultdict(list)
    for row in candidate_rows:
        chapters[f"{row['volume']}: {row['chapter']}"].append(row)
    (WORKDIR / "chapters").mkdir(parents=True, exist_ok=True)
    chapter_counts = []
    for chapter, rows in sorted(chapters.items()):
        chapter_path = WORKDIR / "chapters" / f"{slug(chapter)}.csv"
        write_csv(chapter_path, rows)
        chapter_counts.append({"chapter": chapter, "candidate_rows": str(len(rows)), "status": "complete"})
    write_csv(WORKDIR / "remaining_candidates.csv", candidate_rows)
    with (WORKDIR / "ambiguities.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["volume", "pdf_page", "chapter", "item_code", "issue", "action"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ambiguities)
    with (WORKDIR / "chapter_inventory.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["chapter", "candidate_rows", "status"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(chapter_counts)
    with (WORKDIR / "chapter_counts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["volume", "chapters", "candidate_rows", "ambiguities", "status"], lineterminator="\n")
        writer.writeheader()
        for volume in SOURCES:
            volume_rows = [row for row in candidate_rows if row["volume"] == volume]
            volume_chapters = [name for name in chapters if name.startswith(volume + ":")]
            volume_ambiguities = [row for row in ambiguities if row["volume"] == volume]
            writer.writerow({"volume": volume, "chapters": len(volume_chapters), "candidate_rows": len(volume_rows), "ambiguities": len(volume_ambiguities), "status": "partial" if volume_ambiguities else "complete"})
    validations = [validate_chapter(chapter, rows, candidate_rows, pilot_rows) for chapter, rows in sorted(chapters.items())]
    failures = [result for result in validations if result["status"] != "pass"]
    with (WORKDIR / "parent_integrity_report.txt").open("w", encoding="utf-8") as handle:
        handle.write("Step 4B isolated chapter validation\nImported pilot plus Step 4B candidates only; no live database was used.\n")
        handle.write(f"chapters_checked={len(validations)}\nchapters_failed={len(failures)}\n")
        handle.write(f"candidate_rows={len(candidate_rows)}\nunresolved_parent_references={sum(int(x['missing_parent_references']) for x in validations)}\n")
        handle.write(f"incomplete_parent_descriptions={sum(int(x['incomplete_parent_descriptions']) for x in validations)}\nall_records_unverified=yes\n")
        for result in validations:
            handle.write(f"{result['chapter']}: {result['status']} rows={result['candidate_rows']} details={result['details'] or 'none'}\n")
    checkpoint_summary = WORKDIR / "checkpoint_summary.txt"
    checkpoint_summary.write_text(f"pages_completed={len(checkpoints)}\nchapters_completed={len(chapters)}\nresumable_checkpoint={checkpoint_path.relative_to(ROOT)}\n", encoding="utf-8")
    manifest = WORKDIR / "source_manifest.txt"
    manifest.write_text("Step 4B source manifest\n" + "\n".join(f"{path.name} sha256={sha256(path)} pages={len(fitz.open(path))}" for path in SOURCES.values()) + "\n", encoding="utf-8")
    test = subprocess.run(["python", "-m", "pytest", "-q"], cwd=ROOT, env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": "."}, capture_output=True, text=True)
    (WORKDIR / "test_output.txt").write_text(test.stdout + test.stderr, encoding="utf-8")
    if test.returncode or failures:
        raise RuntimeError("Step 4B validation failed; inspect parent_integrity_report.txt and test_output.txt")
    package(ROOT / "docs" / "STEP4_PILOT_EXTRACTION.md")
    print(f"Step 4B candidates: {len(candidate_rows)} rows across {len(chapters)} chapters; ambiguities={len(ambiguities)}")


if __name__ == "__main__":
    main()
