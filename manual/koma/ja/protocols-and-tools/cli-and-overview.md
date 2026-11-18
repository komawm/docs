# komactl とワークスペース概観

`komactl` は Koma の管理 CLI（`koma-admin.sock`）兼オフライン Lua バリデータであり、`koma-overview` は全ワークスペースを俯瞰する `wlr-layer-shell` 空間概観ツールです。

## `komactl` コマンドリファレンス

`komactl` は `$XDG_RUNTIME_DIR/koma/<signature>/koma-admin.sock` を自動検出します（`KOMA_INSTANCE_SIGNATURE` で明示指定も可能）。

| コマンド | 動作モード | 説明 |
| :--- | :--- | :--- |
| `komactl validate [path/to/init.lua]` | オフライン | 隔離された Lua サンドボックスで `init.lua` を評価し、ルール正規表現・ジェスチャ検証とリソース数を出力 |
| `komactl doctor [path/to/init.lua] [--json] [--strict]` | オフライン | 破壊的でない設定チェックを領域別に実行し、`ok` / `warn` / `error` / `skip` を報告。`error` は終了コードを変えない |
| `komactl keys [path/to/init.lua] [--json] [--grep <pattern>]` | オフライン（接続時は稼働状態を読み取り専用で併記） | 実効キーマップ（組み込みカタログと `init.lua` のマージ、ポインタバインド、ジェスチャ）を一覧。リピートする行には `[repeat]` |
| `komactl reload [path/to/init.lua]` | IPC（`admin.sock`） | `config.reload` を送信し、実行中コンポジタの設定をアトミックに切り替え |
| `komactl config-status` | IPC（`admin.sock`）+ オフライン | 有効な設定パス、リロード世代、直近のエラー（`config.status`）、実際に適用中の `input.keyboard` / `input.pointer` / `input.touchpad` 設定に加え、生成テンプレートの `template.{init_lua,present,installed_version,shipped_version,outdated,missing_files}` を表示 |
| `komactl init [dir] [--force]` | オフライン | `init.lua`、`lua/{input,workspaces,appearance,window_rules,keybinds}.lua`、`lua/macros/example.lua` を生成。既存ファイルは `--force` がない限り上書きしない |
| `komactl gen-types` | オフライン | `koma-types`（`types/koma.lua`）用の決定論的な `LuaCATS` スタブを出力 |
| `komactl inventory` | IPC（`admin.sock`） | 稼働中のモニター、ワークスペース、`Epoch` カウンタ、Deck ウィンドウ、Stash スロットを出力（`scene.inventory`）。ちょうど 1 つのワークスペースに `"focused": true` が付く |
| `komactl win move-to-workspace <ws_id\|name> [--follow]` | IPC（`admin.sock`） | フォーカス中ワークスペースのアクティブウィンドウを既存ワークスペースへ移動（`win.move_to_workspace`）。`--follow` で移動先へ切り替え、未指定なら移動元のフォーカスを維持 |
| `komactl token mint [label]` | IPC（`admin.sock`） | スコープ付き `CapabilityToken` を発行（`ttl_secs = 28800`、`can_create_headless = true`、`max_owned_workspaces = 4`） |
| `komactl capture [ws_id] [out.rgba]` | IPC（`admin.sock`） | `SCM_RIGHTS` シール済み `memfd` から `grid_225` オーバーレイ付きフレームをゼロコピー取得（既定 `ws_01`） |
| `komactl sandbox <subcmd>` | コンテナ + IPC | `bwrap` またはルートレス `podman` で隔離された `Headless` ワークスペースに GUI コンテナを起動 |
| `komactl -V` / `--version` | オフライン | `komactl <version>` を表示 |

## 生成設定（`komactl init`）

`komactl init` は同梱のスターターツリーを、既定の設定ディレクトリまたは明示的な `[dir]` に生成します：

```text
init.lua
lua/input.lua
lua/workspaces.lua
lua/appearance.lua
lua/window_rules.lua
lua/keybinds.lua
lua/macros/example.lua
```

`init.lua` は薄いルーターで、`lua/keybinds.lua` には既定キーマップ全体が `koma.bind(...)` 呼び出しとして展開されます。そのため生成ファイルと組み込みフォールバックキーマップがずれることはありません。各ファイルの先頭には機械可読マーカー `-- koma-config-template: <version>` が付きます。

既存ファイルは上書きされません。`komactl init` は競合するパスを列挙して停止し、`--force` を付けた場合のみ置き換えます。編集後は `komactl validate` と `komactl reload` を実行してください。`komactl config-status` はオンディスクのマーカーを同梱テンプレートと比較し、`template.installed_version`、`template.shipped_version`、`template.outdated`、`template.missing_files` を報告します。

バージョン比較だけでは判別できない状況を補うため、`template` には 2 つのフィールドがあります。`template.init_lua` は実際に検査したパス（`KOMA_CONFIG`、次に `$XDG_CONFIG_HOME/koma/init.lua`、次に `$HOME/.config/koma/init.lua` の順で解決）で、`template.present` はそのファイルが存在するかどうかを示します。マーカーのない手書きの `init.lua` は `installed_version: null` かつ `outdated: false` と報告され、古いテンプレートとは区別されます。逆に一部だけ削除された雛形は `missing_files` に現れます。

## `komactl config-status` が示す実効入力設定

同じレポートにはコンポジタの `config.status` が含まれ、`input.pointer` と `input.touchpad` ブロックに Koma が実際に適用している値（`accel_speed`、`accel_profile`、`natural_scroll`、`scroll_factor`、`follow_mouse`、タッチパッドでは `tap_to_click` と `disable_while_typing`）が並びます。`null` はそのキーが `init.lua` に一度も書かれていないことを意味し、libinput の組み込み既定値が適用されます。`accel_profile` は `"adaptive"`（既定の曲線）か `"flat"`（加速なし）のいずれかです。同じ物理移動量で他コンポジタとカーソル移動距離が違う場合は、まず `accel_speed` と `accel_profile` を比較してください。プロファイル未設定が差分のほとんどを説明します。

### `config.status` の XKB キーボードマップ

同じ `input` オブジェクトに `input.keyboard` が加わりました：`layout`、`variant`、`model`、`options`、`repeat_delay_ms`、`repeat_rate_hz`。`null` は「未設定」を意味し、XKB／libinput の既定値が適用されます。`options` は生の XKB オプション文字列なので、`init.lua` を開き直さなくてもリマップを確認できます。これらの値はテキストリピートと長押しリピートの両方のタイミングを駆動します。

`options` は XKB の名前を使い、Hyprland の `kb_options` が受け付けるものと同一です。`setxkbmap -option` が受け付ける指定なら何でも動作します：

| オプション | 効果 |
| :--- | :--- |
| `caps:escape` | Caps Lock を Escape として扱う |
| `caps:ctrl_modifier` | Caps Lock を追加の Ctrl にする |
| `ctrl:nocaps` | Caps Lock を Ctrl に割り当てる |
| `altwin:swap_lalt_lwin` | 左 Alt と左 Super を入れ替える |
| `compose:caps` | Caps Lock を Compose キーにする |
| `grp:alt_shift_toggle` | Alt + Shift でキーボードレイアウトグループを切り替える |

### `config.status` のフレーム時間ヒストグラム（`frame_perf`）

`config.status` にはヒープ確保なしの描画時間テレメトリ `frame_perf`（`rendered_frames`、`skipped_frames`、`avg_us`、`max_us`、`last_us`、`p50_bucket`、`p95_bucket`、および `lt_1ms`〜`ge_16ms` バケット）も含まれ、1,000 フレームごとに `tracing::debug!` サマリーも出力されます。

## 設定診断（`komactl doctor` と `komactl keys`）

どちらも `komactl validate` と同じ隔離シャドウ VM 評価を使うため、オフラインで動作しシートを必要としません。`komactl doctor` はチェックを `config`、`template`、`binds`、`monitors`、`workspaces`、`rules`、`environment` に分類し、各行に重大度を付けます：`ok`（実行して問題なし）、`warn`（読み込めるが意図と異なる可能性）、`error`（次回リロードで拒否される）、`skip`（DRM や稼働中コンポジタがない等、ここでは実行不可）。

`error` は終了コードを変えません。コンポジタは最後に有効だった設定で動き続けるため、設定エラーでセッションを壊してはいけないからです。`--strict` は warn か error が 1 つでもあれば `1` で終了し、`2` は設定を全く読めない場合、使い方の誤り、内部障害のために予約されています。`--json` は件数と全チェック行を 1 つのドキュメントで出力します。

`komactl keys` は実効マップを出力します。組み込みカタログに `input.inherit_default_binds`、`koma.unbind`、キーの上書きをマージし、ポインタバインドとジェスチャは別セクションに並びます。各行にはキー、アクション、Lua 式、ソース（`builtin` または `config:<file>`）、説明が付き、上書き時は組み込みの説明が括弧付きで残ります。`--grep <pattern>` は大文字小文字を区別せず絞り込み、`--json` は `{catalogue, keyboard, pointer, gestures, total, overridden_builtins}` を出力します。隠すものはありません：カタログ項目に戻せないバインドは生のアクションディスクリプタ付きで表示されます。既定ではオフラインで、稼働中の `koma-admin.sock` に到達できる場合はヘッダーと JSON の `live` オブジェクトに実行中の世代、有効な設定パス、ロック状態が読み取り専用でマージされます。

## `komactl sandbox` によるコンテナ隔離

`komactl sandbox` はホスト側の `$XDG_RUNTIME_DIR`・`koma-admin.sock`・D-Bus・PipeWire・SSH Agent を一切マウントせず、専用の `0700` `tmpfs` ランタイムディレクトリ内に制限付き `jail-<ws_id>.sock` のみを作成します：

```bash
# ネットワーク隔離された bwrap ブラウザを 1920x1080 Headless 空間で起動
komactl sandbox run --name browser-jail -- firefox

# ルートレス podman でネットワーク有効の OCI コンテナを起動する前の dry-run 確認
komactl sandbox run --runtime podman --image fedora:latest --share-net --dry-run -- glxgears

# 単一ワークスペース限定でエージェントアクセスを明示許可（koma-agent.sock + KOMA_CAPABILITY_TOKEN を付与）
komactl sandbox run --with-agent-sock --ro-bind ~/repo:/workspace -- code-oss
```

| オプション | 既定値 | 説明 |
| :--- | :--- | :--- |
| `--runtime <bwrap\|podman>` | `bwrap` | コンテナエンジン（`--image` 指定時は自動的に `podman` へ切替） |
| `--ws <ws_id\|auto>` | `auto` | 既存 `ws_id` を再利用または新規 `Headless` ワークスペースを作成 |
| `--name <name>` | `sandbox` | 新規作成する `Headless` ワークスペース名 |
| `--geometry <WxH[@scale]>` | `1920x1080` | ビューポート解像度とスケール（例：`2560x1600@1.6`） |
| `--bind <host:guest>` / `--ro-bind` | なし | ホストディレクトリの明示的なバインドマウント |
| `--share-net` | 無効 | ホストネットワーク（`bwrap`）または `pasta`（`podman`）を有効化（既定は隔離） |
| `--no-gpu` | 無効 | `/dev/dri` パススルーを省略しソフトウェア Mesa/Lavapipe を強制 |
| `--nvidia` | 無効 | Podman へ `--device=nvidia.com/gpu=all` CDI フラグを付与 |
| `--with-agent-sock` | 無効 | `koma-agent.sock` と単一ワークスペース用 `KOMA_CAPABILITY_TOKEN` を付与（`koma-admin.sock` は渡さない） |
| `--keep-jail` | 無効 | 終了後も `jail-<ws_id>.sock` を保持（`create-jail` / `revoke-jail` で手動管理可） |
| `--dry-run` | 無効 | 起動せず構築されたコンテナコマンドを表示 |

## `koma` サブコマンド（`init` / `completions` / `mcp`）

コンポジタバイナリ自身が 3 つの非コンポジタサブコマンドを持ちます：

| コマンド | 説明 |
| :--- | :--- |
| `koma init <bash\|zsh\|fish\|nushell> [--unset]` | 稼働中インスタンスのシェル向け環境割り当てを出力 |
| `koma completions <bash\|zsh\|fish>` | バイナリのコマンド表から生成した補完スクリプトを出力 |
| `koma mcp [--print-tools] [--auto-mint-admin]` | `koma-agent.sock` に対する stdio MCP サーバーを起動 |

`koma init` は `WAYLAND_DISPLAY`、`KOMA_INSTANCE_SIGNATURE`、`XDG_RUNTIME_DIR`、`DISPLAY`（`xwayland-satellite` 稼働中のみ）、`XDG_SESSION_TYPE`、`XDG_CURRENT_DESKTOP` を出力し、外部ターミナルから `komactl` などを利用できるようにします：

```bash
koma init fish | source
eval "$(koma init bash)"
koma init zsh --unset   # 逆の代入
```

ケイパビリティトークンは一切出力しません。稼働中インスタンスがない場合や複数ある場合は推測せず明確なエラーで停止するため、`KOMA_INSTANCE_SIGNATURE` で対象を指定します。

`koma mcp` は以前の独立バイナリ `koma-mcp` に代わる stdio サーバーです。`--print-tools` はエージェントソケットに触れずに 17 個のツールスキーマを出力し、`--auto-mint-admin` は `koma-admin.sock` からローカル開発用トークンを発行します。

## 空間ワークスペース概観（`koma-overview`）

![koma-overview 空間ワークスペーススイッチャー](https://cdn.komawm.org/media/koma-overview.webp)

`Mod + Tab`（または `koma.act.overview.toggle()` のキーバインド）で `koma-overview` を表示します：

- アクティブ出力へ `zwlr_layer_shell_v1` としてアタッチし、`koma-admin.sock` の `scene.inventory` を取得します。
- 有画面および `Headless`（`agent:work` デッキや背面 Stash 数を含む）全ワークスペースを、アイドル時の不要な GPU 再描画なしで空間グリッド表示します。
