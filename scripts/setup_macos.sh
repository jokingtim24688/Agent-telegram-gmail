#!/usr/bin/env bash
# Loupe setup for macOS on Apple Silicon (M1–M4). Run from the repo root:
#   bash scripts/setup_macos.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
desktop="$root/desktop"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "This Mac isn't Apple Silicon. Ollama will run on the CPU only, which is slow for vision models."
fi

if ! command -v brew >/dev/null; then
  echo "Install Homebrew first: https://brew.sh" && exit 1
fi
command -v python3.12 >/dev/null || brew install python@3.12
command -v ollama >/dev/null || brew install --cask ollama
open -a Ollama || true   # starts the Ollama server in the menu bar

echo "Creating the Python environment in desktop/.venv ..."
python3.12 -m venv "$desktop/.venv"
py="$desktop/.venv/bin/python"
"$py" -m pip install --upgrade pip
"$py" -m pip install -r "$desktop/requirements.txt" platformio

if [[ ! -f "$desktop/.env" ]]; then
  cp "$desktop/.env.example" "$desktop/.env"
  echo "Created desktop/.env. Fill it in before the next step."
fi

model="$(cd "$desktop" && "$py" -c 'from glasses_agent import hardware as h; print(h.recommend(h.detect()))')"
echo "Best model for this Mac: $model. Downloading it..."
sleep 3   # give the Ollama app a moment to start its server
ollama pull "$model"

cat <<EOF

Done. Next:
  1. Fill in desktop/.env
  2. cd desktop && .venv/bin/python -m glasses_agent login
  3. .venv/bin/python -m glasses_agent        (opens the dashboard)
EOF
