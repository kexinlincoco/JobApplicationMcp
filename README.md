# Job Application Tracker MCP

An MCP server that lets Claude track job applications in a Neon (Postgres) database.
Plan and progress: see `MVP.md`.

## Tools
| Tool | What it does |
|---|---|
| `add_application` | Add an application (duplicate-safe) |
| `update_status` | Update status / deadline / next step; logs every change to `status_events` |
| `list_upcoming` | Deadlines in the next N days, plus OA_Pending without a deadline |
| `list_applications` | Filter by status or company, with per-status counts |

Statuses: Wishlist → Applied → OA_Pending → OA → Interview → Offer / Rejected

## Run locally
```
cp .env.example .env        # fill DATABASE_URL and MCP_TOKEN
pip3 install -r requirements.txt
python3 tests/smoke_test.py # end-to-end check against Neon
python3 server.py           # http://localhost:8000/mcp  (needs ?key=<MCP_TOKEN>)
```

## Deploy
Render reads `render.yaml`. Set `DATABASE_URL` and `MCP_TOKEN` as environment variables in the Render dashboard.
# JobApplicationMcp
