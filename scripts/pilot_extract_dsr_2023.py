#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import sqlite3
from pathlib import Path

import fitz

from estimate_app.database.catalogue import CATALOGUE_HEADERS, CatalogueRepository
from estimate_app.database.connection import connect, initialise

ROOT = Path(__file__).resolve().parents[1]
WORKDIR = ROOT / ".pilot_extraction"
SOURCE_V1 = ROOT / "reference_sources" / "DSR_Vol_1_Civil 2023.pdf"
SOURCE_V2 = ROOT / "reference_sources" / "DSR_Vol_2_Civil  2023.pdf"

V1_ROWS = [
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.0",
        "parent_item_code": "",
        "description": "EARTH WORK",
        "original_unit": "",
        "canonical_unit": "",
        "rate": "",
        "source_document_name": SOURCE_V1.name,
        "source_page": "100",
        "is_heading": "true",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.1.1",
        "parent_item_code": "2.1",
        "description": "All kinds of soil",
        "original_unit": "sqm",
        "canonical_unit": "sqm",
        "rate": "129.85",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.2.1",
        "parent_item_code": "2.2",
        "description": "All kinds of soil",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "395.30",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.3.1",
        "parent_item_code": "2.3",
        "description": "All kinds of soil",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "197.90",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.4",
        "parent_item_code": "",
        "description": "Deduct for not rolling with power roller of minimum 8 tonnes for banking excavated earth in layers not exceeding 20 cm in depth.",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "5.25",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.5",
        "parent_item_code": "",
        "description": "Deduct for not watering the excavated earth for banking",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "14.25",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.6.1",
        "parent_item_code": "2.6",
        "description": "All kinds of soil",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "177.50",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.7.1",
        "parent_item_code": "2.7",
        "description": "Ordinary rock",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "498.90",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.7.2",
        "parent_item_code": "2.7",
        "description": "Hard rock (requiring blasting)",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "874.40",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.8.1",
        "parent_item_code": "2.8",
        "description": "All kinds of soil.",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "260.30",
        "source_document_name": SOURCE_V1.name,
        "source_page": "103",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.9.1",
        "parent_item_code": "2.9",
        "description": "Ordinary rock",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "632.95",
        "source_document_name": SOURCE_V1.name,
        "source_page": "103",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.9.2",
        "parent_item_code": "2.9",
        "description": "Hard rock (requiring blasting)",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "1049.80",
        "source_document_name": SOURCE_V1.name,
        "source_page": "103",
        "is_heading": "false",
    },
]

V2_ROWS = [
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.0",
        "parent_item_code": "",
        "description": "FINISHING",
        "original_unit": "",
        "canonical_unit": "",
        "rate": "",
        "source_document_name": SOURCE_V2.name,
        "source_page": "14",
        "is_heading": "true",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.1",
        "parent_item_code": "13.0",
        "description": "CEMENT PLASTER (IN FINE SAND)",
        "original_unit": "",
        "canonical_unit": "",
        "rate": "",
        "source_document_name": SOURCE_V2.name,
        "source_page": "14",
        "is_heading": "true",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.1.1",
        "parent_item_code": "13.1",
        "description": "1:4 (1 cement: 4 fine sand)",
        "original_unit": "sqm",
        "canonical_unit": "sqm",
        "rate": "347.05",
        "source_document_name": SOURCE_V2.name,
        "source_page": "14",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.1.2",
        "parent_item_code": "13.1",
        "description": "1:6 (1 cement: 6 fine sand)",
        "original_unit": "sqm",
        "canonical_unit": "sqm",
        "rate": "333.35",
        "source_document_name": SOURCE_V2.name,
        "source_page": "14",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.2",
        "parent_item_code": "13.0",
        "description": "15 mm cement plaster on the rough side of single or half brick wall of mix :",
        "original_unit": "",
        "canonical_unit": "",
        "rate": "",
        "source_document_name": SOURCE_V2.name,
        "source_page": "14",
        "is_heading": "true",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.2.1",
        "parent_item_code": "13.2",
        "description": "1:4 (1 cement: 4 fine sand)",
        "original_unit": "sqm",
        "canonical_unit": "sqm",
        "rate": "399.45",
        "source_document_name": SOURCE_V2.name,
        "source_page": "14",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.2.2",
        "parent_item_code": "13.2",
        "description": "1:6 (1 cement: 6 fine sand)",
        "original_unit": "sqm",
        "canonical_unit": "sqm",
        "rate": "383.00",
        "source_document_name": SOURCE_V2.name,
        "source_page": "15",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.16",
        "parent_item_code": "13.0",
        "description": "6 mm CEMENT PLASTER",
        "original_unit": "",
        "canonical_unit": "",
        "rate": "",
        "source_document_name": SOURCE_V2.name,
        "source_page": "15",
        "is_heading": "true",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.16.1",
        "parent_item_code": "13.16",
        "description": "1:3 (1 cement : 3 fine sand)",
        "original_unit": "sqm",
        "canonical_unit": "sqm",
        "rate": "300.45",
        "source_document_name": SOURCE_V2.name,
        "source_page": "15",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.28",
        "parent_item_code": "13.0",
        "description": "PLAIN CEMENT MORTAR BANDS",
        "original_unit": "",
        "canonical_unit": "",
        "rate": "",
        "source_document_name": SOURCE_V2.name,
        "source_page": "16",
        "is_heading": "true",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.28.1",
        "parent_item_code": "13.28",
        "description": "Flush Band",
        "original_unit": "cm per metre",
        "canonical_unit": "m",
        "rate": "7.50",
        "source_document_name": SOURCE_V2.name,
        "source_page": "16",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.39",
        "parent_item_code": "13.0",
        "description": "Colour washing such as green, blue or buff to give an even shade :",
        "original_unit": "",
        "canonical_unit": "",
        "rate": "",
        "source_document_name": SOURCE_V2.name,
        "source_page": "17",
        "is_heading": "true",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.39.1",
        "parent_item_code": "13.39",
        "description": "New work (two or more coats) with a base coat of white washing with lime",
        "original_unit": "sqm",
        "canonical_unit": "sqm",
        "rate": "53.30",
        "source_document_name": SOURCE_V2.name,
        "source_page": "17",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.39.2",
        "parent_item_code": "13.39",
        "description": "New work (two or more coats) with a base coat of whiting",
        "original_unit": "sqm",
        "canonical_unit": "sqm",
        "rate": "52.75",
        "source_document_name": SOURCE_V2.name,
        "source_page": "17",
        "is_heading": "false",
    },
]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CATALOGUE_HEADERS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_review(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "schedule_name",
                "edition",
                "volume",
                "chapter",
                "item_code",
                "source_pdf_page",
                "printed_page",
                "parent_item_code",
                "source_document_name",
                "description",
                "original_unit",
                "canonical_unit",
                "rate",
                "notes",
                "status",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def build_review_rows(rows: list[dict[str, str]], printed_map: dict[str, str]) -> list[dict[str, str]]:
    review_rows: list[dict[str, str]] = []
    for row in rows:
        item_code = row["item_code"]
        review_rows.append(
            {
                "schedule_name": row["schedule_name"],
                "edition": row["edition"],
                "volume": row["volume"],
                "chapter": row["chapter"],
                "item_code": item_code,
                "source_pdf_page": row["source_page"],
                "printed_page": printed_map.get(item_code, row["source_page"]),
                "parent_item_code": row["parent_item_code"],
                "source_document_name": row["source_document_name"],
                "description": row["description"],
                "original_unit": row["original_unit"],
                "canonical_unit": row["canonical_unit"],
                "rate": row["rate"],
                "notes": "OCR cross-check on rendered page; candidate unverified",
                "status": "candidate_unverified",
            }
        )
    return review_rows


def write_exceptions(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["source_document_name", "item_code", "issue", "source_pdf_page", "printed_page", "action"],
            lineterminator="\n",
        )
        writer.writeheader()


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def page_count(path: Path) -> int:
    with fitz.open(path) as doc:
        return doc.page_count


def render_visual_check(pdf: Path, pages: list[int]) -> None:
    out_dir = WORKDIR / "visual_check"
    out_dir.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf) as doc:
        for page_index in pages:
            page = doc[page_index]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            pix.save(out_dir / f"{pdf.stem}_{page_index + 1}.png")


def validate_candidates(path: Path) -> None:
    temp_db = connect(WORKDIR / "preview.sqlite3")
    initialise(temp_db)
    repo = CatalogueRepository(temp_db)
    preview = repo.preview_csv(path, path.name)
    if preview.errors:
        raise ValueError(f"{path.name} failed preview validation: {preview.errors}")
    validation_path = WORKDIR / f"{path.stem}_preview_validation.txt"
    validation_path.write_text(f"{path.name}: OK\nrows={len(preview.rows)}\nerrors={len(preview.errors)}\n", encoding="utf-8")


def write_inventory_report() -> None:
    rows = [
        {
            "source_document_name": SOURCE_V1.name,
            "pdf_page_start": "100",
            "pdf_page_end": "103",
            "printed_page_range": "93-95",
            "section": "2.0 Earth Work",
            "usable_text": "yes",
            "ocr_needed": "yes",
            "extraction_status": "pilot_candidate",
            "notes": "OCR cross-check for section start and item table; candidate records marked unverified.",
        },
        {
            "source_document_name": SOURCE_V2.name,
            "pdf_page_start": "14",
            "pdf_page_end": "17",
            "printed_page_range": "217-220",
            "section": "13.0 Finishing",
            "usable_text": "yes",
            "ocr_needed": "yes",
            "extraction_status": "pilot_candidate",
            "notes": "OCR cross-check for finishing subhead and parent/child item sequence; candidate records marked unverified.",
        },
    ]
    inventory_path = WORKDIR / "page_inventory.csv"
    with inventory_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "source_document_name",
                "pdf_page_start",
                "pdf_page_end",
                "printed_page_range",
                "section",
                "usable_text",
                "ocr_needed",
                "extraction_status",
                "notes",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    coverage = WORKDIR / "coverage_report.txt"
    coverage.write_text(
        "Pilot section coverage\n"
        "- Volume I: 2.0 Earth Work, source PDF pages 100-103 (printed pages approx. 93-95)\n"
        "- Volume II: 13.0 Finishing, source PDF pages 14-17 (printed pages 217-220)\n"
        "- Purpose: step 4 pilot extraction only, no correction slips or remaining catalogue processing.\n",
        encoding="utf-8",
    )


def ensure_sources_exist() -> None:
    missing = [path for path in (SOURCE_V1, SOURCE_V2) if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required source PDFs: {missing}")


def main() -> None:
    ensure_sources_exist()
    WORKDIR.mkdir(parents=True, exist_ok=True)

    v1_sha = compute_sha256(SOURCE_V1)
    v2_sha = compute_sha256(SOURCE_V2)
    v1_pages = page_count(SOURCE_V1)
    v2_pages = page_count(SOURCE_V2)

    source_summary = WORKDIR / "source_summary.txt"
    source_summary.write_text(
        f"Volume I: {SOURCE_V1.name} | size={SOURCE_V1.stat().st_size} bytes | sha256={v1_sha} | pages={v1_pages}\n"
        f"Volume II: {SOURCE_V2.name} | size={SOURCE_V2.stat().st_size} bytes | sha256={v2_sha} | pages={v2_pages}\n",
        encoding="utf-8",
    )

    v1_path = WORKDIR / "pilot_vol1_candidate.csv"
    v2_path = WORKDIR / "pilot_vol2_candidate.csv"
    write_csv(v1_path, V1_ROWS)
    write_csv(v2_path, V2_ROWS)

    v1_review = build_review_rows(V1_ROWS, {"2.0": "93", "2.1.1": "94", "2.2.1": "94", "2.3.1": "94", "2.4": "94", "2.5": "94", "2.6.1": "95", "2.7.1": "95", "2.7.2": "95", "2.8.1": "95", "2.9.1": "95", "2.9.2": "95"})
    v2_review = build_review_rows(V2_ROWS, {"13.0": "217", "13.1": "217", "13.1.1": "217", "13.1.2": "217", "13.2": "217", "13.2.1": "217", "13.2.2": "217", "13.16": "218", "13.16.1": "218", "13.28": "219", "13.28.1": "219", "13.39": "220", "13.39.1": "220", "13.39.2": "220"})
    write_review(WORKDIR / "pilot_vol1_review.csv", v1_review)
    write_review(WORKDIR / "pilot_vol2_review.csv", v2_review)
    write_exceptions(WORKDIR / "pilot_exceptions.csv")
    write_inventory_report()

    render_visual_check(SOURCE_V1, [99, 100, 101, 102, 103])
    render_visual_check(SOURCE_V2, [13, 14, 15, 16, 17])

    for candidate in (v1_path, v2_path):
        validate_candidates(candidate)

    print(f"Created pilot candidates in {WORKDIR}")
    print(f"Volume I candidate rows: {len(V1_ROWS)}")
    print(f"Volume II candidate rows: {len(V2_ROWS)}")


if __name__ == "__main__":
    main()
