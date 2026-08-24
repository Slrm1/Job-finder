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
