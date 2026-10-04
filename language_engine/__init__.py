"""Stable language-model boundary for IRAN.

CognitiveSystem owns decisions; language backends only generate language.
"""
from .base import GenerationRequest, GenerationResult, LanguageBackend
from .engine import IranLanguageEngine

__all__ = ["GenerationRequest", "GenerationResult", "LanguageBackend", "IranLanguageEngine"]
