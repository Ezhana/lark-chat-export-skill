#!/usr/bin/env python3
"""Export every chat visible to a user through the official Lark CLI."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_json(command: list[str], cwd: Path) -> dict:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"exit code {completed.returncode}")
    return json.loads(completed.stdout)


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^\w\-\u4e00-\u9fff]+", "_", value, flags=re.UNICODE).strip("_")
    return cleaned[:60] or "unnamed_chat"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def build_index(output_dir: Path, manifest: dict) -> None:
    rows = []
    for item in manifest["chats"]:
        name = html.escape(item["name"])
        mode = html.escape(item["chat_mode"])
        status = html.escape(item["status"])
        relative_path = html.escape(item.get("messages_file", ""), quote=True)
        link = f'<a href="{relative_path}">messages.json</a>' if relative_path else "—"
        rows.append(
            f"<tr><td>{item['index']}</td><td>{name}</td><td>{mode}</td>"
            f"<td>{item.get('message_count', 0)}</td><td>{status}</td><td>{link}</td></tr>"
        )
    document = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>飞书聊天原始导出清单</title><style>body{{font:15px/1.6 system-ui,sans-serif;max-width:1100px;margin:36px auto;padding:0 18px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:9px;text-align:left}}th{{background:#f5f6f8}}</style></head>
<body><h1>飞书聊天原始导出清单</h1><p>{len(manifest['chats'])} 个会话，{manifest['total_messages']} 条消息。未调用第三方 AI 服务。</p>
<table><thead><tr><th>#</th><th>会话</th><th>类型</th><th>消息</th><th>状态</th><th>数据</th></tr></thead><tbody>{''.join(rows)}</tbody></table></body></html>"""
    (output_dir / "index.html").write_text(document, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path, help="official lark-cli executable")
    parser.add_argument("--output", required=True, type=Path, help="new raw export directory")
    parser.add_argument("--skip-resources", action="store_true", help="do not download attachments")
    args = parser.parse_args()

    cli_path = args.cli.expanduser().resolve()
    if not cli_path.is_file():
        raise SystemExit(f"找不到官方 lark-cli：{cli_path}")
    output_dir = args.output.expanduser().resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"拒绝覆盖非空目录：{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    chats_response = run_json(
        [
            str(cli_path), "im", "+chat-list", "--as", "user", "--types", "p2p,group",
            "--page-all", "--page-limit", "1000", "--page-size", "100", "--format", "json",
        ],
        output_dir,
    )
    chats = chats_response.get("data", {}).get("chats", [])
    write_json(output_dir / "chats.json", chats_response)
    manifest = {
        "exported_at": datetime.now().astimezone().isoformat(),
        "source": "official @larksuite/cli",
        "third_party_ai_used": False,
        "total_messages": 0,
        "chats": [],
    }

    for index, chat in enumerate(chats, start=1):
        chat_id = str(chat.get("chat_id") or "")
        name = str(chat.get("name") or chat_id or f"chat_{index}")
        chat_dir = output_dir / f"{index:03d}_{safe_name(name)}_{chat_id[-8:]}"
        chat_dir.mkdir(parents=True, exist_ok=True)
        write_json(chat_dir / "chat.json", chat)
        messages_path = chat_dir / "messages.json"
        command = [
            str(cli_path), "im", "+chat-messages-list", "--as", "user", "--chat-id", chat_id,
            "--order", "asc", "--page-all", "--page-limit", "1000", "--page-size", "50",
            "--format", "json",
        ]
        if not args.skip_resources:
            command.append("--download-resources")
        print(f"[{index}/{len(chats)}] {name}", flush=True)
        item = {"index": index, "chat_id": chat_id, "name": name, "chat_mode": chat.get("chat_mode", "unknown")}
        try:
            response = run_json(command, chat_dir)
            write_json(messages_path, response)
            messages = response.get("data", {}).get("messages", [])
            item.update(
                status="ok",
                message_count=len(messages),
                messages_file=messages_path.relative_to(output_dir).as_posix(),
                pagination_remaining=bool(response.get("data", {}).get("has_more")),
            )
            manifest["total_messages"] += len(messages)
        except Exception as error:
            item.update(status="error", message_count=0, error=str(error))
            print(f"失败：{name}：{error}", file=sys.stderr, flush=True)
        manifest["chats"].append(item)
        write_json(output_dir / "manifest.json", manifest)
        build_index(output_dir, manifest)

    failed = [item for item in manifest["chats"] if item["status"] != "ok" or item.get("pagination_remaining")]
    print(f"完成：{manifest['total_messages']} 条消息；失败或未取完：{len(failed)}。", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
