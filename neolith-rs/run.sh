#!/bin/sh
# Run Neolith.
#   ./run.sh          native desktop app
#   ./run.sh web      web app on a local dev server (needs trunk)
#   ./run.sh test     run the test suite
set -e
cd "$(dirname "$0")"

command -v cargo >/dev/null 2>&1 || { echo "error: cargo not found; install Rust from https://rustup.rs" >&2; exit 1; }

# Rebuild assets/world.bin with the hex-map pipeline if it is missing.
if [ ! -f assets/world.bin ]; then
    echo "assets/world.bin is missing; building it with 'make -C .. maps'"
    make -C .. maps
fi

case "${1:-native}" in
    native)
        [ $# -gt 0 ] && shift
        exec cargo run --release -p neolith-app -- "$@"
        ;;
    web)
        command -v trunk >/dev/null 2>&1 || { echo "error: trunk not found; install it with: cargo install trunk --locked" >&2; exit 1; }
        rustup target list --installed 2>/dev/null | grep -q wasm32-unknown-unknown || rustup target add wasm32-unknown-unknown
        exec trunk serve --open
        ;;
    test)
        exec cargo test --workspace
        ;;
    *)
        echo "usage: ./run.sh [native [world.bin] | web | test]" >&2
        exit 2
        ;;
esac
