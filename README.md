# Lark Chat Export Skill

安全导出飞书/Lark 聊天记录，并在不修改原始数据的前提下生成可读的 HTML 和 Markdown。

**简体中文** | [English](README.en.md)

## 项目简介

`lark-chat-export` 是一个面向 AI Agent 的飞书聊天备份 Skill。它通过飞书官方 `lark-cli` 读取当前用户可见的群聊和私聊，保存原始 JSON 与附件，并可从原始导出生成便于浏览和检索的 HTML、Markdown。

项目严格区分两类数据：

- **原始导出**：官方 CLI 返回的会话信息、消息 JSON 和附件，不由渲染程序修改。
- **可读派生文件**：通过加载原始导出生成的 HTML 和 Markdown，可随时删除并重新生成。

“全部聊天记录”是指当前认证用户通过飞书 OpenAPI 可以访问的全部会话及平台仍保留的消息。已删除、已撤回、超过企业保留期限或没有权限访问的数据无法恢复。

## 从 GitHub 安装

以下示例假设 GitHub 仓库地址为：

```text
https://github.com/Ezhana/lark-chat-export-skill
```

### 推荐：直接让 Codex 安装

在 Codex 中新建任务并发送：

```text
请使用 skill-installer 从 https://github.com/Ezhana/lark-chat-export-skill
的仓库根目录安装 lark-chat-export Skill。
```

Codex 会把 Skill 安装到自己的 Skills 目录。安装完成后，在下一轮请求或新任务中使用：

```text
使用 $lark-chat-export 备份我当前有权访问的飞书聊天记录，
同时生成 HTML 和 Markdown，不要修改原始数据。
```

### 使用 Codex 内置安装脚本

macOS、Linux 或 WSL：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo Ezhana/lark-chat-export-skill \
  --path . \
  --name lark-chat-export
```

安装器默认读取仓库的 `main` 分支。如果发布的是其他分支，需要增加：

```bash
--ref <branch-name>
```

建议使用标准 `main` 默认分支，避免增加无意义的安装障碍。

### 手动安装

也可以直接克隆到 Codex Skills 目录：

```bash
git clone https://github.com/Ezhana/lark-chat-export-skill.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/lark-chat-export"
```

重新启动 Codex 或开启新任务后，使用 `$lark-chat-export` 调用。

> 安装 Skill 不会自动安装飞书 `lark-cli`，也不会自动获得飞书权限。首次使用前仍需完成下方的环境配置和用户授权。

## 主要能力

- 枚举当前用户可见的群聊和一对一私聊。
- 自动分页读取历史消息。
- 下载图片、音频、视频和普通附件。
- 保留发送者、时间、消息类型、回复关系和表情反应。
- 为每个会话生成可搜索、可按消息类型筛选的本地 HTML。
- 为每个会话生成适合全文检索和后续处理的 Markdown。
- 转换前后计算原始目录的逐文件 SHA-256，证明原始数据未被修改。
- 拒绝覆盖非空输出目录。
- 不调用第三方 AI 摘要或图片分析服务。

## 项目结构

```text
lark-chat-export-skill/
├── SKILL.md                   # Agent 工作流与安全约束，核心入口
├── README.md                  # 中文文档，默认入口
├── README.en.md               # English documentation
├── agents/
│   └── openai.yaml            # OpenAI/Codex 可选 UI 元数据
└── scripts/
    ├── export_all.py          # 从官方 Lark CLI 创建原始导出
    └── render_readable.py     # 只读加载原始导出并生成 HTML/Markdown
```

## 环境要求

- Python 3.10 或更高版本。
- 飞书官方 [`lark-cli`](https://github.com/larksuite/cli)。
- 已配置飞书应用并完成用户身份授权。
- 当前用户具有读取目标会话和下载相关附件的权限。

先检查 CLI 状态：

```bash
lark-cli auth status
lark-cli doctor
```

只为实际导出所需的飞书 IM 读取能力授权。不要为了省事给新应用授予无关的文档删除、权限管理或多维表格写入权限。

## 快速开始

### 1. 创建原始导出

输出目录必须为空或不存在：

```bash
python3 scripts/export_all.py \
  --cli /path/to/lark-cli \
  --output /path/to/lark-chat-export-raw
```

如果明确只需要消息文本、不需要附件：

```bash
python3 scripts/export_all.py \
  --cli /path/to/lark-cli \
  --output /path/to/lark-chat-export-raw \
  --skip-resources
```

### 2. 生成可读版本

可读版必须写入另一个新目录：

```bash
python3 scripts/render_readable.py \
  --source /path/to/lark-chat-export-raw \
  --output /path/to/lark-chat-export-readable
```

完成后打开：

```text
/path/to/lark-chat-export-readable/index.html
```

HTML 支持本地搜索和消息类型筛选。Markdown 位于 `markdown/`，适合 `rg`、本地索引或后续分析。

## 输出说明

原始导出示例：

```text
lark-chat-export-raw/
├── manifest.json
├── chats.json
├── index.html
└── 001_example_<chat-id-suffix>/
    ├── chat.json
    ├── messages.json
    └── lark-im-resources/
```

可读版示例：

```text
lark-chat-export-readable/
├── index.html
├── manifest.json
├── source-integrity.json
├── html/
└── markdown/
```

可读版通过相对路径引用原始附件，不会再复制一份大型二进制文件。因此移动目录时，应保持原始导出与可读版的相对位置；如果位置改变，重新运行渲染即可。

## 数据安全

- `export_all.py` 只调用传入的官方 `lark-cli`。
- `render_readable.py` 只读取原始导出，并写入单独的派生目录。
- 两个脚本都会拒绝覆盖非空输出目录。
- HTML 中的聊天正文会进行转义，不会作为聊天成员注入的 HTML 或 JavaScript 执行。
- 聊天附件可能包含可执行文件；项目只保存附件，不会执行它们。
- `source-integrity.json` 中必须显示 `source_unchanged: true`，否则不能把结果视为成功交付。

## `openai.yaml` 与不同 AI 平台

`SKILL.md` 和 `scripts/` 是本项目的核心：前者描述 Agent 应如何选择和执行工作流，后者承载确定性的数据处理逻辑。

`agents/openai.yaml` 是 **OpenAI/Codex 专用的可选适配文件**，用于提供界面显示名称、简短说明、默认提示词，以及可能的调用策略或工具依赖。它不包含导出逻辑，删除它不会影响两个 Python 脚本的独立运行，但会失去相应的 Codex 界面元数据。

不同 AI 产品的自动发现、插件清单、UI 元数据和权限声明并不通用。需要适配其他平台时：

1. 保留 `SKILL.md` 和 `scripts/` 作为唯一事实来源。
2. 先确认目标平台是否原生识别 `SKILL.md`。
3. 仅在目标平台明确要求时增加一层很薄的平台专用元数据或清单。
4. 不要为每个平台复制或改写 Python 业务逻辑；否则安全修复会迅速分叉。

**不同平台可能需要不同的适配文件，但不应该需要不同版本的 Skill 核心逻辑。**

## 验证 Skill

在安装或发布前，使用 Codex 的 Skill 校验器检查结构：

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py .
```
