#!/bin/bash
# Generate SimCash paper with PDF compilation
#
# This script checks for tectonic (preferred) or pdflatex and generates the paper.
# If neither is installed, it provides installation instructions.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for LaTeX compiler and provide installation instructions if missing
if ! command -v tectonic &> /dev/null && ! command -v pdflatex &> /dev/null; then
    echo "Error: No LaTeX compiler found."
    echo ""
    echo "Install tectonic (recommended, lightweight ~70MB):"
    echo "  curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh"
    echo ""
    echo "Or install via cargo:"
    echo "  cargo install tectonic"
    echo ""
    echo "Alternatively, install pdflatex (larger, ~2-4GB):"

    # Detect OS and provide appropriate pdflatex instructions
    case "$(uname -s)" in
        Darwin)
            echo "  brew install --cask mactex"
            ;;
        Linux)
            echo "  sudo apt-get install texlive-latex-base texlive-latex-recommended texlive-latex-extra"
            ;;
        *)
            echo "  Install TeX Live or MiKTeX"
            ;;
    esac

    echo ""
    echo "Or generate LaTeX only (no PDF):"
    echo "  uv run python -m src.cli --config config.yaml --output-dir output/ --skip-pdf"
    exit 1
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
