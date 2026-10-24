"""Database layer: all reads/writes to Neon go through here."""
import os
import pathlib
from contextlib import contextmanager
from datetime import date, timedelta

import psycopg2
import psycopg2.extras

ROOT = pathlib.Path(__file__).resolve().parent
STATUSES = ["Wishlist", "Applied", "OA_Pending", "OA", "Interview", "Offer", "Rejected"]
FINAL = {"Offer", "Rejected"}
COLUMNS = "id, company, role, status, deadline, next_step, city, link, notes, source, updated_at"


def _load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _dsn():
    """DATABASE_URL, cleaned of stray whitespace/newlines/quotes from copy-paste."""
    return os.environ["DATABASE_URL"].strip().strip('"').strip("'").strip()


def _connect():
    dsn = _dsn()
    try:
        return psycopg2.connect(dsn)
    except psycopg2.OperationalError as e:
        # Some libpq builds reject channel_binding; retry without it (sslmode=require still encrypts).
        if "channel_binding" in str(e) and "channel_binding" in dsn:
            import re
            dsn = re.sub(r"[&?]channel_binding=[^&]*", "", dsn)
            if "?" not in dsn and "&" in dsn:
                dsn = dsn.replace("&", "?", 1)
            return psycopg2.connect(dsn)
        raise


@contextmanager
def _cursor():
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _clean(row):
    """Make a DB row JSON-friendly."""
    if row is None:
        return None
    out = dict(row)
    for k, v in out.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


def _check_status(status):
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {status!r}")


def _parse_date(d):
    return date.fromisoformat(d) if d else None


# ---------- write ----------

def add_application(company, role=None, status="Applied", deadline=None, next_step=None,
                    city=None, link=None, notes=None, source="manual", evidence=None,
                    source_email=None, allow_duplicate=False):
    _check_status(status)
    with _cursor() as cur:
        if not allow_duplicate:
            cur.execute(f"""SELECT {COLUMNS} FROM applications
                            WHERE lower(company) = lower(%s)
                              AND coalesce(lower(role), '') = coalesce(lower(%s), '')""",
                        (company, role))
            existing = cur.fetchone()
            if existing:
                return {"result": "already_exists", "application": _clean(existing),
                        "hint": "Use update_status to change it, or pass allow_duplicate=true."}
        cur.execute(f"""INSERT INTO applications
                        (company, role, status, deadline, next_step, city, link, notes, source, source_email)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING {COLUMNS}""",
                    (company, role, status, _parse_date(deadline), next_step, city, link, notes,
                     source, source_email))
        row = cur.fetchone()
        cur.execute("""INSERT INTO status_events (application_id, new_status, source, evidence)
                       VALUES (%s,%s,%s,%s)""", (row["id"], status, source, evidence))
        return {"result": "added", "application": _clean(row)}


def find_applications(company=None, role=None, app_id=None):
    with _cursor() as cur:
        if app_id is not None:
            cur.execute(f"SELECT {COLUMNS} FROM applications WHERE id = %s", (app_id,))
        else:
            cur.execute(f"""SELECT {COLUMNS} FROM applications
                            WHERE company ILIKE %s AND (%s::text IS NULL OR role ILIKE %s)
                            ORDER BY updated_at DESC""",
                        (f"%{company}%", role, f"%{role}%" if role else None))
        return [_clean(r) for r in cur.fetchall()]


def update_application(company=None, role=None, app_id=None, status=None, deadline=None,
                       next_step=None, notes=None, source="manual", evidence=None,
                       source_email=None):
    if status is not None:
        _check_status(status)
    matches = find_applications(company, role, app_id)
    if not matches:
        return {"result": "not_found",
                "hint": "No match. Check the company name, or use add_application."}
    if len(matches) > 1:
        return {"result": "ambiguous", "candidates": matches,
                "hint": "Several applications match. Ask the user which one, then retry with app_id."}
    app = matches[0]

    # Gmail sync never overrides a final status (Offer / Rejected).
    if source == "gmail" and app["status"] in FINAL and status and status != app["status"]:
        return {"result": "needs_confirmation", "application": app,
                "hint": f"Current status is {app['status']}; not changed automatically. Ask the user."}

    sets, params = ["updated_at = now()"], []
    if status:
        sets.append("status = %s"); params.append(status)
    if deadline:
        sets.append("deadline = %s"); params.append(_parse_date(deadline))
    if next_step is not None:
        sets.append("next_step = %s"); params.append(next_step)
    if notes:
        sets.append("notes = concat_ws('；', nullif(notes, ''), %s)"); params.append(notes)
    if source_email:
        sets.append("source_email = %s"); params.append(source_email)

    with _cursor() as cur:
        cur.execute(f"UPDATE applications SET {', '.join(sets)} WHERE id = %s RETURNING {COLUMNS}",
                    (*params, app["id"]))
        row = cur.fetchone()
        if status and status != app["status"]:
            cur.execute("""INSERT INTO status_events (application_id, old_status, new_status, source, evidence)
                           VALUES (%s,%s,%s,%s,%s)""",
                        (app["id"], app["status"], status, source, evidence))
        return {"result": "updated", "before": app["status"], "application": _clean(row)}


def delete_application(app_id):
    """Not exposed as an MCP tool; used by tests only."""
    with _cursor() as cur:
        cur.execute("DELETE FROM applications WHERE id = %s", (app_id,))


# ---------- read ----------

def list_upcoming(days=7):
    today = date.today()
    with _cursor() as cur:
        cur.execute(f"""SELECT {COLUMNS} FROM applications
                        WHERE deadline IS NOT NULL AND deadline <= %s
                          AND status NOT IN ('Offer', 'Rejected', 'Wishlist')
                        ORDER BY deadline""", (today + timedelta(days=days),))
        rows = [_clean(r) for r in cur.fetchall()]
    for r in rows:
        r["overdue"] = r["deadline"] < today.isoformat()
    cur_pending = list_applications(status="OA_Pending", limit=100)["applications"]
    no_deadline = [r for r in cur_pending if not r["deadline"]]
    return {"today": today.isoformat(), "days": days, "upcoming": rows,
            "oa_pending_without_deadline": no_deadline}


def list_applications(status=None, company=None, limit=50):
    if status:
        _check_status(status)
    with _cursor() as cur:
        cur.execute(f"""SELECT {COLUMNS} FROM applications
                        WHERE (%s::text IS NULL OR status = %s)
                          AND (%s::text IS NULL OR company ILIKE %s)
                        ORDER BY updated_at DESC LIMIT %s""",
                    (status, status, company, f"%{company}%" if company else None, limit))
        rows = [_clean(r) for r in cur.fetchall()]
        cur.execute("SELECT status, count(*) AS n FROM applications GROUP BY status")
        summary = {r["status"]: r["n"] for r in cur.fetchall()}
    return {"summary": summary, "count": len(rows), "applications": rows}
