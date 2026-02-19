#!/usr/bin/env bash
# daccia.io platform setup - macOS
# Usage: bash setup.sh
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_DIR="$PROJECT_ROOT/platform"

echo "=== daccia.io Platform Setup ==="
echo ""

# 1. Verify prerequisites
if ! command -v brew >/dev/null 2>&1; then
    echo "Error: Homebrew is required. Install from https://brew.sh"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: Python 3 is required."
    exit 1
fi

PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Found Python $PYTHON_VER"

# 2. Install uv (fast Python package manager) if not present
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv package manager..."
    brew install uv
else
    echo "uv already installed"
fi

# 3. Initialize git if not already a repo
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo "Initializing git repository..."
    git -C "$PROJECT_ROOT" init
fi

# 4. Create virtual environment via uv
if [ ! -d "$PLATFORM_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    uv venv "$PLATFORM_DIR/.venv" --python python3
else
    echo "Virtual environment already exists"
fi

# 5. Install dependencies
echo "Installing dependencies..."
VIRTUAL_ENV="$PLATFORM_DIR/.venv" uv pip install -e "$PLATFORM_DIR[dev]"

# 6. Create data directories
mkdir -p "$PLATFORM_DIR/data/style_profiles"
mkdir -p "$PLATFORM_DIR/data/drafts"
mkdir -p "$PLATFORM_DIR/data/published"
mkdir -p "$PLATFORM_DIR/data/research_cache"

# 7. Create .env from template if missing
if [ ! -f "$PLATFORM_DIR/.env" ]; then
    cp "$PLATFORM_DIR/.env.example" "$PLATFORM_DIR/.env"
    echo ""
    echo ">>> ACTION REQUIRED: Edit platform/.env and add your ANTHROPIC_API_KEY"
fi

# 8. Verify installation
echo ""
echo "Verifying installation..."
"$PLATFORM_DIR/.venv/bin/python" -c "import daccia; print('daccia package loaded successfully')"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Activate environment:  source platform/.venv/bin/activate"
echo "Run CLI:               daccia --help"
echo ""
