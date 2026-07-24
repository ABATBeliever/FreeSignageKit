# Free Signage Kit - サイネージを作ろう

![License](https://img.shields.io/badge/license-LGPLv3-blue.svg)
![Version](https://img.shields.io/badge/version-0.3.0.0-green.svg)
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
  右クリックメニューの無効化、ダウンロードのブロック、ホームページ消失時の自動リロード
- **縦タブ**
  `target="_blank"` などで開かれた新規ウィンドウを縦タブとして表示
  (ホームタブのみの間はタブパネル自体を非表示にすることも可能)
- **ポータブル**
  プロファイル(Cookie/キャッシュ)は実行ファイルと同じフォルダの`.fsk_profile` に保存され、USBメモリなどでの持ち運びに対応
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

---

## 注意事項

- サイネージ用途を想定しているため、ページ内リンクからのファイルダウンロードはキャンセルされます。
- 新しいタブ/ウィンドウの許可要求(通知・位置情報など)は既定で拒否されます。
- `config.toml`は正しく設定してください。
  - 読み取り専用にしておくことを推奨します。
  - 終了するためのショートカットは変更することを推奨します。

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
