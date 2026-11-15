# Lua サンドボックス・レイアウト・外観

Koma は純 Rust 製のスタックレス Lua 5.4 ランタイム [Phodopus](https://github.com/Xuepoo/phodopus)（`koma-lua`）上で `~/.config/koma/init.lua` を評価します。

![Koma 水平スクロールレイアウトのプレビュー](/placeholders/koma-scrolling.webp "連続水平スクロールレイアウトとフォーカス列のプレビュー。")

## Phodopus サンドボックスとアトミックリロード

- **決定論的リソース上限**：スクリプト評価とコールバックは単調増加する命令燃料（Instruction Fuel）とヒープ上限（既定 `DEFAULT_HEAP_LIMIT_BYTES = 4 MiB`）で保護され、`io` / `os` / `debug` / `package` は除去されているため設定ループでコンポジタが停止しません。
- **シャドウレジストリによるアトミック切替**：`komactl reload`・ファイル監視・`Mod + Shift + R` によるリロード時は、まず新しいシャドウ環境で全ルールと正規表現を検証し、成功した場合のみ実稼働状態へ切り替えます。
- **事前検証**：`komactl validate` でモニター・ワークスペース・バインド・ジェスチャ・ルールの解析結果をオフライン確認できます。

## レイアウトエンジン（`koma.layout`, `koma.workspace`, `koma.dwindle`, `koma.scrolling`）

有画面ワークスペースの既定は `"dwindle"` です。全体またはワークスペース単位で `"dwindle"` / `"scrolling"` / `"deck"` / `"bsp"` を選択できます。

```lua
koma.layout("dwindle") -- "dwindle" | "scrolling" | "deck" | "bsp"

koma.dwindle({
    force_split = 0,         -- 0 = 自動, 1 = 左/上, 2 = 右/下
    preserve_split = true,
    smart_split = true,
    default_split_ratio = 1.0,
    inner_gap = 6,
    outer_gap = 10,
})

koma.scrolling({
    preset_column_widths = { 0.3333, 0.5, 0.6667 },
    default_column_width = { proportion = 0.5 },
    default_column_display = "normal", -- "normal" | "tabbed"
    center_focused_column = "never",   -- "never" | "always" | "on_overflow"
    camera_damping_ratio = 1.0,
    camera_stiffness = 550.0,
    inner_gap = 8,
    outer_gap = 12,
    edge_auto_scroll = { enabled = true, trigger_width = 48, delay_ms = 120, max_speed = 900 },
})

koma.workspace({ name = "1", layout = "dwindle", gaps_in = 6, gaps_out = 10 })
koma.workspace({ name = "2", layout = "scrolling" })
koma.workspace({ name = "agent:work", presentation = "headless", layout = "deck" })
```

## 外観とスプリングアニメーション（`koma.appearance`）

`koma.appearance({...})` はすべて型付きデフォルト値を持ち、必要な項目だけ上書きできます。

```lua
koma.appearance({
    corner_radius = 10,
    border = {
        enabled = true,
        width = 2.0,
        active_color = "#7aa2f7",
        inactive_color = "#3b4261",
        agent_leased_color = "#9ece6a",  -- エージェントが Epoch リース保持中の枠色
        human_preempt_color = "#f7768e", -- Mod + G 人間プリエンプション時の枠色
    },
    focus_ring = { enabled = false, width = 2.0, active_color = "#7dcfff", inactive_color = "#24283b" },
    shadow = {
        enabled = true,
        range = 18,
        render_power = 3,
        sharp = false,
        color = "#00000073",
        inactive_color = "#00000040",
        offset_x = 0.0,
        offset_y = 4.0,
        scale = 1.0,
    },
    dim = { dim_inactive = false, dim_strength = 0.15, brightness = 1.0, contrast = 1.0 },
    blur = {
        enabled = true,
        size = 6,
        passes = 2,
        noise = 0.015,
        contrast = 1.0,
        brightness = 1.0,
        vibrancy = 0.18,
        xray = false,
        ignore_opacity = false,
    },
    animations = {
        enabled = true,
        damping_ratio = 0.9,
        stiffness = 420.0,
        epsilon = 0.5,
        open_scale_from = 0.92,
        close_scale_to = 0.92,
    },
})
```

## 増分キー上書き・アンバインド・モード

既定では `inherit_default_binds = true` により組み込みキーマップが継承され、`koma.bind(...)` で個別上書き、`koma.unbind(chord)` で不要バインドを解除できます。

```lua
koma.unbind("Mod + Return")
koma.bind("Mod + Return", koma.act.spawn({ "foot" }), { desc = "Launch foot" })
koma.bind("Mod + O", koma.act.overview.toggle(), { desc = "Toggle koma-overview" })
```

| 補助 API | 用途 |
| :--- | :--- |
| `koma.env(key, val)` | Koma から起動する子プロセスへ環境変数を渡す |
| `koma.mode(name, spec)` | `koma.act.mode` で切り替えるサブマップモードを定義 |
| `koma.on(event, fn)` | 燃料計測付き Lua コールバックをイベントへ登録 |
| `koma.macro.define(spec)` | トークン消費ゼロのパラメータ化 GUI マクロを定義し `koma-mcp` へ公開 |
