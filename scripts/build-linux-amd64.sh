#!/usr/bin/env bash
set -e

VERSION="${1:?バージョン番号を指定してください（例: 1.0.2.0）}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APPDIR="$ROOT_DIR/FSKit.AppDir"
BIN_DEST="$APPDIR/usr/bin/FSKit"
APPIMAGETOOL="$SCRIPT_DIR/appimagetool-x86_64.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
NUITKA_OUTPUT="$ROOT_DIR/FSKit.bin"

APP_NAME="freesignagekit"
BIN_NAME="FSKit"
INSTALL_PREFIX="/opt/FreeSignageKit"
MAINTAINER="ABATBeliever <abatbeliever@outlook.jp>"
URL="https://abatbeliever.net"
LICENSE="LGPL"
DESCRIPTION="Free Signage Kit"

# このスクリプト自身のファイル名でターゲットアーキテクチャを固定
ARCH="amd64"
RPM_ARCH="x86_64"
APPIMAGE_ARCH="x86_64"
APPIMAGE_NAME="FSKit-x64.AppImage"

DIST_DIR="$ROOT_DIR/${ARCH}-bin"
DIST_APPIMAGE="$DIST_DIR/AppImage"
DIST_DEB="$DIST_DIR/deb"
DIST_RPM="$DIST_DIR/rpm"
DIST_TARBALL="$DIST_DIR/tarball"
mkdir -p "$DIST_APPIMAGE" "$DIST_DEB" "$DIST_RPM" "$DIST_TARBALL"

APPIMAGE_OUTPUT="$DIST_APPIMAGE/$APPIMAGE_NAME"

LICENSE_FILE="$ROOT_DIR/LICENSE"
RELEASE_NOTE_FILE="$ROOT_DIR/ReleaseNote.txt"
README_FILE="$ROOT_DIR/README.TXT"
for _doc in "$LICENSE_FILE" "$RELEASE_NOTE_FILE" "$README_FILE"; do
    if [ ! -f "$_doc" ]; then
        echo "[ERROR] 同梱予定のドキュメントが見つかりません: $_doc" >&2
        exit 1
    fi
done

copy_release_docs() {
    local dest="$1"
    cp "$LICENSE_FILE" "$dest/LICENSE"
    cp "$RELEASE_NOTE_FILE" "$dest/ReleaseNote.txt"
    cp "$README_FILE" "$dest/README.TXT"
}

echo "======================================================================"
echo "[INFO] Free Signage Kit Linux ビルド開始 (version=$VERSION, arch=$ARCH)"
echo "======================================================================"
echo "[INFO] SCRIPT_DIR : $SCRIPT_DIR"
echo "[INFO] ROOT_DIR   : $ROOT_DIR"
echo "[INFO] APPDIR     : $APPDIR"
echo "[INFO] 出力先     : $DIST_DIR/{AppImage,deb,rpm,tarball}/"

echo ""
echo "---- [1/5] AppImageTool の準備 ----"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "[INFO] AppImageTool が無いため取得します: $APPIMAGETOOL_URL"
    curl -fsSL "$APPIMAGETOOL_URL" -o "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
    echo "[INFO] 取得完了: $APPIMAGETOOL"
else
    echo "[INFO] AppImageTool は取得済みです: $APPIMAGETOOL"
fi

echo ""
echo "---- [2/5] Nuitkaでバイナリをビルド中...（数分かかります）----"
cd "$ROOT_DIR"
uv run nuitka \
    --standalone --onefile \
    --enable-plugin=pyside6 \
    --company-name=ABATBeliever \
    --product-name="Free Signage Kit" \
    --file-description="Free Signage Kit" \
    FSKit.py
echo "[INFO] Nuitkaビルド完了"

if [ ! -f "$NUITKA_OUTPUT" ]; then
    echo "[ERROR] Failed to find FSKit.bin: $NUITKA_OUTPUT" >&2
    exit 1
fi
echo "[INFO] ビルド成果物: $NUITKA_OUTPUT ($(du -h "$NUITKA_OUTPUT" | cut -f1))"

echo ""
echo "---- [3/5] AppImageを作成中... ----"
mkdir -p "$APPDIR/usr/bin"
cp "$NUITKA_OUTPUT" "$BIN_DEST"
chmod +x "$APPDIR/AppRun"
chmod +x "$BIN_DEST"
chmod +x "$APPDIR/app.png"
cd "$ROOT_DIR"
ARCH="$APPIMAGE_ARCH" "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_OUTPUT"
chmod +x "$APPIMAGE_OUTPUT"
echo "[INFO] AppImage: $APPIMAGE_OUTPUT ($(du -h "$APPIMAGE_OUTPUT" | cut -f1))"

DESKTOP_SRC="$(find "$APPDIR" -maxdepth 1 -name '*.desktop' | head -n1 || true)"
ICON_SRC="$APPDIR/app.png"
if [ -z "$DESKTOP_SRC" ] || [ ! -f "$ICON_SRC" ]; then
    echo "[ERROR] FSKit.AppDir に .desktop または app.png が見つかりません" >&2
    exit 1
fi
echo "[INFO] desktop source: $DESKTOP_SRC"
echo "[INFO] icon source   : $ICON_SRC"

cp "$DESKTOP_SRC" "$DIST_APPIMAGE/FreeSignageKit.desktop"
cp "$ICON_SRC" "$DIST_APPIMAGE/FreeSignageKit.png"
copy_release_docs "$DIST_APPIMAGE"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
echo "[INFO] work dir: $WORK_DIR"

echo ""
echo "---- [4/5] tarball を作成中... ----"
TARBALL_ROOT="$WORK_DIR/tarball/${APP_NAME}-${VERSION}"
mkdir -p "$TARBALL_ROOT"
cp "$NUITKA_OUTPUT" "$TARBALL_ROOT/$BIN_NAME"
chmod +x "$TARBALL_ROOT/$BIN_NAME"
cp "$DESKTOP_SRC" "$TARBALL_ROOT/freesignagekit.desktop"
cp "$ICON_SRC" "$TARBALL_ROOT/freesignagekit.png"

cat > "$TARBALL_ROOT/install.sh" <<INSTALL_EOF
#!/usr/bin/env bash
set -e
HERE="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
BIN_NAME="$BIN_NAME"

if [ "\${1:-}" = "--user" ]; then
    PREFIX="\$HOME/.local/share/FreeSignageKit"
    BIN_DIR="\$HOME/.local/bin"
    APPS_DIR="\$HOME/.local/share/applications"
    ICON_DIR="\$HOME/.local/share/icons/hicolor/256x256/apps"
else
    if [ "\$(id -u)" -ne 0 ]; then
        echo "システム全体へのインストールには root 権限が必要です。" >&2
        echo "root なしでインストールする場合は ./install.sh --user を使ってください。" >&2
        exit 1
    fi
    PREFIX="/opt/FreeSignageKit"
    BIN_DIR="/usr/local/bin"
    APPS_DIR="/usr/share/applications"
    ICON_DIR="/usr/share/icons/hicolor/256x256/apps"
fi

mkdir -p "\$PREFIX" "\$BIN_DIR" "\$APPS_DIR" "\$ICON_DIR"
cp "\$HERE/\$BIN_NAME" "\$PREFIX/\$BIN_NAME"
chmod +x "\$PREFIX/\$BIN_NAME"
ln -sf "\$PREFIX/\$BIN_NAME" "\$BIN_DIR/freesignagekit"

sed "s#^Exec=.*#Exec=\$PREFIX/\$BIN_NAME %U#; s#^Icon=.*#Icon=\$ICON_DIR/freesignagekit.png#" \
    "\$HERE/freesignagekit.desktop" > "\$APPS_DIR/freesignagekit.desktop"
cp "\$HERE/freesignagekit.png" "\$ICON_DIR/freesignagekit.png"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "\$APPS_DIR" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f "\$(dirname "\$(dirname "\$ICON_DIR")")" || true

echo "==> 完了。'freesignagekit' コマンド、またはアプリ一覧から起動できます。"
INSTALL_EOF
chmod +x "$TARBALL_ROOT/install.sh"

cat > "$TARBALL_ROOT/uninstall.sh" <<UNINSTALL_EOF
#!/usr/bin/env bash
set -e
if [ "\${1:-}" = "--user" ]; then
    PREFIX="\$HOME/.local/share/FreeSignageKit"
    rm -f "\$HOME/.local/bin/freesignagekit"
    rm -f "\$HOME/.local/share/applications/freesignagekit.desktop"
    rm -f "\$HOME/.local/share/icons/hicolor/256x256/apps/freesignagekit.png"
else
    if [ "\$(id -u)" -ne 0 ]; then
        echo "システム全体からのアンインストールには root 権限が必要です。" >&2
        exit 1
    fi
    PREFIX="/opt/FreeSignageKit"
    rm -f /usr/local/bin/freesignagekit
    rm -f /usr/share/applications/freesignagekit.desktop
    rm -f /usr/share/icons/hicolor/256x256/apps/freesignagekit.png
fi
rm -rf "\$PREFIX"
echo "==> アンインストール完了"
UNINSTALL_EOF
chmod +x "$TARBALL_ROOT/uninstall.sh"

TARBALL_OUT="$DIST_TARBALL/${APP_NAME}-${VERSION}-linux-${ARCH}.tar.xz"
tar -C "$WORK_DIR/tarball" -cJf "$TARBALL_OUT" "${APP_NAME}-${VERSION}"
echo "[INFO] tarball: $TARBALL_OUT ($(du -h "$TARBALL_OUT" | cut -f1))"
copy_release_docs "$DIST_TARBALL"

echo ""
echo "---- [5/5] .deb / .rpm を作成中... ----"
PKG_ROOT="$WORK_DIR/pkgroot"
mkdir -p "$PKG_ROOT$INSTALL_PREFIX"
cp "$NUITKA_OUTPUT" "$PKG_ROOT$INSTALL_PREFIX/$BIN_NAME"
chmod +x "$PKG_ROOT$INSTALL_PREFIX/$BIN_NAME"

mkdir -p "$PKG_ROOT/usr/share/applications"
sed "s#^Exec=.*#Exec=$INSTALL_PREFIX/$BIN_NAME %U#; s#^Icon=.*#Icon=$APP_NAME#" \
    "$DESKTOP_SRC" > "$PKG_ROOT/usr/share/applications/freesignagekit.desktop"

mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps"
cp "$ICON_SRC" "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"

mkdir -p "$PKG_ROOT/usr/bin"
ln -sf "$INSTALL_PREFIX/$BIN_NAME" "$PKG_ROOT/usr/bin/$APP_NAME"

DEB_ROOT="$WORK_DIR/deb_root"
cp -a "$PKG_ROOT" "$DEB_ROOT"
mkdir -p "$DEB_ROOT/DEBIAN"
INSTALLED_SIZE="$(du -sk "$PKG_ROOT" | cut -f1)"
cat > "$DEB_ROOT/DEBIAN/control" <<EOF
Package: $APP_NAME
Version: $VERSION
Section: graphics
Priority: optional
Architecture: $ARCH
Installed-Size: $INSTALLED_SIZE
Maintainer: $MAINTAINER
Homepage: $URL
Description: $DESCRIPTION
EOF
DEB_OUT="$DIST_DEB/${APP_NAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$DEB_ROOT" "$DEB_OUT"
echo "[INFO] .deb: $DEB_OUT ($(du -h "$DEB_OUT" | cut -f1))"
copy_release_docs "$DIST_DEB"

RPM_TOPDIR="$WORK_DIR/rpmbuild"
mkdir -p "$RPM_TOPDIR"/{SPECS,RPMS,BUILD,BUILDROOT,SOURCES,SRPMS}
SPEC="$RPM_TOPDIR/SPECS/${APP_NAME}.spec"
cat > "$SPEC" <<EOF
Name: $APP_NAME
Version: $VERSION
Release: 1
Summary: $DESCRIPTION
License: $LICENSE
URL: $URL
BuildArch: $RPM_ARCH

%description
$DESCRIPTION

%install
mkdir -p %{buildroot}
cp -a $PKG_ROOT/. %{buildroot}/

%files
$INSTALL_PREFIX/$BIN_NAME
/usr/bin/$APP_NAME
/usr/share/applications/freesignagekit.desktop
/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png
EOF

rpmbuild -bb --define "_topdir $RPM_TOPDIR" "$SPEC" > "$WORK_DIR/rpmbuild.log" 2>&1
BUILT_RPM="$(find "$RPM_TOPDIR/RPMS" -name '*.rpm' | head -n1)"
if [ -z "$BUILT_RPM" ]; then
    echo "[ERROR] .rpm の生成に失敗しました。ログ: $WORK_DIR/rpmbuild.log" >&2
    cat "$WORK_DIR/rpmbuild.log" >&2
    exit 1
fi
RPM_OUT="$DIST_RPM/$(basename "$BUILT_RPM")"
cp "$BUILT_RPM" "$RPM_OUT"
echo "[INFO] .rpm: $RPM_OUT ($(du -h "$RPM_OUT" | cut -f1))"
copy_release_docs "$DIST_RPM"

echo ""
echo "======================================================================"
echo "[INFO] Build Success! 生成物一覧 ($DIST_DIR):"
echo "  - AppImage/$(basename "$APPIMAGE_OUTPUT")"
echo "  - tarball/$(basename "$TARBALL_OUT")"
echo "  - deb/$(basename "$DEB_OUT")"
echo "  - rpm/$(basename "$RPM_OUT")"
echo "======================================================================"
