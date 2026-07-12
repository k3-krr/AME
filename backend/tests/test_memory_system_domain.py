"""Domain tests for hybrid memory system classification (Milestone 7 Phase 1)."""

import uuid
from datetime import datetime, timezone

import pytest

from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.domain.memory_system import (
    MemorySystem,
    MEMORY_TYPE_TO_SYSTEM,
    default_memory_system_for_type,
    validate_memory_system_constraints,
    compute_working_memory_expiry,
)


def test_memory_system_enum_values():
    assert MemorySystem.SEMANTIC.value == "Semantic"
    assert MemorySystem.EPISODIC.value == "Episodic"
    assert MemorySystem.PROCEDURAL.value == "Procedural"
    assert MemorySystem.WORKING.value == "Working"


def test_memory_type_to_system_mapping_covers_all_content_types():
    from app.domain.entities import MemoryType

    for memory_type in MemoryType:
        assert memory_type.value in MEMORY_TYPE_TO_SYSTEM
        assert isinstance(MEMORY_TYPE_TO_SYSTEM[memory_type.value], MemorySystem)


def test_default_memory_system_for_type():
    assert default_memory_system_for_type(MemoryType.EVENT) == MemorySystem.EPISODIC
    assert default_memory_system_for_type(MemoryType.INSTRUCTION) == MemorySystem.PROCEDURAL
    assert default_memory_system_for_type(MemoryType.FACT) == MemorySystem.SEMANTIC


def test_episodic_requires_conversation_id():
    with pytest.raises(ValueError, match="conversation_id"):
        validate_memory_system_constraints(
            memory_system=MemorySystem.EPISODIC,
            conversation_id=None,
            occurred_at=None,
            expires_at=None,
        )


def test_working_requires_conversation_and_expiry():
    conv_id = uuid.uuid4()
    with pytest.raises(ValueError, match="expires_at"):
        validate_memory_system_constraints(
            memory_system=MemorySystem.WORKING,
            conversation_id=conv_id,
            occurred_at=None,
            expires_at=None,
        )


def test_expires_at_only_valid_for_working():
    conv_id = uuid.uuid4()
    expires = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="expires_at is only valid"):
        validate_memory_system_constraints(
            memory_system=MemorySystem.SEMANTIC,
            conversation_id=conv_id,
            occurred_at=None,
            expires_at=expires,
        )


def test_memory_entity_validate_hybrid_constraints():
    now = datetime.now(timezone.utc)
    memory = Memory(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="User attended a conference.",
        memory_type=MemoryType.EVENT,
        memory_system=MemorySystem.EPISODIC,
        importance=0.5,
        confidence=0.8,
        status=MemoryStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        last_accessed_at=now,
        conversation_id=uuid.uuid4(),
        occurred_at=now,
    )
    memory.validate()


def test_compute_working_memory_expiry_is_future():
    expiry = compute_working_memory_expiry(24.0)
    assert expiry > datetime.now(timezone.utc)
