"""
FreeSignageKit
Copyright (C) 2026 ABATBeliever
Under LGPL v3
"""

APP_VERSION = "v0.4.0.0"
APP_NAME    = f"FreeSignageKit {APP_VERSION}"

import sys
import os
import re
import tomllib
from pathlib import Path
from urllib.parse import quote_plus

# フラグ注入やCWD変更が行われる"前"の、素のsys.argvを退避しておく。
# ハードリスタート(os.execv)時にこの値を使う。
_ORIGINAL_ARGV = list(sys.argv)

print(f"\n      mmmmmmmm     mmmm      mm   mmm    ##         ")
print(f"     ##         m#m    #    ##  ##              ##  ")
print(f"    ##         ##m         ##m##     ####    #######")
print(f"   #######      ####m     #####       ##      ##    ")
print(f"  ##               ##    ##  ##m     ##      ##     ")
print(f" ##         #mmmmm#+    ##   ##m mmm##mmm   ##mmm   \n")
print("Free Signage Kit")
print("Copyright (C) 2026 ABATBeliever. Under LGPL v3\n")

# ─────────────────────────────────────────────
# ログレベル制御
# ─────────────────────────────────────────────
#
# 24/7稼働するサイネージ端末では、すべてのイベントを標準出力にprintし続けると
# (特にログをファイルにリダイレクトして運用する場合)継続的なディスクI/Oの
# 原因になる。config.toml の [logging] level で出力量を絞れるようにする。
#
#   debug : 開発時のみ必要な詳細ログまで全て出力(権限拒否など高頻度なものも含む)
#   info  : 通常運用のイベントログ(タブ操作・設定読み込み等)を出力(デフォルト)
#   warn  : 異常系(ホーム到達不可・レンダラークラッシュ・設定不備等)のみ出力
#   error : 致命的なものだけ出力(現状は使用箇所なし。将来の拡張用)
#
# 起動直後のバナー(上記print)はconfig読み込み前なので常に表示される。

_LOG_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
_DEFAULT_LOG_LEVEL = "info"
_CURRENT_LOG_LEVEL = _LOG_LEVELS[_DEFAULT_LOG_LEVEL]


def _set_log_level(level: str):
    global _CURRENT_LOG_LEVEL
    _CURRENT_LOG_LEVEL = _LOG_LEVELS.get(str(level).lower(), _LOG_LEVELS[_DEFAULT_LOG_LEVEL])


def _resolve_log_level(raw_toml: dict) -> str:
    """
    config.toml をスキーマ検証する"前"に、まず [logging] level だけを覗き見る。
    (検証エラー自体のログ出力レベルを決めるために、検証より先に必要なため)
    不正な値の場合は既定値にフォールバックする。
    """
    if isinstance(raw_toml, dict):
        logging_cfg = raw_toml.get("logging")
        if isinstance(logging_cfg, dict):
            level = logging_cfg.get("level")
            if isinstance(level, str) and level.lower() in _LOG_LEVELS:
                return level.lower()
    return _DEFAULT_LOG_LEVEL


def _log(level: str, message: str, file=None):
    """指定レベルが現在の出力しきい値以上の場合のみ標準出力(またはfile)に出す。"""
    if _LOG_LEVELS.get(level, _LOG_LEVELS["info"]) >= _CURRENT_LOG_LEVEL:
        print(message, file=file or sys.stdout)

# ─────────────────────────────────────────────
# config.toml 読み込み
# ─────────────────────────────────────────────

def _get_exe_dir() -> Path:
    # AppImage 実行時: $APPIMAGE に実際の .AppImage ファイルのパスが入る
    appimage_path = os.environ.get("APPIMAGE")
    if appimage_path:
        return Path(appimage_path).parent.resolve()
    # Nuitka standalone (Windows等) / 通常のfrozen実行
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    # 開発時 (python FSKit.py で直接実行)
    return Path(__file__).parent.resolve()

_EXE_DIR = _get_exe_dir()
_CONFIG_PATH = _EXE_DIR / "config.toml"

_DEFAULT_CONFIG: dict = {
    "browser": {
        "home_url":           "http://localhost",
        "fullscreen":         True,
        "show_home_in_tabs":  False,           # ホームタブを縦タブに載せるか
        "home_retry_ms":      2000,            # ホーム再試行の初回待ち時間(ms)。指数バックオフの基準値
        "home_retry_max_ms":  60000,           # ホーム再試行間隔の上限(ms)
        "user_agent":         "",              # 空 = デフォルト Chromium UA
        "javascript":         True,
        "autoplay":           True,            # 自動再生を許可
    },
    "navbar": {
        "show":               True,            # ツールバー常時表示
        "show_url_bar":       True,
        "show_back_forward":  True,
        "show_reload":        True,
    },
    "kiosk": {
        "exit_shortcut":      "Ctrl+Shift+Q", # 終了ショートカット
        "disable_context_menu": True,
        "restart_interval_hours": 0,          # ハードリスタート間隔(時間)。0以下で無効
        "restart_at":         "",             # "HH:MM"形式で時刻指定。空なら経過時間のみで判定
    },
    "chromium": {
        "extra_flags":        "",              # スペース区切りで追加フラグ
        "vaapi":              False,
        "gpu_rasterization":  False,
        "zero_copy":          False,
        "autoplay_policy":    True,            # --autoplay-policy=no-user-gesture-required
    },
    "downloads": {
        # ダウンロードを許可するホストのリスト。"*" で全許可、空リストで全拒否(デフォルト)。
        # 例: ["example.com", "*.cdn.example.com", "*"]
        "allowed_domains":    [],
    },
    "permissions": {
        # マイク/カメラ/位置情報へのアクセスを許可するホストのホワイトリスト。
        # 空リストで全拒否(デフォルト)。安全のため "*" (全許可)はここでは指定できません。
        "microphone":         [],
        "camera":             [],
        "geolocation":        [],
    },
    "logging": {
        # ログ出力レベル: "debug" / "info" / "warn" / "error"
        "level":              "info",
    },
}


def _validate_and_merge(base: dict, override: dict, path: tuple = ()) -> dict:
    """
    base(デフォルト値)の型を基準に override(ユーザーconfig)を検証しながらマージする。
    キー単位で型が不正な場合はそのキーだけデフォルトのまま残し、警告を出す。
    これにより、config.toml内の一箇所の記述ミスでアプリ全体が起動不能になることを防ぐ。
    """
    result = dict(base)
    for k, v in override.items():
        full_path = path + (k,)
        dotted = ".".join(full_path)

        if k not in base:
            _log("warn", f"[FSK][WARN] 未知の設定項目 '{dotted}' は無視されます", file=sys.stderr)
            continue

        default_v = base[k]

        if isinstance(default_v, dict):
            if isinstance(v, dict):
                result[k] = _validate_and_merge(default_v, v, full_path)
            else:
                _log("warn", f"[FSK][WARN] '{dotted}' はテーブル([...])である必要があります — デフォルト値を使用します", file=sys.stderr)
            continue

        # bool は int のサブクラスなので bool を先に判定する
        if isinstance(default_v, bool):
            if isinstance(v, bool):
                result[k] = v
            else:
                _log("warn", f"[FSK][WARN] '{dotted}' は true/false である必要があります — デフォルト値({default_v})を使用します", file=sys.stderr)

        elif isinstance(default_v, int):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                result[k] = v
            else:
                _log("warn", f"[FSK][WARN] '{dotted}' は数値である必要があります — デフォルト値({default_v})を使用します", file=sys.stderr)

        elif isinstance(default_v, str):
            if isinstance(v, str):
                result[k] = v
            else:
                _log("warn", f"[FSK][WARN] '{dotted}' は文字列である必要があります — デフォルト値({default_v!r})を使用します", file=sys.stderr)

        elif isinstance(default_v, list):
            if isinstance(v, list) and all(isinstance(x, str) for x in v):
                result[k] = v
            else:
                _log("warn", f"[FSK][WARN] '{dotted}' は文字列のリストである必要があります — デフォルト値({default_v!r})を使用します", file=sys.stderr)

        else:
            result[k] = v

    return result


def _validate_permissions(cfg: dict) -> dict:
    """permissions.* に '*'(全許可)が指定されていた場合は無効化して警告する。"""
    perms = cfg.get("permissions", {})
    for key in ("microphone", "camera", "geolocation"):
        lst = perms.get(key, [])
        if "*" in lst:
            _log(
                "warn",
                f"[FSK][WARN] permissions.{key} に '*' は指定できません(危険なため禁止)。"
                f"'*' を除いたリストとして扱います。",
                file=sys.stderr,
            )
            perms[key] = [x for x in lst if x != "*"]
    cfg["permissions"] = perms
    return cfg


def _validate_logging(cfg: dict) -> dict:
    """logging.level が既定の4段階以外だった場合はデフォルトへフォールバックする。"""
    level = str(cfg.get("logging", {}).get("level", _DEFAULT_LOG_LEVEL)).lower()
    if level not in _LOG_LEVELS:
        _log("warn", f"[FSK][WARN] logging.level の値 '{level}' は不正です — '{_DEFAULT_LOG_LEVEL}' を使用します", file=sys.stderr)
        level = _DEFAULT_LOG_LEVEL
    cfg.setdefault("logging", {})["level"] = level
    return cfg


def _load_config() -> dict:
    cfg = _DEFAULT_CONFIG
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "rb") as f:
                user = tomllib.load(f)
            # 検証・マージ処理自体のログレベルを決めるため、先に[logging] levelだけ読む
            _set_log_level(_resolve_log_level(user))
            cfg = _validate_and_merge(cfg, user)
            _log("info", f"[FSK] config.toml loaded: {_CONFIG_PATH}")
        except Exception as e:
            print(f"[FSK][WARN] config.toml parse error: {e}  — using defaults", file=sys.stderr)
    else:
        _log("info", f"[FSK] config.toml not found at {_CONFIG_PATH}, using defaults")
    cfg = _validate_permissions(cfg)
    cfg = _validate_logging(cfg)
    _set_log_level(cfg["logging"]["level"])  # 検証後の確定値で最終的にセットし直す
    return cfg


CONFIG = _load_config()


def _cfg(*keys):
    """CONFIG から . 区切りでネストした値を取得する。"""
    v = CONFIG
    for k in keys:
        v = v[k]
    return v


# ─────────────────────────────────────────────
# ドメインホワイトリスト照合(ダウンロード許可 / 権限許可で共用)
# ─────────────────────────────────────────────

def _host_matches(host: str, pattern: str) -> bool:
    host = (host or "").lower()
    pattern = (pattern or "").lower().strip()
    if not pattern:
        return False
    if pattern == "*":
        return True
    if pattern.startswith("*."):
        suffix = pattern[1:]          # ".example.com"
        bare   = pattern[2:]          # "example.com"
        return host == bare or host.endswith(suffix)
    return host == pattern


def _host_allowed(host: str, allowed_patterns) -> bool:
    return any(_host_matches(host, p) for p in (allowed_patterns or []))


# ─────────────────────────────────────────────
# Chromium フラグ（QApplication 生成前に適用）
# ─────────────────────────────────────────────

def _apply_chromium_flags():
    flags = []
    c = CONFIG.get("chromium", {})
    if c.get("vaapi"):
        flags += [
            "--enable-features=VaapiVideoDecodeLinuxGL,VaapiVideoEncoder,"
            "AcceleratedVideoDecodeLinuxGL,AcceleratedVideoDecodeLinuxZeroCopyGL"
        ]
    if c.get("gpu_rasterization"):
        flags += ["--enable-gpu-rasterization", "--enable-oop-rasterization"]
    if c.get("zero_copy"):
        flags += ["--enable-zero-copy"]
    if c.get("autoplay_policy") or CONFIG["browser"].get("autoplay"):
        flags += ["--autoplay-policy=no-user-gesture-required"]
    for tok in (c.get("extra_flags") or "").split():
        if tok:
            flags.append(tok)
    for f in flags:
        if f not in sys.argv:
            sys.argv.append(f)
    if flags:
        _log("info", f"[FSK] Chromium flags: {' '.join(flags)}")


_apply_chromium_flags()

# ─────────────────────────────────────────────
# Qt imports
# ─────────────────────────────────────────────

from PySide6.QtCore    import Qt, QUrl, QTimer, Signal, QDateTime, QTime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, QSplitter,
    QLabel, QProgressBar, QToolBar,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore    import (
    QWebEngineProfile, QWebEngineSettings, QWebEnginePage,
)
from PySide6.QtGui import QShortcut, QKeySequence

# ─────────────────────────────────────────────
# カスタム WebEnginePage
# ─────────────────────────────────────────────

# QWebEnginePage.Feature → permissions.toml のキーへのマッピング。
# 未対応の機能(通知・クリップボード等)は常に拒否する。
_FEATURE_PERMISSION_MAP = {
    QWebEnginePage.Feature.MediaAudioCapture:      ("microphone",),
    QWebEnginePage.Feature.MediaVideoCapture:      ("camera",),
    QWebEnginePage.Feature.MediaAudioVideoCapture: ("microphone", "camera"),
    QWebEnginePage.Feature.Geolocation:            ("geolocation",),
}


def _feature_allowed(url: QUrl, feature) -> bool:
    keys = _FEATURE_PERMISSION_MAP.get(feature)
    if not keys:
        return False  # ホワイトリスト対象外の機能はデフォルト拒否
    perms = CONFIG.get("permissions", {})
    host = url.host()
    return all(_host_allowed(host, perms.get(key, [])) for key in keys)


class _Page(QWebEnginePage):
    """
    新しいタブ/ウィンドウ要求・権限要求を親ブラウザに委譲するページ。

    NOTE: 非アクティブなタブは Qt のウィジェット親子関係から一時的に外れる
    (SignageBrowser._on_tab_changed 参照)ため、self.parent() を辿って
    ブラウザを探す実装は背面タブで壊れる。ブラウザへの参照は生成時に直接渡す。
    """

    def __init__(self, profile, browser: "SignageBrowser", parent=None):
        super().__init__(profile, parent)
        self._browser = browser
        self.featurePermissionRequested.connect(self._handle_permission_request)

    def _handle_permission_request(self, url, feature):
        granted = _feature_allowed(url, feature)
        self.setFeaturePermission(
            url, feature,
            QWebEnginePage.PermissionGrantedByUser if granted else QWebEnginePage.PermissionDeniedByUser,
        )
        if not granted:
            _log("debug", f"[FSK] Permission denied: {feature} for {url.toString()}")

    def createWindow(self, window_type):
        """target="_blank" / window.open() → 必ず新しいタブで開く"""
        view = self._browser.add_tab("about:blank", activate=True, _return_view=True)
        if view is not None:
            return view.page()
        return super().createWindow(window_type)


# ─────────────────────────────────────────────
# タブウィジェット（縦タブの1行）
# ─────────────────────────────────────────────

class _TabWidget(QWidget):
    close_requested = Signal()

    def __init__(self, title: str, closable: bool = True, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)

        self.label = QLabel(title)
        # タイトルはリモートページ(document.title)由来の非信頼な文字列のため、
        # HTML/リッチテキストとして解釈させない(外部リソース読み込み等を防ぐ)
        self.label.setTextFormat(Qt.PlainText)
        self.label.setStyleSheet("color: #e0e0e0; font-size: 13px; background: transparent;")
        self.label.setWordWrap(False)
        lay.addWidget(self.label, 1)

        if closable:
            btn = QPushButton("✕")
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(
                "QPushButton { background: transparent; color: #888; border: none; font-size: 11px; }"
                "QPushButton:hover { color: #fff; }"
            )
            btn.clicked.connect(self.close_requested.emit)
            lay.addWidget(btn)

    def set_title(self, title: str):
        self.label.setText(title[:40] + "…" if len(title) > 40 else title)


class _TabItem(QListWidgetItem):
    def __init__(self, title: str, web_view: QWebEngineView, closable: bool = True):
        super().__init__()
        self.web_view = web_view
        self.widget   = _TabWidget(title, closable=closable)
        self.setSizeHint(self.widget.sizeHint())
        self.setFlags(self.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)


# ─────────────────────────────────────────────
# メインウィンドウ
# ─────────────────────────────────────────────

class SignageBrowser(QMainWindow):
    """
    FreeSignageKit メインウィンドウ。

    - スロット0 = ホームタブ（home_url）
      show_home_in_tabs=False のとき縦タブパネルは隠れている。
      新規タブが1つでも開いたら縦タブパネルを表示する。
      新規タブが全部閉じたら縦タブパネルを隠す。
    - ホームタブが何らかの理由で消えたら home_retry_ms 後に自動再起動。
    """

    def __init__(self):
        super().__init__()
        self._tabs:           list[QWebEngineView] = []
        self._home_view:      QWebEngineView | None = None
        self._home_item:      _TabItem        | None = None
        self._show_home_tab:  bool = bool(_cfg("browser", "show_home_in_tabs"))
        self._home_url:       str  = str(_cfg("browser", "home_url"))

        # ホーム再試行の指数バックオフ状態
        self._retry_base_ms:  int  = max(100, int(_cfg("browser", "home_retry_ms")))
        self._retry_max_ms:   int  = max(self._retry_base_ms, int(_cfg("browser", "home_retry_max_ms")))
        self._retry_ms:       int  = self._retry_base_ms

        # プロファイル（ポータブル：同ディレクトリ配下）
        profile_path = _EXE_DIR / ".fsk_profile"
        self.profile = QWebEngineProfile("FSKProfile")
        self.profile.setPersistentStoragePath(str(profile_path / "storage"))
        self.profile.setCachePath(str(profile_path / "cache"))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.AllowPersistentCookies)

        ws = self.profile.settings()
        ws.setAttribute(QWebEngineSettings.JavascriptEnabled,
                        bool(_cfg("browser", "javascript")))
        ws.setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        ws.setAttribute(QWebEngineSettings.AutoLoadImages, True)
        ws.setAttribute(QWebEngineSettings.PdfViewerEnabled, False)

        ua = str(_cfg("browser", "user_agent") or "")
        if ua:
            self.profile.setHttpUserAgent(ua)

        self.profile.downloadRequested.connect(self._on_download)

        self._init_ui()
        self._setup_shortcuts()
        self._setup_restart_watchdog()

        # ホームタブを起動（遅延ゼロで次のループへ）
        QTimer.singleShot(0, self._open_home)

    # ──────────────────────────────────────
    # UI 構築
    # ──────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle(APP_NAME)
        self.setStyleSheet("QMainWindow, QWidget { background: #0f0f0f; }")

        if _cfg("browser", "fullscreen"):
            self.showFullScreen()
        else:
            self.showMaximized()

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 縦タブパネル ──
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setStyleSheet(
            "QSplitter::handle { background: #2a2a2a; width: 1px; }"
        )

        self._tab_panel = QWidget()
        self._tab_panel.setFixedWidth(200)
        self._tab_panel.setStyleSheet("background: #1a1a1a;")
        tab_lay = QVBoxLayout(self._tab_panel)
        tab_lay.setContentsMargins(4, 4, 4, 4)
        tab_lay.setSpacing(4)

        self._tab_list = QListWidget()
        self._tab_list.setStyleSheet(
            "QListWidget { background: transparent; border: none; outline: none; }"
            "QListWidget::item { border-radius: 6px; margin: 1px 0; }"
            "QListWidget::item:selected { background: #2d4a6e; }"
            "QListWidget::item:hover:!selected { background: #262626; }"
        )
        self._tab_list.currentItemChanged.connect(self._on_tab_changed)
        self._tab_list.setDragDropMode(QListWidget.InternalMove)
        self._tab_list.setDefaultDropAction(Qt.MoveAction)
        self._tab_list.model().rowsMoved.connect(self._on_tabs_reordered)
        tab_lay.addWidget(self._tab_list)

        self._splitter.addWidget(self._tab_panel)

        # ── ブラウザエリア ──
        browser_widget = QWidget()
        browser_widget.setStyleSheet("background: #0f0f0f;")
        b_lay = QVBoxLayout(browser_widget)
        b_lay.setContentsMargins(0, 0, 0, 0)
        b_lay.setSpacing(0)

        # ツールバー
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setStyleSheet(
            "QToolBar { background: #1e1e1e; border-bottom: 1px solid #333; spacing: 2px; padding: 2px 4px; }"
        )
        show_nav = bool(_cfg("navbar", "show"))
        self._toolbar.setVisible(show_nav)

        if show_nav and _cfg("navbar", "show_back_forward"):
            self._back_btn = QPushButton("◀")
            self._back_btn.setFixedSize(32, 32)
            self._back_btn.setToolTip("戻る  (Alt+←)")
            self._back_btn.setStyleSheet(self._nav_btn_style())
            self._back_btn.clicked.connect(self._go_back)
            self._toolbar.addWidget(self._back_btn)

            self._fwd_btn = QPushButton("▶")
            self._fwd_btn.setFixedSize(32, 32)
            self._fwd_btn.setToolTip("進む  (Alt+→)")
            self._fwd_btn.setStyleSheet(self._nav_btn_style())
            self._fwd_btn.clicked.connect(self._go_forward)
            self._toolbar.addWidget(self._fwd_btn)

        if show_nav and _cfg("navbar", "show_reload"):
            self._reload_btn = QPushButton("↺")
            self._reload_btn.setFixedSize(32, 32)
            self._reload_btn.setToolTip("再読み込み  (F5)")
            self._reload_btn.setStyleSheet(self._nav_btn_style())
            self._reload_btn.clicked.connect(self._reload)
            self._toolbar.addWidget(self._reload_btn)

        if show_nav and _cfg("navbar", "show_url_bar"):
            self._url_bar = QLineEdit()
            self._url_bar.setStyleSheet(
                "QLineEdit { background: #2a2a2a; color: #e0e0e0; border: 1px solid #444;"
                " border-radius: 4px; padding: 4px 8px; font-size: 13px; }"
                "QLineEdit:focus { border-color: #5ec4ff; }"
            )
            self._url_bar.setPlaceholderText("URLを入力")
            self._url_bar.returnPressed.connect(self._navigate_from_bar)
            self._toolbar.addWidget(self._url_bar)
        else:
            self._url_bar = None

        b_lay.addWidget(self._toolbar)

        # ロード進捗バー（3px）
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(3)
        self._progress.setStyleSheet(
            "QProgressBar { background: transparent; border: none; }"
            "QProgressBar::chunk { background: #5ec4ff; border-radius: 1px; }"
        )
        b_lay.addWidget(self._progress)

        # WebView コンテナ
        self._web_container = QWidget()
        self._web_layout    = QVBoxLayout(self._web_container)
        self._web_layout.setContentsMargins(0, 0, 0, 0)
        b_lay.addWidget(self._web_container, 1)

        self._splitter.addWidget(browser_widget)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([200, 9999])

        root.addWidget(self._splitter)

        # 初期状態ではタブパネルを隠す
        self._update_tab_panel_visibility()

    @staticmethod
    def _nav_btn_style() -> str:
        return (
            "QPushButton { background: transparent; color: #ccc; border: none; font-size: 15px; }"
            "QPushButton:hover { background: #2d2d2d; border-radius: 4px; }"
            "QPushButton:pressed { background: #383838; }"
        )

    # ──────────────────────────────────────
    # ショートカット
    # ──────────────────────────────────────

    def _setup_shortcuts(self):
        exit_seq = str(_cfg("kiosk", "exit_shortcut") or "Ctrl+Shift+Q")
        QShortcut(QKeySequence(exit_seq), self).activated.connect(self.close)

        QShortcut(QKeySequence("Ctrl+Tab"),       self).activated.connect(self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self).activated.connect(self._prev_tab)
        QShortcut(QKeySequence("Alt+Left"),        self).activated.connect(self._go_back)
        QShortcut(QKeySequence("Alt+Right"),       self).activated.connect(self._go_forward)
        QShortcut(QKeySequence("F5"),              self).activated.connect(self._reload)
        QShortcut(QKeySequence("Ctrl+R"),          self).activated.connect(self._reload)
        QShortcut(QKeySequence("Ctrl+Shift+H"),    self).activated.connect(self._go_home)

    # ──────────────────────────────────────
    # ホームタブ管理
    # ──────────────────────────────────────

    def _open_home(self):
        """ホームタブを開く（または再起動）。"""
        view = self._make_view()
        view.setUrl(QUrl(self._home_url))

        closable = self._show_home_tab  # show_home_in_tabs=False なら閉じるボタンなし
        item = _TabItem("ホーム", view, closable=closable)
        self._tab_list.insertItem(0, item)
        self._tab_list.setItemWidget(item, item.widget)

        if closable:
            # ユーザーが意図的に閉じた場合も再起動する
            item.widget.close_requested.connect(lambda: self._close_tab(item))

        self._tabs.insert(0, view)
        self._home_view = view
        self._home_item = item

        # タブ選択（他タブが開いていれば最初のサブタブのまま）
        if self._tab_list.count() == 1:
            self._tab_list.setCurrentItem(item)

        self._update_tab_panel_visibility()

        _log("info", f"[FSK] Home tab opened: {self._home_url}")

    def _schedule_home_reopen(self):
        """ホームが閉じられた後、指数バックオフ間隔で再起動するタイマーをセット。"""
        delay = self._retry_ms
        _log("warn", f"[FSK] Home tab lost — reopening in {delay} ms")
        QTimer.singleShot(delay, self._open_home)
        self._bump_retry_delay()

    def _bump_retry_delay(self):
        """次回の再試行間隔を倍にする(上限あり)。"""
        self._retry_ms = min(self._retry_ms * 2, self._retry_max_ms)
        return self._retry_ms

    def _reset_retry_delay(self):
        """ホームの読み込みに成功したら再試行間隔を初期値に戻す。"""
        self._retry_ms = self._retry_base_ms

    def _is_home_view(self, view: QWebEngineView) -> bool:
        return view is self._home_view

    # ──────────────────────────────────────
    # タブ操作
    # ──────────────────────────────────────

    def add_tab(self, url: str, activate: bool = True,
                _return_view: bool = False) -> QWebEngineView | None:
        """新規サブタブを追加（ホームタブとは別）。"""
        view = self._make_view()
        view.setUrl(QUrl(url))

        item = _TabItem(url[:30] or "新しいタブ", view, closable=True)
        item.widget.close_requested.connect(lambda: self._close_tab(item))

        self._tab_list.addItem(item)
        self._tab_list.setItemWidget(item, item.widget)
        self._tabs.append(view)

        if activate:
            self._tab_list.setCurrentItem(item)

        self._update_tab_panel_visibility()
        _log("info", f"[FSK] New tab: {url}")

        if _return_view:
            return view
        return None

    def _close_tab(self, item: _TabItem):
        """タブを閉じる。ホームタブが閉じられたら再起動スケジュール。"""
        is_home = (item is self._home_item)
        for i in range(self._tab_list.count()):
            if self._tab_list.item(i) is item:
                self._tab_list.takeItem(i)
                break
        if item.web_view in self._tabs:
            self._tabs.remove(item.web_view)

        view = item.web_view
        try:
            view.stop()
            page = view.page()
            if page is not None:
                page.blockSignals(True)
            view.blockSignals(True)
        except RuntimeError:
            # 既にC++側オブジェクトが破棄されている場合はここで無視する
            pass
        view.deleteLater()

        if is_home:
            self._home_view = None
            self._home_item = None
            self._schedule_home_reopen()
        else:
            # サブタブが全部閉じたら → ホームを選択
            if self._tab_list.count() > 0 and self._home_item is not None:
                self._tab_list.setCurrentItem(self._home_item)

        self._update_tab_panel_visibility()

    def _make_view(self) -> QWebEngineView:
        view = QWebEngineView()
        page = _Page(self.profile, self, view)
        page.fullScreenRequested.connect(self._handle_fullscreen)
        page.renderProcessTerminated.connect(lambda *_: self._on_render_process_terminated(view))
        view.setPage(page)

        view.titleChanged.connect(lambda t: self._on_title_changed(view, t))
        view.urlChanged.connect(lambda u: self._on_url_changed(view, u))
        view.loadStarted.connect(lambda: self._on_load_start(view))
        view.loadFinished.connect(lambda ok: self._on_load_finish(view, ok))
        view.loadProgress.connect(lambda p: self._on_load_progress(view, p))

        if bool(_cfg("kiosk", "disable_context_menu")):
            view.setContextMenuPolicy(Qt.NoContextMenu)

        return view

    def _on_render_process_terminated(self, view: QWebEngineView):
        """
        レンダラープロセスのクラッシュを検知して復旧する(バグ#5対応)。
        組み込み環境ではGPUドライバ起因のクラッシュが起こりうるため、
        検知せず放置すると画面が固まったままになる。
        """
        _log("warn", f"[FSK] Render process terminated: {view.url().toString()}")

        if self._is_home_view(view):
            item = self._home_item
            if item is not None:
                # _close_tab → is_home分岐で _schedule_home_reopen が呼ばれる
                self._close_tab(item)
            return

        for i in range(self._tab_list.count()):
            item = self._tab_list.item(i)
            if isinstance(item, _TabItem) and item.web_view is view:
                url = view.url().toString()
                self._close_tab(item)
                QTimer.singleShot(500, lambda: self.add_tab(url))
                break

    # ──────────────────────────────────────
    # タブパネル表示切り替え
    # ──────────────────────────────────────

    def _update_tab_panel_visibility(self):
        """
        show_home_in_tabs=False の場合：
          サブタブ（非ホーム）が1つでも存在 → パネル表示
          サブタブがゼロ                    → パネル非表示
        show_home_in_tabs=True の場合：
          常に表示（タブが存在する限り）
        """
        if self._show_home_tab:
            visible = self._tab_list.count() > 0
        else:
            # ホームタブ以外のタブ数を数える
            sub_count = sum(
                1 for i in range(self._tab_list.count())
                if self._tab_list.item(i) is not self._home_item
            )
            visible = sub_count > 0

        self._tab_panel.setVisible(visible)

    # ──────────────────────────────────────
    # タブイベント
    # ──────────────────────────────────────

    def _on_tab_changed(self, current: _TabItem, previous):
        if current is None:
            return
        # コンテナ内の既存ウィジェットをデタッチ
        for i in reversed(range(self._web_layout.count())):
            w = self._web_layout.itemAt(i).widget()
            if w:
                self._web_layout.removeWidget(w)
                w.setParent(None)  # type: ignore[arg-type]

        self._web_layout.addWidget(current.web_view)
        current.web_view.show()
        if self._url_bar:
            self._url_bar.setText(current.web_view.url().toString())
        self._progress.setValue(0)
        self.setWindowTitle(current.web_view.title() or APP_NAME)

    def _on_tabs_reordered(self, *_):
        for i in range(self._tab_list.count()):
            item = self._tab_list.item(i)
            if isinstance(item, _TabItem):
                self._tab_list.setItemWidget(item, item.widget)

    # ──────────────────────────────────────
    # WebView イベント
    # ──────────────────────────────────────

    def _on_title_changed(self, view: QWebEngineView, title: str):
        for i in range(self._tab_list.count()):
            item = self._tab_list.item(i)
            if isinstance(item, _TabItem) and item.web_view is view:
                item.widget.set_title(title or "…")
                if self._tab_list.currentItem() is item:
                    self.setWindowTitle(title or APP_NAME)
                break

    def _on_url_changed(self, view: QWebEngineView, url: QUrl):
        current = self._tab_list.currentItem()
        if isinstance(current, _TabItem) and current.web_view is view:
            if self._url_bar:
                self._url_bar.setText(url.toString())

    def _on_load_start(self, view: QWebEngineView):
        current = self._tab_list.currentItem()
        if isinstance(current, _TabItem) and current.web_view is view:
            self._progress.setValue(10)

    def _on_load_finish(self, view: QWebEngineView, ok: bool):
        current = self._tab_list.currentItem()
        if isinstance(current, _TabItem) and current.web_view is view:
            self._progress.setValue(100)
            QTimer.singleShot(400, lambda: self._progress.setValue(0))

        if not self._is_home_view(view):
            return

        url_str = view.url().toString()
        fell_blank = url_str in ("about:blank", "") and not self._home_url.startswith("about:")

        if ok and not fell_blank:
            # 正常に読み込めた → バックオフをリセット
            self._reset_retry_delay()
            return

        # 読み込み失敗(DNS/接続エラー等) または about:blank に落ちた場合 → 再試行
        # loadFinishedのokだけを見ると about:blank への遷移自体は"成功"扱いになるため、
        # fell_blankも合わせて判定する。
        delay = self._retry_ms
        reason = "load failed" if not ok else "fell back to about:blank"
        _log("warn", f"[FSK] Home {reason} — retrying in {delay} ms")
        QTimer.singleShot(delay, lambda: view.setUrl(QUrl(self._home_url)))
        self._bump_retry_delay()

    def _on_load_progress(self, view: QWebEngineView, p: int):
        current = self._tab_list.currentItem()
        if isinstance(current, _TabItem) and current.web_view is view and 0 < p < 100:
            self._progress.setValue(p)

    # ──────────────────────────────────────
    # ナビゲーション
    # ──────────────────────────────────────

    def _current_view(self) -> QWebEngineView | None:
        item = self._tab_list.currentItem()
        if isinstance(item, _TabItem):
            return item.web_view
        return None

    def _go_back(self):
        wv = self._current_view()
        if wv:
            wv.back()

    def _go_forward(self):
        wv = self._current_view()
        if wv:
            wv.forward()

    def _reload(self):
        wv = self._current_view()
        if wv:
            wv.reload()

    def _go_home(self):
        """ホームタブを選択する。"""
        if self._home_item is not None:
            self._tab_list.setCurrentItem(self._home_item)

    def _navigate_from_bar(self):
        if not self._url_bar:
            return
        text = self._url_bar.text().strip()
        if not text:
            return
        url = self._resolve_url(text)
        wv = self._current_view()
        if wv:
            wv.setUrl(QUrl(url))

    @staticmethod
    def _resolve_url(text: str) -> str:
        if re.match(r'^[a-zA-Z][\w+\-.]*://', text):
            return text
        if re.match(r'^(www\.|\d{1,3}\.)', text) or (
            '.' in text and ' ' not in text and not text.startswith('.')
        ):
            return "https://" + text
        return "https://www.google.com/search?q=" + quote_plus(text)

    # ──────────────────────────────────────
    # タブ切り替え
    # ──────────────────────────────────────

    def _next_tab(self):
        n = self._tab_list.count()
        if n > 1:
            self._tab_list.setCurrentRow((self._tab_list.currentRow() + 1) % n)

    def _prev_tab(self):
        n = self._tab_list.count()
        if n > 1:
            self._tab_list.setCurrentRow((self._tab_list.currentRow() - 1) % n)

    # ──────────────────────────────────────
    # 全画面
    # ──────────────────────────────────────

    def _handle_fullscreen(self, request):
        request.accept()

    # ──────────────────────────────────────
    # ダウンロード（ページ内リンクによるファイル）
    # ──────────────────────────────────────

    def _on_download(self, download):
        url = download.url()
        allowed = CONFIG.get("downloads", {}).get("allowed_domains", [])
        if _host_allowed(url.host(), allowed):
            download.accept()
            _log("info", f"[FSK] Download allowed: {url.toString()}")
        else:
            download.cancel()
            _log("info", f"[FSK] Download blocked (domain not in allowlist): {url.toString()}")

    # ──────────────────────────────────────
    # ハードリスタート（プロセス完全再起動）
    # ──────────────────────────────────────

    def _setup_restart_watchdog(self):
        """
        kiosk.restart_interval_hours が設定されていれば、定期的に
        (必要ならkiosk.restart_atで指定した時刻に合わせて)
        アプリを丸ごと再起動するウォッチドッグを起動する。
        メモリリーク等、アプリ内の対処では防げない劣化を定期リセットで解消するための機能。
        """
        hours = _cfg("kiosk", "restart_interval_hours")
        try:
            hours = float(hours)
        except (TypeError, ValueError):
            hours = 0

        if hours <= 0:
            _log("info", "[FSK] Hard restart watchdog: disabled (restart_interval_hours <= 0)")
            self._restart_interval_ms = 0
            return

        self._restart_interval_ms = int(hours * 3600 * 1000)
        self._restart_at = str(_cfg("kiosk", "restart_at") or "").strip()
        self._app_start_time = QDateTime.currentDateTime()

        self._restart_check_timer = QTimer(self)
        self._restart_check_timer.timeout.connect(self._check_restart_schedule)
        self._restart_check_timer.start(60_000)  # 1分間隔でチェック

        msg = f"[FSK] Hard restart watchdog enabled: every {hours}h"
        if self._restart_at:
            msg += f", aligned to {self._restart_at}"
        _log("info", msg)

    def _check_restart_schedule(self):
        now = QDateTime.currentDateTime()
        elapsed_ms = self._app_start_time.msecsTo(now)

        if elapsed_ms < self._restart_interval_ms:
            return  # まだ最低経過時間に達していない

        if self._restart_at:
            try:
                hh, mm = (int(x) for x in self._restart_at.split(":", 1))
            except ValueError:
                _log("warn", f"[FSK][WARN] kiosk.restart_at の形式が不正です: {self._restart_at!r}")
                self._restart_at = ""  # 以後は経過時間のみで判定
                return
            target_time = QTime(hh, mm)
            if now.time() < target_time:
                return  # 指定時刻にまだ達していない
        _request_restart(f"interval {self._restart_interval_ms}ms elapsed"
                          + (f", scheduled at {self._restart_at}" if self._restart_at else ""))

    # ──────────────────────────────────────
    # 終了処理
    # ──────────────────────────────────────

    def closeEvent(self, event):
        _log("info", "[FSK] Closing.")
        event.accept()


# ─────────────────────────────────────────────
# ハードリスタート（プロセス完全再起動）
# ─────────────────────────────────────────────

_restart_requested = False


def _request_restart(reason: str = ""):
    """
    アプリを正常終了させたうえで、プロセスを丸ごと立ち上げ直す。
    強制killではなく必ずQtの正常終了経路(app.quit())を通すことで、
    Cookie/永続ストレージの破損を防ぐ。実際のプロセス置き換えは
    main() 側で app.exec() が返った後に行う。
    """
    global _restart_requested
    if _restart_requested:
        return
    _restart_requested = True
    _log("info", f"[FSK] Hard restart requested ({reason}) — shutting down gracefully")
    app = QApplication.instance()
    if app is not None:
        app.quit()


def _do_hard_restart():
    """os.execv で自プロセスを置き換える。フラグ注入前の素のargvを使う。"""
    _log("info", "[FSK] Restarting process now...")
    appimage_path = os.environ.get("APPIMAGE")
    if appimage_path:
        os.execv(appimage_path, [appimage_path] + _ORIGINAL_ARGV[1:])
    elif getattr(sys, "frozen", False):
        os.execv(sys.executable, [sys.executable] + _ORIGINAL_ARGV[1:])
    else:
        os.execv(sys.executable, [sys.executable] + _ORIGINAL_ARGV)


# ─────────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────────

def main():
    _log("info", f"Home URL : {_cfg('browser', 'home_url')}")
    _log("info", f"Config   : {_CONFIG_PATH}")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    window = SignageBrowser()
    window.show()

    app.exec()

    if _restart_requested:
        _do_hard_restart()
        return  # execvが成功すればここには到達しない

    sys.exit(0)


if __name__ == "__main__":
    main()
