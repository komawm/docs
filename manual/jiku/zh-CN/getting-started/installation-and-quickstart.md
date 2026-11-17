# 安装与首次运行

> [!NOTE]
> 安装 Jiku 完全可选。[Koma](/zh-CN/docs/getting-started/installation/) 无需 `jikud` 或 `jiku` 即可作为纯 Wayland 平铺合成器独立运行。

![在 Koma 终端中执行 jiku 状态检查](https://cdn.komawm.org/media/jiku-terminal.webp "在 Koma 终端中检查 Jiku 状态并运行命令行工具。")

## 安装 `jikud` 与 `jiku`

可通过 [komawm/packaging](https://github.com/komawm/packaging) 安装预构建软件包（签名 APT `jiku` 包、AUR `jiku-bin`、Linuxbrew `jiku.rb` 或 `.deb`/`.rpm`/`.apk` 包），从 [komawm/jiku](https://github.com/komawm/jiku) 下载 `v0.0.1` 发布压缩包（`jiku-0.0.1-x86_64-unknown-linux-gnu.tar.gz` 或 `jiku-0.0.1-aarch64-unknown-linux-gnu.tar.gz`），从 npm 安装发布二进制（`@koma-wm/jiku`），或从源码构建。

### 预构建二进制渠道（`x86_64` 与 `aarch64`）

```bash
# Arch Linux（AUR 预构建二进制包）
paru -S jiku-bin

# Debian / Ubuntu（签名 APT 软件源）
curl -fsSL https://cdn.komawm.org/apt/setup.sh | sudo bash && sudo apt install -y jiku

# Linuxbrew
curl -fsSLO https://cdn.komawm.org/install/jiku/jiku.rb && brew install --formula ./jiku.rb

# npm / Bun（registry 作用域 `@koma-wm`，因 `komawm` 已被占用）
bun add -g @koma-wm/jiku
# 或
npm install -g @koma-wm/jiku
```

两个 shim 都是 Node 脚本（`#!/usr/bin/env node`），因此即使用 bun 安装，`PATH` 上也必须有
Node.js 18.17 或更高版本。该路径下 bun 只承担包管理器角色（除非显式用 `bun` 启动 shim）。

registry 上已提供 glibc 版 `linux-x64` 与 `linux-arm64` 的 `v0.0.1`，`latest` 与 `development`
都指向该版本。新版本只会在 `komawm/packaging` 的发布派发之后出现，因此查不到某个版本属于预期，
不是安装故障。musl/Alpine、macOS 与 Windows 不受支持，launcher 会给出明确提示并拒绝运行。
若要显式固定预发布渠道，请使用 `@koma-wm/jiku@development`。

### 从源码构建

```bash
# 从代码仓库直接安装
cargo +1.100.0 install --git https://github.com/komawm/jiku.git jikud jiku --locked

# 或克隆仓库并在本地构建
git clone https://github.com/komawm/jiku.git
cd jiku
cargo +1.100.0 build --release --locked -p jikud -p jiku
./target/release/jikud --headless-check
```

### 智能体 Skill（`npx skills`）

仓库提供可直接安装的编码智能体 skill：

```bash
# Jiku：目标级桌面编排
npx skills add komawm/jiku --skill jiku-desktop-orchestration -g

# Koma：工作区、截图与输入原语
npx skills add komawm/koma --skill koma-desktop -g
```

skill 采用 MIT 许可，并自带独立于 `GPL-3.0-or-later` 产品许可的 `LICENSE`，因此被复制的
skill 仍然自包含。

若安装的包由包含 `skills/jiku-desktop-orchestration/` 的 tag 构建，`npx skills experimental_sync`
也能为项目依赖（`bun add -d @koma-wm/jiku`）链接包内自带的 skill。早于 skill 目录的 tag
（包括 `v0.0.1`）不含该内容，请使用 `npx skills add`。

## Shell 补全

发行版软件包会为 `jiku` 注册 bash、zsh、fish 补全。手动安装时从二进制生成：

```bash
jiku completions bash > ~/.local/share/bash-completion/completions/jiku
jiku completions zsh  > ~/.zsh/completions/_jiku
jiku completions fish > ~/.config/fish/completions/jiku.fish
```

补全脚本与 `jiku --help` 来自同一张表，因此 `a11y snapshot`、`skills approve`、`bench run` 等嵌套命令也能补全真实参数。

## API 密钥与环境变量

`jikud` 仅从 `config.toml` 或 `config.lua` 中 `api_key_env` 指定的环境变量读取凭据。切勿把明文密钥写入配置文件。

| 环境变量 | 默认提供方 | 承担角色 |
| :--- | :--- | :--- |
| `JIKU_PLANNER_API_KEY` | `primary`（`[providers.primary]`） | 主规划文本/VLM 模型 `[roles.planner]`，以及判定时的结构化 JSON 回退 |
| `JIKU_DECISION_API_KEY` | `decision`（`[providers.decision]`） | 可选专用判定模型，以及可选实时语音会话 |
| `KOMA_CAPABILITY_TOKEN` | Koma IPC（`koma-agent.sock`） | 通过 `komactl token mint jiku` 签发的作用域租约令牌 |

> [!TIP]
> **没有专用判定模型密钥？** 若判定提供方的密钥未设置（或将 `[roles.decision_router]` 指向任意 OpenAI 兼容、Anthropic、vLLM 或 Ollama 提供方），Jiku 会自动回退到 `[roles.planner]` 并使用结构化 JSON 输出完成判定，不会报错。

## 首次运行步骤

1. **离线校验配置与 Lua 策略**：
   ```bash
   jiku validate-config
   ```
2. **在 Koma 运行状态下签发作用域令牌**：
   ```bash
   export KOMA_CAPABILITY_TOKEN="$(komactl token mint jiku | jq -r '.token')"
   ```
3. **启动 `jikud` 守护进程并检查状态**：
   ```bash
   jikud --daemon &
   jiku status --json
   ```
4. **先试跑 Dry-Run 任务与本地诊断**：
   ```bash
   jiku run --dry-run "Open a terminal and check uname -a"
   jiku a11y snapshot --json
   jiku context inspect --max-tokens 4096
   jiku tts say "Jiku is ready"
   jiku avatar serve --bind 127.0.0.1:4190
   jiku bench run --offline
   ```

## 接入外部编码智能体（`Claude Code`、`Codex`、`OpenCode`、`pi`、`Cursor`）

`jiku mcp`（12 个编排工具）与 `koma-mcp`（17 个合成器工具）均会在每条消息边界自动识别 `Content-Length` 与 `NDJSON` stdio 帧格式。可在 `Claude Code`、`Codex`、`Cursor`、`pi` 或 OpenCode（`~/.config/opencode/opencode.json`）中注册接入：

```json
{
  "mcp": {
    "koma": {
      "type": "local",
      "command": ["koma-mcp"],
      "enabled": true
    },
    "jiku": {
      "type": "local",
      "command": ["jiku", "mcp"],
      "enabled": true
    }
  }
}
```

用 `komactl token mint <label>` 签发令牌，并在启动智能体宿主的 shell 中导出。`koma-mcp`
从环境读取 `KOMA_CAPABILITY_TOKEN`，因此令牌无需写入配置文件；若宿主不继承环境，请在其
自身的 environment 配置块中设置。不要给由智能体控制的 MCP 服务器传 `--auto-mint-admin`，
否则智能体可以自行签发权限。`jiku status` 需要 Koma 会话在运行，
没有会话时的失败是预期行为，不是安装问题。

请安装[智能体 skill](#智能体-skillnpx-skills)，而不是复制 `SKILL.md` 路径；这样智能体才能在
Koma 的 Epoch 隔离保护下调用 `jiku run`、`jiku decide`、`jiku a11y`、`jiku context inspect`、
`jiku box classify` 与 `jiku memory search`。
