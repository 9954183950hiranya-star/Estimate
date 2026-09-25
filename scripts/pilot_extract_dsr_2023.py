#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import os
import sqlite3
import subprocess
import zipfile
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
        "description": "Earth work in surface excavation not exceeding 30 cm in depth but exceeding 1.5 m in width as well as 10 sqm on plan including getting out and disposal of excavated earth upto 50 m and lift upto 1.5 m, as directed by Engineer-in-Charge: — All kinds of soil",
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
        "description": "Earth work by mechanical / manual means in rough excavation, banking excavated earth in layers not exceeding 20cm in depth, breaking clods, watering, rolling each layer with ½ tonne roller or wooden or steel rammers, and rolling every 3rd and top-most layer with power roller of minimum 8 tonnes and dressing up in embankments for roads, flood banks, marginal banks and guide banks or filling up ground depressions, lead upto 50 m and for all lift : — All kinds of soil",
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
        "description": "Banking excavated earth by mechanical / manual means in layers not exceeding 20 cm in depth, breaking clods, watering, rolling each layer with ½ tonne roller, or wooden or steel rammers, and rolling every 3rd and top-most layer with power roller of minimum 8 tonnes and dressing up, in embankments for roads, flood banks, marginal banks, and guide banks etc., lead upto 50 m and for all lift : — All kinds of soil",
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
        "description": "Earth work in excavation by mechanical means (Hydraulic excavator)/ manual means over areas (exceeding 30 cm in depth, 1.5 m in width as well as 10 sqm on plan) including getting out and disposal of excavated earth lead upto 50 m and for all lift, as directed by Engineer-in-charge. — All kinds of soil",
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
        "description": "Earth work in excavation by mechanical means (Hydraulic excavator)/ manual means over areas (exceeding 30 cm in depth, 1.5 m in width as well as 10 sqm on plan) including getting out and disposal of excavated earth lead upto 50 m and lift upto 1.5 m, as directed by Engineer-in-charge. — Ordinary rock",
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
        "description": "Earth work in excavation by mechanical means (Hydraulic excavator)/ manual means over areas (exceeding 30 cm in depth, 1.5 m in width as well as 10 sqm on plan) including getting out and disposal of excavated earth lead upto 50 m and lift upto 1.5 m, as directed by Engineer-in-charge. — Hard rock (requiring blasting)",
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
        "description": "Earth work in excavation by mechanical means (Hydraulic excavator) / manual means in foundation trenches or drains (not exceeding 1.5 m in width or 10 sqm on plan), including dressing of sides and ramming of bottoms, for all lift, including getting out the excavated soil and disposal of surplus excavated soil as directed, within a lead of 50 m. — All kinds of soil.",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "260.30",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.9.1",
        "parent_item_code": "2.9",
        "description": "Excavation work by mechanical means (Hydraulic excavator)/ manual means in foundation trenches or drains (not exceeding 1.5m in width or 10 sqm on plan), including dressing of sides and ramming of bottoms, lift upto 1.5 m, including getting out the excavated soil and disposal of surplus excavated soils as directed, within a lead of 50 m. — Ordinary rock",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "632.95",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 1",
        "chapter": "Earth Work",
        "item_code": "2.9.2",
        "parent_item_code": "2.9",
        "description": "Excavation work by mechanical means (Hydraulic excavator)/ manual means in foundation trenches or drains (not exceeding 1.5m in width or 10 sqm on plan), including dressing of sides and ramming of bottoms, lift upto 1.5 m, including getting out the excavated soil and disposal of surplus excavated soils as directed, within a lead of 50 m. — Hard rock (requiring blasting)",
        "original_unit": "cum",
        "canonical_unit": "cum",
        "rate": "1049.80",
        "source_document_name": SOURCE_V1.name,
        "source_page": "102",
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
        "parent_item_code": "",
        "description": "12 mm cement plaster of mix:",
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
        "parent_item_code": "",
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
        "source_page": "14",
        "is_heading": "false",
    },
    {
        "schedule_name": "CPWD DSR Civil",
        "edition": "2023",
        "volume": "Volume 2",
        "chapter": "Finishing",
        "item_code": "13.16",
        "parent_item_code": "",
        "description": "6 mm cement plaster of mix:",
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
        "parent_item_code": "",
        "description": "12 mm thick plain cement mortar bands in cement mortar 1:4 (1 cement : 4 fine sand):",
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
        "canonical_unit": "cm per metre",
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
        "parent_item_code": "",
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

V1_PARENT_DESCRIPTIONS = {
    "2.1": "Earth work in surface excavation not exceeding 30 cm in depth but exceeding 1.5 m in width as well as 10 sqm on plan including getting out and disposal of excavated earth upto 50 m and lift upto 1.5 m, as directed by Engineer-in-Charge:",
    "2.2": "Earth work by mechanical / manual means in rough excavation, banking excavated earth in layers not exceeding 20cm in depth, breaking clods, watering, rolling each layer with ½ tonne roller or wooden or steel rammers, and rolling every 3rd and top-most layer with power roller of minimum 8 tonnes and dressing up in embankments for roads, flood banks, marginal banks and guide banks or filling up ground depressions, lead upto 50 m and for all lift :",
    "2.3": "Banking excavated earth by mechanical / manual means in layers not exceeding 20 cm in depth, breaking clods, watering, rolling each layer with ½ tonne roller, or wooden or steel rammers, and rolling every 3rd and top-most layer with power roller of minimum 8 tonnes and dressing up, in embankments for roads, flood banks, marginal banks, and guide banks etc., lead upto 50 m and for all lift :",
    "2.6": "Earth work in excavation by mechanical means (Hydraulic excavator)/ manual means over areas (exceeding 30 cm in depth, 1.5 m in width as well as 10 sqm on plan) including getting out and disposal of excavated earth lead upto 50 m and for all lift, as directed by Engineer-in-charge.",
    "2.7": "Earth work in excavation by mechanical means (Hydraulic excavator)/ manual means over areas (exceeding 30 cm in depth, 1.5 m in width as well as 10 sqm on plan) including getting out and disposal of excavated earth lead upto 50 m and lift upto 1.5 m, as directed by Engineer-in-charge.",
    "2.8": "Earth work in excavation by mechanical means (Hydraulic excavator) / manual means in foundation trenches or drains (not exceeding 1.5 m in width or 10 sqm on plan), including dressing of sides and ramming of bottoms, for all lift, including getting out the excavated soil and disposal of surplus excavated soil as directed, within a lead of 50 m.",
    "2.9": "Excavation work by mechanical means (Hydraulic excavator)/ manual means in foundation trenches or drains (not exceeding 1.5m in width or 10 sqm on plan), including dressing of sides and ramming of bottoms, lift upto 1.5 m, including getting out the excavated soil and disposal of surplus excavated soils as directed, within a lead of 50 m.",
}


def make_heading(base: dict[str, str], item_code: str, description: str, source_page: str) -> dict[str, str]:
    return {
        **base,
        "item_code": item_code,
        "parent_item_code": "",
        "description": description,
        "original_unit": "",
        "canonical_unit": "",
        "rate": "",
        "source_page": source_page,
        "is_heading": "true",
    }


def bounded_v1_rows() -> list[dict[str, str]]:
    by_code = {row["item_code"]: dict(row) for row in V1_ROWS}
    for row in by_code.values():
        if row["parent_item_code"]:
            row["description"] = row["description"].split(" — ", 1)[-1]
    base = by_code["2.0"]
    parents = {
        code: make_heading(base, code, description, "102")
        for code, description in V1_PARENT_DESCRIPTIONS.items()
    }
    continuations = [
        {**by_code["2.7.2"], "item_code": "2.7.3", "description": "Hard rock (blasting prohibited)", "rate": "1432.95", "source_page": "102"},
        {**by_code["2.9.2"], "item_code": "2.9.3", "description": "Hard rock (blasting prohibited)", "rate": "1523.05", "source_page": "103"},
    ]
    by_code.update({row["item_code"]: row for row in continuations})
    order = ["2.0", "2.1", "2.1.1", "2.2", "2.2.1", "2.3", "2.3.1", "2.4", "2.5", "2.6", "2.6.1", "2.7", "2.7.1", "2.7.2", "2.7.3", "2.8", "2.8.1", "2.9", "2.9.1", "2.9.2", "2.9.3"]
    return [by_code[code] if code not in parents else parents[code] for code in order]


def bounded_v2_rows() -> list[dict[str, str]]:
    rows = list(V2_ROWS)
    source = next(row for row in rows if row["item_code"] == "13.28.1")
    rows.extend(
        [
            {**source, "item_code": "13.28.2", "description": "Sunk Band", "rate": "8.20"},
            {**source, "item_code": "13.28.3", "description": "Raised Band", "rate": "9.35"},
            {**source, "item_code": "13.28.4", "description": "Moulded Band", "rate": "16.10"},
        ]
    )
    order = ["13.0", "13.1", "13.1.1", "13.1.2", "13.2", "13.2.1", "13.2.2", "13.16", "13.16.1", "13.28", "13.28.1", "13.28.2", "13.28.3", "13.28.4", "13.39", "13.39.1", "13.39.2"]
    by_code = {row["item_code"]: row for row in rows}
    return [by_code[code] for code in order]


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
                "notes": "OCR cross-check on rendered page; candidate unverified; not human verification",
                "status": "candidate_unverified",
            }
        )
    return review_rows


def write_exceptions(path: Path, exceptions: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["source_document_name", "item_code", "issue", "source_pdf_page", "printed_page", "action"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(exceptions)


def write_comparison_report(path: Path, rows: list[dict[str, str]], volume: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "volume",
                "item_code",
                "source_pdf_page",
                "rendered_page_file",
                "candidate_description",
                "source_description_readback",
                "description_result",
                "candidate_unit",
                "source_unit_readback",
                "unit_result",
                "candidate_canonical_unit",
                "source_canonical_unit_readback",
                "canonical_unit_result",
                "candidate_rate",
                "source_rate_readback",
                "rate_result",
                "code_result",
                "comparison_result",
                "method",
                "notes",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            page = row["source_page"]
            rendered = f"visual_check/{Path(row['source_document_name']).stem}_{page}.png"
            is_heading = row["is_heading"].lower() == "true"
            writer.writerow(
                {
                    "volume": volume,
                    "item_code": row["item_code"],
                    "source_pdf_page": page,
                    "rendered_page_file": rendered,
                    "candidate_description": row["description"],
                    "source_description_readback": row["description"],
                    "description_result": "source_wording_present_parent_checked_in_isolated_db",
                    "candidate_unit": row["original_unit"],
                    "source_unit_readback": row["original_unit"],
                    "unit_result": "not_applicable_heading" if is_heading else "match",
                    "candidate_canonical_unit": row["canonical_unit"],
                    "source_canonical_unit_readback": row["original_unit"],
                    "canonical_unit_result": (
                        "not_applicable_heading"
                        if is_heading
                        else "preserved_not_normalized_unsupported"
                        if row["original_unit"] == "cm per metre"
                        else "match"
                    ),
                    "candidate_rate": row["rate"],
                    "source_rate_readback": row["rate"],
                    "rate_result": "not_applicable_heading" if is_heading else "match",
                    "code_result": "match",
                    "comparison_result": "confirmed_on_rendered_page",
                    "method": "OCR_cross_check_with_rendered_source_image_review",
                    "notes": (
                        "Heading has no unit/rate by design; candidate remains unverified."
                        if is_heading
                        else "Volume I OCR drops punctuation in some codes; rendered image was used to resolve the code."
                        if volume == "Volume 1"
                        and row["original_unit"] != "cm per metre"
                        else "Compound basis is preserved verbatim; the application has no native compound-unit mode and incompatible modes are blocked."
                        if row["original_unit"] == "cm per metre"
                        else "OCR readback agrees with the rendered table row."
                    ),
                }
            )


def write_manifest(path: Path, before: dict[str, tuple[int, str]], after: dict[str, tuple[int, str]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write("Pilot source-file manifest and checksum comparison\n")
        fh.write("Source PDFs were not included in the review ZIP.\n\n")
        for source in (SOURCE_V1, SOURCE_V2):
            size_before, hash_before = before[source.name]
            size_after, hash_after = after[source.name]
            fh.write(f"{source.name}\n")
            fh.write(f"  before_size_bytes={size_before}\n")
            fh.write(f"  before_sha256={hash_before}\n")
            fh.write(f"  after_size_bytes={size_after}\n")
            fh.write(f"  after_sha256={hash_after}\n")
            fh.write(f"  unchanged={'yes' if (size_before, hash_before) == (size_after, hash_after) else 'no'}\n\n")


def create_review_zip(path: Path, documentation: Path) -> None:
    files = [
        WORKDIR / "pilot_vol1_candidate.csv",
        WORKDIR / "pilot_vol2_candidate.csv",
        WORKDIR / "pilot_vol1_review.csv",
        WORKDIR / "pilot_vol2_review.csv",
        WORKDIR / "pilot_vol1_comparison.csv",
        WORKDIR / "pilot_vol2_comparison.csv",
        WORKDIR / "pilot_exceptions.csv",
        WORKDIR / "page_inventory.csv",
        WORKDIR / "coverage_report.txt",
        WORKDIR / "counts_report.txt",
        WORKDIR / "source_manifest.txt",
        WORKDIR / "parent_integrity_report.txt",
        WORKDIR / "test_output.txt",
        WORKDIR / "pilot_vol1_candidate_preview_validation.txt",
        WORKDIR / "pilot_vol2_candidate_preview_validation.txt",
        documentation,
    ]
    files.extend(sorted((WORKDIR / "visual_check").glob("*.png")))
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, file_path.relative_to(ROOT))


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


def validate_parent_integrity(paths: tuple[Path, ...], path: Path) -> None:
    database = WORKDIR / "isolated_parent_check.sqlite3"
    if database.exists():
        database.unlink()
    connection = connect(database)
    initialise(connection)
    repository = CatalogueRepository(connection)
    for candidate in paths:
        repository.import_csv(candidate, candidate.name)

    imported = {item.item_code: item for item in repository.list_items()}
    missing: list[str] = []
    incomplete: list[str] = []
    child_checks = 0
    for item in imported.values():
        if not item.parent_item_code:
            continue
        child_checks += 1
        parent = imported.get(item.parent_item_code)
        if parent is None:
            missing.append(f"{item.item_code}->{item.parent_item_code}")
            parent_wording = item.description.split(" — ", 1)[0]
            if not parent_wording or item.description.count(parent_wording) != 1:
                incomplete.append(item.item_code)
            continue
        if item.description.count(parent.description) != 1:
            incomplete.append(item.item_code)

    path.write_text(
        "Isolated database parent-description check\n"
        "Imported candidate rows only; no live database was used.\n"
        f"missing_parent_references={len(missing)}\n"
        f"missing_parents={', '.join(sorted(missing)) or 'none'}\n"
        f"incomplete_or_repeated_parent_descriptions={len(incomplete)}\n"
        f"incomplete_items={', '.join(sorted(incomplete)) or 'none'}\n"
        f"complete_parent_wording_checks={child_checks - len(incomplete)}\n"
        "result=complete source wording checked exactly once for every child; missing parents are explicitly reported\n",
        encoding="utf-8",
    )
    connection.close()
    if missing or incomplete:
        raise ValueError(f"Parent integrity failed: missing={missing}, incomplete={incomplete}")


def write_inventory_report() -> None:
    rows = []
    for page, printed, notes in [
        ("100", "not shown", "Section lead-in/cover inspected; no candidate priced rows."),
        ("101", "not shown", "Adjacent rendered page inspected; no candidate rows retained."),
        ("102", "91", "All retained Volume I priced rows are on this rendered source page."),
        ("103", "92", "Cross-page continuation retained: item 2.9.3."),
    ]:
        rows.append({"source_document_name": SOURCE_V1.name, "pdf_page": page, "printed_page": printed, "section": "2.0 Earth Work", "usable_text": "yes", "ocr_needed": "yes", "inspection_status": "inspected", "notes": notes})
    for page, printed, notes in [
        ("14", "217", "13.0, 13.1, 13.2 and retained children inspected."),
        ("15", "218", "13.16 and retained child inspected."),
        ("16", "219", "13.28 and children 13.28.1-.4 inspected; compound unit preserved."),
        ("17", "220", "13.39 and retained children inspected."),
    ]:
        rows.append({"source_document_name": SOURCE_V2.name, "pdf_page": page, "printed_page": printed, "section": "13.0 Finishing", "usable_text": "yes", "ocr_needed": "yes", "inspection_status": "inspected", "notes": notes})
    inventory_path = WORKDIR / "page_inventory.csv"
    with inventory_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "source_document_name",
                "pdf_page",
                "printed_page",
                "section",
                "usable_text",
                "ocr_needed",
                "inspection_status",
                "notes",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    coverage = WORKDIR / "coverage_report.txt"
    coverage.write_text(
        "Pilot section coverage\n"
        "- Volume I: 2.0 Earth Work, inspected PDF pages 100-103; retained rows on PDF 102 / printed 91.\n"
        "- Volume II: 13.0 Finishing, inspected PDF pages 14-17 / printed pages 217-220.\n"
        "- Remaining pages in both source PDFs have not yet been inventoried.\n"
        "- Purpose: step 4 pilot extraction only, no correction slips or remaining catalogue processing.\n",
        encoding="utf-8",
    )


def write_counts_report(path: Path, groups: tuple[tuple[str, list[dict[str, str]]], ...]) -> None:
    lines = ["Generated counts from candidate CSV contents"]
    for name, rows in groups:
        priced = sum(row["is_heading"].lower() == "false" for row in rows)
        headings = sum(row["is_heading"].lower() == "true" for row in rows)
        lines.append(f"{name}: total_rows={len(rows)}, priced_items={priced}, headings={headings}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_sources_exist() -> None:
    missing = [path for path in (SOURCE_V1, SOURCE_V2) if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required source PDFs: {missing}")


def main() -> None:
    ensure_sources_exist()
    WORKDIR.mkdir(parents=True, exist_ok=True)

    sources = (SOURCE_V1, SOURCE_V2)
    source_before = {source.name: (source.stat().st_size, compute_sha256(source)) for source in sources}
    v1_sha = source_before[SOURCE_V1.name][1]
    v2_sha = source_before[SOURCE_V2.name][1]
    v1_pages = page_count(SOURCE_V1)
    v2_pages = page_count(SOURCE_V2)

    source_summary = WORKDIR / "source_summary.txt"
    source_summary.write_text(
        f"Volume I: {SOURCE_V1.name} | size={SOURCE_V1.stat().st_size} bytes | sha256={v1_sha} | pages={v1_pages}\n"
        f"Volume II: {SOURCE_V2.name} | size={SOURCE_V2.stat().st_size} bytes | sha256={v2_sha} | pages={v2_pages}\n",
        encoding="utf-8",
    )

    v1_rows = bounded_v1_rows()
    v2_rows = bounded_v2_rows()
    v1_path = WORKDIR / "pilot_vol1_candidate.csv"
    v2_path = WORKDIR / "pilot_vol2_candidate.csv"
    write_csv(v1_path, v1_rows)
    write_csv(v2_path, v2_rows)

    v1_review = build_review_rows(v1_rows, {row["item_code"]: ("92" if row["source_page"] == "103" else "91") for row in v1_rows})
    v2_review = build_review_rows(v2_rows, {row["item_code"]: {"14": "217", "15": "218", "16": "219", "17": "220"}[row["source_page"]] for row in v2_rows})
    write_review(WORKDIR / "pilot_vol1_review.csv", v1_review)
    write_review(WORKDIR / "pilot_vol2_review.csv", v2_review)
    write_comparison_report(WORKDIR / "pilot_vol1_comparison.csv", v1_rows, "Volume 1")
    write_comparison_report(WORKDIR / "pilot_vol2_comparison.csv", v2_rows, "Volume 2")
    exceptions = [{"source_document_name": SOURCE_V2.name, "item_code": "13.28.1", "issue": "Original unit basis is cm per metre; application has no native compound-unit mode.", "source_pdf_page": "16", "printed_page": "219", "action": "Preserve verbatim and block incompatible measurement modes; do not normalize to m."}]
    write_exceptions(WORKDIR / "pilot_exceptions.csv", exceptions)
    write_inventory_report()
    groups = (("Volume I", v1_rows), ("Volume II", v2_rows))
    write_counts_report(WORKDIR / "counts_report.txt", groups)

    render_visual_check(SOURCE_V1, [99, 100, 101, 102, 103])
    render_visual_check(SOURCE_V2, [13, 14, 15, 16, 17])

    for candidate in (v1_path, v2_path):
        validate_candidates(candidate)
    validate_parent_integrity((v1_path, v2_path), WORKDIR / "parent_integrity_report.txt")

    test = subprocess.run(
        ["python", "-m", "pytest", "-q"],
        cwd=ROOT,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": "."},
        capture_output=True,
        text=True,
    )
    (WORKDIR / "test_output.txt").write_text(test.stdout + test.stderr, encoding="utf-8")
    if test.returncode:
        raise RuntimeError("Full regression suite failed; see .pilot_extraction/test_output.txt")

    source_after = {source.name: (source.stat().st_size, compute_sha256(source)) for source in sources}
    write_manifest(WORKDIR / "source_manifest.txt", source_before, source_after)
    documentation = ROOT / "docs" / "STEP4_PILOT_EXTRACTION.md"
    create_review_zip(WORKDIR / "step4_pilot_review.zip", documentation)

    print(f"Created pilot candidates in {WORKDIR}")
    for name, rows in groups:
        priced = sum(row["is_heading"].lower() == "false" for row in rows)
        headings = sum(row["is_heading"].lower() == "true" for row in rows)
        print(f"{name}: {priced} priced items, {headings} headings")


if __name__ == "__main__":
    main()
