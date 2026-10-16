# Findings & Fixes

| # | Symptom | Root cause | Fix |
|---|---------|-----------|-----|
| 1 | Ocean Rentals sees another company's revenue on refresh | Redis key was `revenue:{property_id}`; `prop-001` exists in both tenants, so whoever loaded it first had their totals served to the other tenant for 5 min | Key is now `revenue:{tenant_id}:{property_id}` (`services/cache.py`) |
| 2 | Sunset's numbers don't match their records | `DatabasePool.initialize()` read nonexistent `settings.supabase_db_*` fields and used `QueuePool` (invalid for async engines); `get_session` was `async def` but used with `async with`. Every request failed and `calculate_total_revenue` silently returned **hardcoded mock data** (prop-001 = 1000.00 / 3 bookings; real = 2250.00 / 4) | Build URL from `settings.database_url`, use default async pool, make `get_session` sync, reuse the global pool, remove the mock fallback so errors surface (`core/database_pool.py`, `services/reservations.py`) |
| 3 | Totals "off by a few cents" | Amounts stored as `NUMERIC(10,3)`, converted to `float` and rounded on the frontend | Sum in SQL, round once with `Decimal` `ROUND_HALF_UP` to cents in the service |
| 4 | March totals differ by timezone | Month boundaries were naive UTC; `res-tz-1` checks in 2024-02-29 23:30 UTC = **March 1 00:30 Paris** | `calculate_monthly_revenue` now queries with boundaries in the property's timezone (`AT TIME ZONE p.timezone`) and filters by tenant |
| 5 | Latent cross-tenant leak | Tenant resolver ignored token claims and defaulted unknown users to `tenant-a`; dashboard defaulted to a shared `default_tenant` | Resolve from JWT `app_metadata.tenant_id`, no default; dashboard returns 403 without a tenant |

Not changed: frontend `Dashboard.tsx` hardcodes all 5 property names for every tenant (Ocean sees "Beach House Alpha" for its prop-001). Should come from a per-tenant properties endpoint.
