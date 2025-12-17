#!/bin/bash
# Generate SimCash paper with PDF compilation
#
# This script checks for pdflatex and generates the paper.
# If pdflatex is not installed, it provides platform-specific instructions.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for pdflatex and provide platform-specific installation instructions
if ! command -v pdflatex &> /dev/null; then
    echo "Error: pdflatex not found."
    echo ""

    # Detect OS and provide appropriate instructions
    case "$(uname -s)" in
        Darwin)
            echo "On macOS, install MacTeX using Homebrew:"
            echo "  brew install --cask mactex"
            echo ""
            echo "After installation, you may need to restart your terminal"
            echo "or add /Library/TeX/texbin to your PATH:"
            echo "  export PATH=\"/Library/TeX/texbin:\$PATH\""
            ;;
        Linux)
            echo "On Debian/Ubuntu, install texlive:"
            echo "  sudo apt-get update && sudo apt-get install -y \\"
            echo "      texlive-latex-base \\"
            echo "      texlive-latex-recommended \\"
            echo "      texlive-latex-extra \\"
            echo "      texlive-fonts-recommended \\"
            echo "      cm-super"
            echo ""
            echo "On Fedora/RHEL:"
            echo "  sudo dnf install texlive-scheme-medium"
            echo ""
            echo "On Arch Linux:"
            echo "  sudo pacman -S texlive-core texlive-latexextra"
            ;;
        *)
            echo "Please install a LaTeX distribution with pdflatex."
            echo "Common options: TeX Live, MiKTeX"
            ;;
    esac

    echo ""
    echo "Alternatively, generate LaTeX only (no PDF):"
    echo "  uv run python -m src.cli --config config.yaml --output-dir output/ --skip-pdf"
    exit 1
fi

# Generate paper with PDF compilation
uv run python -m src.cli --config config.yaml --output-dir output/

echo ""
echo "Done! Output files:"
ls -la output/paper.*
