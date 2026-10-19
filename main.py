"""Procurement Agent — main CLI entry point."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from config import settings
from core.comparator import compare_tables, get_comparison_summary
from core.grouper import group_by_supplier, get_supplier_email
from core.normalizer import normalize_data
from generators.excel_gen import generate_comparison_report, generate_purchase_order
from logging_setup import setup_logging
from models import Product, SupplierMatchStatus
from parsers import parse_document

setup_logging()
logger = logging.getLogger(__name__)

app = typer.Typer(name="procurement", help="Автоматизация закупок", invoke_without_command=True)
console = Console()

DEMO_SUPPLIERS = ("ООО БумагаПром", "ООО КанцТовары")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Procurement Agent — Автоматизация закупок."""
    if ctx.invoked_subcommand is None:
        _interactive_menu()


def _interactive_menu() -> None:
    console.print("[bold blue]========================================[/]")
    console.print("[bold blue]   Procurement Agent[/]")
    console.print("[bold blue]   Автоматизация закупок[/]")
    console.print("[bold blue]========================================[/]\n")

    console.print("[bold]Доступные команды:[/]\n")
    console.print("  [cyan]1[/] - Демо (показать пример работы)")
    console.print("  [cyan]2[/] - Обработать документы")
    console.print("  [cyan]3[/] - Сравнить заявку и счет")
    console.print("  [cyan]0[/] - Выход\n")

    while True:
        try:
            choice = input("Выберите действие (0-3): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            _run_demo()
            break
        elif choice == "2":
            _interactive_process()
            break
        elif choice == "3":
            _interactive_compare()
            break
        elif choice == "0":
            break
        else:
            console.print("[yellow]Неверный выбор, попробуйте снова[/]")


def _run_demo() -> None:
    demo()


def _interactive_process() -> None:
    console.print("\n[bold]Обработка документов[/]")
    console.print("Введите пути к файлам (каждый с новой строки, пустая строка для завершения):\n")

    files: list[Path] = []
    while True:
        try:
            path = input("  Файл: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not path:
            break
        files.append(Path(path))

    if not files:
        console.print("[yellow]Файлы не указаны[/]")
        return

    process(files=files, output_dir=settings.output_dir)


def _interactive_compare() -> None:
    console.print("\n[bold]Сравнение заявки и счета[/]")

    try:
        order_file = input("  Файл заявки (xlsx): ").strip()
        invoice_file = input("  Файл счета (xlsx): ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if not order_file or not invoice_file:
        console.print("[yellow]Не все файлы указаны[/]")
        return

    compare(order_file=Path(order_file), invoice_files=[Path(invoice_file)], output=Path("output/comparison_report.xlsx"))


@app.command()
def process(
    files: list[Path] = typer.Argument(..., help="Path to input documents"),
    output_dir: Path = typer.Option("output", help="Output directory for generated files"),
    send_emails: bool = typer.Option(False, "--send-emails", "-e", help="Send emails to suppliers"),
    emails_db: Path | None = typer.Option(None, "--emails-db", help="Path to emails JSON file"),
) -> None:
    """Process documents and generate purchase orders."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse all documents
    console.print("[bold blue]Step 1: Parsing documents...[/]")
    all_products: list[Product] = []
    for file_path in files:
        if not file_path.exists():
            console.print(f"  [red]File not found: {file_path}[/]")
            continue
        result = parse_document(file_path)
        console.print(f"  {file_path.name}: {len(result.products)} items")
        for err in result.errors:
            console.print(f"    [yellow]Warning: {err}[/]")
        all_products.extend(result.products)

    if not all_products:
        console.print("[red]No products found in any document.[/]")
        raise typer.Exit(1)

    # Step 2: Normalize
    console.print("[bold blue]Step 2: Normalizing data...[/]")
    normalized = normalize_data(all_products)
    console.print(f"  {len(all_products)} raw -> {len(normalized)} after normalization")

    # Step 3: Group by supplier
    console.print("[bold blue]Step 3: Grouping by supplier...[/]")
    suppliers = group_by_supplier(normalized)
    for sg in suppliers:
        console.print(f"  {sg.name}: {len(sg.products)} items")

    # Step 4: Generate purchase orders
    console.print("[bold blue]Step 4: Generating purchase orders...[/]")
    generated_files: list[Path] = []
    for sg in suppliers:
        filepath = generate_purchase_order(sg, output_dir)
        generated_files.append(filepath)
        console.print(f"  [green]+[/] {filepath.name}")

    # Step 5: Send emails (if requested)
    emails_sent: list[str] = []
    if send_emails:
        console.print("[bold blue]Step 5: Sending emails...[/]")
        emails_map: dict[str, str] = {}
        if emails_db and emails_db.exists():
            emails_map = json.loads(emails_db.read_text(encoding="utf-8"))

        from mailer.sender import send_purchase_order_email

        for sg, attachment in zip(suppliers, generated_files):
            email = get_supplier_email(sg.name, emails_map)
            if not email:
                console.print(f"  [yellow]No email for {sg.name}, skipping[/]")
                continue

            result = send_purchase_order_email(to=email, supplier_name=sg.name, attachment_path=attachment)
            if result["status"] == "success":
                console.print(f"  [green]+[/] Email sent to {email}")
                emails_sent.append(email)
            else:
                console.print(f"  [red]-[/] {result['message']}")

    console.print("\n[bold green]Done![/]")
    _print_summary(normalized, suppliers, generated_files, emails_sent)


@app.command()
def compare(
    order_file: Path = typer.Argument(..., help="Order file (xlsx)"),
    invoice_files: list[Path] = typer.Argument(..., help="Invoice files"),
    output: Path = typer.Option("comparison_report.xlsx", help="Output report file"),
) -> None:
    """Compare an order against invoices."""
    console.print("[bold blue]Comparing order against invoices...[/]")

    order_result = parse_document(order_file)
    order_products = normalize_data(order_result.products)
    console.print(f"  Order: {len(order_products)} items")

    invoice_products: list[Product] = []
    for inv_file in invoice_files:
        inv_result = parse_document(inv_file)
        invoice_products.extend(inv_result.products)
        console.print(f"  Invoice {inv_file.name}: {len(inv_result.products)} items")

    invoice_products = normalize_data(invoice_products)

    results = compare_tables(order_products, invoice_products)
    summary = get_comparison_summary(results)

    generate_comparison_report(results, output)
    console.print(f"  [green]+[/] Report saved to {output}")

    _print_comparison_summary(summary, results)


@app.command()
def demo() -> None:
    """Run a demo with sample data."""
    console.print("[bold blue]Procurement Agent - Demo[/]\n")

    products = [
        Product(name="Бумага А4", article="PAPER-A4-500", quantity=100, supplier=DEMO_SUPPLIERS[0]),
        Product(name="Ручка шариковая синяя", article="PEN-001", quantity=50, supplier=DEMO_SUPPLIERS[1]),
        Product(name="Степлер настольный", article="STAP-10", quantity=10, supplier=DEMO_SUPPLIERS[1]),
        Product(name="Папка для документов", article="FOLDER-A4", quantity=30, supplier=DEMO_SUPPLIERS[0]),
        Product(name="Маркер черный", article="MARK-BLK", quantity=25, supplier=DEMO_SUPPLIERS[1]),
    ]

    normalized = normalize_data(products)
    console.print(f"[bold]Normalized {len(products)} products -> {len(normalized)}[/]\n")

    suppliers = group_by_supplier(normalized)

    table = Table(title="Поставщики и товары")
    table.add_column("Поставщик", style="cyan")
    table.add_column("Товар", style="green")
    table.add_column("Артикул")
    table.add_column("Кол-во", justify="right")

    for sg in suppliers:
        for i, p in enumerate(sg.products):
            table.add_row(
                sg.name if i == 0 else "",
                p.name,
                p.article,
                str(p.quantity),
            )

    console.print(table)

    output_dir = settings.output_dir
    output_dir.mkdir(exist_ok=True)

    console.print("\n[bold]Generating purchase orders...[/]")
    for sg in suppliers:
        filepath = generate_purchase_order(sg, output_dir)
        console.print(f"  [green]+[/] {filepath.name}")

    console.print("\n[bold green]Demo complete![/]")


def _print_summary(
    products: list[Product],
    suppliers,
    generated_files: list[Path],
    emails_sent: list[str],
) -> None:
    table = Table(title="Итоги обработки")
    table.add_column("Метрика", style="cyan")
    table.add_column("Значение", style="green")

    table.add_row("Всего позиций", str(len(products)))
    table.add_row("Поставщиков", str(len(suppliers)))
    table.add_row("Файлов создано", str(len(generated_files)))
    table.add_row("Писем отправлено", str(len(emails_sent)))

    console.print(table)


def _print_comparison_summary(summary: dict, results: list) -> None:
    table = Table(title="Результаты сравнения")
    table.add_column("Метрика", style="cyan")
    table.add_column("Значение", style="green")

    table.add_row("Всего позиций", str(summary["total"]))
    table.add_row("Совпадений", f"{summary['ok']} ({summary['match_pct']}%)")
    table.add_row("Расхождения по количеству", str(summary["mismatches"]))
    table.add_row("Отсутствует в счете", str(summary["missing"]))
    table.add_row("Лишнее в счете", str(summary["extra"]))

    console.print(table)

    mismatches = [r for r in results if r.status != SupplierMatchStatus.OK]
    if mismatches:
        console.print("\n[bold yellow]Проблемные позиции:[/]")
        for item in mismatches:
            status_label = {
                SupplierMatchStatus.MISMATCH_QUANTITY: "Расхождение",
                SupplierMatchStatus.MISSING: "Отсутствует",
                SupplierMatchStatus.EXTRA: "Лишний",
            }.get(item.status, item.status.value)
            console.print(f"  * {item.product.name} - {status_label}")


if __name__ == "__main__":
    app()
