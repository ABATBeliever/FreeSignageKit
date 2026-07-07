# FreeSignageKit

暫定

**FreeSignageKit** は、組み込み機器・デジタルサイネージ端末での利用を想定した、
キオスクモード専用のシンプルなWebブラウザです。
指定したURL(ホームページ)を全画面表示し続ける「サイネージ表示専用機」として動作します。

- PySide6 (Qt for Python) + QtWebEngine (Chromium) ベース
- ホームページが閉じられても自動的に再起動
- `config.toml` 1つで挙動をカスタマイズ可能(設定ファイルが無くても既定値で動作)
- Windows / Linux(AppImage)双方でポータブルに動作

## 特徴

- **キオスク運用向け**: 右クリックメニューの無効化、ダウンロードのブロック、
  ホームページ消失時の自動リロードなど、無人運用を前提とした設計
- **縦タブ**: `target="_blank"` などで開かれた新規ウィンドウは縦タブとして表示
  (ホームタブのみの間はタブパネル自体を非表示にできます)
- **ポータブル**: プロファイル(Cookie/キャッシュ)は実行ファイルと同じフォルダの
  `.fsk_profile` に保存されるため、USBメモリなどでの持ち運びに対応
- **Chromiumフラグの調整**: VA-AAPIによるハードウェアデコード、GPUラスタライズなど
  組み込み機器向けのチューニングを `config.toml` から有効化可能

## 動作環境

- Python 3.11+ (`tomllib` を使用)
- PySide6 (`pip install PySide6`)

```bash
pip install PySide6
python FSKit.py
```

AppImage化やNuitkaでのスタンドアロン実行にも対応しています
(`APPIMAGE` 環境変数 / `sys.frozen` を見て実行ファイルの場所を自動判定します)。

## 使い方

実行ファイル(`FSKit.py` / `.AppImage` / `.exe`)と同じフォルダに
`config.toml` を置くと、起動時に自動的に読み込まれます。

```
my_signage_folder/
├── FreeSignageKit.AppImage   (または FSKit.py / FreeSignageKit.exe)
├── config.toml               ← ここに設置
└── .fsk_profile/             ← 初回起動時に自動生成される(Cookie/キャッシュ)
```

`config.toml` が存在しない場合は、リポジトリ同封の
[`config.toml`](./config.toml)(既定値そのもの)の内容で動作します。
設定したい項目だけを残して自由に編集してください。未指定の項目は
自動的にデフォルト値で補われます。

### 設定項目

| セクション | キー | 既定値 | 説明 |
|---|---|---|---|
| `[browser]` | `home_url` | `"http://localhost"` | 起動時に開くホームページURL |
| | `fullscreen` | `true` | 全画面表示で起動するか |
| | `show_home_in_tabs` | `false` | ホームタブを縦タブ一覧に常時表示するか |
| | `home_retry_ms` | `2000` | ホームが消えてから再表示するまでの待ち時間(ms) |
| | `user_agent` | `""` | 送信するUser-Agent(空なら既定のChromium UA) |
| | `javascript` | `true` | JavaScriptを有効にするか |
| | `autoplay` | `true` | 動画・音声の自動再生を許可するか |
| `[navbar]` | `show` | `true` | ツールバーを表示するか |
| | `show_url_bar` | `true` | URL入力欄を表示するか |
| | `show_back_forward` | `true` | 戻る/進むボタンを表示するか |
| | `show_reload` | `true` | 再読み込みボタンを表示するか |
| `[kiosk]` | `exit_shortcut` | `"Ctrl+Shift+Q"` | アプリを終了するショートカット |
| | `disable_context_menu` | `true` | 右クリックメニューを無効化するか |
| `[chromium]` | `extra_flags` | `""` | 追加のChromium起動フラグ(スペース区切り) |
| | `vaapi` | `false` | VA-APIによるハードウェア動画支援 |
| | `gpu_rasterization` | `false` | GPUラスタライズ |
| | `zero_copy` | `false` | ゼロコピー転送 |
| | `autoplay_policy` | `true` | 自動再生ポリシーの緩和 |

### キーボードショートカット

| キー | 動作 |
|---|---|
| `Ctrl+Shift+Q`(既定・変更可) | アプリ終了 |
| `Ctrl+Shift+H` | ホームタブへ移動 |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | 次/前のタブへ移動 |
| `Alt+←` / `Alt+→` | 戻る / 進む |
| `F5` / `Ctrl+R` | 再読み込み |

## 注意事項

- サイネージ用途を想定しているため、ページ内リンクからのファイルダウンロードは
  自動的にキャンセルされます。
- 新しいタブ/ウィンドウの許可要求(通知・位置情報など)は既定で拒否されます。

## ライセンス

このプロジェクトは **GNU Lesser General Public License v3.0 (LGPL-3.0)** の下で
公開されています。詳細は [LICENSE](./LICENSE) を参照してください。

```
Copyright (C) 2026 ABATBeliever
```
