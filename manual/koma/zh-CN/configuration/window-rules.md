# 窗口规则与受保护表面

Koma 在 `~/.config/koma/init.lua` 中使用 `koma.rule.window({...})` 匹配 Wayland / XWayland 应用窗口，使用 `koma.rule.layer({...})` 匹配 `wlr-layer-shell` 面板与通知表面。规则按声明顺序求值（后匹配的同名属性覆盖前者），每条规则都会返回一个支持 `:set_enabled(bool)` 和 `:remove()` 的 `KomaHandle`。`app_id`、`title` 与 `namespace` 正则会在加载配置时预校验，避免错误规则影响当前会话。

## 窗口规则（`koma.rule.window`）

| 字段 | 生效阶段 | 说明 |
| :--- | :--- | :--- |
| `matches` / `excludes` | 匹配 / 排除列表 | 支持 `app_id`、`title`、`workspace`、`is_floating`、`is_focused`、`is_modal_dialog`、`is_xwayland`、`is_screencast_target`、`is_agent_workspace`、`at_startup`（`tag` / `is_urgent` 为保留字段，加载时会显式拒绝） |
| `initial` | 仅首次打开 | `open_on_output`、`open_on_workspace`、`open_mode`（`"tile"` \| `"float"` \| `"fullscreen"` \| `"maximized"` \| `"deck_top"` \| `"stash_background"`）、`open_focused`、`default_width` / `default_height`（别名 `width` / `height`）、`min_width` / `min_height`、`max_width` / `max_height`、`default_floating_pos = { x, y, anchor }` |
| `opacity` | 运行时表面 | 窗口透明度覆盖（`0.0..=1.0`） |
| `inactive_opacity` | 运行时表面 | 非聚焦状态透明度乘数（`0.0..=1.0`） |
| `corner_radius` | 运行时表面 | 单窗口圆角半径（逻辑像素） |
| `clip_to_geometry` | 运行时表面 | 按布局几何边界裁剪客户端纹理 |
| `animation` | 运行时表面 | 单窗口开关动画预设（如 `"popin 88%"`、`"slide:top"`、`"instant"`） |
| `immediate` | 打开 / 关闭 | 设为 `true` 时跳过该窗口的打开与关闭动画 |
| `no_blur` / `no_shadow` | 运行时表面 | 禁用该窗口的背景模糊或阴影 |
| `border_color` | 运行时表面 | 覆盖该窗口的聚焦边框色（`"#rrggbb"` / `"#rrggbbaa"`） |
| `focusable` | 运行时输入 | 允许或禁止获取键盘焦点 |
| `pin_on_output` | 运行时表面 | 在同一输出屏幕切换工作区时保持浮动窗口置顶可见 |
| `suppress_events` | 运行时表面 | 忽略客户端请求（例如 `{ "maximize" }`） |
| `block_out_from` | 隐私 / 截屏隔离 | `"agent_capture"` \| `"screencast"` \| `"screencopy"` \| `"all"` |

`default_floating_pos.anchor` 支持 `"top-left"`、`"top"`、`"top-right"`、`"left"`、`"center"`、`"right"`、`"bottom-left"`、`"bottom"` 与 `"bottom-right"`。窗口对应的边缘或中心会对齐到工作区内的目标锚点 `(anchor_origin + (x, y))`。

- **启动尺寸与按比例浮动**：`default_width`、`default_height`（别名 `width`、`height`）、`min_*` 与 `max_*` 均支持逻辑像素数（`> 1` 或 `{ fixed = px }`）以及工作区比例（`0.0..=1.0` 或 `{ proportion = p }`，钳位至 `0.1..=1.0`）；在 `scrolling` 工作区中 `default_width` 同时决定初始列宽。当 `open_mode = "float"` 且未同时固定宽高时，Koma 会在首次 configure 时保持尺寸无约束（`size = nil`）让客户端按自身比例提交尺寸；若窗口超出工作区或仅指定单轴尺寸，则会整体等比缩小以保留原始宽高比。
- **全屏、最大化与悬浮窗口层级**：`initial.open_mode = "fullscreen"` 覆盖包含间隙的整个显示器（激活期间抑制 `Top`/`Overlay` 表面，且不再拦截该屏幕指针点击），`"maximized"` 则填充排除区域之外再减去间隙的工作区，因此面板保持可见。两者互斥；且浮动窗口在 **全屏与最大化** 窗口之上均保持可见并可正常交互，平铺兄弟窗口则隐藏在底层。

### 常用配置示例（`~/.config/koma/init.lua`）

```lua
-- 密码管理器默认居中浮动，并从所有截屏与录屏通道屏蔽
local vault_rule = koma.rule.window({
    name = "vault-redaction",
    matches = {
        { app_id = "^org\\.keepassxc\\.KeePassXC$" },
        { app_id = "^Bitwarden$" },
        { title = ".*(1Password|Private Browsing).*" },
    },
    initial = {
        open_mode = "float",
        default_floating_pos = { x = 0, y = 0, anchor = "center" },
    },
    block_out_from = "all",
})

-- 将浏览器画中画窗口固定在右下角并跨工作区悬浮
koma.rule.window({
    name = "browser-pip",
    matches = { { app_id = "^(firefox|chromium)$", title = "^Picture-in-Picture$" } },
    initial = {
        open_mode = "float",
        open_focused = false,
        default_floating_pos = { x = 24, y = 24, anchor = "bottom-right" },
    },
    pin_on_output = true,
    opacity = 0.96,
})

-- 文件管理器与文件选择器以固定尺寸居中浮动启动（无需手写外置脚本）
koma.rule.window({
    name = "file-managers-floating",
    matches = {
        { app_id = "^(org\\.gnome\\.Nautilus|thunar|Thunar|org\\.kde\\.dolphin|nemo|xdg-desktop-portal-gtk)$" },
    },
    initial = {
        open_mode = "float",
        default_width = 1100,
        default_height = 720,
        default_floating_pos = { x = 0, y = 0, anchor = "center" },
    },
})

-- 截图查看/标注（satty）：保留截图原始宽高比居中浮动，超屏时等比缩小
koma.rule.window({
    name = "satty-natural-aspect",
    matches = { { app_id = "^com\\.gabm\\.satty$" } },
    initial = {
        open_mode = "float",
        default_floating_pos = { x = 0, y = 0, anchor = "center" },
    },
})

-- 为对延迟敏感的游戏或工具关闭开关动画
koma.rule.window({
    name = "instant-game-window",
    matches = { { app_id = "^osu!$" } },
    immediate = true,
    no_blur = true,
    no_shadow = true,
})

-- 启动时自动将聊天软件分配到 3 号工作区且不抢占焦点
koma.rule.window({
    name = "chat-workspace",
    matches = { { app_id = "^(org\\.telegram\\.desktop|discord)$", at_startup = true } },
    initial = {
        open_on_workspace = "3",
        open_focused = false,
    },
})

-- 通过快捷键重新启用规则
koma.bind("Mod + Shift + B", function()
    vault_rule:set_enabled(true)
end, { desc = "确保敏感窗口黑屏遮罩规则生效" })
```

## Layer-Shell 规则（`koma.rule.layer`）

通过 `namespace`、`layer`（`"background"`、`"bottom"`、`"top"`、`"overlay"`）与 `at_startup` 匹配状态栏、通知弹窗、壁纸和启动器表面：

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

## 受保护表面（`4032 ERR_PROTECTED_SURFACE`）

> [!IMPORTANT]
> 锁屏表面（`ext-session-lock-v1`）、权限认证框（`polkit-gnome-authentication-agent`、`hyprpolkitagent`、`pinentry`）以及常见密码管理器（`KeePassXC`、`Bitwarden`、`1Password`）默认自动受保护；其他窗口可通过 `block_out_from` 加入保护。

- **截屏涂黑**：命中 `block_out_from = "agent_capture"` 或 `"all"` 的窗口与 Layer 表面在导出离屏帧（`capture.frame`）时会被直接涂黑为 `#000000`，即使被其他窗口遮挡或重叠也同样生效。
- **输入拦截（`4032`）**：任何落入受保护表面区域的虚拟座席（`vseat.*`）点击、拖拽、按键或文本注入都会被拒绝并返回 `4032 ERR_PROTECTED_SURFACE`。`koma mcp` 与 [Jiku](/zh-CN/jiku/) 都无法查看或操作受保护表面。
- **截图与录屏隔离**：`"screencopy"` 与 `"all"` 会在 `zwlr_screencopy_manager_v1`（`grim`）抓屏中涂黑；`"screencast"` 会在 Portal PipeWire 录屏流中涂黑。

## 兼容说明

- **Waydroid（`Waydroid`、`waydroid.<package>`）**：除非被用户 `koma.rule.window` 规则显式覆盖，否则默认应用 `no_blur = true`；当容器表面提交空的 `wl_surface.set_input_region` 时，自动按可穿透表面处理并抑制边框、焦点环、阴影、模糊及 `clip_to_geometry` 裁剪，确保多窗口应用正常响应。
- **远程桌面客户端**：聚焦时支持 `zwlr_virtual_pointer_manager_v1` 虚拟指针与 `zwp_keyboard_shortcuts_inhibit_manager_v1` 快捷键透传，同时始终保留 `Mod + G` 人类接管热键与 TTY/VT 切换快捷键。
- **状态栏与桌面组件（`waybar`、`ironbar`、`quickshell`）**：支持 `get_popup` 弹窗边界放开与抓取、`wp_single_pixel_buffer_v1`、`wp_presentation` 反馈及 `wl_shm` `Abgr8888`/`Xbgr8888` 像素格式。
