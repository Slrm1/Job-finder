from jobfinder.mcp_server import handle_rpc


def test_initialize_and_tools_list():
    init = handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "jobfinder"
    listed = handle_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert names == {"add_job", "list_jobs", "set_status", "pipeline_stats"}


def test_add_list_status_and_stats(tmp_path, monkeypatch):
    monkeypatch.setattr("jobfinder.tracker.JOBFINDER_DB", tmp_path / "apps.db")
    added = handle_rpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "add_job",
                "arguments": {
                    "title": "Python Intern",
                    "company": "Acme",
                    "url": "https://example.com/mcp",
                },
            },
        }
    )
    assert "Python Intern" in added["result"]["content"][0]["text"]
    listed = handle_rpc(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "list_jobs"}}
    )
    assert "Acme" in listed["result"]["content"][0]["text"]
    changed = handle_rpc(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "set_status", "arguments": {"id": 1, "status": "applied"}},
        }
    )
    assert "applied" in changed["result"]["content"][0]["text"]
    stats = handle_rpc(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "pipeline_stats"},
        }
    )
    text = stats["result"]["content"][0]["text"]
    assert '"total": 1' in text
    assert '"applied": 1' in text


def test_unknown_method():
    reply = handle_rpc({"jsonrpc": "2.0", "id": 9, "method": "nope"})
    assert reply["error"]["code"] == -32601
