"""Minimal MCP server so agents can add jobs to the local tracker."""

from __future__ import annotations

import json
import sys
from typing import Any

from jobfinder.jobs import Job
from jobfinder.tracker import (
    STATUSES,
    dashboard_stats,
    list_tracked,
    save_job,
    set_status,
)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "jobfinder"
SERVER_VERSION = "0.1.0"

TOOLS = [
    {
        "name": "add_job",
        "description": "Save a job application to the local Job-finder tracker.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "company": {"type": "string"},
                "url": {"type": "string"},
                "location": {"type": "string"},
                "notes": {"type": "string"},
                "status": {"type": "string", "enum": list(STATUSES)},
            },
            "required": ["title", "company"],
        },
    },
    {
        "name": "list_jobs",
        "description": "List saved applications, optionally filtered by status.",
        "inputSchema": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": list(STATUSES)}},
        },
    },
    {
        "name": "set_status",
        "description": "Update the status of a saved application by numeric id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "status": {"type": "string", "enum": list(STATUSES)},
            },
            "required": ["id", "status"],
        },
    },
    {
        "name": "pipeline_stats",
        "description": "Return dashboard counts for the local application pipeline.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "draft_cover_letter",
        "description": "Write a cover letter for a saved job using the loaded resume.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    },
    {
        "name": "apply_job",
        "description": (
            "Draft a cover letter, save an application package, and optionally email it. "
            "Set send=true to submit by email when a hiring address exists."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "send": {"type": "boolean"},
                "mark_applied": {"type": "boolean"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "run_pipeline",
        "description": (
            "Run the supervisor agents: resume, search, rank, optional draft/apply. "
            "send/yes defaults to false (preview only)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "url": {"type": "string"},
                "limit": {"type": "integer"},
                "apply": {"type": "integer"},
                "yes": {"type": "boolean"},
                "affine": {"type": "boolean"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "followups",
        "description": "Draft follow-up notes for applications with no reply.",
        "inputSchema": {"type": "object", "properties": {"days": {"type": "integer"}}},
    },
]


def handle_rpc(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method in {"notifications/initialized", "initialized"}:
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            text = _call_tool(name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": [{"type": "text", "text": text}]},
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32000, "message": str(exc)},
            }
    if msg_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Unknown method {method}"},
    }


def _call_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "add_job":
        job = Job(
            id="mcp",
            title=str(arguments.get("title") or "Untitled"),
            company=str(arguments.get("company") or "Unknown"),
            location=str(arguments.get("location") or ""),
            url=str(arguments.get("url") or ""),
            description=str(arguments.get("notes") or ""),
            source="mcp",
        )
        saved = save_job(
            job,
            status=str(arguments.get("status") or "saved"),
            notes=str(arguments.get("notes") or ""),
        )
        return json.dumps(saved.to_dict(), indent=2)
    if name == "list_jobs":
        status = arguments.get("status") or None
        rows = [row.to_dict() for row in list_tracked(status=status)]
        return json.dumps(rows, indent=2)
    if name == "set_status":
        row = set_status(int(arguments["id"]), str(arguments["status"]))
        return json.dumps(row.to_dict(), indent=2)
    if name == "pipeline_stats":
        stats = dashboard_stats()
        stats["recent"] = [row.to_dict() for row in stats["recent"]]
        return json.dumps(stats, indent=2)
    if name == "draft_cover_letter":
        from jobfinder.apply import apply_to_tracked
        from jobfinder.resume import resolve_profile

        result = apply_to_tracked(
            int(arguments["id"]),
            resolve_profile(),
            send=False,
            mark_applied=False,
        )
        return json.dumps(result.to_dict(), indent=2)
    if name == "apply_job":
        from jobfinder.apply import apply_to_tracked
        from jobfinder.resume import resolve_profile

        result = apply_to_tracked(
            int(arguments["id"]),
            resolve_profile(),
            send=bool(arguments.get("send") or arguments.get("yes")),
            mark_applied=bool(arguments.get("mark_applied", True)),
        )
        return json.dumps(result.to_dict(), indent=2)
    if name == "run_pipeline":
        from jobfinder.agents import Supervisor

        pipeline = Supervisor().run(
            str(arguments.get("query") or ""),
            url=str(arguments.get("url") or ""),
            limit=int(arguments.get("limit") or 20),
            apply_count=int(arguments["apply"]) if arguments.get("apply") else None,
            yes=bool(arguments.get("yes") or arguments.get("send")),
            affine=bool(arguments.get("affine")),
        )
        return json.dumps(pipeline.to_dict(), indent=2)
    if name == "followups":
        from jobfinder.followup import draft_followup, due_followups
        from jobfinder.resume import resolve_profile

        profile = resolve_profile()
        notes = []
        for row in due_followups(days=arguments.get("days")):
            notes.append(
                {
                    "id": row.id,
                    "title": row.title,
                    "company": row.company,
                    "letter": draft_followup(row, profile),
                }
            )
        return json.dumps(notes, indent=2)
    raise ValueError(f"Unknown tool {name}")


def serve_stdio() -> int:
    """JSON-RPC MCP loop on stdin/stdout."""
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = handle_rpc(message)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
    return 0
