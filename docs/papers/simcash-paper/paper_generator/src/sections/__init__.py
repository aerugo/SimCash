"""Section generators for paper content."""

from src.sections.abstract import generate_abstract
from src.sections.appendices import generate_appendices
from src.sections.conclusion import generate_conclusion
from src.sections.discussion import generate_discussion
from src.sections.introduction import generate_introduction
from src.sections.methods import generate_methods
from src.sections.references import generate_references
from src.sections.results import generate_results

__all__ = [
    "generate_abstract",
    "generate_introduction",
    "generate_methods",
    "generate_results",
    "generate_discussion",
    "generate_conclusion",
    "generate_appendices",
    "generate_references",
]
