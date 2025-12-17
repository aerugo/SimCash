#!/bin/bash
# Generate SimCash paper with PDF compilation
#
# This script installs pdflatex (if needed) and generates the paper.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Install pdflatex and required LaTeX packages if not available
if ! command -v pdflatex &> /dev/null; then
    echo "Installing texlive packages..."
    apt-get update && apt-get install -y \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended \
        cm-super
fi

# Generate paper with PDF compilation
uv run python -m src.cli --config config.yaml --output-dir output/

echo ""
echo "Done! Output files:"
ls -la output/paper.*
