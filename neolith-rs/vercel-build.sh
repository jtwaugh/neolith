#!/bin/sh
# Vercel build: installs Rust + trunk in the build image, then builds the WASM app into dist/.
set -eu
export PATH="$HOME/.cargo/bin:$PATH"
if ! command -v cargo >/dev/null 2>&1; then
    curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --target wasm32-unknown-unknown
fi
rustup target add wasm32-unknown-unknown
if ! command -v trunk >/dev/null 2>&1; then
    curl -fsSL https://github.com/trunk-rs/trunk/releases/download/v0.21.14/trunk-x86_64-unknown-linux-gnu.tar.gz \
        | tar -xz -C "$HOME/.cargo/bin"
fi
trunk build --release
