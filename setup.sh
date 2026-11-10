#!/usr/bin/env bash
# One-time setup for a fresh workspace: installs the tools and downloads the voice model.
set -e
cd "$(dirname "$0")/pipeline"
pip install --break-system-packages -q kokoro-onnx soundfile pycairo bpy
mkdir -p models out
[ -f models/kokoro.onnx ] || curl -sSL -o models/kokoro.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
[ -f models/voices.bin ]  || curl -sSL -o models/voices.bin  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
echo "setup done"
