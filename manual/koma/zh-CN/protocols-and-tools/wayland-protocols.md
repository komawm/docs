# 状态栏、Portal、输入法与应用兼容

Koma 实现了桌面面板、锁屏、Portal、远程桌面与输入法所需的核心 Wayland 协议，并将 `wp_security_context_manager_v1` 与 `komactl sandbox` 的连接标记为受限，禁止沙箱客户端绑定特权全局对象。

## 窗口、面板与输出管理协议

| 协议 / 全局对象 | 用途与生态工具 | 安全与沙箱隔离规则 |
| :--- | :--- | :--- |
| `xdg_shell`（`xdg_wm_base`） | 桌面应用窗口、弹窗、全屏及 SSD 服务端装饰协商（`zxdg_decoration_manager_v1`） | 沙箱客户端严格限制在指定 `Headless` 工作区内 |
| `zwlr_layer_shell_v1` | 状态栏与面板小组件（`waybar`、`ironbar`、`quickshell`）、通知（`swaync`）、启动器（`fuzzel`/`rofi`）、`koma-overview` | 支持互斥区、`get_popup` -> `xdg_popup` 弹窗边界放开与键鼠抓取；对沙箱客户端隐藏 |
| `ext_session_lock_v1` | 故障闭锁（Fail-closed）锁屏（`swaylock`、`hyprlock`） | 锁屏期间遮蔽画面、拒绝 `grim` 截屏（`failed`）、延迟 `xdg-activation` |
| `zwlr_output_manager_v1` | 多显示器动态探测、`test` 与 `apply`（`kanshi`、`wdisplays`） | 禁止沙箱/受限客户端绑定 |
| `zwlr_output_power_manager_v1` 与 `zwlr_gamma_control_manager_v1` | DPMS 息屏唤醒（`wlopm`）与夜览色温调节（`wlsunset`、`gammastep`） | 对受限客户端屏蔽 |
| `wp_fractional_scale_manager_v1` 与 `wp_viewporter` | 原生锐利分数 HiDPI 缩放（`1.25`、`1.5`、`1.6`、`"auto"`） | 按显示器独立下发 |
| `wp_single_pixel_buffer_v1`、`wp_presentation` 与 `wl_shm` 格式 | 纯色小组件（`ironbar`/`quickshell`）、呈现时间反馈与 `Abgr8888`/`Xbgr8888` 缓冲格式（`Waydroid`） | 向图形客户端开放 |
| `xdg_activation_v1` 与 `xdg_toplevel_icon_v1` | 跨应用焦点激活令牌（`10 s` TTL）与窗口图标校验 | 校验沙箱归属并在锁屏期间自动推迟 |
| `zwlr_foreign_toplevel_manager_v1` 与 `ext_foreign_toplevel_list_v1` | 任务栏窗口列表、激活、最小化与关闭控制 | 禁止沙箱绑定且在锁屏下自动保护 |
| `zwlr_virtual_pointer_manager_v1` 与 `zwp_keyboard_shortcuts_inhibit_manager_v1` | 远程桌面虚拟指针与快捷键抑制传递（`RustDesk`） | 禁止沙箱客户端绑定；始终保留 `Mod + G` 抢占与 VT 切换不进入抑制 |

## 工作区模型（`ext-workspace-v1`）与 Waybar

Koma 将 [`ext-workspace-v1`](https://wayland.app/protocols/ext-workspace-v1)（staging）以 `ext_workspace_manager_v1` 的形式向不受限客户端公开，状态栏因此无需轮询运行时文件即可列出、跟踪并切换工作区。被沙箱标记的客户端以及经 `wp_security_context_manager_v1` 接入的客户端，与 `zwlr_layer_shell_v1` 一样无法绑定该全局对象。

| 状态栏收到的信息 | Koma 的取值 |
| :--- | :--- |
| 分组 | 仅有 1 个 `ext_workspace_group_handle_v1`，通过 `output_enter` / `output_leave` 持有全部输出 |
| 工作区 | 每个工作区对应 1 个 `ext_workspace_handle_v1`（包含 `special:` 浮层） |
| `id` | Koma 工作区 ID（`ws_01`）：稳定的门牌 ID，而非条带序号 |
| `name` | 你配置的工作区名（`1`、`chat`、`special:magic`） |
| `coordinates` | 条带顺序中唯一的 1 维索引：数字名先按数值排序，其后是命名工作区 |
| `capabilities` | 仅 `activate` |
| `state` | 工作区处于显示状态（已分配到输出、正在打开的 `special:` 浮层，或为 `active_ws_id`）时为 `active`；没有窗口或属于无头／`agent:` 工作区时为 `hidden`；已被占用但未显示时不带任何状态位 |

属性事件仅发送增量，每个批次以 `done` 结束，因此请缓存已收到的值，不要凭单个事件重建状态。`workspace.activate` 是一个请求：该 manager 发送 `commit` 时才生效。一次 `commit` 之前的多次 activate 会作为一个批次应用，只有最后一个请求生效，因此中间工作区不会闪现，也不会触发 `workspace.focused`。切换本身走与 `Mod + 1..0` 相同的路径；manager 发送 `stop` 或断开连接时，挂起的请求会被丢弃。锁屏期间的 `commit` 会被忽略。

### 状态栏中的工作区可见性

协议本身没有“已占用”状态，因此由 Koma 自行推导可见性：工作区处于显示状态时为 `active`；没有窗口（或属于无头／`agent:` 工作区）时为 `hidden`；已被占用但未显示时**不带**任何状态位。所谓占用，指至少有一个未最小化的已映射窗口；置于暂存区或 Deck 背景的窗口也算，因为隐藏其工作区会连带删除唯一能把窗口取回的栏项，而已最小化的窗口不计入。

这一默认值是为了减少状态栏噪音：配置 `ignore-hidden: true` 的状态栏只列出正在使用的工作区，而不是十个空槽位。空工作区仍可通过 `Mod + 1..9` 切换，只是不占用状态栏槽位。协议将 `hidden` 定义为“该工作区在工作区分组中不可见，尝试可视化合成器工作区状态的客户端不应显示这类工作区”，Koma 正是按这一含义设置。

如需保留一个空工作区在列表中，可按工作区单独退出该行为：

```lua
koma.workspace({ name = "5", persistent = true })
```

`persistent = true` 在创建时与重载配置时都会应用；处于显示状态的工作区仍然优先为 `active`。

### Waybar 的 `ext/workspaces`

```jsonc
// ~/.config/waybar/config.jsonc
"modules-center": ["ext/workspaces"],

"ext/workspaces": {
  "format": "{name} {icon}",
  "on-click": "activate",
  "ignore-hidden": true,
  "sort-by-name": true,
  "format-icons": {
    "active": "●",
    "default": "○"
  }
}
```

```css
/* ~/.config/waybar/style.css */
#workspaces button {
  padding: 0 6px;
  border-radius: 4px;
}
#workspaces button.active {
  background: #7aa2f7;
  color: #16161e;
}
#workspaces button.hidden {
  opacity: 0.55;
}
```

`ignore-hidden: true` 是安全且推荐的配置：Koma 严格按照协议定义设置 `hidden`，因此空工作区会从状态栏消失，仍有窗口的工作区则保持列出。若希望保留空工作区，请设置 `persistent = true`（见上文）。`icon` / `format-icons` 可用（该模块只匹配 `active` 与 `default` 键，工作区名键同样生效），但 `urgent` 永远不会触发：Koma 没有窗口紧急度概念，因此不存在紧急工作区。请保留 `"sort-by-name": true`；使用 `"sort-by-id": true` 会按门牌 ID（`ws_01`、`ws_02`…）排序，只有 ID 恰好与创建顺序一致时才看起来正确。配置 `"on-click-right": "close"` 或 `"deactivate"` 不会有任何效果——Koma 只公开 `activate`。

## 截屏与 `xdg-desktop-portal`

- **`zwlr_screencopy_manager_v1` (v3)**：支持 SHM 与 DMA-BUF 零拷贝截屏（兼容 `grim`、`wayshot`、`slurp`），每帧仅发出单个 `buffer`/`linux_dmabuf` 事件，并严格执行 `block_out_from = "screencopy"`/`"all"` 黑屏掩码及 `ext-session-lock-v1` 拒截保护。
- **原生 `xdg-desktop-portal-koma`（`org.freedesktop.impl.portal.desktop.koma`、`koma.portal`）**：实现 `ScreenCast`（PipeWire `pw_stream` + `zwlr_screencopy_manager_v1`）、`RemoteDesktop`（`zwlr_virtual_pointer_v1` + `zwp_virtual_keyboard_v1`）与 `Session` 接口，并随 `koma-portals.conf` 路由搭配 `xdg-desktop-portal-gtk`，为 Wayland 屏幕共享与远程桌面（`RustDesk`、浏览器、OBS）提供原生支持。

## 中文/日文输入法（IME）与虚拟输入栈

Koma 原生实现现代 Wayland CJK/IME 协议栈，无需依赖 X11 兼容层：

- **`zwp_text_input_manager_v3`**（`text-input-v3`）：服务 GTK4、Qt6、Chromium/Electron（`--enable-wayland-ime`）及原生 Wayland 终端。
- **`zwp_input_method_manager_v2`**（`input-method-v2`）与 **`zwp_virtual_keyboard_manager_v1`**：支持 **`Fcitx5`** 与 **`IBus`** 候选词浮窗及预编辑（preedit）输入。
- **`zwp_pointer_constraints_v1` 与 `zwp_relative_pointer_manager_v1`**：支持游戏与 3D 视口指针锁定/限制及相对位移（`ext-session-lock` 锁屏或失焦时自动解除）。
- **`wl_touch` 与 `wp_cursor_shape_manager_v1`**：多点触控表面路由与合成器端光标形状主题。

> [!TIP]
> **日常 IME 与自动化文本注入分离**：手动打字走 `Fcitx5` / `IBus`（`text-input-v3` + `input-method-v2`）；而通过 `koma-agent.sock` 注入文本时会直接经由按键映射、`text-input-v3` 或剪贴板粘贴（`Ctrl+Shift+V`）送入窗口，绝不会误弹出中文候选框。

## `wp_security_context_manager_v1` 与受限容器隔离

无论是 Wayland 原生 `wp_security_context_manager_v1`（用于 Flatpak / `bubblewrap`）还是 `komactl sandbox`，都会将客户端连接标记为受限状态。受限连接无法绑定特权全局对象（`zwlr_layer_shell_v1`、`zwlr_screencopy_manager_v1`、`zwlr_data_control_manager_v1`、`zwp_virtual_keyboard_manager_v1`、`ext_session_lock_manager_v1`、`zwlr_output_manager_v1` 或 `wp_security_context_manager_v1` 本身）。
