# 窗口规则与受保护表面

Koma 通过 `koma.rule.window` 与 `koma.rule.layer` 为 Wayland/XWayland 应用窗口以及 `wlr-layer-shell` 面板提供声明式规则匹配。每条规则均返回支持 `:set_enabled(bool)` 与 `:remove()` 的 `KomaHandle`，且所有 `app_id` / `title` / `namespace` 正则均在影子沙箱阶段预编译校验，防止非法规则破坏线上状态。

## 窗口规则结构（`koma.rule.window`）

| 字段 | 生效阶段 | 说明 |
| :--- | :--- | :--- |
| `matches` / `excludes` | 匹配/排除数组 | 支持 `app_id`、`title`、`tag`、`workspace`、`is_floating`、`is_focused`、`is_urgent`、`is_modal_dialog`、`is_xwayland`、`is_screencast_target`、`is_agent_workspace`、`at_startup` |
| `initial` | 仅首次映射 | `open_on_output`、`open_on_workspace`、`open_mode`（`"tiled"` / `"floating"` / `"fullscreen"`）、`open_focused`、`default_floating_pos = { x, y, anchor }` |
| `opacity` | 运行时表面 | 窗口透明度覆盖（`0.0..=1.0`） |
| `inactive_opacity` | 运行时表面 | 非聚焦窗口透明度覆盖（`0.0..=1.0`） |
| `corner_radius` | 运行时表面 | 单独覆盖窗口圆角半径（逻辑像素） |
| `clip_to_geometry` | 运行时表面 | 按布局几何边界裁剪客户端纹理 |
| `animation` | 运行时表面 | 单窗口开关动画预设（如 `"popin 88%"`、`"slide:top"`） |
| `no_blur` / `no_shadow` | 运行时表面 | 禁用该窗口的 Dual Kawase 背景模糊或合成器阴影 |
| `border_color` | 运行时表面 | 单窗口聚焦边框色覆盖（`"#rrggbb"` / `"#rrggbbaa"`） |
| `focusable` | 运行时输入 | 允许或禁止获得键盘焦点 |
| `pin_on_output` | 运行时表面 | 在同一输出设备切换工作区时置顶固定浮动窗 |
| `block_out_from` | 隐私 / 截屏隔离 | `"agent_capture"` \| `"screencast"` \| `"screencopy"` \| `"all"` |

### 规则配置示例

```lua
-- 将密码管理器设为居中浮动，并屏蔽智能体截屏、录屏流与 grim 截图
local vault_rule = koma.rule.window({
    name = "vault-redaction",
    matches = {
        { app_id = "^org\\.keepassxc\\.KeePassXC$" },
        { app_id = "^Bitwarden$" },
        { title = ".*(1Password|Private Browsing).*" },
    },
    initial = {
        open_mode = "floating",
        default_floating_pos = { x = 0, y = 0, anchor = "center" },
    },
    block_out_from = "all", -- "agent_capture" | "screencast" | "screencopy" | "all"
})

-- 启动时自动将聊天软件分配到 3 号工作区且不抢焦点
koma.rule.window({
    name = "chat-workspace",
    matches = { { app_id = "^(org\\.telegram\\.desktop|discord)$", at_startup = true } },
    initial = {
        open_on_workspace = "3",
        open_focused = false,
    },
})

-- 在快捷键回调中动态确认规则启用状态
koma.bind("Mod + Shift + B", function()
    vault_rule:set_enabled(true)
end, { desc = "确保敏感窗口黑屏遮罩规则生效" })
```

## Layer-Shell 表面规则（`koma.rule.layer`）

通过 `namespace`、`layer`（`"background"` / `"bottom"` / `"top"` / `"overlay"`）与 `at_startup` 匹配状态栏、通知弹窗或启动器表面：

```lua
koma.rule.layer({
    name = "swaync-privacy",
    matches = { { namespace = "^swaync-notification-window$" } },
    corner_radius = 12,
    opacity = 0.96,
    place_within_backdrop = false,
    block_out_from = "screencast",
})
```

## 受保护表面黑屏遮罩（`4032 ERR_PROTECTED_SURFACE`）

> [!IMPORTANT]
> **合成器底层强制涂黑**：当窗口或 Layer 表面命中 `block_out_from = "agent_capture"` 或 `"all"` 时，`koma-render` 会在导出 `capture.frame`（`SCM_RIGHTS` `memfd`）图像之前直接将其像素涂黑为 `#000000`（`[PROTECTED]`）。

- **输入写隔离（`4032`）**：任何落入受保护窗口区域的 `vseat.*` 点击、拖拽、按键或文本注入都会在合成器门控阶段被直接拒绝并返回 `4032 ERR_PROTECTED_SURFACE`。
- **隐私零泄漏**：无论 `koma-mcp` 还是 [Jiku](/zh-CN/jiku/) 都无法读取标记为 `block_out_from` 的密码管理器、二次验证框或支付界面内容。
- **截图与录屏分离**：设置为 `"screencopy"` 或 `"all"` 时同时遮蔽 `zwlr_screencopy_manager_v1`（`grim`）抓屏；`"screencast"` 仅在 Portal 录屏流中涂黑。

## Waydroid、远程桌面（`RustDesk`）与面板小组件适配

- **Android / `Waydroid` 容器（`Waydroid`、`waydroid.<package>`）**：除非用户显式在 `koma.rule.window` 中覆盖，否则 Koma 自动为 Waydroid 窗口应用 `no_blur = true`；当检测到容器表面提交空的 `wl_surface.set_input_region` 时，自动将其视为可穿透表面（抑制边框、焦点环、阴影、模糊并放开 `clip_to_geometry` 裁剪），确保 `waydroid.*` 多窗口与子表面正常渲染与点击。
- **远程桌面（`RustDesk`）**：支持 `zwlr_virtual_pointer_manager_v1` 虚拟指针注入与聚焦下的 `zwp_keyboard_shortcuts_inhibit_manager_v1` 快捷键抑制，同时始终保留 `Mod + G` 人类紧急抢占与 VT 切换热键不进入抑制。
- **状态栏与桌面小组件（`waybar`、`ironbar`、`quickshell`）**：支持 `zwlr_layer_shell_v1` 的 `get_popup` 弹窗边界放开与键鼠抓取、`wp_single_pixel_buffer_v1`、`wp_presentation` 反馈及 `wl_shm` `Abgr8888`/`Xbgr8888` 像素格式。
