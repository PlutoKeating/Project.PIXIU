"""V0.1 temporary contract stand-ins.

foundation/core is not implemented yet. Engine services depend on these
Pydantic models and Mock repositories until Module C freezes core/.
"""

from engine.mocks.models import (
    ConflictRecord,
    Entity,
    Evidence,
    ForgetResult,
    KnowledgeItem,
    Preference,
    PreferenceSnapshot,
    Relation,
)
from engine.mocks.repository import (
    MockConflictRepository,
    MockEntityRepository,
    MockEvidenceRepository,
    MockKnowledgeRepository,
    MockPreferenceRepository,
)

__all__ = [
    "ConflictRecord",
    "Entity",
    "Evidence",
    "ForgetResult",
    "KnowledgeItem",
    "Preference",
    "PreferenceSnapshot",
    "Relation",
    "MockConflictRepository",
    "MockEntityRepository",
    "MockEvidenceRepository",
    "MockKnowledgeRepository",
    "MockPreferenceRepository",
]
