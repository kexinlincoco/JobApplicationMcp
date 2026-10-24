"""Job Application Tracker MCP server (HTTP).

Run locally:  python3 server.py   ->  http://localhost:8000/mcp
Auth: every request needs the MCP_TOKEN from .env, either as
      header  Authorization: Bearer <token>   or   query  ?key=<token>
"""
import logging
import os
import re
import secrets
from typing import Optional

import uvicorn
from mcp.server.fastmcp import FastMCP

import db

# host="0.0.0.0" so the server accepts requests addressed to its Render domain
mcp = FastMCP("job-tracker", host="0.0.0.0", stateless_http=True, json_response=True)

@mcp.tool()
def add_application(company: str, role: Optional[str] = None, status: str = "Applied",
                    deadline: Optional[str] = None, next_step: Optional[str] = None,
                    city: Optional[str] = None, link: Optional[str] = None,
                    notes: Optional[str] = None, source: str = "manual",
                    evidence: Optional[str] = None, source_email: Optional[str] = None,
                    allow_duplicate: bool = False) -> dict:
    """Add a new job application.

    company: company name, e.g. 字节 or Stripe. role: job title.
    status: one of Wishlist (想投还没投), Applied (已投递), OA_Pending (待测评), OA (完成测评), Interview (面试中), Offer, Rejected (挂).
    deadline: YYYY-MM-DD (e.g. OA due date). next_step: what to do next.
    source: manual (user said it) or gmail (found in email); evidence: email subject/sender.
    Returns already_exists instead of inserting if the same company+role exists.
    """
    return db.add_application(company, role, status, deadline, next_step, city, link, notes,
                              source, evidence, source_email, allow_duplicate)


@mcp.tool()
def update_status(company: Optional[str] = None, role: Optional[str] = None,
                  app_id: Optional[int] = None, status: Optional[str] = None,
                  deadline: Optional[str] = None, next_step: Optional[str] = None,
                  notes: Optional[str] = None, source: str = "manual",
                  evidence: Optional[str] = None, source_email: Optional[str] = None) -> dict:
    """Update an existing application's status, deadline, next step or notes.

    Find it by company (partial match, e.g. 快手) plus optional role, or by app_id.
    status: one of Wishlist (想投还没投), Applied (已投递), OA_Pending (待测评), OA (完成测评), Interview (面试中), Offer, Rejected (挂). deadline: YYYY-MM-DD. notes are appended, not replaced.
    If the result is 'ambiguous', show the candidates to the user and retry with app_id.
    If 'not_found', offer add_application. Gmail updates never override Offer/Rejected.
    """
    if not company and app_id is None:
        return {"result": "error", "hint": "Give company or app_id."}
    return db.update_application(company, role, app_id, status, deadline, next_step, notes,
                                 source, evidence, source_email)


@mcp.tool()
def list_upcoming(days: int = 7) -> dict:
    """List active applications with a deadline within the next `days` days (overdue included),
    plus OA_Pending applications that have no deadline recorded."""
    return db.list_upcoming(days)


@mcp.tool()
def list_applications(status: Optional[str] = None, company: Optional[str] = None,
                      limit: int = 50) -> dict:
    """List applications, newest first, with a count per status.

    status: filter, one of Wishlist (想投还没投), Applied (已投递), OA_Pending (待测评), OA (完成测评), Interview (面试中), Offer, Rejected (挂). company: partial name filter.
    """
    return db.list_applications(status, company, limit)


class TokenAuth:
    """Rejects any request without the right token (header or ?key=)."""

    def __init__(self, app, token):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and ".well-known" in scope.get("path", ""):
            # OAuth discovery probes from clients: we don't use OAuth, so say "not here" (404),
            # not 401, which would make clients think they must log in.
            await send({"type": "http.response.start", "status": 404,
                        "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"not found"})
            return
        if scope["type"] == "http":
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"").decode()
            query = scope.get("query_string", b"").decode()
            given = auth[7:] if auth.lower().startswith("bearer ") else ""
            for part in query.split("&"):
                if part.startswith("key="):
                    given = part[4:]
            if not secrets.compare_digest(given, self.token):
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"text/plain")]})
                await send({"type": "http.response.body", "body": b"unauthorized"})
                return
        await self.app(scope, receive, send)


class _HideKey(logging.Filter):
    """Never write the ?key=<token> secret into the access logs."""

    def filter(self, record):
        if record.args:
            record.args = tuple(re.sub(r"key=[^&\s\"]+", "key=***", a) if isinstance(a, str) else a
                                for a in record.args)
        return True


def main():
    token = os.environ.get("MCP_TOKEN")
    if not token:
        raise SystemExit("MCP_TOKEN is not set in .env")
    app = TokenAuth(mcp.streamable_http_app(), token)
    logging.getLogger("uvicorn.access").addFilter(_HideKey())
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))


if __name__ == "__main__":
    main()
