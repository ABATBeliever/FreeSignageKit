# Free Signage Kit - サイネージを作ろう

![License](https://img.shields.io/badge/license-LGPLv3-blue.svg)
![Version](https://img.shields.io/badge/version-0.4.0.0-green.svg)
![Version](https://img.shields.io/badge/Language-Python-yellow.svg)

---

## 概要

**FreeSignageKit**(FSKit) は、WindowsまたはLinuxの組み込み機器・デジタルサイネージ端末での利用を想定した、キオスクモード専用のシンプルなWebブラウザです。<br>
指定したURL(ホームページ)を全画面表示し続ける「サイネージ表示専用機」として動作します。

- PySide6 (Qt for Python) + QtWebEngine (Chromium) ベース
- ホームページが閉じられても自動的に再起動
- `config.toml` 1つで挙動をカスタマイズ可能(設定ファイルが無くても既定値で動作)
- Windows / Linux(AppImage)双方でポータブルに動作

Python, PySide6 そしてChromium エンジンを採用する LGPLライセンスの下で、
[Strollon](https://github.com/ABATBeliever/Strollon) 0.7.0.0の派生として作成されました。

---

## 入手・ダウンロード

準備中

---

## 特徴

- **キオスク運用向け**
  右クリックメニューの無効化、ホームページ消失・読み込み失敗時の自動リロード(指数バックオフ方式)
- **レンダラークラッシュからの自動復旧**
  ページの描画プロセスがクラッシュした場合も、タブを自動的に再生成して復旧します
- **ドメインホワイトリストによるアクセス制御**
  ダウンロード先ホスト、マイク/カメラ/位置情報へのアクセス許可を、それぞれ許可ドメインのリストで制御可能(既定はすべて拒否)
- **自動フルリスタート**
  一定間隔、または指定時刻でアプリ自体を丸ごと再起動する機能を搭載(長時間稼働によるメモリ増大等のリセット用途)
- **縦タブ**
  `target="_blank"` などで開かれた新規ウィンドウを縦タブとして表示
  (ホームタブのみの間はタブパネル自体を非表示にすることも可能)
- **ポータブル**
  プロファイル(Cookie/キャッシュ)は実行ファイルと同じフォルダの`.fsk_profile` に保存され、USBメモリなどでの持ち運びに対応
- **ログレベル調整**
  `debug`/`info`/`warn`/`error` の4段階でログ出力量を制御でき、24時間稼働時のディスクI/Oを抑制可能
- **Chromiumフラグの調整**
  チューニングを `config.toml` から有効化可能

---

## 動作環境・対応状況
| OS              | アーキテクチャ | 対応 |
|-----------------|---------------|------|
| Windows 10 以降 | x64           |対応済|
| Linux (Wayland/X11) | x64           |対応済(*)|

(*): X11またはWSLの場合、依存関係のインストールが必須です。

### スクリプトの場合
- Python 3.11+ (`tomllib` を使用)
- PySide6 (`pip install PySide6`)

```bash
chmod +x ./scripts/devkit-linux.sh
./scripts/devkit-linux.sh

call ./scripts/devkit-win.bat
```
---

## 使い方

実行ファイル(`FSKit.py` / `FSKit.AppImage` / `FSKit.exe`)と同じフォルダに
`config.toml` を置くと、起動時に自動的に読み込まれます。

```
/fskit/
├── FSKit.(py/AppImage/exe)
├── config.toml
└── .fsk_profile/
```

`config.toml` が存在しない場合は、リポジトリ同封の[`config.toml`](./config.toml)(既定値そのもの)で動作します。
未指定の項目は自動的にデフォルト値で補われます。

### 設定項目

| セクション | キー | 既定値 | 説明 |
|---|---|---|---|
| `[browser]` | `home_url` | `"http://localhost"` | 起動時に開くホームページURL |
| | `fullscreen` | `true` | 全画面表示で起動するか |
| | `show_home_in_tabs` | `false` | ホームタブを縦タブ一覧に常時表示するか |
| | `home_retry_ms` | `2000` | ホーム再試行の初回待ち時間(ms)。失敗するたびに指数バックオフ(2倍ずつ)で延び、成功するとリセットされる |
| | `home_retry_max_ms` | `60000` | `home_retry_ms` の指数バックオフの上限(ms) |
| | `user_agent` | `""` | 送信するUser-Agent(空なら既定のChromium UA) |
| | `javascript` | `true` | JavaScriptを有効にするか |
| | `autoplay` | `true` | 動画・音声の自動再生を許可するか |
| `[navbar]` | `show` | `true` | ツールバーを表示するか |
| | `show_url_bar` | `true` | URL入力欄を表示するか |
| | `show_back_forward` | `true` | 戻る/進むボタンを表示するか |
| | `show_reload` | `true` | 再読み込みボタンを表示するか |
| `[kiosk]` | `exit_shortcut` | `"Ctrl+Shift+Q"` | アプリを終了するショートカット |
| | `disable_context_menu` | `true` | 右クリックメニューを無効化するか |
| | `restart_interval_hours` | `0` | アプリ自体を丸ごと再起動する間隔(時間)。`0`以下で無効 |
| | `restart_at` | `""` | 再起動を実行する時刻(`"HH:MM"`、24時間表記)。空なら経過時間のみで即再起動 |
| `[chromium]` | `extra_flags` | `""` | 追加のChromium起動フラグ(スペース区切り) |
| | `vaapi` | `false` | VA-APIによるハードウェア動画支援 |
| | `gpu_rasterization` | `false` | GPUラスタライズ |
| | `zero_copy` | `false` | ゼロコピー転送 |
| | `autoplay_policy` | `true` | 自動再生ポリシーの緩和 |
| `[downloads]` | `allowed_domains` | `[]` | ダウンロードを許可するホストのリスト(`"*"`で全許可、空で全拒否) |
| `[permissions]` | `microphone` | `[]` | マイクへのアクセスを許可するホストのリスト(`"*"`指定不可) |
| | `camera` | `[]` | カメラへのアクセスを許可するホストのリスト(`"*"`指定不可) |
| | `geolocation` | `[]` | 位置情報へのアクセスを許可するホストのリスト(`"*"`指定不可) |
| `[logging]` | `level` | `"info"` | ログ出力レベル(`debug`/`info`/`warn`/`error`) |

ホスト指定は完全一致のほか、`*.example.com` のようなサブドメインワイルドカードにも対応しています。

### キーボードショートカット

| キー | 動作 |
|---|---|
| `Ctrl+Shift+Q`(既定・変更可) | アプリ終了 |
| `Ctrl+Shift+H` | ホームタブへ移動 |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | 次/前のタブへ移動 |
| `Alt+←` / `Alt+→` | 戻る / 進む |
| `F5` / `Ctrl+R` | 再読み込み |

---

## 注意事項

- サイネージ用途を想定しているため、ページ内リンクからのファイルダウンロードは既定ですべて拒否されます。許可したい場合は `[downloads] allowed_domains` にホストを追加してください。
- マイク/カメラ/位置情報へのアクセス要求は既定ですべて拒否されます。許可したい場合は `[permissions]` の対応する項目にホストを追加してください(通知など上記以外の許可要求は常に拒否されます)。
- `config.toml`は正しく設定してください。
  - 読み取り専用にしておくことを推奨します。
  - 終了するためのショートカットは変更することを推奨します。
  - `restart_interval_hours` を有効にする場合、利用者への影響が少ない時間帯を `restart_at` で指定することを推奨します。
  - 24時間稼働でログをファイルに保存する場合は、`[logging] level` を `"warn"` 程度に絞ることでディスクI/Oを抑えられます。

---

## ライセンス

FSKit は **GNU Lesser General Public License (LGPL)** に基づいて配布されています。  
詳細は [LICENSE](./LICENSE) を参照してください。

---

## クレジット / サードパーティライブラリ

- Qt (Qt Company)  
- QtWebEngine

各ライブラリのライセンスはそれぞれの配布元に準拠します。

---

## 連絡先

- **作者:** ABATBeliever  
