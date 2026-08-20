#!/usr/bin/env python3
"""Render an immutable Lark CLI export into readable HTML and Markdown."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def fingerprint(root: Path) -> dict[str, dict[str, int | str]]:
    result = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        result[path.relative_to(root).as_posix()] = {
            "sha256": digest.hexdigest(),
            "size": path.stat().st_size,
        }
    return result


def safe_filename(value: str) -> str:
    value = re.sub(r"[^\w\-\u4e00-\u9fff]+", "_", value, flags=re.UNICODE).strip("_")
    return value[:80] or "unnamed_chat"


def sender_name(message: dict) -> str:
    sender = message.get("sender") or {}
    return str(sender.get("name") or sender.get("id") or "未知发送者")


def message_content(message: dict) -> str:
    if message.get("deleted"):
        return "[消息已删除]"
    content = str(message.get("content") or "")
    if not content:
        return f"[{message.get('msg_type', 'unknown')} 消息]"
    if message.get("msg_type") == "text":
        try:
            decoded = json.loads(content)
            if isinstance(decoded, dict) and isinstance(decoded.get("text"), str):
                return decoded["text"]
        except (json.JSONDecodeError, TypeError):
            pass
    return content


def local_resource(source_chat_dir: Path, resource: dict) -> Path | None:
    local_path = str(resource.get("local_path") or "")
    if not local_path:
        return None
    candidate = (source_chat_dir / local_path).resolve()
    try:
        candidate.relative_to(source_chat_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def relative_url(target: Path, rendered_file: Path) -> str:
    relative = os.path.relpath(target, rendered_file.parent).replace(os.sep, "/")
    return quote(relative, safe="/._-~")


def resources_html(message: dict, source_chat_dir: Path, output_file: Path) -> str:
    blocks = []
    for resource in message.get("resources") or []:
        path = local_resource(source_chat_dir, resource)
        if path is None:
            continue
        url = html.escape(relative_url(path, output_file), quote=True)
        label = html.escape(path.name)
        extension = path.suffix.lower()
        if extension in IMAGE_EXTENSIONS:
            blocks.append(f'<figure><a href="{url}"><img loading="lazy" src="{url}" alt="{label}"></a><figcaption>{label}</figcaption></figure>')
        elif extension in AUDIO_EXTENSIONS:
            blocks.append(f'<div class="media"><audio controls preload="none" src="{url}"></audio><a href="{url}">{label}</a></div>')
        elif extension in VIDEO_EXTENSIONS:
            blocks.append(f'<div class="media"><video controls preload="metadata" src="{url}"></video><a href="{url}">{label}</a></div>')
        else:
            size = resource.get("size_bytes")
            size_label = f" · {size / 1024 / 1024:.1f} MB" if isinstance(size, int) else ""
            blocks.append(f'<div class="attachment">📎 <a href="{url}">{label}</a>{size_label}</div>')
    return "".join(blocks)


def reactions_html(message: dict) -> str:
    parts = []
    for item in (message.get("reactions") or {}).get("counts") or []:
        reaction_type = html.escape(str(item.get("reaction_type") or "reaction"))
        count = html.escape(str(item.get("count") or ""))
        parts.append(f"{reaction_type} {count}")
    return f'<div class="reactions">{" · ".join(parts)}</div>' if parts else ""


def render_html(chat: dict, messages: list[dict], source_chat_dir: Path, output_file: Path) -> None:
    cards = []
    for message in messages:
        content = message_content(message)
        sender = sender_name(message)
        message_type = str(message.get("msg_type") or "unknown")
        reply_to = message.get("reply_to")
        reply = f'<div class="reply">回复：{html.escape(str(reply_to))}</div>' if reply_to else ""
        cards.append(
            f'<article class="message" data-type="{html.escape(message_type, quote=True)}" '
            f'data-search="{html.escape(f"{sender} {content} {message_type}", quote=True)}">'
            f'<header><strong>{html.escape(sender)}</strong><time>{html.escape(str(message.get("create_time") or ""))}</time>'
            f'<span>{html.escape(message_type)}</span></header>{reply}'
            f'<div class="content">{html.escape(content).replace(chr(10), "<br>")}</div>'
            f'{resources_html(message, source_chat_dir, output_file)}{reactions_html(message)}</article>'
        )
    chat_name = str(chat.get("name") or "未命名会话")
    counts = Counter(str(message.get("msg_type") or "unknown") for message in messages)
    options = "".join(f'<option value="{html.escape(key, quote=True)}">{html.escape(key)} ({count})</option>' for key, count in sorted(counts.items()))
    document = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(chat_name)} · 飞书聊天记录</title><style>
:root{{--bg:#f5f6f8;--card:#fff;--text:#1f2329;--muted:#646a73;--line:#dee0e3;--accent:#3370ff}}*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}}.page{{max-width:980px;margin:auto;padding:24px}}
.hero{{position:sticky;top:0;z-index:2;background:rgba(245,246,248,.96);padding:10px 0 16px}}h1{{margin:0 0 4px;font-size:24px}}.summary{{color:var(--muted);margin:0 0 12px}}
.tools{{display:flex;gap:8px}}input,select{{border:1px solid var(--line);border-radius:8px;background:#fff;padding:9px 12px;font:inherit}}input{{flex:1}}
.message{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0;overflow-wrap:anywhere}}header{{display:flex;gap:10px;align-items:baseline}}
header time,header span{{color:var(--muted);font-size:12px}}header span{{margin-left:auto}}.content{{margin-top:7px}}.reply{{border-left:3px solid #bbbfc4;padding-left:8px;color:var(--muted);font-size:12px}}
figure{{margin:12px 0}}img{{max-width:min(100%,720px);max-height:680px;border-radius:8px}}figcaption,.media a{{display:block;color:var(--muted);font-size:12px}}video{{max-width:100%;max-height:600px}}
audio{{width:min(100%,520px)}}.attachment,.reactions{{margin-top:8px;font-size:13px}}a{{color:var(--accent)}}.hidden{{display:none}}@media(max-width:640px){{.page{{padding:12px}}.tools{{flex-direction:column}}.hero{{position:static}}}}
</style></head><body><main class="page"><section class="hero"><h1>{html.escape(chat_name)}</h1><p class="summary">{len(messages):,} 条消息 · {html.escape(str(chat.get('chat_mode') or 'unknown'))} · 只读派生视图</p>
<div class="tools"><input id="query" type="search" placeholder="搜索发送者或消息内容"><select id="type"><option value="">全部类型</option>{options}</select></div></section><section>{''.join(cards)}</section></main>
<script>const q=document.querySelector('#query'),t=document.querySelector('#type'),cards=[...document.querySelectorAll('.message')];function filter(){{const query=q.value.trim().toLowerCase(),type=t.value;for(const card of cards){{card.classList.toggle('hidden',!((!query||card.dataset.search.toLowerCase().includes(query))&&(!type||card.dataset.type===type)))}}}}q.addEventListener('input',filter);t.addEventListener('change',filter);</script>
</body></html>"""
    write_text(output_file, document)


def render_markdown(chat: dict, messages: list[dict], source_chat_dir: Path, output_file: Path) -> None:
    escape = lambda value: str(value).replace("<", "&lt;").replace(">", "&gt;")
    lines = [f"# {escape(chat.get('name') or '未命名会话')}", "", f"- 类型：`{chat.get('chat_mode') or 'unknown'}`", f"- 消息数：{len(messages)}", "- 来源：官方 Lark CLI 原始导出的只读派生视图", "", "---", ""]
    for message in messages:
        lines.extend([
            f"## {escape(message.get('create_time') or '')} · {escape(sender_name(message))}", "",
            f"类型：`{escape(message.get('msg_type') or 'unknown')}` · ID：`{message.get('message_id') or ''}`", "",
        ])
        if message.get("reply_to"):
            lines.extend([f"> 回复：`{message['reply_to']}`", ""])
        lines.extend("> " + line for line in escape(message_content(message)).splitlines() or [""])
        lines.append("")
        for resource in message.get("resources") or []:
            path = local_resource(source_chat_dir, resource)
            if path is None:
                continue
            url = relative_url(path, output_file)
            label = escape(path.name).replace("[", "\\[").replace("]", "\\]")
            lines.append(f"![{label}](<{url}>)" if path.suffix.lower() in IMAGE_EXTENSIONS else f"- [附件：{label}](<{url}>)")
        reactions = (message.get("reactions") or {}).get("counts") or []
        if reactions:
            lines.extend(["", "反应：" + " · ".join(f"{item.get('reaction_type')} {item.get('count')}" for item in reactions)])
        lines.extend(["", "---", ""])
    write_text(output_file, "\n".join(lines))


def render_index(output_dir: Path, entries: list[dict], source_root: Path) -> None:
    rows = "".join(
        f'<tr><td>{entry["index"]}</td><td>{html.escape(entry["name"])}</td><td>{entry["count"]:,}</td>'
        f'<td><a href="{html.escape(entry["html"], quote=True)}">HTML</a></td><td><a href="{html.escape(entry["markdown"], quote=True)}">Markdown</a></td></tr>'
        for entry in entries
    )
    page = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>飞书聊天记录 · 可读版</title>
<style>body{{font:15px/1.6 system-ui,sans-serif;max-width:1100px;margin:36px auto;padding:0 18px;color:#1f2329}}table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #ddd;padding:10px;text-align:left}}th{{background:#f5f6f8}}a{{color:#3370ff}}</style></head>
<body><h1>飞书聊天记录 · 可读版</h1><p>从 <code>{html.escape(source_root.name)}</code> 只读加载生成；原始数据未改动。</p><table><thead><tr><th>#</th><th>会话</th><th>消息</th><th>网页</th><th>Markdown</th></tr></thead><tbody>{rows}</tbody></table></body></html>"""
    write_text(output_dir / "index.html", page)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="immutable raw export directory")
    parser.add_argument("--output", required=True, type=Path, help="new readable export directory")
    args = parser.parse_args()
    source_root = args.source.expanduser().resolve()
    output_dir = args.output.expanduser().resolve()
    if not (source_root / "manifest.json").is_file():
        raise SystemExit(f"无效原始导出，缺少 manifest.json：{source_root}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"拒绝覆盖非空目录：{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("计算转换前校验值…", flush=True)
    before = fingerprint(source_root)
    manifest = load_json(source_root / "manifest.json")
    entries = []
    for position, item in enumerate(manifest.get("chats") or [], start=1):
        messages_file = source_root / item["messages_file"]
        source_chat_dir = messages_file.parent
        messages = load_json(messages_file).get("data", {}).get("messages", [])
        chat = load_json(source_chat_dir / "chat.json")
        stem = f"{position:03d}_{safe_filename(str(chat.get('name') or item['chat_id']))}"
        html_file = output_dir / "html" / f"{stem}.html"
        markdown_file = output_dir / "markdown" / f"{stem}.md"
        print(f"[{position}/{len(manifest['chats'])}] {chat.get('name') or item['chat_id']}：{len(messages)} 条", flush=True)
        render_html(chat, messages, source_chat_dir, html_file)
        render_markdown(chat, messages, source_chat_dir, markdown_file)
        entries.append({"index": position, "name": str(chat.get("name") or item["chat_id"]), "count": len(messages), "html": html_file.relative_to(output_dir).as_posix(), "markdown": markdown_file.relative_to(output_dir).as_posix()})

    render_index(output_dir, entries, source_root)
    print("复核转换后校验值…", flush=True)
    unchanged = before == fingerprint(source_root)
    integrity = {"verified_at": datetime.now().astimezone().isoformat(), "source": str(source_root), "file_count": len(before), "source_unchanged": unchanged, "files": before}
    write_text(output_dir / "source-integrity.json", json.dumps(integrity, ensure_ascii=False, indent=2))
    write_text(output_dir / "manifest.json", json.dumps({"source": str(source_root), "source_unchanged": unchanged, "chat_count": len(entries), "message_count": sum(item["count"] for item in entries), "entries": entries}, ensure_ascii=False, indent=2))
    if not unchanged:
        raise SystemExit("原始数据在转换过程中发生变化，停止交付")
    print(f"完成：{len(entries)} 个 HTML，{len(entries)} 个 Markdown；原始数据校验一致。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
