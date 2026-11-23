# ウィンドウルールと保護サーフェス

Koma は `~/.config/koma/init.lua` の `koma.rule.window({...})` で Wayland / XWayland ウィンドウを、`koma.rule.layer({...})` で `wlr-layer-shell` サーフェスを制御します。ルールは宣言順に評価され（後続の一致プロパティが上書き）、戻り値の `KomaHandle` で `:set_enabled(bool)` や `:remove()` を動的に呼び出せます。`app_id`・`title`・`namespace` の正規表現は設定読み込み時に検証されるため、不正なパターンで稼働中のウィンドウが壊れることはありません。

## ウィンドウルール（`koma.rule.window`）

| フィールド | 適用タイミング | 内容 |
| :--- | :--- | :--- |
| `matches` / `excludes` | 一致・除外条件 | `app_id`、`title`、`workspace`、`is_floating`、`is_focused`、`is_modal_dialog`、`is_xwayland`、`is_screencast_target`、`is_agent_workspace`、`at_startup`（`tag` / `is_urgent` は予約済みでロード時に拒否） |
| `initial` | 初回マッピングのみ | `open_on_output`、`open_on_workspace`、`open_mode`（`"tile"` \| `"float"` \| `"fullscreen"` \| `"maximized"` \| `"deck_top"` \| `"stash_background"`）、`open_focused`、`default_width` / `default_height`（別名 `width` / `height`）、`min_width` / `min_height`、`max_width` / `max_height`、`default_floating_pos = { x, y, anchor }` |
| `opacity` | ライブサーフェス | 透過率の上書き（`0.0..=1.0`） |
| `inactive_opacity` | ライブサーフェス | 非フォーカス時の透過率乗数（`0.0..=1.0`） |
| `corner_radius` | ライブサーフェス | ウィンドウ単位の角丸半径（論理ピクセル） |
| `clip_to_geometry` | ライブサーフェス | レイアウト境界でクライアント描画をクリップ |
| `animation` | ライブサーフェス | ウィンドウ単位の開閉アニメーション指定（例: `"popin 88%"`, `"slide:top"`, `"instant"`） |
| `immediate` | 開閉時 | `true` のとき開閉アニメーションをスキップ |
| `no_blur` / `no_shadow` | ライブサーフェス | 背景ブラーまたはドロップシャドウを無効化 |
| `border_color` | ライブサーフェス | アクティブボーダー色の上書き（`"#rrggbb"` / `"#rrggbbaa"`） |
| `focusable` | ライブ入力 | キーボードフォーカスの可否を制御 |
| `pin_on_output` | ライブサーフェス | 同一出力でのワークスペース切替時もフローティングウィンドウを維持 |
| `suppress_events` | ライブサーフェス | クライアントからの状態要求を無視（例: `{ "maximize" }`） |
| `block_out_from` | プライバシー保護 | `"agent_capture"` \| `"screencast"` \| `"screencopy"` \| `"all"` |

`default_floating_pos.anchor` には `"top-left"`, `"top"`, `"top-right"`, `"left"`, `"center"`, `"right"`, `"bottom-left"`, `"bottom"`, `"bottom-right"` を指定できます。ウィンドウの対応する辺または中心が、作業領域内のアンカー点 `(anchor_origin + (x, y))` に揃えられます。

- **起動サイズとアスペクト比維持フロート**：`default_width`・`default_height`（別名 `width`・`height`）・`min_*`・`max_*` は論理ピクセル数（`> 1` または `{ fixed = px }`）や作業領域の割合（`0.0..=1.0` または `{ proportion = p }`、`0.1..=1.0` にクランプ）を指定でき、`scrolling` では `default_width` が初期カラム幅にもなります。`open_mode = "float"` で幅・高さの両方を固定しない場合、初回 configure でサイズ未指定（`size = nil`）を送りクライアント自身の比率を受け取り、作業領域を超える場合や片軸のみ指定した場合はアスペクト比を保ったまま全体が比例縮小されます。
- **フルスクリーン・最大化とフロートの重なり順**：`initial.open_mode = "fullscreen"` はギャップを含むモニター全体を覆い（有効中は `Top`/`Overlay` サーフェスが抑止されポインタクリックも奪いません）、`"maximized"` は排他ゾーンとギャップを除いた作業領域を埋めるためパネルは表示されたままです。両者は相互排他で、フローティングウィンドウは **フルスクリーンおよび最大化** のどちらの上でも表示・操作可能なまま保たれ、他のタイルウィンドウは背後に隠れます。

### 設定例（`~/.config/koma/init.lua`）

```lua
-- パスワードマネージャを中央フロート配置し、あらゆるキャプチャから黒塗り遮蔽
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

-- ブラウザのピクチャ・イン・ピクチャを右下へ固定配置
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

-- ファイルマネージャとファイル選択ダイアログを固定サイズで中央フロート起動
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

-- スクリーンショット注釈 (satty)：画像のアスペクト比を維持したまま中央フロート起動
koma.rule.window({
    name = "satty-natural-aspect",
    matches = { { app_id = "^com\\.gabm\\.satty$" } },
    initial = {
        open_mode = "float",
        default_floating_pos = { x = 0, y = 0, anchor = "center" },
    },
})

-- 低遅延を優先するゲーム等で開閉アニメーションを無効化
koma.rule.window({
    name = "instant-game-window",
    matches = { { app_id = "^osu!$" } },
    immediate = true,
    no_blur = true,
    no_shadow = true,
})

-- 起動時のチャットアプリをワークスペース 3 へ自動配置（フォーカスを奪わない）
koma.rule.window({
    name = "chat-workspace",
    matches = { { app_id = "^(org\\.telegram\\.desktop|discord)$", at_startup = true } },
    initial = {
        open_on_workspace = "3",
        open_focused = false,
    },
})

-- キーバインドからルールを動的に有効化
koma.bind("Mod + Shift + B", function()
    vault_rule:set_enabled(true)
end, { desc = "機密ウィンドウ保護ルールを有効化" })
```

## Layer-Shell ルール（`koma.rule.layer`）

`namespace`、`layer`（`"background"`, `"bottom"`, `"top"`, `"overlay"`）、`at_startup` でパネル・通知・壁紙サーフェスを制御します。

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

## 保護サーフェス（`4032 ERR_PROTECTED_SURFACE`）

> [!IMPORTANT]
> セッションロック画面（`ext-session-lock-v1`）、認証ダイアログ（`polkit-gnome-authentication-agent`, `hyprpolkitagent`, `pinentry`）、主要パスワードマネージャ（`KeePassXC`, `Bitwarden`, `1Password`）は既定で保護対象となります。追加のウィンドウやレイヤーは `block_out_from` で指定できます。

- **キャプチャ遮蔽**：`block_out_from = "agent_capture"` または `"all"` に一致するサーフェスは、オフスクリーン `capture.frame` 出力前に `#000000` で塗り潰されます（他のウィンドウと重なっている場合も同様です）。
- **入力ブロック（`4032`）**：保護サーフェス領域への仮想シート（`vseat.*`）クリック・ドラッグ・キー・テキスト注入は `4032 ERR_PROTECTED_SURFACE` で拒否されます。`koma mcp` や [Jiku](/ja/jiku/) から保護対象を読み取ったり操作したりすることはできません。
- **スクリーンコピー／画面共有の分離**：`"screencopy"` と `"all"` は `zwlr_screencopy_manager_v1`（`grim`）から遮蔽し、`"screencast"` は Portal PipeWire ストリームで遮蔽します。

## 互換性に関する補足

- **Waydroid（`Waydroid`, `waydroid.<package>`）**：ユーザーの `koma.rule.window` で明示的に上書きしない限り既定で `no_blur = true` が適用されます。空の `wl_surface.set_input_region` を持つコンテナサーフェスはクリックスルーとして扱い、枠線・フォーカスリング・影・ブラーおよび `clip_to_geometry` を抑止してマルチウィンドウ動作を維持します。
- **リモートデスクトップクライアント**：フォーカス中は `zwlr_virtual_pointer_manager_v1` と `zwp_keyboard_shortcuts_inhibit_manager_v1` に対応しつつ、緊急復帰用の `Mod + G` と VT 切替ショートカットは常に有効なまま保ちます。
- **パネル・ウィジェット（`waybar`, `ironbar`, `quickshell`）**：`get_popup` の制約解除、単色バッファ（`wp_single_pixel_buffer_v1`）、`wp_presentation` フィードバック、`wl_shm` `Abgr8888`/`Xbgr8888` 形式に対応しています。
