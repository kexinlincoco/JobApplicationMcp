"""Quick end-to-end check against Neon. Creates one __TEST__ row and deletes it afterwards.
Usage: python3 tests/smoke_test.py"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import db

def show(title, x): print(f"\n== {title} ==\n{x}")

s = db.list_applications(limit=3)
show("1. list_applications summary", s["summary"])
assert sum(s["summary"].values()) >= 180, "expected the 180 imported rows"

r = db.add_application("__TEST__", "测试岗位", status="OA_Pending", deadline="2026-12-31")
show("2. add_application", r["result"]); app_id = r["application"]["id"]
try:
    show("3. duplicate add", db.add_application("__TEST__", "测试岗位")["result"])
    u = db.update_application(app_id=app_id, status="Interview", next_step="一面", evidence="smoke test")
    show("4. update_status", f'{u["result"]}: {u["before"]} -> {u["application"]["status"]}')
    show("5. gmail cannot override Rejected",
         (db.update_application(app_id=app_id, status="Rejected"),
          db.update_application(app_id=app_id, status="Interview", source="gmail")["result"])[1])
    show("6. ambiguous match (company with several rows)", db.update_application(company="小米", status="OA")["result"])
    up = db.list_upcoming(days=120)
    show("7. list_upcoming", f'{len(up["upcoming"])} upcoming, {len(up["oa_pending_without_deadline"])} OA_Pending without deadline')
finally:
    db.delete_application(app_id)
    print("\ncleanup done; ALL CHECKS RAN")
