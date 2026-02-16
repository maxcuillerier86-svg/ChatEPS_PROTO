from app.services.obsidian.ObsidianClient import ObsidianClient


def obsidian_tool_schemas() -> list[dict]:
    return [
        {"name": "obsidian.search", "description": "Search notes in Obsidian vault", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "filters": {"type": "object"}}, "required": ["query"]}},
        {"name": "obsidian.write", "description": "Create/write a note in Obsidian", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
        {"name": "obsidian.append", "description": "Append to an existing Obsidian note", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
        {"name": "obsidian.open", "description": "Generate URI to open note in Obsidian", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
        {"name": "obsidian.status", "description": "Get Obsidian connector status", "input_schema": {"type": "object", "properties": {}}},
    ]


async def execute_obsidian_tool(client: ObsidianClient, call: dict) -> dict:
    tool = (call.get("tool") or call.get("name") or "").strip()
    args = call.get("args") or call.get("arguments") or {}

    if tool == "obsidian.search":
        items = await client.search(args.get("query", ""), args.get("filters") or {})
        return {"ok": True, "tool": tool, "results": items}
    if tool == "obsidian.write":
        return await client.create_note(args.get("path", ""), args.get("content", "")) | {"tool": tool}
    if tool == "obsidian.append":
        return await client.append_note(args.get("path", ""), args.get("content", "")) | {"tool": tool}
    if tool == "obsidian.open":
        return {"ok": True, "tool": tool, "open_uri": client.fs.open_uri(args.get("path", ""))}
    if tool == "obsidian.status":
        return {"ok": True, "tool": tool, "status": await client.status()}
    return {"ok": False, "tool": tool, "error": "unknown_tool"}
