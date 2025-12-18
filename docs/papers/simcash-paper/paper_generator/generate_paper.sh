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

    # Use the official tectonic installer
    if curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh; then
        echo ""
        echo "Tectonic installed successfully!"

        # Add to PATH for this session if installed to ~/.cargo/bin
        if [ -f "$HOME/.cargo/bin/tectonic" ]; then
            export PATH="$HOME/.cargo/bin:$PATH"
        fi

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
