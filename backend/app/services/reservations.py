from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any

from sqlalchemy import text

from app.core.database_pool import db_pool

CENTS = Decimal("0.01")


def to_money(value) -> Decimal:
    """Round a database amount to cents using ordinary financial rounding."""
    return Decimal(str(value or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)

async def calculate_monthly_revenue(
    property_id: str, tenant_id: str, month: int, year: int
) -> Decimal:
    """
    Calculate revenue using the property's local timezone for month boundaries.
    """
    query = text("""
        SELECT COALESCE(SUM(r.total_amount), 0) AS total
        FROM reservations r
        JOIN properties p ON p.id = r.property_id AND p.tenant_id = r.tenant_id
        WHERE r.property_id = :property_id
          AND r.tenant_id = :tenant_id
          AND r.check_in_date >= (
              make_date(:year, :month, 1)::timestamp AT TIME ZONE p.timezone
          )
          AND r.check_in_date < (
              (make_date(:year, :month, 1) + INTERVAL '1 month')
              AT TIME ZONE p.timezone
          )
    """)

    if not db_pool.session_factory:
        await db_pool.initialize()

    async with db_pool.get_session() as session:
        result = await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "month": month,
            "year": year,
        })
        return to_money(result.scalar())

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    if not db_pool.session_factory:
        await db_pool.initialize()

    query = text("""
        SELECT
            property_id,
            SUM(total_amount) AS total_revenue,
            COUNT(*) AS reservation_count
        FROM reservations
        WHERE property_id = :property_id AND tenant_id = :tenant_id
        GROUP BY property_id
    """)

    async with db_pool.get_session() as session:
        result = await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
        })
        row = result.fetchone()

    if not row:
        return {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "total": "0.00",
            "currency": "USD",
            "count": 0,
        }

    total_revenue = to_money(row.total_revenue)
    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(total_revenue),
        "currency": "USD",
        "count": row.reservation_count,
    }
