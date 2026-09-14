#!/usr/bin/env bash
# Rasterize a reviewed WPS/LibreOffice PDF inside the production workspace.
set -euo pipefail
TASK_DIR=$(cd "$(dirname "$0")/.." && pwd)
export TMPDIR="$TASK_DIR/.runtime/tmp"
PDF_INPUT=$(realpath "$1")
OUTPUT_DIR=$(realpath -m "$2")
case "$PDF_INPUT" in "$TASK_DIR"/*) ;; *) echo 'PDF must be inside presentation-production' >&2; exit 1;; esac
case "$OUTPUT_DIR" in "$TASK_DIR"/*) ;; *) echo 'Output must be inside presentation-production' >&2; exit 1;; esac
mkdir -p "$TMPDIR" "$OUTPUT_DIR"
pdftoppm -scale-to 1600 -png "$PDF_INPUT" "$OUTPUT_DIR/slide" > "$TASK_DIR/.runtime/render.log" 2>&1
