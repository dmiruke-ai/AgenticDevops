"""
Unit tests for Session Manager (S4-03).

Tests multi-tenant session isolation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from intent.session_manager import (
    SessionManager,
    SessionInfo,
    SessionStatus,
    SessionAccessDenied,
    SessionNotFound,
    SessionExpired,
    create_session_manager,
)


class TestSessionInfo:
    """Test SessionInfo model."""

    def test_create_session_info(self):
        """Test creating session info."""
        info = SessionInfo(
            session_id="test-session",
            tenant_id="tenant-a",
            user_id="user-1",
        )

        assert info.session_id == "test-session"
        assert info.tenant_id == "tenant-a"
        assert info.user_id == "user-1"
        assert info.status == SessionStatus.ACTIVE

    def test_session_info_defaults(self):
        """Test session info default values."""
        info = SessionInfo(
            session_id="test",
            tenant_id="tenant",
            user_id="user",
        )

        assert info.turn_count == 0
        assert info.spec_version == 0
        assert info.metadata == {}
        assert info.created_at <= datetime.now(timezone.utc)

    def test_session_info_with_metadata(self):
        """Test session info with metadata."""
        info = SessionInfo(
            session_id="test",
            tenant_id="tenant",
            user_id="user",
            metadata={"source": "cli", "version": "1.0"},
        )

        assert info.metadata["source"] == "cli"
        assert info.metadata["version"] == "1.0"


class TestSessionAccessExceptions:
    """Test session access exception classes."""

    def test_session_access_denied(self):
        """Test SessionAccessDenied exception."""
        exc = SessionAccessDenied("session-123", "tenant-b")

        assert exc.session_id == "session-123"
        assert exc.tenant_id == "tenant-b"
        assert "tenant-b" in str(exc)
        assert "session-123" in str(exc)

    def test_session_not_found(self):
        """Test SessionNotFound exception."""
        exc = SessionNotFound("session-xyz")

        assert exc.session_id == "session-xyz"
        assert "session-xyz" in str(exc)

    def test_session_expired(self):
        """Test SessionExpired exception."""
        exc = SessionExpired("old-session")

        assert exc.session_id == "old-session"
        assert "old-session" in str(exc)


class TestSessionManagerCreation:
    """Test SessionManager creation."""

    def test_create_manager(self):
        """Test creating session manager with mock Redis."""
        mock_redis = MagicMock()
        manager = SessionManager(redis_client=mock_redis)

        assert manager.redis == mock_redis

    def test_factory_function(self):
        """Test create_session_manager factory."""
        mock_redis = MagicMock()
        manager = create_session_manager(redis_client=mock_redis)

        assert isinstance(manager, SessionManager)


class TestSessionIsolation:
    """Test multi-tenant session isolation."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock()
        mock.delete = AsyncMock()
        mock.sadd = AsyncMock()
        mock.srem = AsyncMock()
        mock.smembers = AsyncMock(return_value=set())
        mock.expire = AsyncMock()
        mock.exists = AsyncMock(return_value=0)
        return mock

    @pytest.fixture
    def manager(self, mock_redis):
        """Create SessionManager with mock Redis."""
        return SessionManager(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_create_session_stores_tenant(self, manager, mock_redis):
        """Test session creation stores tenant ID."""
        session = await manager.create_session(
            tenant_id="tenant-a",
            user_id="user-1",
        )

        assert session.tenant_id == "tenant-a"
        assert session.user_id == "user-1"
        assert session.status == SessionStatus.ACTIVE

        # Verify Redis calls
        assert mock_redis.set.called

    @pytest.mark.asyncio
    async def test_tenant_cannot_access_other_tenant_session(self, manager, mock_redis):
        """Test tenant B cannot access tenant A's session."""
        # Create session info for tenant A
        session_info = SessionInfo(
            session_id="session-123",
            tenant_id="tenant-a",
            user_id="user-1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        # Mock Redis to return this session info
        mock_redis.get = AsyncMock(return_value=session_info.model_dump_json())

        # Tenant B tries to access
        with pytest.raises(SessionAccessDenied) as exc_info:
            await manager.get_spec("session-123", tenant_id="tenant-b")

        assert exc_info.value.tenant_id == "tenant-b"

    @pytest.mark.asyncio
    async def test_tenant_can_access_own_session(self, manager, mock_redis):
        """Test tenant can access their own session."""
        session_info = SessionInfo(
            session_id="session-123",
            tenant_id="tenant-a",
            user_id="user-1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        # Mock get to return session info first, then spec JSON
        from intent.schema import IntentSpec

        spec = IntentSpec(session_id="session-123")

        call_count = [0]

        async def mock_get(key):
            call_count[0] += 1
            if "info" in key:
                return session_info.model_dump_json()
            elif "spec" in key:
                return spec.model_dump_json()
            return None

        mock_redis.get = mock_get

        # Tenant A can access their session
        result = await manager.get_spec("session-123", tenant_id="tenant-a")

        assert result.session_id == "session-123"

    @pytest.mark.asyncio
    async def test_expired_session_raises(self, manager, mock_redis):
        """Test accessing expired session raises exception."""
        # Create expired session info
        session_info = SessionInfo(
            session_id="old-session",
            tenant_id="tenant-a",
            user_id="user-1",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        )

        mock_redis.get = AsyncMock(return_value=session_info.model_dump_json())

        with pytest.raises(SessionExpired):
            await manager.get_spec("old-session", tenant_id="tenant-a")

    @pytest.mark.asyncio
    async def test_nonexistent_session_raises(self, manager, mock_redis):
        """Test accessing nonexistent session raises exception."""
        mock_redis.get = AsyncMock(return_value=None)

        with pytest.raises(SessionNotFound):
            await manager.get_spec("nonexistent", tenant_id="tenant-a")

    @pytest.mark.asyncio
    async def test_save_spec_requires_tenant_match(self, manager, mock_redis):
        """Test saving spec requires tenant ownership."""
        session_info = SessionInfo(
            session_id="session-123",
            tenant_id="tenant-a",
            user_id="user-1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        mock_redis.get = AsyncMock(return_value=session_info.model_dump_json())

        from intent.schema import IntentSpec

        spec = IntentSpec(session_id="session-123")

        # Tenant B cannot save
        with pytest.raises(SessionAccessDenied):
            await manager.save_spec(spec, tenant_id="tenant-b")

    @pytest.mark.asyncio
    async def test_delete_session_requires_tenant_match(self, manager, mock_redis):
        """Test deleting session requires tenant ownership."""
        session_info = SessionInfo(
            session_id="session-123",
            tenant_id="tenant-a",
            user_id="user-1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        mock_redis.get = AsyncMock(return_value=session_info.model_dump_json())

        # Tenant B cannot delete
        with pytest.raises(SessionAccessDenied):
            await manager.delete_session("session-123", tenant_id="tenant-b")


class TestSessionListing:
    """Test session listing functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock()
        mock.sadd = AsyncMock()
        mock.expire = AsyncMock()
        return mock

    @pytest.fixture
    def manager(self, mock_redis):
        """Create SessionManager with mock Redis."""
        return SessionManager(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_list_sessions_for_tenant(self, manager, mock_redis):
        """Test listing sessions only returns tenant's sessions."""
        # Create session infos
        session1 = SessionInfo(
            session_id="s1",
            tenant_id="tenant-a",
            user_id="user",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session2 = SessionInfo(
            session_id="s2",
            tenant_id="tenant-a",
            user_id="user",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        mock_redis.smembers = AsyncMock(return_value={"s1", "s2"})

        async def mock_get(key):
            if "s1" in key:
                return session1.model_dump_json()
            elif "s2" in key:
                return session2.model_dump_json()
            return None

        mock_redis.get = mock_get

        sessions = await manager.list_sessions(tenant_id="tenant-a")

        assert len(sessions) == 2
        assert all(s.tenant_id == "tenant-a" for s in sessions)

    @pytest.mark.asyncio
    async def test_list_sessions_with_status_filter(self, manager, mock_redis):
        """Test listing sessions with status filter."""
        active_session = SessionInfo(
            session_id="active",
            tenant_id="tenant-a",
            user_id="user",
            status=SessionStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        completed_session = SessionInfo(
            session_id="completed",
            tenant_id="tenant-a",
            user_id="user",
            status=SessionStatus.COMPLETED,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        mock_redis.smembers = AsyncMock(return_value={"active", "completed"})

        async def mock_get(key):
            if "active" in key:
                return active_session.model_dump_json()
            elif "completed" in key:
                return completed_session.model_dump_json()
            return None

        mock_redis.get = mock_get

        # Filter by ACTIVE only
        active_sessions = await manager.list_sessions(
            tenant_id="tenant-a",
            status=SessionStatus.ACTIVE,
        )

        assert len(active_sessions) == 1
        assert active_sessions[0].session_id == "active"


class TestSessionLifecycle:
    """Test session lifecycle operations."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock()
        mock.delete = AsyncMock()
        mock.sadd = AsyncMock()
        mock.srem = AsyncMock()
        mock.expire = AsyncMock()

        # Mock scan_iter for delete_session
        async def mock_scan_iter(match=None):
            if match:
                yield match.replace("*", "spec")
                yield match.replace("*", "info")

        mock.scan_iter = mock_scan_iter
        return mock

    @pytest.fixture
    def manager(self, mock_redis):
        """Create SessionManager with mock Redis."""
        return SessionManager(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_end_session_updates_status(self, manager, mock_redis):
        """Test ending session updates status."""
        session_info = SessionInfo(
            session_id="session-123",
            tenant_id="tenant-a",
            user_id="user",
            status=SessionStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        mock_redis.get = AsyncMock(return_value=session_info.model_dump_json())

        await manager.end_session(
            "session-123",
            tenant_id="tenant-a",
            status=SessionStatus.COMPLETED,
        )

        # Verify status was updated in set call
        assert mock_redis.set.called

    @pytest.mark.asyncio
    async def test_delete_session_removes_all_data(self, manager, mock_redis):
        """Test deleting session removes all data."""
        session_info = SessionInfo(
            session_id="session-123",
            tenant_id="tenant-a",
            user_id="user",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        mock_redis.get = AsyncMock(return_value=session_info.model_dump_json())

        await manager.delete_session("session-123", tenant_id="tenant-a")

        # Verify delete and srem were called
        assert mock_redis.delete.called
        assert mock_redis.srem.called


class TestConcurrentAccess:
    """Test concurrent session access."""

    @pytest.mark.asyncio
    async def test_multiple_tenants_isolated(self):
        """Test multiple tenants are properly isolated."""
        mock_redis = AsyncMock()

        # Track tenant access patterns
        access_log = []

        async def mock_get(key):
            # Parse tenant from key pattern
            if "tenant-a" in key or "session-a" in key:
                access_log.append(("tenant-a", key))
                return SessionInfo(
                    session_id="session-a",
                    tenant_id="tenant-a",
                    user_id="user",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                ).model_dump_json()
            elif "tenant-b" in key or "session-b" in key:
                access_log.append(("tenant-b", key))
                return SessionInfo(
                    session_id="session-b",
                    tenant_id="tenant-b",
                    user_id="user",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                ).model_dump_json()
            return None

        mock_redis.get = mock_get
        mock_redis.set = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()

        manager = SessionManager(redis_client=mock_redis)

        # Tenant A accesses their session
        info_a = await manager.get_session_info("session-a", "tenant-a")
        assert info_a.tenant_id == "tenant-a"

        # Tenant B tries to access Tenant A's session
        with pytest.raises(SessionAccessDenied):
            await manager.get_session_info("session-a", "tenant-b")
