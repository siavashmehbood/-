"""Compatibility facade for versioned local brain snapshots."""
from .versioning import BrainVersionStore

VersionedBrain = BrainVersionStore

__all__ = ["BrainVersionStore", "VersionedBrain"]
