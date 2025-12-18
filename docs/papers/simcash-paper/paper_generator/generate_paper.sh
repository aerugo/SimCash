#!/bin/bash
# Generate SimCash paper with PDF compilation
#
# This script automatically installs tectonic if no LaTeX compiler is found,
# then generates the paper with PDF output.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to install tectonic
install_tectonic() {
    echo "Installing tectonic (lightweight LaTeX compiler, ~70MB)..."
    echo ""

    # Create local bin directory for tectonic
    LOCAL_BIN="$SCRIPT_DIR/.bin"
    mkdir -p "$LOCAL_BIN"

    # Download tectonic to local bin directory
    if (cd "$LOCAL_BIN" && curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh); then
        echo ""
        echo "Tectonic installed successfully to $LOCAL_BIN"

        # Add to PATH for this session
        export PATH="$LOCAL_BIN:$PATH"

        # Verify installation
        if command -v tectonic &> /dev/null; then
            return 0
        fi
    fi

    echo "Error: Failed to install tectonic automatically."
    echo ""
    echo "Please install manually:"
    echo "  curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh"
    echo ""
    echo "Or via cargo:"
    echo "  cargo install tectonic"
    return 1
}

# Add local bin to PATH if it exists (from previous install)
if [ -d "$SCRIPT_DIR/.bin" ]; then
    export PATH="$SCRIPT_DIR/.bin:$PATH"
fi

# Check for LaTeX compiler, auto-install tectonic if missing
if ! command -v tectonic &> /dev/null && ! command -v pdflatex &> /dev/null; then
    echo "No LaTeX compiler found."
    echo ""

    # Auto-install tectonic
    if ! install_tectonic; then
        echo ""
        echo "Alternatively, generate LaTeX only (no PDF):"
        echo "  uv run python -m src.cli --config config.yaml --output-dir output/ --skip-pdf"
        exit 1
    fi
    echo ""
fi

# Show which compiler will be used
if command -v tectonic &> /dev/null; then
    echo "Using tectonic for PDF compilation"
elif command -v pdflatex &> /dev/null; then
    echo "Using pdflatex for PDF compilation"
fi

# Generate paper with PDF compilation
uv run python -m src.cli --config config.yaml --output-dir output/

echo ""
echo "Done! Output files:"
ls -la output/paper.*
