from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any

from sqlalchemy import text

from app.core.database_pool import db_pool

CENTS = Decimal("0.01")


def to_money(value) -> Decimal:
    """Sum first at full precision, round once at the end (amounts are stored with 3 decimals)."""
    return Decimal(str(value or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


async def _session():
    # Reuse the shared pool instead of building a new engine on every request.
    if not db_pool.session_factory:
        await db_pool.initialize()
    return db_pool.get_session()


async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int) -> Decimal:
    """
    Calculates revenue for a specific month, using the property's local timezone
    for month boundaries (a 23:30 UTC check-in on Feb 29 is March 1 in Paris).
    """
    query = text("""
        SELECT COALESCE(SUM(r.total_amount), 0) AS total
        FROM reservations r
        JOIN properties p ON p.id = r.property_id AND p.tenant_id = r.tenant_id
        WHERE r.property_id = :property_id
          AND r.tenant_id = :tenant_id
          AND r.check_in_date >= (make_date(:year, :month, 1)::timestamp AT TIME ZONE p.timezone)
          AND r.check_in_date < ((make_date(:year, :month, 1) + INTERVAL '1 month') AT TIME ZONE p.timezone)
    """)
    async with await _session() as session:
        result = await session.execute(query, {
            "property_id": property_id, "tenant_id": tenant_id, "month": month, "year": year,
        })
        return to_money(result.scalar())


async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database, scoped to the tenant.
    Errors propagate: silently returning mock numbers showed clients fake totals.
    """
    query = text("""
        SELECT
            COALESCE(SUM(total_amount), 0) AS total_revenue,
            COUNT(*) AS reservation_count
        FROM reservations
        WHERE property_id = :property_id AND tenant_id = :tenant_id
    """)
    async with await _session() as session:
        result = await session.execute(query, {"property_id": property_id, "tenant_id": tenant_id})
        row = result.fetchone()

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(to_money(row.total_revenue)),
        "currency": "USD",
        "count": row.reservation_count,
    }
