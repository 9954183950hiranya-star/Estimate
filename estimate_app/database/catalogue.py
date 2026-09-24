from __future__ import annotations

import csv
import hashlib
import io
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TextIO

from estimate_app.calculation.decimal_policy import decimal_from_text, decimal_to_text


CATALOGUE_SCHEDULE = "CPWD DSR Civil"
CATALOGUE_EDITION = "2023"
VERIFIED = "Verified"
UNVERIFIED = "Unverified"
WITHDRAWN = "Withdrawn"
SUPERSEDED = "Superseded"
MANUAL_OVERRIDE = "Manual override"
CATALOGUE_HEADERS = (
    "schedule_name",
    "edition",
    "volume",
    "chapter",
    "item_code",
    "parent_item_code",
    "description",
    "original_unit",
    "canonical_unit",
    "rate",
    "source_document_name",
    "source_page",
    "is_heading",
)
CORRECTION_HEADERS = (
    "slip_reference",
    "publication_date",
    "effective_date",
    "effective_date_source",
    "item_code",
    "operation",
    "changed_parent_item_code",
    "changed_description",
    "changed_original_unit",
    "changed_canonical_unit",
    "changed_rate",
    "changed_volume",
    "changed_chapter",
    "source_document_name",
    "source_page",
)


@dataclass(frozen=True)
class CatalogueItem:
    id: int | None
    schedule_name: str
    edition: str
    volume: str
    chapter: str
    item_code: str
    parent_item_code: str | None
    description: str
    original_unit: str
    canonical_unit: str
    rate: Decimal | None
    source_document_name: str
    source_page: int
    verification_status: str = UNVERIFIED
    reviewer: str | None = None
    verification_date: str | None = None
    is_heading: bool = False
    verification_withdrawn_by: str | None = None
    verification_withdrawn_date: str | None = None
    verification_withdrawal_reason: str | None = None


@dataclass(frozen=True)
class CorrectionSlip:
    id: int | None
    slip_reference: str
    publication_date: str
    effective_date: str
    effective_date_source: str
    item_code: str
    operation: str
    source_document_name: str
    source_page: int
    changed_parent_item_code: str | None = None
    changed_description: str | None = None
    changed_original_unit: str | None = None
    changed_canonical_unit: str | None = None
    changed_rate: Decimal | None = None
    changed_volume: str | None = None
    changed_chapter: str | None = None
    verification_status: str = UNVERIFIED
    reviewer: str | None = None
    verification_date: str | None = None
    verification_withdrawn_by: str | None = None
    verification_withdrawn_date: str | None = None
    verification_withdrawal_reason: str | None = None


@dataclass(frozen=True)
class ResolvedCatalogueItem:
    item: CatalogueItem
    deleted: bool
    applied_corrections: tuple[CorrectionSlip, ...]


@dataclass(frozen=True)
class ImportHistory:
    id: int
    source_file_name: str
    source_checksum: str
    row_count: int
    status: str
    error_summary: str | None


@dataclass(frozen=True)
class CatalogueImportPreview:
    source_file_name: str
    source_checksum: str
    rows: tuple[CatalogueItem, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class CorrectionImportPreview:
    source_file_name: str
    source_checksum: str
    rows: tuple[CorrectionSlip, ...]
    errors: tuple[str, ...]


class CatalogueImportError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Catalogue import failed:\n" + "\n".join(errors))


class ConflictingCorrectionsError(ValueError):
    pass


def blank_catalogue_template() -> str:
    output = io.StringIO()
    csv.writer(output, lineterminator="\n").writerow(CATALOGUE_HEADERS)
    return output.getvalue()


def blank_correction_template() -> str:
    output = io.StringIO()
    csv.writer(output, lineterminator="\n").writerow(CORRECTION_HEADERS)
    return output.getvalue()


class CatalogueRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def import_csv(self, source: Path | str | TextIO, source_file_name: str | None = None) -> ImportHistory:
        preview = self.preview_csv(source, source_file_name)
        if preview.errors:
            raise CatalogueImportError(list(preview.errors))
        file_name = preview.source_file_name
        checksum = preview.source_checksum
        existing_import = self.connection.execute(
            "SELECT * FROM catalogue_imports WHERE source_checksum = ?", (checksum,)
        ).fetchone()
        if existing_import and existing_import["status"] == "Imported":
            return self._history_from_row(existing_import)
        try:
            rows = list(preview.rows)
            with self.connection:
                for item in rows:
                    existing = self.connection.execute(
                        """
                        SELECT * FROM catalogue_items
                        WHERE schedule_name = ? AND edition = ? AND item_code = ?
                        """,
                        (item.schedule_name, item.edition, item.item_code),
                    ).fetchone()
                    if existing:
                        existing_item = replace(self._item_from_row(existing), id=None)
                        if existing_item != item:
                            raise CatalogueImportError([f"item code {item.item_code!r} conflicts with an existing record"])
                        continue
                    self._insert_item(item)
                cursor = self.connection.execute(
                    """
                    INSERT INTO catalogue_imports
                    (source_file_name, source_checksum, row_count, status)
                    VALUES (?, ?, ?, 'Imported')
                    """,
                    (file_name, checksum, len(rows)),
                )
                history_id = cursor.lastrowid
        except CatalogueImportError:
            raise
        except (sqlite3.Error, ValueError) as error:
            raise CatalogueImportError([str(error)]) from error
        row = self.connection.execute(
            "SELECT * FROM catalogue_imports WHERE id = ?", (history_id,)
        ).fetchone()
        return self._history_from_row(row)

    def import_correction_csv(self, source: Path | str | TextIO, source_file_name: str | None = None) -> ImportHistory:
        preview = self.preview_correction_csv(source, source_file_name)
        if preview.errors:
            raise CatalogueImportError(list(preview.errors))
        existing = self.connection.execute(
            "SELECT * FROM correction_imports WHERE source_checksum = ?", (preview.source_checksum,)
        ).fetchone()
        if existing and existing["status"] == "Imported":
            return ImportHistory(existing["id"], existing["source_file_name"], existing["source_checksum"], existing["row_count"], existing["status"], existing["error_summary"])
        try:
            with self.connection:
                for correction in preview.rows:
                    self.connection.execute(
                        """
                        INSERT INTO correction_slips (
                            slip_reference, publication_date, effective_date, effective_date_source,
                            item_code, operation, changed_parent_item_code, changed_description,
                            changed_original_unit, changed_canonical_unit, changed_rate,
                            changed_volume, changed_chapter, source_document_name, source_page,
                            verification_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            correction.slip_reference, correction.publication_date, correction.effective_date,
                            correction.effective_date_source, correction.item_code, correction.operation,
                            correction.changed_parent_item_code, correction.changed_description,
                            correction.changed_original_unit, correction.changed_canonical_unit,
                            decimal_to_text(correction.changed_rate), correction.changed_volume,
                            correction.changed_chapter, correction.source_document_name,
                            correction.source_page, UNVERIFIED,
                        ),
                    )
                cursor = self.connection.execute(
                    "INSERT INTO correction_imports (source_file_name, source_checksum, row_count, status) VALUES (?, ?, ?, 'Imported')",
                    (preview.source_file_name, preview.source_checksum, len(preview.rows)),
                )
                import_id = cursor.lastrowid
        except sqlite3.Error as error:
            raise CatalogueImportError([str(error)]) from error
        return ImportHistory(import_id, preview.source_file_name, preview.source_checksum, len(preview.rows), "Imported", None)

    def preview_correction_csv(self, source: Path | str | TextIO, source_file_name: str | None = None) -> CorrectionImportPreview:
        raw, file_name = self._read_source(source, source_file_name)
        checksum = hashlib.sha256(raw).hexdigest()
        try:
            text = raw.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            if reader.fieldnames != list(CORRECTION_HEADERS):
                raise CatalogueImportError(["CSV headers must be exactly: " + ", ".join(CORRECTION_HEADERS)])
            rows: list[CorrectionSlip] = []
            errors: list[str] = []
            seen: set[tuple[str, str, str]] = set()
            for row_number, row in enumerate(reader, 2):
                try:
                    required = ["slip_reference", "publication_date", "effective_date", "effective_date_source", "item_code", "operation", "source_document_name", "source_page"]
                    missing = [field for field in required if not row.get(field, "").strip()]
                    if missing:
                        raise ValueError("missing " + ", ".join(missing))
                    self._validate_date(row["publication_date"], "publication date")
                    self._validate_date(row["effective_date"], "effective date")
                    if row["operation"] not in {"add", "amend", "delete"}:
                        raise ValueError("operation must be add, amend, or delete")
                    source_page = int(row["source_page"])
                    if source_page < 1:
                        raise ValueError("source_page must be positive")
                    correction = CorrectionSlip(
                        None, row["slip_reference"].strip(), row["publication_date"].strip(), row["effective_date"].strip(),
                        row["effective_date_source"].strip(), row["item_code"].strip(), row["operation"].strip(),
                        row["source_document_name"].strip(), source_page,
                        row.get("changed_parent_item_code", "").strip() or None,
                        row.get("changed_description", "").strip() or None,
                        row.get("changed_original_unit", "").strip() or None,
                        row.get("changed_canonical_unit", "").strip() or None,
                        decimal_from_text(row.get("changed_rate", "").strip(), "changed rate"),
                        row.get("changed_volume", "").strip() or None,
                        row.get("changed_chapter", "").strip() or None,
                    )
                    key = (correction.slip_reference, correction.item_code, correction.operation)
                    if key in seen:
                        raise ValueError("duplicate correction record")
                    seen.add(key)
                    rows.append(correction)
                except (ValueError, TypeError) as error:
                    errors.append(f"row {row_number}: {error}")
            if errors:
                return CorrectionImportPreview(file_name, checksum, tuple(), tuple(errors))
            return CorrectionImportPreview(file_name, checksum, tuple(rows), tuple())
        except UnicodeDecodeError as error:
            return CorrectionImportPreview(file_name, checksum, tuple(), (f"file is not valid UTF-8: {error}",))
        except CatalogueImportError as error:
            return CorrectionImportPreview(file_name, checksum, tuple(), tuple(error.errors))

    def reference_documents_directory(self) -> Path:
        from estimate_app.database.connection import user_data_directory

        directory = user_data_directory() / "reference_documents"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def attach_reference_document(self, source: Path | str) -> sqlite3.Row:
        source_path = Path(source)
        if source_path.suffix.lower() != ".pdf":
            raise ValueError("Reference document must be a PDF file.")
        if not source_path.is_file():
            raise FileNotFoundError(f"Reference PDF was not found: {source_path}")
        checksum = hashlib.sha256(source_path.read_bytes()).hexdigest()
        existing = self.connection.execute("SELECT * FROM reference_documents WHERE source_checksum = ?", (checksum,)).fetchone()
        if existing:
            return existing
        stored_path = self.reference_documents_directory() / f"{checksum[:16]}-{source_path.name}"
        shutil.copy2(source_path, stored_path)
        cursor = self.connection.execute(
            "INSERT INTO reference_documents (document_name, stored_path, source_checksum) VALUES (?, ?, ?)",
            (source_path.name, str(stored_path), checksum),
        )
        self.connection.commit()
        return self.connection.execute("SELECT * FROM reference_documents WHERE id = ?", (cursor.lastrowid,)).fetchone()

    def open_reference_document(self, document_id: int) -> Path:
        row = self.connection.execute("SELECT * FROM reference_documents WHERE id = ?", (document_id,)).fetchone()
        if row is None:
            raise FileNotFoundError("Reference document record does not exist.")
        path = Path(row["stored_path"])
        if not path.is_file():
            raise FileNotFoundError(f"Reference PDF is missing: {path}")
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return path

    def list_reference_documents(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM reference_documents ORDER BY document_name"
        ).fetchall()

    def open_reference_document_by_name(self, document_name: str) -> Path:
        row = self.connection.execute(
            "SELECT * FROM reference_documents WHERE document_name = ? ORDER BY id DESC LIMIT 1",
            (document_name,),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(f"Reference PDF is not attached: {document_name}")
        return self.open_reference_document(row["id"])

    def preview_csv(self, source: Path | str | TextIO, source_file_name: str | None = None) -> CatalogueImportPreview:
        raw, file_name = self._read_source(source, source_file_name)
        checksum = hashlib.sha256(raw).hexdigest()
        try:
            rows = self._validate_csv(raw)
        except CatalogueImportError as error:
            return CatalogueImportPreview(file_name, checksum, tuple(), tuple(error.errors))
        errors: list[str] = []
        for row_number, item in enumerate(rows, 2):
            existing = self.connection.execute(
                """
                SELECT * FROM catalogue_items
                WHERE schedule_name = ? AND edition = ? AND item_code = ?
                """,
                (item.schedule_name, item.edition, item.item_code),
            ).fetchone()
            if existing and replace(self._item_from_row(existing), id=None) != item:
                errors.append(f"row {row_number}: item code {item.item_code!r} conflicts with an existing record")
        return CatalogueImportPreview(file_name, checksum, tuple(rows), tuple(errors))

    def list_imports(self) -> list[ImportHistory]:
        rows = self.connection.execute(
            "SELECT * FROM catalogue_imports ORDER BY imported_at DESC, id DESC"
        ).fetchall()
        return [self._history_from_row(row) for row in rows]

    def list_items(self, *, include_headings: bool = True) -> list[CatalogueItem]:
        query = "SELECT * FROM catalogue_items"
        if not include_headings:
            query += " WHERE is_heading = 0"
        query += " ORDER BY volume, chapter, item_code"
        return [self._item_from_row(row) for row in self.connection.execute(query)]

    def search(
        self,
        *,
        query: str = "",
        volume: str = "",
        chapter: str = "",
        unit: str = "",
        cutoff_date: str | None = None,
    ) -> list[ResolvedCatalogueItem]:
        params: list[str] = []
        clauses = ["is_heading = 0", "verification_status = ?", "original_rate IS NOT NULL"]
        params.append(VERIFIED)
        if query:
            clauses.append("(item_code LIKE ? OR description LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if volume:
            clauses.append("volume = ?")
            params.append(volume)
        if chapter:
            clauses.append("chapter = ?")
            params.append(chapter)
        if unit:
            clauses.append("canonical_unit = ?")
            params.append(unit)
        rows = self.connection.execute(
            "SELECT * FROM catalogue_items WHERE " + " AND ".join(clauses) + " ORDER BY item_code",
            params,
        ).fetchall()
        results = []
        seen_codes: set[str] = set()
        for row in rows:
            item = self._item_from_row(row)
            resolved = self.resolve_item(item.schedule_name, item.edition, item.item_code, cutoff_date)
            if not resolved.deleted and resolved.item.verification_status == VERIFIED and resolved.item.rate is not None:
                results.append(resolved)
                seen_codes.add(resolved.item.item_code)
        added_codes = self.connection.execute(
            "SELECT DISTINCT item_code FROM correction_slips WHERE operation = 'add' AND verification_status = ?",
            (VERIFIED,),
        ).fetchall()
        for row in added_codes:
            item_code = row["item_code"]
            if item_code in seen_codes:
                continue
            try:
                resolved = self.resolve_item(CATALOGUE_SCHEDULE, CATALOGUE_EDITION, item_code, cutoff_date)
            except (ValueError, ConflictingCorrectionsError):
                continue
            item = resolved.item
            if resolved.deleted or item.rate is None or item.verification_status != VERIFIED:
                continue
            if query and query.lower() not in item.item_code.lower() and query.lower() not in item.description.lower():
                continue
            if volume and item.volume != volume:
                continue
            if chapter and item.chapter != chapter:
                continue
            if unit and item.canonical_unit != unit:
                continue
            results.append(resolved)
        return results

    def get_item(self, item_id: int) -> CatalogueItem | None:
        row = self.connection.execute("SELECT * FROM catalogue_items WHERE id = ?", (item_id,)).fetchone()
        return self._item_from_row(row) if row else None

    def verify_item(self, item_id: int, reviewer: str, verification_date: str) -> CatalogueItem:
        self._validate_date(verification_date, "verification date")
        if not reviewer.strip():
            raise ValueError("Reviewer is required for verification.")
        item = self.get_item(item_id)
        if item is None:
            raise ValueError("Catalogue item does not exist.")
        if not item.source_document_name.strip() or item.source_page < 1:
            raise ValueError("Source document and positive source page are required for verification.")
        self.connection.execute(
            """
            UPDATE catalogue_items
            SET verification_status = ?, reviewer = ?, verification_date = ?
            WHERE id = ?
            """,
            (VERIFIED, reviewer.strip(), verification_date, item_id),
        )
        self._record_event("catalogue_item", item_id, VERIFIED, reviewer, verification_date)
        self.connection.commit()
        item = self.get_item(item_id)
        if item is None:
            raise ValueError("Catalogue item does not exist.")
        return item

    def withdraw_item(self, item_id: int, reviewer: str, withdrawal_date: str, reason: str) -> CatalogueItem:
        self._validate_date(withdrawal_date, "withdrawal date")
        if not reviewer.strip() or not reason.strip():
            raise ValueError("Reviewer and withdrawal reason are required.")
        item = self.get_item(item_id)
        if item is None:
            raise ValueError("Catalogue item does not exist.")
        self.connection.execute(
            """
            UPDATE catalogue_items
            SET verification_status = ?, verification_withdrawn_by = ?,
                verification_withdrawn_date = ?, verification_withdrawal_reason = ?
            WHERE id = ?
            """,
            (WITHDRAWN, reviewer.strip(), withdrawal_date, reason.strip(), item_id),
        )
        self._record_event("catalogue_item", item_id, WITHDRAWN, reviewer, withdrawal_date, reason)
        self.connection.execute(
            "UPDATE boq_items SET needs_catalogue_review = 1 WHERE catalogue_item_id = ?",
            (item_id,),
        )
        self.connection.commit()
        return self.get_item(item_id)  # type: ignore[return-value]

    def list_review_items(self, status: str = "") -> list[CatalogueItem]:
        if status:
            rows = self.connection.execute(
                "SELECT * FROM catalogue_items WHERE verification_status = ? ORDER BY item_code", (status,)
            ).fetchall()
        else:
            rows = self.connection.execute("SELECT * FROM catalogue_items ORDER BY item_code").fetchall()
        return [self._item_from_row(row) for row in rows]

    def verification_events(self, record_type: str, record_id: int) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM verification_events WHERE record_type = ? AND record_id = ? ORDER BY id",
            (record_type, record_id),
        ).fetchall()

    def add_correction(self, correction: CorrectionSlip) -> CorrectionSlip:
        self._validate_date(correction.publication_date, "publication date")
        self._validate_date(correction.effective_date, "effective date")
        if correction.operation not in {"add", "amend", "delete"}:
            raise ValueError("Correction operation must be add, amend, or delete.")
        if not correction.effective_date_source.strip():
            raise ValueError("The source supporting the effective date is required.")
        cursor = self.connection.execute(
            """
            INSERT INTO correction_slips (
                slip_reference, publication_date, effective_date, effective_date_source,
                item_code, operation, changed_parent_item_code, changed_description,
                changed_original_unit, changed_canonical_unit, changed_rate,
                changed_volume, changed_chapter, source_document_name, source_page,
                verification_status, reviewer, verification_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                correction.slip_reference,
                correction.publication_date,
                correction.effective_date,
                correction.effective_date_source,
                correction.item_code,
                correction.operation,
                correction.changed_parent_item_code,
                correction.changed_description,
                correction.changed_original_unit,
                correction.changed_canonical_unit,
                decimal_to_text(decimal_from_text(correction.changed_rate, "changed rate")),
                correction.changed_volume,
                correction.changed_chapter,
                correction.source_document_name,
                correction.source_page,
                correction.verification_status,
                correction.reviewer,
                correction.verification_date,
            ),
        )
        self.connection.commit()
        row = self.connection.execute("SELECT * FROM correction_slips WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._correction_from_row(row)

    def verify_correction(self, correction_id: int, reviewer: str, verification_date: str) -> CorrectionSlip:
        self._validate_date(verification_date, "verification date")
        if not reviewer.strip():
            raise ValueError("Reviewer is required for verification.")
        correction = next((item for item in self.list_corrections() if item.id == correction_id), None)
        if correction is None:
            raise ValueError("Correction slip does not exist.")
        if not correction.source_document_name.strip() or correction.source_page < 1:
            raise ValueError("Source document and positive source page are required for verification.")
        self.connection.execute(
            "UPDATE correction_slips SET verification_status = ?, reviewer = ?, verification_date = ? WHERE id = ?",
            (VERIFIED, reviewer.strip(), verification_date, correction_id),
        )
        self._record_event("correction_slip", correction_id, VERIFIED, reviewer, verification_date)
        self.connection.commit()
        row = self.connection.execute("SELECT * FROM correction_slips WHERE id = ?", (correction_id,)).fetchone()
        if row is None:
            raise ValueError("Correction slip does not exist.")
        return self._correction_from_row(row)

    def withdraw_correction(self, correction_id: int, reviewer: str, withdrawal_date: str, reason: str) -> CorrectionSlip:
        self._validate_date(withdrawal_date, "withdrawal date")
        if not reviewer.strip() or not reason.strip():
            raise ValueError("Reviewer and withdrawal reason are required.")
        correction = next((item for item in self.list_corrections() if item.id == correction_id), None)
        if correction is None:
            raise ValueError("Correction slip does not exist.")
        self.connection.execute(
            """
            UPDATE correction_slips
            SET verification_status = ?, verification_withdrawn_by = ?,
                verification_withdrawn_date = ?, verification_withdrawal_reason = ?
            WHERE id = ?
            """,
            (WITHDRAWN, reviewer.strip(), withdrawal_date, reason.strip(), correction_id),
        )
        self._record_event("correction_slip", correction_id, WITHDRAWN, reviewer, withdrawal_date, reason)
        self.connection.execute(
            "UPDATE boq_items SET needs_catalogue_review = 1 WHERE dsr_item_code = ?",
            (correction.item_code,),
        )
        self.connection.commit()
        row = self.connection.execute("SELECT * FROM correction_slips WHERE id = ?", (correction_id,)).fetchone()
        return self._correction_from_row(row)

    def revise_correction(self, correction_id: int, replacement: CorrectionSlip) -> CorrectionSlip:
        current = next((item for item in self.list_corrections() if item.id == correction_id), None)
        if current is None:
            raise ValueError("Correction slip does not exist.")
        self.connection.execute(
            "UPDATE correction_slips SET verification_status = ? WHERE id = ?",
            (SUPERSEDED, correction_id),
        )
        created = self.add_correction(replace(replacement, id=None, verification_status=UNVERIFIED))
        self._record_event("correction_slip", correction_id, SUPERSEDED, "system", replacement.publication_date, f"Replaced by correction {created.id}")
        self.connection.commit()
        return created

    def list_corrections(self, item_code: str | None = None) -> list[CorrectionSlip]:
        if item_code is None:
            rows = self.connection.execute("SELECT * FROM correction_slips ORDER BY effective_date, id").fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM correction_slips WHERE item_code = ? ORDER BY effective_date, id", (item_code,)
            ).fetchall()
        return [self._correction_from_row(row) for row in rows]

    def resolve_item(
        self, schedule_name: str, edition: str, item_code: str, cutoff_date: str | None
    ) -> ResolvedCatalogueItem:
        if cutoff_date is not None:
            self._validate_date(cutoff_date, "cutoff date")
        row = self.connection.execute(
            "SELECT * FROM catalogue_items WHERE schedule_name = ? AND edition = ? AND item_code = ?",
            (schedule_name, edition, item_code),
        ).fetchone()
        base = self._item_from_row(row) if row else None
        current = base
        corrections = [
            correction
            for correction in self.list_corrections(item_code)
            if correction.verification_status == VERIFIED
            and (cutoff_date is None or correction.effective_date <= cutoff_date)
        ]
        self._check_correction_conflicts(corrections)
        deleted = False
        applied: list[CorrectionSlip] = []
        for correction in corrections:
            if correction.operation == "add":
                if current is not None and not deleted:
                    raise ConflictingCorrectionsError(f"Correction {correction.slip_reference} adds an existing item {item_code}.")
                if current is None:
                    current = self._item_from_correction(correction, schedule_name, edition)
                else:
                    current = self._apply_correction(current, correction)
                deleted = False
            elif correction.operation == "delete":
                if current is None:
                    raise ConflictingCorrectionsError(f"Correction {correction.slip_reference} deletes an unknown item {item_code}.")
                deleted = True
            elif correction.operation == "amend":
                if current is None:
                    raise ConflictingCorrectionsError(f"Correction {correction.slip_reference} amends an unknown item {item_code}.")
                current = self._apply_correction(current, correction)
            applied.append(correction)
        if current is None:
            raise ValueError(f"Catalogue item {item_code!r} does not exist.")
        if applied:
            current = replace(current, id=current.id, verification_status=VERIFIED)
        return ResolvedCatalogueItem(current, deleted, tuple(applied))

    def coverage_summary(self) -> dict[str, object]:
        row = self.connection.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN verification_status = ? THEN 1 ELSE 0 END) AS verified, MAX(source_page) AS last_page FROM catalogue_items",
            (VERIFIED,),
        ).fetchone()
        return {
            "record_count": row["total"],
            "verified_count": row["verified"] or 0,
            "last_source_page": row["last_page"],
            "coverage_note": "Recorded imports only; this is not a claim that the catalogue is up to date.",
        }

    def _record_event(
        self,
        record_type: str,
        record_id: int,
        action: str,
        reviewer: str,
        event_date: str,
        reason: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO verification_events
            (record_type, record_id, action, reviewer, event_date, reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (record_type, record_id, action, reviewer, event_date, reason),
        )

    def _validate_csv(self, raw: bytes) -> list[CatalogueItem]:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise CatalogueImportError([f"file is not valid UTF-8: {error}"]) from error
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames != list(CATALOGUE_HEADERS):
            raise CatalogueImportError(["CSV headers must be exactly: " + ", ".join(CATALOGUE_HEADERS)])
        raw_rows = list(reader)
        errors: list[str] = []
        rows: list[CatalogueItem] = []
        seen: set[tuple[str, str, str]] = set()
        for row_number, row in enumerate(raw_rows, 2):
            try:
                item = self._parse_row(row, row_number, raw_rows)
                key = (item.schedule_name, item.edition, item.item_code)
                if key in seen:
                    raise ValueError(f"duplicate item code {item.item_code!r} in import")
                seen.add(key)
                rows.append(item)
            except ValueError as error:
                errors.append(f"row {row_number}: {error}")
        if errors:
            raise CatalogueImportError(errors)
        return rows

    def _parse_row(self, row: dict[str, str], row_number: int, raw_rows: list[dict[str, str]]) -> CatalogueItem:
        required = ["schedule_name", "edition", "volume", "chapter", "item_code", "description", "original_unit", "canonical_unit", "source_document_name", "source_page"]
        missing = [field for field in required if not row.get(field, "").strip()]
        if missing:
            raise ValueError("missing " + ", ".join(missing))
        rate = decimal_from_text(row.get("rate", "").strip(), "rate")
        is_heading = self._parse_bool(row.get("is_heading", ""), "is_heading")
        if not is_heading and rate is None:
            raise ValueError("priced items require a rate")
        try:
            source_page = int(row["source_page"])
        except ValueError as error:
            raise ValueError("source_page must be an integer") from error
        if source_page < 1:
            raise ValueError("source_page must be positive")
        parent_code = row.get("parent_item_code", "").strip() or None
        description = row["description"].strip()
        if parent_code:
            parent = next((candidate for candidate in raw_rows if candidate.get("item_code", "").strip() == parent_code), None)
            parent_description = parent.get("description", "").strip() if parent else ""
            if not parent_description:
                stored_parent = self.connection.execute(
                    """
                    SELECT description FROM catalogue_items
                    WHERE schedule_name = ? AND edition = ? AND item_code = ?
                    """,
                    (row["schedule_name"].strip(), row["edition"].strip(), parent_code),
                ).fetchone()
                parent_description = stored_parent["description"] if stored_parent else ""
            if parent_description and parent_description not in description:
                description = f"{parent_description} — {description}"
        return CatalogueItem(
            None,
            row["schedule_name"].strip(),
            row["edition"].strip(),
            row["volume"].strip(),
            row["chapter"].strip(),
            row["item_code"].strip(),
            parent_code,
            description,
            row["original_unit"].strip(),
            row["canonical_unit"].strip(),
            rate,
            row["source_document_name"].strip(),
            source_page,
            UNVERIFIED,
            None,
            None,
            is_heading,
        )

    @staticmethod
    def _parse_bool(value: str, field_name: str) -> bool:
        if value.strip().lower() in {"1", "true", "yes"}:
            return True
        if value.strip().lower() in {"0", "false", "no"}:
            return False
        raise ValueError(f"{field_name} must be true or false")

    @staticmethod
    def _read_source(source: Path | str | TextIO, source_file_name: str | None) -> tuple[bytes, str]:
        if hasattr(source, "read"):
            text = source.read()
            raw = text.encode("utf-8") if isinstance(text, str) else text
            return raw, source_file_name or "catalogue.csv"
        path = Path(source)
        return path.read_bytes(), source_file_name or path.name

    def _insert_item(self, item: CatalogueItem) -> None:
        self.connection.execute(
            """
            INSERT INTO catalogue_items (
                schedule_name, edition, volume, chapter, item_code,
                parent_item_code, description, original_unit, canonical_unit,
                original_rate, source_document_name, source_page,
                verification_status, reviewer, verification_date, is_heading
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.schedule_name, item.edition, item.volume, item.chapter,
                item.item_code, item.parent_item_code, item.description,
                item.original_unit, item.canonical_unit, decimal_to_text(item.rate),
                item.source_document_name, item.source_page, item.verification_status,
                item.reviewer, item.verification_date, int(item.is_heading),
            ),
        )

    @staticmethod
    def _item_from_row(row: sqlite3.Row) -> CatalogueItem:
        return CatalogueItem(
            row["id"], row["schedule_name"], row["edition"], row["volume"],
            row["chapter"], row["item_code"], row["parent_item_code"],
            row["description"], row["original_unit"], row["canonical_unit"],
            decimal_from_text(row["original_rate"], "rate"), row["source_document_name"],
            row["source_page"], row["verification_status"], row["reviewer"],
            row["verification_date"], bool(row["is_heading"]),
            row["verification_withdrawn_by"], row["verification_withdrawn_date"],
            row["verification_withdrawal_reason"],
        )

    @staticmethod
    def _history_from_row(row: sqlite3.Row) -> ImportHistory:
        return ImportHistory(row["id"], row["source_file_name"], row["source_checksum"], row["row_count"], row["status"], row["error_summary"])

    @staticmethod
    def _correction_from_row(row: sqlite3.Row) -> CorrectionSlip:
        return CorrectionSlip(
            row["id"], row["slip_reference"], row["publication_date"], row["effective_date"],
            row["effective_date_source"], row["item_code"], row["operation"],
            row["source_document_name"], row["source_page"], row["changed_parent_item_code"],
            row["changed_description"], row["changed_original_unit"], row["changed_canonical_unit"],
            decimal_from_text(row["changed_rate"], "changed rate"), row["changed_volume"],
            row["changed_chapter"], row["verification_status"], row["reviewer"], row["verification_date"],
            row["verification_withdrawn_by"], row["verification_withdrawn_date"],
            row["verification_withdrawal_reason"],
        )

    @staticmethod
    def _validate_date(value: str, label: str) -> None:
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{label} must be an ISO date (YYYY-MM-DD).") from error

    @staticmethod
    def _check_correction_conflicts(corrections: list[CorrectionSlip]) -> None:
        by_date: dict[str, list[CorrectionSlip]] = {}
        for correction in corrections:
            by_date.setdefault(correction.effective_date, []).append(correction)
        fields = ("changed_parent_item_code", "changed_description", "changed_original_unit", "changed_canonical_unit", "changed_rate", "changed_volume", "changed_chapter")
        for effective_date, same_date in by_date.items():
            if len(same_date) < 2:
                continue
            for index, first in enumerate(same_date):
                for second in same_date[index + 1:]:
                    if first.operation != second.operation or any(getattr(first, field) is not None and getattr(second, field) is not None for field in fields):
                        raise ConflictingCorrectionsError(f"Conflicting verified corrections for {first.item_code} effective {effective_date}.")

    @staticmethod
    def _apply_correction(item: CatalogueItem, correction: CorrectionSlip) -> CatalogueItem:
        changes = {
            "parent_item_code": correction.changed_parent_item_code,
            "description": correction.changed_description,
            "original_unit": correction.changed_original_unit,
            "canonical_unit": correction.changed_canonical_unit,
            "rate": correction.changed_rate,
            "volume": correction.changed_volume,
            "chapter": correction.changed_chapter,
        }
        return replace(item, **{key: value for key, value in changes.items() if value is not None})

    @staticmethod
    def _item_from_correction(correction: CorrectionSlip, schedule_name: str, edition: str) -> CatalogueItem:
        if correction.changed_description is None or correction.changed_original_unit is None or correction.changed_canonical_unit is None or correction.changed_rate is None:
            raise ValueError(f"Add correction {correction.slip_reference} lacks required item fields.")
        return CatalogueItem(
            None, schedule_name, edition, correction.changed_volume or "", correction.changed_chapter or "",
            correction.item_code, correction.changed_parent_item_code, correction.changed_description,
            correction.changed_original_unit, correction.changed_canonical_unit, correction.changed_rate,
            correction.source_document_name, correction.source_page, VERIFIED,
        )