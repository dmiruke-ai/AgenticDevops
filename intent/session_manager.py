"""
Session Manager - Multi-tenant session isolation (S4-03).

Provides tenant-aware session management with access control.
Ensures Tenant A cannot access Tenant B's sessions.

Usage:
    manager = SessionManager()

    # Create session for tenant
    session = await manager.create_session(tenant_id="tenant-a", user_id="user-1")

    # Access requires matching tenant
    spec = await manager.get_spec(session.session_id, tenant_id="tenant-a")  # OK
    spec = await manager.get_spec(session.session_id, tenant_id="tenant-b")  # Raises
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from enum import Enum

import redis.asyncio as redis
from pydantic import BaseModel, Field

from config import config
from intent.schema import IntentSpec
from intent.state_store import SessionStateStore


class SessionAccessDenied(Exception):
    """Raised when tenant tries to access another tenant's session."""

    def __init__(self, session_id: str, tenant_id: str):
        self.session_id = session_id
        self.tenant_id = tenant_id
        super().__init__(
            f"Access denied: Tenant '{tenant_id}' cannot access session '{session_id}'"
        )


class SessionNotFound(Exception):
    """Raised when session does not exist."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class SessionExpired(Exception):
    """Raised when session has expired."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session expired: {session_id}")


class SessionStatus(str, Enum):
    """Session status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SessionInfo(BaseModel):
    """
    Session information with ownership and status.
    """
    session_id: str
    tenant_id: str
    user_id: str

    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24))

    # Stats
    turn_count: int = 0
    spec_version: int = 0

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionManager:
    """
    Multi-tenant session manager with isolation.

    Implements S4-03: Session isolation for multi-tenant support.
    Ensures Tenant A cannot read/write Tenant B's sessions.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize SessionManager.

        Args:
            redis_client: Optional Redis client
        """
        self.redis = redis_client or redis.from_url(
            config.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self.state_store = SessionStateStore(self.redis)
        self.ttl = config.intent_spec_ttl_seconds

    async def create_session(
        self,
        tenant_id: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionInfo:
        """
        Create a new session for tenant.

        Args:
            tenant_id: Tenant identifier (required)
            user_id: User identifier
            metadata: Optional session metadata

        Returns:
            SessionInfo with session details
        """
        session_id = str(uuid4())

        # Create session info
        session_info = SessionInfo(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            metadata=metadata or {},
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.ttl),
        )

        # Store session ownership
        await self._store_session_info(session_info)

        # Create IntentSpec via state store
        spec = IntentSpec(session_id=session_id)
        await self.state_store.save_spec(spec)

        # Add to tenant's session list
        await self._add_to_tenant_sessions(tenant_id, session_id)

        return session_info

    async def get_spec(
        self,
        session_id: str,
        tenant_id: str,
    ) -> IntentSpec:
        """
        Get IntentSpec with tenant verification.

        Args:
            session_id: Session identifier
            tenant_id: Requesting tenant ID

        Returns:
            IntentSpec

        Raises:
            SessionNotFound: If session doesn't exist
            SessionExpired: If session has expired
            SessionAccessDenied: If tenant doesn't own session
        """
        # Verify access
        await self._verify_access(session_id, tenant_id)

        # Get spec
        spec = await self.state_store.get_spec(session_id)
        if not spec:
            raise SessionNotFound(session_id)

        # Update last accessed
        await self._touch_session(session_id)

        return spec

    async def save_spec(
        self,
        spec: IntentSpec,
        tenant_id: str,
    ) -> None:
        """
        Save IntentSpec with tenant verification.

        Args:
            spec: IntentSpec to save
            tenant_id: Requesting tenant ID

        Raises:
            SessionAccessDenied: If tenant doesn't own session
        """
        # Verify access
        await self._verify_access(spec.session_id, tenant_id)

        # Save spec
        await self.state_store.save_spec(spec)

        # Update session info
        await self._update_session_stats(spec.session_id, spec)

    async def get_session_info(
        self,
        session_id: str,
        tenant_id: str,
    ) -> SessionInfo:
        """
        Get session information with tenant verification.

        Args:
            session_id: Session identifier
            tenant_id: Requesting tenant ID

        Returns:
            SessionInfo

        Raises:
            SessionNotFound: If session doesn't exist
            SessionAccessDenied: If tenant doesn't own session
        """
        # Verify access
        await self._verify_access(session_id, tenant_id)

        info = await self._get_session_info(session_id)
        if not info:
            raise SessionNotFound(session_id)

        return info

    async def list_sessions(
        self,
        tenant_id: str,
        status: Optional[SessionStatus] = None,
        limit: int = 100,
    ) -> List[SessionInfo]:
        """
        List all sessions for a tenant.

        Args:
            tenant_id: Tenant identifier
            status: Optional status filter
            limit: Maximum number of sessions to return

        Returns:
            List of SessionInfo for tenant's sessions
        """
        # Get tenant's session IDs
        tenant_key = f"tenant:{tenant_id}:sessions"
        session_ids = await self.redis.smembers(tenant_key)

        sessions = []
        for session_id in list(session_ids)[:limit]:
            info = await self._get_session_info(session_id)
            if info:
                if status is None or info.status == status:
                    sessions.append(info)

        # Sort by last accessed (newest first)
        sessions.sort(key=lambda s: s.last_accessed, reverse=True)

        return sessions

    async def end_session(
        self,
        session_id: str,
        tenant_id: str,
        status: SessionStatus = SessionStatus.COMPLETED,
    ) -> None:
        """
        End a session (mark as completed/cancelled).

        Args:
            session_id: Session identifier
            tenant_id: Requesting tenant ID
            status: Final status (COMPLETED or CANCELLED)

        Raises:
            SessionAccessDenied: If tenant doesn't own session
        """
        # Verify access
        await self._verify_access(session_id, tenant_id)

        # Update status
        info = await self._get_session_info(session_id)
        if info:
            info.status = status
            await self._store_session_info(info)

    async def delete_session(
        self,
        session_id: str,
        tenant_id: str,
    ) -> None:
        """
        Delete session and all data.

        Args:
            session_id: Session identifier
            tenant_id: Requesting tenant ID

        Raises:
            SessionAccessDenied: If tenant doesn't own session
        """
        # Verify access
        await self._verify_access(session_id, tenant_id)

        # Delete from state store
        await self.state_store.delete_session(session_id)

        # Delete session info
        info_key = f"session:{session_id}:info"
        await self.redis.delete(info_key)

        # Remove from tenant's session list
        tenant_key = f"tenant:{tenant_id}:sessions"
        await self.redis.srem(tenant_key, session_id)

    async def cleanup_expired_sessions(self, tenant_id: str) -> int:
        """
        Clean up expired sessions for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Number of sessions cleaned up
        """
        sessions = await self.list_sessions(tenant_id)
        cleaned = 0

        for session in sessions:
            if session.status == SessionStatus.EXPIRED:
                await self.delete_session(session.session_id, tenant_id)
                cleaned += 1
            elif session.expires_at < datetime.now(timezone.utc):
                # Mark as expired
                session.status = SessionStatus.EXPIRED
                await self._store_session_info(session)
                cleaned += 1

        return cleaned

    async def _verify_access(self, session_id: str, tenant_id: str) -> None:
        """
        Verify tenant has access to session.

        Raises:
            SessionNotFound: If session doesn't exist
            SessionExpired: If session has expired
            SessionAccessDenied: If tenant doesn't own session
        """
        info = await self._get_session_info(session_id)

        if not info:
            raise SessionNotFound(session_id)

        # Check ownership
        if info.tenant_id != tenant_id:
            raise SessionAccessDenied(session_id, tenant_id)

        # Check expiration
        if info.status == SessionStatus.EXPIRED:
            raise SessionExpired(session_id)

        if info.expires_at < datetime.now(timezone.utc):
            # Mark as expired
            info.status = SessionStatus.EXPIRED
            await self._store_session_info(info)
            raise SessionExpired(session_id)

    async def _store_session_info(self, info: SessionInfo) -> None:
        """Store session info in Redis."""
        info_key = f"session:{info.session_id}:info"
        await self.redis.set(
            info_key,
            info.model_dump_json(),
            ex=self.ttl,
        )

    async def _get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """Get session info from Redis."""
        info_key = f"session:{session_id}:info"
        info_json = await self.redis.get(info_key)

        if not info_json:
            return None

        return SessionInfo.model_validate_json(info_json)

    async def _add_to_tenant_sessions(self, tenant_id: str, session_id: str) -> None:
        """Add session to tenant's session set."""
        tenant_key = f"tenant:{tenant_id}:sessions"
        await self.redis.sadd(tenant_key, session_id)
        await self.redis.expire(tenant_key, self.ttl * 2)  # Longer TTL for tenant index

    async def _touch_session(self, session_id: str) -> None:
        """Update last accessed time."""
        info = await self._get_session_info(session_id)
        if info:
            info.last_accessed = datetime.now(timezone.utc)
            await self._store_session_info(info)

    async def _update_session_stats(self, session_id: str, spec: IntentSpec) -> None:
        """Update session statistics from spec."""
        info = await self._get_session_info(session_id)
        if info:
            info.spec_version = spec.version
            info.turn_count = spec.current_turn
            info.last_accessed = datetime.now(timezone.utc)
            await self._store_session_info(info)

    async def close(self) -> None:
        """Close connections."""
        await self.state_store.close()


def create_session_manager(
    redis_client: Optional[redis.Redis] = None,
) -> SessionManager:
    """Factory function for creating SessionManager."""
    return SessionManager(redis_client=redis_client)
