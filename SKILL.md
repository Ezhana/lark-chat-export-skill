---
name: lark-chat-export
description: Safely export all Feishu/Lark chats through the official Lark CLI and derive readable HTML or Markdown without modifying the raw export. Use for complete chat backup, archival, offline reading, or converting an existing CLI export. Do not use for sending messages or modifying Feishu data.
---

# Lark Chat Export

Export chat data with the bundled deterministic scripts. Keep the raw export and readable derivatives in separate directories.

## Safety invariants

- Use only the official `lark-cli` executable for Feishu API access.
- Treat an existing raw export as immutable. Never render into it or overwrite it.
- Do not start local proxies, enable AI summaries, or send messages or attachments to third-party AI services.
- Downloaded attachments are inert backup files. Never execute them.
- State clearly that “all chats” means all chats and retained messages visible to the authenticated user through OpenAPI; deleted, recalled, expired, or inaccessible records cannot be recovered.

## Choose the workflow

For a new backup:

1. Resolve the official CLI executable and run `lark-cli auth status` and `lark-cli doctor`.
2. Review the active identity and required read scopes. Do not broaden permissions unless the export fails for a documented missing scope.
3. Run `scripts/export_all.py --cli <official-lark-cli> --output <new-raw-directory>`.
4. Run `scripts/render_readable.py --source <raw-directory> --output <new-readable-directory>`.

For an existing raw export, skip authentication and export. Confirm it contains `manifest.json`, per-chat `chat.json`, and per-chat `messages.json`, then run only `render_readable.py`.

Both scripts refuse to overwrite a non-empty output directory. Choose a new destination instead of deleting or patching an earlier backup.

## Verification and handoff

- The raw export succeeds only when every enumerated chat completes. Inspect its `manifest.json` for failures and confirm no message response has `data.has_more: true`.
- The readable renderer writes `source-integrity.json`. Require `source_unchanged: true` before delivery.
- Open `index.html` as the entry point. HTML supports local search and type filtering; Markdown is suited to grep, indexing, and later processing.
- Readable files reference raw attachments by relative path to avoid duplicating large binaries. Keep the raw and readable directories in their original relative locations, or regenerate the readable directory after moving them.

## Commands

```bash
python3 scripts/export_all.py \
  --cli /path/to/lark-cli \
  --output /path/to/new-raw-export

python3 scripts/render_readable.py \
  --source /path/to/raw-export \
  --output /path/to/new-readable-export
```

Use `--skip-resources` during export only when the user explicitly wants message text without attachments.
