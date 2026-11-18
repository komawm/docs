# レイアウト・外観・init.lua

Koma は `~/.config/koma/init.lua`（または `$XDG_CONFIG_HOME/koma/init.lua`、フォールバックは `/etc/xdg/koma/init.lua`）から設定を読み込みます。環境変数 `KOMA_CONFIG` または `koma -c <path>` で設定ファイルを切り替えられるほか、`~/.config/koma/lua/` 配下に分割したモジュールを `require(...)` で読み込めます。`komactl init` を実行すると、このモジュール構成の雛形を生成できます（詳細は [komactl とワークスペース概観](/ja/docs/protocols-and-tools/cli-and-overview/)）。

![Koma 横スクロールレイアウトと Lua 設定のプレビュー](https://cdn.komawm.org/media/koma-scrolling.webp "Scrolling レイアウトのマルチカラム表示とステータスバーの例。")

## 検証と安全なリロード

- **サンドボックス評価**：Lua 5.4 の評価環境はヒープ上限 `4 MiB` と命令数上限で制限されており、`io`・`os`・`debug`・`package` の各 OS ライブラリは無効化されているため、設定内の無限ループ等でコンポジタが停止することはありません。
- **事前検証**：`~/.config/koma/init.lua` を編集したら、リロード前に `komactl validate` で構文・正規表現・ジェスチャをオフライン確認できます。
  ```bash
  komactl validate ~/.config/koma/init.lua
  ```
- **安全なリロード**：`init.lua` の保存（自動監視）、`komactl reload`、または `Mod + Shift + R` で設定を再読み込みします。新しい設定は独立環境で評価され、エラーがある場合は稼働中のウィンドウやキーバインドを維持したまま失敗します。現在の状態と最後のエラーは `komactl config-status` で確認できます。

## レイアウトとワークスペース（`koma.layout`, `koma.dwindle`, `koma.scrolling`, `koma.workspace`）

画面付きワークスペースの既定レイアウトは `"dwindle"` です。`~/.config/koma/init.lua` では全体またはワークスペース単位で `"dwindle"`・`"scrolling"`・`"deck"`（アクティブウィンドウ全画面 + バックグラウンドスタッシュ）・`"bsp"` を指定できます。

```lua
koma.layout("dwindle") -- "dwindle" | "scrolling" | "deck" | "bsp"

koma.dwindle({
    force_split = 0,         -- 0 = 縦横比で自動分割, 1 = 左/上, 2 = 右/下
    preserve_split = false,
    smart_split = false,
    default_split_ratio = 1.0,
    inner_gap = 6,
    outer_gap = 10,
})

koma.scrolling({
    preset_column_widths = { 1 / 3, 0.5, 2 / 3 },
    default_column_width = { proportion = 0.5 },
    default_column_display = "normal", -- "normal" | "tabbed"
    center_focused_column = "never",   -- "never" | "always" | "on_overflow"
    camera_damping_ratio = 1.0,
    camera_stiffness = 800.0,
    inner_gap = 8,
    outer_gap = 10,
    edge_auto_scroll = { enabled = true, trigger_width = 30, delay_ms = 100, max_speed = 1500 },
})

koma.workspace({ name = "1", layout = "dwindle", gaps = { inner = 6, outer = 10 } })
koma.workspace({ name = "2", layout = "scrolling" })
koma.workspace({ name = "agent:work", presentation = "headless", layout = "deck" })
```

`koma.workspace({...})` では `preferred_output`（`"eDP-1"` 等のコネクタ名）や整数指定の `gaps_in` / `gaps_out` も使用できます。

## 外観（`koma.appearance`）

`koma.appearance({...})` の各項目には既定値が設定されているため、変更したい設定だけ記述できます。

```lua
koma.appearance({
    corner_radius = 10,
    border = {
        enabled = true,
        width = 2.0,
        active_color = "#58a6ff",
        inactive_color = "#30363d",
        agent_leased_color = "#d2a8ff",  -- エージェントの Epoch リース保持中の枠線色
        human_preempt_color = "#f0883e", -- Mod + G 人間接収時の枠線色
    },
    focus_ring = { enabled = false, width = 2.0, active_color = "#58a6ff", inactive_color = "#30363d" },
    shadow = {
        enabled = true,
        range = 16,
        render_power = 3,
        sharp = false,
        color = "#00000073",
        offset_x = 0.0,
        offset_y = 4.0,
        scale = 1.0,
    },
    dim = { dim_inactive = false, dim_strength = 0.15, brightness = 1.0, contrast = 1.0 },
    blur = {
        enabled = true,
        size = 6,
        passes = 3,
        noise = 0.0117,
        contrast = 0.8916,
        brightness = 0.8172,
        vibrancy = 0.1696,
        xray = true,
        ignore_opacity = false,
    },
    animations = {
        enabled = true,
        damping_ratio = 1.0,
        stiffness = 800.0,
        epsilon = 0.0005,
        open_scale_from = 0.88,
        close_scale_to = 0.92,
    },
})
```

グラデーション枠線・カスタムカーブ・チャネル別スタイルについては [アニメーション・枠線・ブラー](/ja/docs/configuration/animations-and-rice/)、LuaLS の型補完については [エディタ補完 (koma-types)](/ja/docs/configuration/lua-types/) を参照してください。

## キーバインド・モード・補助 API

既定では `inherit_default_binds = true` により組み込みキーマップが読み込まれます。`koma.bind(...)` で特定のキーを上書きし、`koma.unbind(chord)` で不要な既定バインドを解除できます。

```lua
koma.unbind("Mod + Return")
koma.bind("Mod + Return", koma.act.spawn({ "foot" }), { desc = "Launch foot" })
koma.bind("Mod + O", koma.act.overview.toggle(), { desc = "Toggle koma-overview" })
koma.bind("Mod + Shift + E", koma.act.quit(), { desc = "Exit Koma" })
```

組み込みの既定バインドも同じアクション体系で表現されており、`koma.act.reload_config()`、`koma.act.quit()`、`koma.act.window.maximize_toggle()` を利用できます。

| 補助 API | 用途 |
| :--- | :--- |
| `koma.env(key, val)` | Koma から起動する子プロセスへ環境変数を渡す |
| `koma.mode(name, spec)` | `koma.act.mode.enter(name)` / `koma.act.mode.exit()` で切り替えるサブマップモードを定義 |
| `koma.on(event, fn)` | ライフサイクルイベントの Lua コールバックを登録 |
| `koma.macro.define(spec)` | パラメータ化マクロを定義し `koma mcp` に公開 |

### キーバインド一覧オーバーレイ

`Mod + Shift + Slash` は `koma.act.overlay.keybinds_toggle()` を実行します。一覧は Koma 自身が描画するため、ランチャーを入れていない素のセッションでも動作します。`Escape`、同じキー、またはクリックで閉じます。開いている間はキーボードとポインタボタンをこのオーバーレイが占有し、ロック中・放棄済みのセッションでは開きません（設定リロードでも閉じます）。

パネルはカタログのカテゴリごとにまとまり、実効キーマップを表示します。`koma.bind` で上書きしたキーや `koma.unbind` で削除した既定はすでに反映されています。行は `komactl keys` と同じマージ結果から生成されるため、オーバーレイと CLI が食い違うことはありません。各行のソース（`builtin` または `config:<file>`）と Lua 式は CLI 側で確認できます。狭い出力ではパネルが複数列に折り返し、最後の列はバインドを黙って落とす代わりに正確な `+N more` を表示します。

### 長押しリピート

移動・リサイズ・プリセット・巡回系のアクションは、キーを押し続ける間、テキスト入力のリピートと同じ `repeat_delay` / `repeat_rate`（既定は `600` ms 後、`25` Hz）で繰り返します。分類はキーの組み合わせではなくアクションから決まります。方向フォーカス、ウィンドウの移動・入れ替え、方向リサイズ、Dwindle 分割比のドラッグ、スクロール列・プリセットの巡回、ワークスペースの前後移動、Deck 巡回、モニターのフォーカス・移動・入れ替えがリピート対象です。起動、クローズ、終了、リロード、スクラッチパッド、取り込み・切り離し、各種トグルは 1 回だけ実行されます。

バインド単位で分類を上書きできます：

```lua
koma.bind("Mod + D", koma.act.focus.left())                                  -- リピートする（方向フォーカス）
koma.bind("Mod + D", koma.act.window.close(), { repeat_while_held = false }) -- リピートしない
```

`repeat` は Lua の予約語なので、素の指定は `repeat_while_held` です。`["repeat"] = false` も使用でき、JSON/IPC ではこちらがフィールド名になります。明示値はアクションの分類より優先されます。保留中のリピートは、キーを離す、修飾キーを変える、ポインタ操作によるフォーカス変更、外部からのワークスペース切り替え、コンポジタの移動・リサイズや枠線ドラッグ、クライアントのドラッグ、セッションロック、設定リロードで取り消されます。

`pass_through` バインドはコンポジタ側ではリピートしません。フォーカス中のクライアントが同じ `wl_keyboard.repeat_info` に従って転送キーをリピートするため、押し続けたキーを実行するレイヤーは常に 1 つだけです。`komactl keys` はリピートする行に `[repeat]` を付け、`komactl keys --json` は `"repeat": bool` を含みます。

## 環境変数（`koma.env`）

`koma.env(key, val)` は、Koma が**起動するすべての子プロセス**に適用する変数を登録します。対象はキーバインドの `spawn`/`exec` アクション、イベントハンドラ内の `ctx:spawn(...)`、マクロ実行です。コンポジタ自身の環境はプロセス起動時に確定するため変更できません。

```lua
koma.env("QT_QPA_PLATFORM", "wayland;xcb")
koma.env("GDK_BACKEND", "wayland")
koma.env("NIXOS_OZONE_WL", "1")
```

| 対象 | `koma.env` の適用 | 補足 |
| :--- | :--- | :--- |
| キーバインド、`ctx:spawn`、マクロから起動したプログラム | あり | `WAYLAND_DISPLAY`・`DISPLAY`・`KOMA_INSTANCE_SIGNATURE` と `--session` 時の `XDG_*` 既定値の上に重ねて適用されます |
| Koma 自身（カーソルのテーマとサイズ、GPU/EGL バックエンド） | なし | 起動時に Koma 自身の環境から読み取ります。Koma を起動する前に設定してください |
| systemd ユーザーユニット、D-Bus アクティベーション、別 TTY から起動したクライアント | なし | これらのプロセスは Koma の子プロセス環境を継承しません |
| `xwayland-satellite` | なし | コンポジタのソケット／ディスプレイ変数のみを受け取ります |

セッション全体に届ける必要がある変数——Koma 自身のカーソルが使う `XCURSOR_SIZE`・`XCURSOR_THEME`、および systemd や D-Bus 経由で起動するアプリ——は `~/.config/environment.d/*.conf` に置いてください。`koma-session` ラッパーはログインシェル経由で再実行し、その環境を `systemd --user` と D-Bus アクティベーション環境に取り込んでから `koma.service` を起動します。

```ini
# ~/.config/environment.d/90-koma.conf
XCURSOR_SIZE=24
XCURSOR_THEME=Adwaita
```

`--session` モードでは `XDG_SESSION_TYPE=wayland` と `XDG_CURRENT_DESKTOP=koma` が既に子プロセスへ渡されるため、記述する必要はありません。

## 動的スナップショットとイベントフック（`MacroContext`, `koma.on`）

キーバインドのコールバックや `koma.on` リスナーには、読み取り専用のスナップショット `ctx`（`MacroContext`）が渡されます。保護対象ウィンドウは `app_id` と `title` の両方が `"[protected]"` にマスクされ、ヘッドレスワークスペースのウィンドウは通常クエリから分離されます。

- `ctx:focused_window()` — フォーカス中のウィンドウ情報（`id`, `app_id`, `title`, `workspace`, `floating`, `fullscreen`, `focused`）または `nil` を返します。
- `ctx:windows()` / `ctx:outputs()` / `ctx:workspaces()` — 表示対象ウィンドウ・出力・ワークスペースの一覧を返します。
- `ctx:dispatch(action)` — コンパイル済み `koma.act.*` アクション（`koma.act.window.focus(win_id)` や `koma.act.workspace.set_layout(mode, workspace?)` 等）をキューへ投入します（`dispatch` 内のネストした Lua コールバックは拒否されます）。

`koma.on(event_name, function(ctx, event) ... end)` で利用できるイベント（再帰深度上限 `4`）は `"compositor.start"`・`"config.reloaded"`・`"window.mapped"`・`"window.closed"`・`"window.focused"`・`"workspace.focused"`・`"output.changed"` です。

```lua
-- Run-or-Raise：既存の foot をフォーカス、無ければ起動
koma.bind("Mod + Shift + T", function(ctx)
    for _, win in ipairs(ctx:windows()) do
        if win.app_id == "foot" then
            ctx:dispatch(koma.act.window.focus(win.id))
            return
        end
    end
    ctx:dispatch(koma.act.spawn({ "foot" }))
end, { desc = "Focus foot or launch it" })

-- ウルトラワイド出力の検出時に scrolling レイアウトへ自動切替
koma.on("output.changed", function(ctx, ev)
    if ev.width and ev.width >= 3440 then
        ctx:dispatch(koma.act.workspace.set_layout("scrolling"))
    end
end)
```
