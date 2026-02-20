"""Web blog-style section generators."""

from src.web_sections.abstract import generate_abstract
from src.web_sections.discussion import generate_discussion
from src.web_sections.introduction import generate_introduction
from src.web_sections.methods import generate_methods
from src.web_sections.results import generate_results

__all__ = [
    "generate_abstract",
    "generate_introduction",
    "generate_methods",
    "generate_results",
    "generate_discussion",
]
