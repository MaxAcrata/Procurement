"""Supplier grouping logic."""

from models import Product, SupplierGroup


def group_by_supplier(products: list[Product]) -> list[SupplierGroup]:
    """Group products by supplier.

    Returns a sorted list of SupplierGroup objects:
    - Suppliers sorted alphabetically
    - Products within each supplier sorted by name
    """
    groups: dict[str, list[Product]] = {}

    for product in products:
        supplier = product.supplier if product.supplier != "UNKNOWN" else "Неизвестный поставщик"
        if supplier not in groups:
            groups[supplier] = []
        groups[supplier].append(product)

    # Sort suppliers alphabetically
    sorted_suppliers = sorted(groups.keys())

    result: list[SupplierGroup] = []
    for supplier_name in sorted_suppliers:
        # Sort products by name within each supplier
        sorted_products = sorted(groups[supplier_name], key=lambda p: p.name.lower())
        result.append(SupplierGroup(name=supplier_name, products=sorted_products))

    return result


def get_supplier_email(supplier_name: str, emails_db: dict[str, str] | None = None) -> str | None:
    """Look up supplier email from database.

    Args:
        supplier_name: The supplier name to look up
        emails_db: Optional dict mapping supplier names to emails

    Returns:
        Email address or None if not found
    """
    if emails_db:
        # Try exact match first
        if supplier_name in emails_db:
            return emails_db[supplier_name]
        # Try case-insensitive match
        lower_name = supplier_name.lower()
        for name, email in emails_db.items():
            if name.lower() == lower_name:
                return email
    return None
