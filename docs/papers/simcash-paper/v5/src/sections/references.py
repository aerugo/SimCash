"""References section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_references(provider: DataProvider) -> str:
    """Generate the references section with bibliography.

    Args:
        provider: DataProvider instance (unused but required for interface consistency)

    Returns:
        LaTeX string for the references section
    """
    # Provider is unused but kept for interface consistency
    _ = provider

    return r"""
\begin{thebibliography}{9}

\bibitem{castro2013}
Castro, P., Cramton, P., Malec, D., \& Schwierz, C. (2013).
\textit{Payment Timing Games in RTGS Systems}.
Working Paper, Bank of Canada.

\bibitem{martin2010}
Martin, A. \& McAndrews, J. (2010).
Liquidity-saving mechanisms.
\textit{Journal of Monetary Economics}, 57(5), 621--630.

\bibitem{openai2024}
OpenAI (2024).
\textit{GPT-5.2 Technical Report}.
OpenAI Technical Documentation.

\bibitem{bech2008}
Bech, M. L. \& Garratt, R. (2008).
The intraday liquidity management game.
\textit{Journal of Economic Theory}, 109(2), 198--219.

\bibitem{kahn2009}
Kahn, C. M. \& Roberds, W. (2009).
Why pay? An introduction to payments economics.
\textit{Journal of Financial Intermediation}, 18(1), 1--23.

\end{thebibliography}
"""
