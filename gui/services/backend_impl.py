"""Backend service implementation — wraps core modules for GUI use."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from config import settings
from core.comparator import compare_tables
from core.grouper import group_by_supplier
from core.normalizer import normalize_data
from generators.excel_gen import generate_purchase_order
from gui.services.backend_interface import BackendService
from mailer.sender import is_valid_email, send_purchase_order_email
from models import ComparisonItem, Product, ReviewPair, SupplierGroup
from parsers import parse_document

logger = logging.getLogger(__name__)


class ProcurementBackend(BackendService):
    """Production backend wrapping core modules."""

    def __init__(self) -> None:
        self._products: list[Product] = []
        self._suppliers: list[SupplierGroup] = []
        self._emails: dict[str, str] = {}
        self._history: list[dict] = []
        self._generated_orders: dict[str, Path] = {}
        self._pending_review_pairs: list[ReviewPair] = []
        self._review_decisions: list[dict] = []
        self._load_review_db()
        self._load_emails_db()

    # ── Review queue persistence ─────────────────────────────────────────

    def _review_db_path(self) -> Path:
        return settings.emails_db_path.parent / "match_review.json"

    def _load_review_db(self) -> None:
        path = self._review_db_path()
        if path.exists():
            try:
                self._review_decisions = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Failed to load match review DB from %s", path)
                self._review_decisions = []

    def _save_review_db(self) -> None:
        try:
            self._review_db_path().write_text(
                json.dumps(self._review_decisions, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save match review DB")

    def get_review_pairs(self) -> list[dict]:
        decided = {(d["article_a"], d["article_b"]) for d in self._review_decisions}
        return [
            {"article_a": p.article_a, "article_b": p.article_b, "score": p.score, "source": p.source}
            for p in self._pending_review_pairs
            if (p.article_a, p.article_b) not in decided
        ]

    def decide_review_pair(self, article_a: str, article_b: str, decision: str) -> None:
        if decision not in ("confirmed", "rejected"):
            raise ValueError(f"Invalid decision: {decision}")
        self._review_decisions.append(
            {
                "article_a": article_a,
                "article_b": article_b,
                "decision": decision,
                "ts": datetime.now().isoformat(),
            }
        )
        self._save_review_db()

    # ── Email DB persistence ─────────────────────────────────────────────

    def _load_emails_db(self) -> None:
        db_path = settings.emails_db_path
        if db_path.exists():
            try:
                self._emails = json.loads(db_path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Failed to load emails DB from %s", db_path)
                self._emails = {}

    def _save_emails_db(self) -> None:
        db_path = settings.emails_db_path
        try:
            db_path.write_text(json.dumps(self._emails, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("Failed to save emails DB")

    # ── Core operations ──────────────────────────────────────────────────

    def process_files(self, files: list[Path]) -> dict:
        all_products: list[Product] = []
        errors: list[str] = []

        for file_path in files:
            result = parse_document(file_path)
            all_products.extend(result.products)
            errors.extend(result.errors)

        self._pending_review_pairs = []
        self._products = normalize_data(all_products, review_pairs=self._pending_review_pairs)
        self._suppliers = group_by_supplier(self._products)

        self._add_history("process", f"Processed {len(files)} files, found {len(self._products)} items")
        logger.info(
            "Processed %d files → %d products, %d suppliers", len(files), len(self._products), len(self._suppliers)
        )

        return {
            "status": "error" if errors else "success",
            "count": len(self._products),
            "errors": errors,
        }

    def get_parsed_data(self) -> list[Product]:
        return self._products.copy()

    def update_product(self, index: int, product: Product) -> None:
        if 0 <= index < len(self._products):
            self._products[index] = product
            self._suppliers = group_by_supplier(self._products)

    def delete_product(self, index: int) -> None:
        if 0 <= index < len(self._products):
            self._products.pop(index)
            self._suppliers = group_by_supplier(self._products)

    def get_suppliers(self) -> list[SupplierGroup]:
        if not self._suppliers:
            self._suppliers = group_by_supplier(self._products)
        return self._suppliers.copy()

    def rename_supplier(self, old_name: str, new_name: str) -> None:
        for p in self._products:
            if p.supplier == old_name:
                p.supplier = new_name
        self._suppliers = group_by_supplier(self._products)

    def generate_orders(self, output_dir: Path) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)

        if not self._products:
            return []

        # Group by supplier and generate one file per supplier
        suppliers = group_by_supplier(self._products)
        generated: list[Path] = []

        for sg in suppliers:
            filepath = generate_purchase_order(sg, output_dir)
            generated.append(filepath)
            self._generated_orders[sg.name] = filepath

        self._add_history("generate", f"Generated {len(generated)} order files")
        return generated

    def compare(self, order_path: Path, invoice_paths: list[Path]) -> list[ComparisonItem]:
        order_result = parse_document(order_path)
        self._pending_review_pairs = []
        order_products = normalize_data(order_result.products, review_pairs=self._pending_review_pairs)

        invoice_products: list[Product] = []
        for inv_path in invoice_paths:
            inv_result = parse_document(inv_path)
            invoice_products.extend(inv_result.products)
        invoice_products = normalize_data(invoice_products, review_pairs=self._pending_review_pairs)

        results = compare_tables(order_products, invoice_products, review_pairs=self._pending_review_pairs)
        self._add_history("compare", f"Compared {len(order_products)} vs {len(invoice_products)} items")
        return results

    def get_emails(self) -> dict[str, str]:
        return self._emails.copy()

    def update_email(self, supplier: str, email: str) -> None:
        if email and not is_valid_email(email):
            raise ValueError(f"Invalid email address: {email}")
        self._emails[supplier] = email
        self._save_emails_db()

    def send_emails(self, emails_db_path: Path | None = None) -> list[dict]:
        results: list[dict] = []
        for sg in self._suppliers:
            email = self._emails.get(sg.name)
            if not email:
                results.append({"supplier": sg.name, "status": "no_email"})
                continue
            order_path = self._generated_orders.get(sg.name)
            if not order_path or not order_path.exists():
                results.append({"supplier": sg.name, "status": "no_order_file"})
                continue
            outcome = send_purchase_order_email(
                to=email,
                supplier_name=sg.name,
                attachment_path=order_path,
            )
            if outcome.get("status") == "success":
                results.append({"supplier": sg.name, "email": email, "status": "sent"})
            else:
                results.append(
                    {
                        "supplier": sg.name,
                        "email": email,
                        "status": outcome.get("status", "error"),
                        "message": outcome.get("message", ""),
                    }
                )

        sent_count = sum(1 for r in results if r["status"] == "sent")
        self._add_history("email", f"Sent {sent_count} emails")
        return results

    def get_history(self) -> list[dict]:
        return self._history.copy()

    def _add_history(self, action: str, details: str) -> None:
        self._history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "details": details,
            }
        )
