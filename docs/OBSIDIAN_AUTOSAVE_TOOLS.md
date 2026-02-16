# Obsidian Auto-save & Tool Calls (Local-first)

## 1) Filesystem mode (fallback, robust)
1. Set `OBSIDIAN_MODE=filesystem`
2. Set `OBSIDIAN_VAULT_PATH=/absolute/path/to/vault`
3. Ensure the process can write in the vault path.
4. Use UI button **Indexer Obsidian**.

Notes:
- Writes are blocked outside vault root.
- Excluded by default: `.obsidian/`, `templates/`, `attachments/`.

## 2) REST plugin mode (preferred if available)
1. Install/enable Obsidian Local REST API plugin.
2. Set:
   - `OBSIDIAN_MODE=rest`
   - `OBSIDIAN_REST_API_BASE_URL=http://127.0.0.1:<port>`
   - `OBSIDIAN_API_KEY=<key>`
3. Use `GET /obsidian/status` to check REST health.

Fallback behavior:
- If REST is down/unreachable, backend automatically falls back to filesystem when available.

## 3) Auto-save behavior
UI controls:
- Auto-save toggle
- Mode:
  - `manual-only`
  - `per-message`
  - `daily-note-append`
  - `canonical-only`
- Target folder
- Include sources / trace / summary toggles

Manual save:
- Use **Save to Obsidian** button under assistant message.

## 4) Tool call protocol
Supported internal tools:
- `obsidian.search`
- `obsidian.write`
- `obsidian.append`
- `obsidian.open`
- `obsidian.status`

Tool-call envelope expected from model:
```text
<tool_call>{"tool":"obsidian.search","args":{"query":"..."}}</tool_call>
```

## 5) Troubleshooting
- `vault_path invalide ou inaccessible`:
  - check absolute path
  - check permissions (OneDrive can lock files)
- REST health KO:
  - plugin not running
  - wrong port/api key
- No saved note visible in Obsidian:
  - verify folder path under vault
  - reopen vault / wait for file watcher refresh
- Path traversal or excluded path errors:
  - target path must stay inside vault and outside excluded folders
