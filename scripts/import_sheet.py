"""One-time import of data/applications_clean.xlsx into Neon.
Usage: python3 scripts/import_sheet.py            (dry run)
       python3 scripts/import_sheet.py --commit   (write)
Refuses to run if applications already has rows (avoid double import)."""
import os, sys, pathlib, openpyxl, psycopg2
ROOT = pathlib.Path(__file__).resolve().parent.parent
for line in (ROOT / '.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute((ROOT / 'schema.sql').read_text())
cur.execute('SELECT count(*) FROM applications')
if cur.fetchone()[0] > 0:
    sys.exit('applications already has rows; aborting to avoid duplicates.')
ws = openpyxl.load_workbook(ROOT / 'data' / 'applications_clean.xlsx').active
n = 0
for row in ws.iter_rows(min_row=2, values_only=True):
    _, company, role, _, status, city, link, notes, _ = [(x if x not in ('', None) else None) for x in row[:9]]
    if not company: continue
    cur.execute("""INSERT INTO applications (company, role, status, city, link, notes, source)
                   VALUES (%s,%s,%s,%s,%s,%s,'import') RETURNING id""",
                (str(company), role, status or 'Applied', city, link, notes))
    aid = cur.fetchone()[0]
    cur.execute("INSERT INTO status_events (application_id, new_status, source, evidence) VALUES (%s,%s,'import','MCIT sheet')",
                (aid, status or 'Applied'))
    n += 1
cur.execute('SELECT status, count(*) FROM applications GROUP BY 1 ORDER BY 2 DESC')
print('rows:', n, dict(cur.fetchall()))
if '--commit' in sys.argv: conn.commit(); print('COMMITTED')
else: conn.rollback(); print('dry run, rolled back')
