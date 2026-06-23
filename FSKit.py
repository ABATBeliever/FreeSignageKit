"""
FreeSignageKit
Copyright (C) 2026 ABATBeliever
Under LGPL v3

組み込みサイネージ向け軽量ブラウザ。
config.toml を同ディレクトリに置いて設定する。
"""

APP_VERSION = "v0.2.0"
APP_NAME    = f"FreeSignageKit {APP_VERSION}"

import sys
import os
import re
import tomllib
from pathlib import Path
from urllib.parse import quote_plus

print(f"\n      mmmmmmmm     mmmm      mm   mmm    ##         ")
print(f"     ##         m#m    #    ##  ##              ##  ")
print(f"    ##         ##m         ##m##     ####    #######")
print(f"   #######      ####m     #####       ##      ##    ")
print(f"  ##               ##    ##  ##m     ##      ##     ")
print(f" ##         #mmmmm#+    ##   ##m mmm##mmm   ##mmm   \n")
print("Free Signage Kit")
print("Copyright (C) 2026 ABATBeliever. Under LGPL v3\n")

# ─────────────────────────────────────────────
# config.toml 読み込み
# ─────────────────────────────────────────────

_EXE_DIR = Path(sys.executable).parent.resolve() if getattr(sys, "frozen", False) \
           else Path(__file__).parent.resolve()

_CONFIG_PATH = _EXE_DIR / "config.toml"

_DEFAULT_CONFIG: dict = {
    "browser": {
        "home_url":           "http://localhost",
        "fullscreen":         True,
        "show_home_in_tabs":  False,           # ホームタブを縦タブに載せるか
        "home_retry_ms":      2000,            # ホームが閉じた/消えた後の再起動待ち(ms)
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
    },
    "chromium": {
        "extra_flags":        "",              # スペース区切りで追加フラグ
        "vaapi":              False,
        "gpu_rasterization":  False,
        "zero_copy":          False,
        "autoplay_policy":    True,            # --autoplay-policy=no-user-gesture-required
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_config() -> dict:
    cfg = _DEFAULT_CONFIG
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "rb") as f:
                user = tomllib.load(f)
            cfg = _deep_merge(cfg, user)
            print(f"[FSK] config.toml loaded: {_CONFIG_PATH}")
        except Exception as e:
            print(f"[FSK][WARN] config.toml parse error: {e}  — using defaults", file=sys.stderr)
    else:
        print(f"[FSK] config.toml not found at {_CONFIG_PATH}, using defaults")
    return cfg


CONFIG = _load_config()


def _cfg(*keys):
    """CONFIG から . 区切りでネストした値を取得する。"""
    v = CONFIG
    for k in keys:
        v = v[k]
    return v


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
        print(f"[FSK] Chromium flags: {' '.join(flags)}")


_apply_chromium_flags()

# ─────────────────────────────────────────────
# Qt imports
# ─────────────────────────────────────────────

from PySide6.QtCore    import Qt, QUrl, QTimer, Signal
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

class _Page(QWebEnginePage):
    """
    新しいタブ/ウィンドウ要求を親ブラウザに委譲するページ。
    """

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.featurePermissionRequested.connect(self._deny_permission)

    def _deny_permission(self, url, feature):
        self.setFeaturePermission(url, feature, QWebEnginePage.PermissionDeniedByUser)

    def createWindow(self, window_type):
        """target="_blank" / window.open() → 必ず新しいタブで開く"""
        browser = self._find_browser()
        if browser:
            view = browser.add_tab("about:blank", activate=True, _return_view=True)
            if view is not None:
                return view.page()
        return super().createWindow(window_type)

    def _find_browser(self):
        w = self.parent()
        while w and not isinstance(w, SignageBrowser):
            w = w.parent()
        return w


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
        self._retry_ms:       int  = int(_cfg("browser", "home_retry_ms"))

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

        print(f"[FSK] Home tab opened: {self._home_url}")

    def _schedule_home_reopen(self):
        """ホームが閉じられた後、retry_ms 後に再起動するタイマーをセット。"""
        print(f"[FSK] Home tab lost — reopening in {self._retry_ms} ms")
        QTimer.singleShot(self._retry_ms, self._open_home)

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
        print(f"[FSK] New tab: {url}")

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
        item.web_view.deleteLater()

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
        page = _Page(self.profile, view)
        page.fullScreenRequested.connect(self._handle_fullscreen)
        view.setPage(page)

        view.titleChanged.connect(lambda t: self._on_title_changed(view, t))
        view.urlChanged.connect(lambda u: self._on_url_changed(view, u))
        view.loadStarted.connect(lambda: self._on_load_start(view))
        view.loadFinished.connect(lambda: self._on_load_finish(view))
        view.loadProgress.connect(lambda p: self._on_load_progress(view, p))

        if bool(_cfg("kiosk", "disable_context_menu")):
            view.setContextMenuPolicy(Qt.NoContextMenu)

        return view

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

    def _on_load_finish(self, view: QWebEngineView):
        current = self._tab_list.currentItem()
        if isinstance(current, _TabItem) and current.web_view is view:
            self._progress.setValue(100)
            QTimer.singleShot(400, lambda: self._progress.setValue(0))

        # ホームがクラッシュ・エラー等でabout:blankになっていたら再起動
        if self._is_home_view(view):
            url_str = view.url().toString()
            if url_str in ("about:blank", "") and not self._home_url.startswith("about:"):
                print(f"[FSK] Home fell to about:blank — reloading {self._home_url}")
                QTimer.singleShot(self._retry_ms, lambda: view.setUrl(QUrl(self._home_url)))

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
        # サイネージ用途ではダウンロードはキャンセルする
        download.cancel()
        print(f"[FSK] Download blocked: {download.url().toString()}")

    # ──────────────────────────────────────
    # 終了処理
    # ──────────────────────────────────────

    def closeEvent(self, event):
        print("[FSK] Closing.")
        event.accept()


# ─────────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────────

def main():
    print(f"Home URL : {_cfg('browser', 'home_url')}")
    print(f"Config   : {_CONFIG_PATH}")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    window = SignageBrowser()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
