"""
Session State Store - Redis-backed IntentSpec storage.

Provides versioned CRUD operations for IntentSpec with TTL.
Supports session resume and version rewind.
"""

import json
from typing import Optional
from uuid import uuid4

import redis.asyncio as redis

from config import config
from intent.schema import IntentSpec


class SessionStateStore:
    """
    Redis-backed store for IntentSpec with versioning.

    Key structure:
    - session:{session_id}:spec - Current IntentSpec
    - session:{session_id}:version:{n} - Versioned snapshot
    - session:{session_id}:metadata - Session metadata

    All keys have TTL (default 24 hours).
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize state store.

        Args:
            redis_client: Optional Redis client. If None, creates new client.
        """
        self.redis = redis_client or redis.from_url(
            config.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self.ttl = config.intent_spec_ttl_seconds

    async def create_session(self, user_id: Optional[str] = None) -> str:
        """
        Create a new session.

        Args:
            user_id: Optional user identifier

        Returns:
            New session_id
        """
        session_id = str(uuid4())

        # Create empty IntentSpec
        spec = IntentSpec(session_id=session_id)

        # Store initial spec
        await self.save_spec(spec)

        # Store metadata
        metadata = {
            "session_id": session_id,
            "user_id": user_id or "anonymous",
            "created_at": spec.created_at.isoformat(),
            "last_updated": spec.updated_at.isoformat(),
            "turn_count": 0,
        }
        metadata_key = f"session:{session_id}:metadata"
        await self.redis.set(
            metadata_key,
            json.dumps(metadata),
            ex=self.ttl,
        )

        return session_id

    async def save_spec(self, spec: IntentSpec) -> None:
        """
        Save IntentSpec to Redis.

        Creates versioned snapshot and updates current spec.

        Args:
            spec: IntentSpec to save
        """
        session_id = spec.session_id
        spec_key = f"session:{session_id}:spec"
        version_key = f"session:{session_id}:version:{spec.version}"

        # Serialize spec
        spec_json = spec.model_dump_json()

        # Store current spec
        await self.redis.set(spec_key, spec_json, ex=self.ttl)

        # Store versioned snapshot
        await self.redis.set(version_key, spec_json, ex=self.ttl)

        # Update metadata
        await self._update_metadata(session_id, spec)

    async def get_spec(self, session_id: str) -> Optional[IntentSpec]:
        """
        Retrieve current IntentSpec for session.

        Args:
            session_id: Session identifier

        Returns:
            IntentSpec or None if session doesn't exist
        """
        spec_key = f"session:{session_id}:spec"
        spec_json = await self.redis.get(spec_key)

        if not spec_json:
            return None

        return IntentSpec.model_validate_json(spec_json)

    async def get_spec_version(
        self, session_id: str, version: int
    ) -> Optional[IntentSpec]:
        """
        Retrieve specific version of IntentSpec.

        Args:
            session_id: Session identifier
            version: Version number to retrieve

        Returns:
            IntentSpec at that version or None
        """
        version_key = f"session:{session_id}:version:{version}"
        spec_json = await self.redis.get(version_key)

        if not spec_json:
            return None

        return IntentSpec.model_validate_json(spec_json)

    async def rewind_to_version(
        self, session_id: str, version: int
    ) -> Optional[IntentSpec]:
        """
        Rewind session to a previous version.

        Args:
            session_id: Session identifier
            version: Version to rewind to

        Returns:
            IntentSpec at that version or None
        """
        spec = await self.get_spec_version(session_id, version)

        if spec:
            # Save as current spec
            await self.save_spec(spec)

        return spec

    async def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists.

        Args:
            session_id: Session identifier

        Returns:
            True if session exists
        """
        spec_key = f"session:{session_id}:spec"
        return await self.redis.exists(spec_key) > 0

    async def delete_session(self, session_id: str) -> None:
        """
        Delete session and all its data.

        Args:
            session_id: Session identifier
        """
        # Get all keys for this session
        pattern = f"session:{session_id}:*"
        keys = []

        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            await self.redis.delete(*keys)

    async def extend_ttl(self, session_id: str) -> None:
        """
        Extend TTL for all session keys.

        Args:
            session_id: Session identifier
        """
        pattern = f"session:{session_id}:*"

        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.expire(key, self.ttl)

    async def get_metadata(self, session_id: str) -> Optional[dict]:
        """
        Get session metadata.

        Args:
            session_id: Session identifier

        Returns:
            Metadata dict or None
        """
        metadata_key = f"session:{session_id}:metadata"
        metadata_json = await self.redis.get(metadata_key)

        if not metadata_json:
            return None

        return json.loads(metadata_json)

    async def _update_metadata(self, session_id: str, spec: IntentSpec) -> None:
        """Update session metadata."""
        metadata_key = f"session:{session_id}:metadata"
        metadata_json = await self.redis.get(metadata_key)

        if metadata_json:
            metadata = json.loads(metadata_json)
            metadata["last_updated"] = spec.updated_at.isoformat()
            metadata["version"] = spec.version
            metadata["item_count"] = len(spec.items)

            await self.redis.set(
                metadata_key,
                json.dumps(metadata),
                ex=self.ttl,
            )

    async def close(self) -> None:
        """Close Redis connection."""
        await self.redis.close()


async def create_state_store() -> SessionStateStore:
    """Factory function to create state store."""
    return SessionStateStore()
