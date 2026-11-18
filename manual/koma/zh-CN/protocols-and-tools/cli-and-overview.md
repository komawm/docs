# komactl 与工作区概览

`komactl` 是 Koma 的管理命令行工具（连接 `koma-admin.sock`）与离线 Lua 配置校验器；`koma-overview` 则是基于 `wlr-layer-shell` 的全局工作区空间概览程序。

## `komactl` 子命令一览

`komactl` 会自动探测 `$XDG_RUNTIME_DIR/koma/<signature>/koma-admin.sock`（也可通过 `KOMA_INSTANCE_SIGNATURE` 指定实例）。

| 子命令 | 运行模式 | 功能说明 |
| :--- | :--- | :--- |
| `komactl validate [path/to/init.lua]` | 离线 | 在隔离 Lua 沙箱中求值 `init.lua`，校验规则正则与手势并输出统计 |
| `komactl doctor [path/to/init.lua] [--json] [--strict]` | 离线 | 按领域运行全部非破坏性配置检查，报告 `ok` / `warn` / `error` / `skip`；`error` 不会改变退出码 |
| `komactl keys [path/to/init.lua] [--json] [--grep <pattern>]` | 离线（可连接时只读并入运行状态） | 列出实际生效的键位表：内置目录与 `init.lua` 合并，另含指针绑定与手势；会重复的行带 `[repeat]` |
| `komactl reload [path/to/init.lua]` | IPC（`admin.sock`） | 调用 `config.reload` 原子热重载合成器配置 |
| `komactl config-status` | IPC（`admin.sock`）+ 离线 | 查看当前配置路径、重载代数与最近报错（`config.status`）、实际生效的 `input.keyboard` / `input.pointer` / `input.touchpad` 参数，并报告生成模板的 `template.{init_lua,present,installed_version,shipped_version,outdated,missing_files}` |
| `komactl init [dir] [--force]` | 离线 | 生成 `init.lua`、`lua/{input,workspaces,appearance,window_rules,keybinds}.lua` 与 `lua/macros/example.lua`；除非传入 `--force`，否则拒绝覆盖已有文件 |
| `komactl gen-types` | 离线 | 确定性输出供 `koma-types`（`types/koma.lua`）使用的 `LuaCATS` 存根 |
| `komactl inventory` | IPC（`admin.sock`） | 导出显示器、工作区、`Epoch` 计数、Deck 活跃窗与 Stash 列表（`scene.inventory`）；恰好一个工作区带 `"focused": true` |
| `komactl win move-to-workspace <ws_id\|name> [--follow]` | IPC（`admin.sock`） | 把当前聚焦工作区的活跃窗口移动到已存在的工作区（`win.move_to_workspace`）；加 `--follow` 会切换到目标工作区，否则保持源工作区聚焦 |
| `komactl token mint [label]` | IPC（`admin.sock`） | 签发受限 `CapabilityToken`（默认 `ttl_secs = 28800`、`can_create_headless = true`、`max_owned_workspaces = 4`） |
| `komactl capture [ws_id] [out.rgba]` | IPC（`admin.sock`） | 通过 `SCM_RIGHTS` 零拷贝密封 `memfd` 抓取带 `grid_225` 叠加层的画面（默认 `ws_01`） |
| `komactl sandbox <subcmd>` | 容器 + IPC | 使用 `bwrap` 或无根 `podman` 在隔离 `Headless` 工作区中运行受限 GUI 容器 |
| `komactl -V` / `--version` | 离线 | 输出 `komactl <version>` |

## 生成的配置（`komactl init`）

`komactl init` 会将随包提供的起始配置树渲染到默认配置目录或显式指定的 `[dir]`：

```text
init.lua
lua/input.lua
lua/workspaces.lua
lua/appearance.lua
lua/window_rules.lua
lua/keybinds.lua
lua/macros/example.lua
```

`init.lua` 只是一个薄路由，`lua/keybinds.lua` 则把完整默认键位展开为 `koma.bind(...)` 调用，因此生成文件与内置回退键位表不会漂移。每个生成文件开头都带有机器可读标记 `-- koma-config-template: <version>`。

已有文件不会被覆盖：`komactl init` 会列出冲突路径并停止，只有传入 `--force` 才会替换。编辑后请运行 `komactl validate` 与 `komactl reload`。`komactl config-status` 会将磁盘上的标记与随包模板比较，并报告 `template.installed_version`、`template.shipped_version`、`template.outdated` 与 `template.missing_files`。

为区分版本比较无法覆盖的情形，`template` 还提供两个字段：`template.init_lua` 是实际被检查的路径（依次解析 `KOMA_CONFIG`、`$XDG_CONFIG_HOME/koma/init.lua`、`$HOME/.config/koma/init.lua`），`template.present` 表示该文件是否存在。手写且没有标记的 `init.lua` 会报告 `installed_version: null` 与 `outdated: false`，不会被误判为过期模板；而被删掉部分文件的骨架会出现在 `missing_files` 中。

## `komactl config-status` 报告的实际输入参数

同一份报告内嵌合成器的 `config.status`，其中的 `input.pointer` 与 `input.touchpad` 块列出 Koma 真正应用的取值：`accel_speed`、`accel_profile`、`natural_scroll`、`scroll_factor`、`follow_mouse`，触控板另有 `tap_to_click` 与 `disable_while_typing`。`null` 表示该项从未写入 `init.lua`，此时生效的是 libinput 内置默认值；`accel_profile` 只可能是 `"adaptive"`（默认曲线）或 `"flat"`（完全关闭加速）。当相同物理位移下指针移动距离与其他合成器不同，请先比较 `accel_speed` 与 `accel_profile`——未设置 profile 通常就能解释大部分差异。

### `config.status` 中的 XKB 键盘映射

同一个 `input` 对象新增了 `input.keyboard`：`layout`、`variant`、`model`、`options`、`repeat_delay_ms`、`repeat_rate_hz`。`null` 依然表示“未配置”，此时应用 XKB／libinput 的默认值；`options` 是原始 XKB 选项字符串，无需重开 `init.lua` 就能验证改键是否生效。这些值同时驱动文本重复与按住重复的节奏。

`options` 使用 XKB 名称，与 Hyprland `kb_options` 接受的名称完全一致；凡是 `setxkbmap -option` 接受的写法都可用：

| 选项 | 作用 |
| :--- | :--- |
| `caps:escape` | Caps Lock 作为 Escape |
| `caps:ctrl_modifier` | Caps Lock 作为额外的 Ctrl |
| `ctrl:nocaps` | 将 Caps Lock 映射为 Ctrl |
| `altwin:swap_lalt_lwin` | 交换左 Alt 与左 Super |
| `compose:caps` | Caps Lock 作为 Compose 键 |
| `grp:alt_shift_toggle` | Alt + Shift 切换键盘布局组 |

### `config.status` 中的帧时间直方图（`frame_perf`）

`config.status` 还会返回无堆分配的渲染帧耗时统计 `frame_perf`（包含 `rendered_frames`、`skipped_frames`、`avg_us`、`max_us`、`last_us`、`p50_bucket`、`p95_bucket` 以及 `lt_1ms` 至 `ge_16ms` 固定分桶），并在每渲染 1,000 帧时输出一次 `tracing::debug!` 汇总日志用于性能调试。

## 配置诊断（`komactl doctor` 与 `komactl keys`）

两个命令都复用 `komactl validate` 的隔离影子虚拟机求值，因此可离线运行，无需 seat。`komactl doctor` 将检查分为 `config`、`template`、`binds`、`monitors`、`workspaces`、`rules`、`environment` 七组，每行带有严重级别：`ok`（已运行且未发现问题）、`warn`（可以加载，但很可能不是本意）、`error`（下次重载会被拒绝）、`skip`（当前环境无法运行，例如没有 DRM 或没有运行中的合成器）。

`error` 不会改变退出码，因为合成器会继续使用最后一份有效配置，配置错误不应让会话瘫痪。`--strict` 在出现任何 warn 或 error 时以 `1` 退出；`2` 保留给完全无法读取配置、用法错误或内部故障。`--json` 输出包含计数与全部检查行的单个文档。

`komactl keys` 输出实际生效的键位表：内置目录与 `input.inherit_default_binds`、`koma.unbind`、组合键覆盖合并，指针绑定与手势单独成节。每一行显示组合键、动作、Lua 表达式、来源（`builtin` 或 `config:<file>`）与说明；覆盖内置绑定时，原说明会以括号保留。`--grep <pattern>` 按不区分大小写过滤，`--json` 输出 `{catalogue, keyboard, pointer, gestures, total, overridden_builtins}`。列表不会隐藏任何内容：无法映射回目录条目的绑定会连同原始动作描述一起打印。默认离线运行；若能连到运行中的 `koma-admin.sock`，头部与 JSON 的 `live` 对象会以只读方式并入运行代次、当前配置路径与锁屏状态。

## `komactl sandbox` 容器级 Wayland 隔离

`komactl sandbox` 仅在私有 `0700` `tmpfs` 运行目录中暴露受限的 `jail-<ws_id>.sock`（绝不挂载宿主机 `$XDG_RUNTIME_DIR`、`koma-admin.sock`、D-Bus、PipeWire 或 SSH Agent）：

```bash
# 在独立 1920x1080 无头工作区通过 bwrap 运行默认断网的隔离浏览器
komactl sandbox run --name browser-jail -- firefox

# 使用无根 podman 运行 OCI 容器并开启网络（先 dry-run 预览完整命令）
komactl sandbox run --runtime podman --image fedora:latest --share-net --dry-run -- glxgears

# 按需授予单工作区代理通道权限（仅挂载 koma-agent.sock + 作用域令牌）
komactl sandbox run --with-agent-sock --ro-bind ~/repo:/workspace -- code-oss
```

| 选项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `--runtime <bwrap\|podman>` | `bwrap` | 指定容器引擎（传入 `--image` 时自动切换 `podman`） |
| `--ws <ws_id\|auto>` | `auto` | 复用既有 `ws_id` 或自动新建 `Headless` 工作区 |
| `--name <name>` | `sandbox` | 新建无头工作区名称 |
| `--geometry <WxH[@scale]>` | `1920x1080` | 无头视口分辨率与缩放（如 `2560x1600@1.6`） |
| `--bind <host:guest>` / `--ro-bind` | 无 | 显式声明读写或只读挂载目录 |
| `--share-net` | 关闭 | 启用宿主机网络（`bwrap`）或 `pasta`（`podman`）；默认断网隔离 |
| `--no-gpu` | 关闭 | 不挂载 `/dev/dri`，强制走 Mesa/Lavapipe 软件渲染 |
| `--nvidia` | 关闭 | 为 Podman 附加 `--device=nvidia.com/gpu=all` CDI 设备参数 |
| `--with-agent-sock` | 关闭 | 挂载 `koma-agent.sock` 并注入单工作区 `KOMA_CAPABILITY_TOKEN`（永不挂载 `koma-admin.sock`） |
| `--keep-jail` | 关闭 | 容器退出后保留 `jail-<ws_id>.sock`（可用 `create-jail` / `revoke-jail` 手动管理） |
| `--dry-run` | 关闭 | 仅打印生成的容器命令而不实际拉起进程 |

## `koma` 子命令（`init` / `completions` / `mcp`）

合成器二进制本身还提供三个非合成器子命令：

| 命令 | 说明 |
| :--- | :--- |
| `koma init <bash\|zsh\|fish\|nushell> [--unset]` | 输出当前实例的 shell 环境赋值 |
| `koma completions <bash\|zsh\|fish>` | 输出根据二进制命令表生成的补全脚本 |
| `koma mcp [--print-tools] [--auto-mint-admin]` | 对 `koma-agent.sock` 启动 stdio MCP 服务器 |

`koma init` 会输出 `WAYLAND_DISPLAY`、`KOMA_INSTANCE_SIGNATURE`、`XDG_RUNTIME_DIR`、`DISPLAY`（仅 `xwayland-satellite` 运行时）、`XDG_SESSION_TYPE` 与 `XDG_CURRENT_DESKTOP`，让外部终端也能使用 `komactl` 等工具：

```bash
koma init fish | source
eval "$(koma init bash)"
koma init zsh --unset   # 相反的赋值
```

它绝不输出能力令牌。没有活动实例或存在多个实例时会给出明确错误而不做猜测，请用 `KOMA_INSTANCE_SIGNATURE` 指定目标实例。

`koma mcp` 是取代原独立二进制 `koma-mcp` 的 stdio 服务器。`--print-tools` 在不接触智能体套接字的情况下输出 17 个工具 Schema，`--auto-mint-admin` 则通过 `koma-admin.sock` 签发本地开发令牌。

## 全局空间概览（`koma-overview`）

![koma-overview 空间工作区概览界面](https://cdn.komawm.org/media/koma-overview.webp)

通过 `Mod + Tab`（或自定义绑定 `koma.act.overview.toggle()`）呼出 `koma-overview`：

- 通过 `zwlr_layer_shell_v1` 挂载在当前活跃显示器上，并从 `koma-admin.sock` 读取 `scene.inventory`。
- 将有头桌面工作区与 `agent:work` 无头工作区（含 Deck 焦点窗与 Stash 数量）同屏平铺展示，空闲时不触发多余 GPU 重绘。
