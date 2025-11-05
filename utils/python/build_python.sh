#!/usr/bin/env bash
set -euo pipefail

# Usage: ./install_python_from_source.sh 3.14.0
# This will install into ~/Python/3.14.0

 if [[ $# -ne 1  ]]; then
    echo "Usage: $0 <python-version>"
    echo "Example: $0 3.14.0"
    exit 1
fi

PYVER="$1"
PREFIX="$HOME/Python/$PYVER"
SRC_DIR="$HOME/Downloads/Python-$PYVER"
TARBALL="Python-$PYVER.tgz"
URL="https://www.python.org/ftp/python/$PYVER/$TARBALL"

echo "Installing build dependencies..."
sudo dnf -y groupinstall "Development Tools"
sudo dnf -y install \
    zlib-devel \
    bzip2-devel \
    libffi-devel \
    xz-devel \
    ncurses-devel \
    readline-devel \
    sqlite-devel \
    openssl-devel \
    tk-devel \
    gdbm-devel \
    libuuid-devel \
    wget \
    make \
    gcc

echo "Downloading Python $PYVER..."
mkdir -p "$HOME/Downloads"
cd "$HOME/Downloads"

if [[ ! -f "$TARBALL"  ]]; then
    wget -q "$URL" -O "$TARBALL"
    else
    echo "Tarball already exists: $TARBALL"
fi

echo "Extracting..."
rm -rf "$SRC_DIR"
tar -xf "$TARBALL"
cd "$SRC_DIR"

echo "Configuring build..."
./configure \
    --prefix="$PREFIX" \
    --enable-optimizations \
    --with-ensurepip=install

echo "Building (this may take a while)..."
make -j"$(nproc)"

echo "Installing to $PREFIX..."
make install

echo "Verifying installation..."
"$PREFIX/bin/python3" --version
"$PREFIX/bin/python3" -m ensurepip
"$PREFIX/bin/python3" -m pip --version

echo "Done!"
echo "Python $PYVER installed at: $PREFIX"
echo "To use it, add this to your PATH:"
echo "  export PATH=\"$PREFIX/bin:\$PATH\""

