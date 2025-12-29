"""Agent memory and session management."""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MemoryEvent(BaseModel):
    """Represents a single event in agent session memory."""
    event_id: str
    timestamp: datetime
    event_type: str  # "user_message", "agent_response", "tool_call", "reasoning", etc.
    content: Any
    metadata: Dict[str, Any] = {}

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SessionMemory(BaseModel):
    """Represents a complete session with all its events."""
    session_id: str
    user_id: str
    app_name: str
    events: List[MemoryEvent] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LocalMemory:
    """Local in-memory session storage similar to Google ADK's InMemorySessionService."""

    def __init__(self):
        """Initialize local memory storage."""
        self._sessions: Dict[str, SessionMemory] = {}
        logger.debug("LocalMemory initialized")

    async def create_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str = None
    ) -> str:
        """Create a new session.

        Args:
            app_name: Name of the application
            user_id: User identifier
            session_id: Optional custom session ID (generated if not provided)

        Returns:
            The session ID
        """
        if not session_id:
            session_id = f"session_{uuid.uuid4().hex[:12]}"

        now = datetime.utcnow()
        session = SessionMemory(
            session_id=session_id,
            user_id=user_id,
            app_name=app_name,
            events=[],
            created_at=now,
            updated_at=now
        )

        self._sessions[session_id] = session
        logger.debug(f"Created session: {session_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[SessionMemory]:
        """Retrieve a session by ID.

        Args:
            session_id: The session ID

        Returns:
            SessionMemory or None if not found
        """
        return self._sessions.get(session_id)

    async def add_event(self, session_id: str, event: MemoryEvent):
        """Add an event to a session.

        Args:
            session_id: The session ID
            event: The event to add
        """
        if session_id in self._sessions:
            self._sessions[session_id].events.append(event)
            self._sessions[session_id].updated_at = datetime.utcnow()
            logger.debug(f"Added {event.event_type} event to session {session_id}")
        else:
            logger.warning(f"Session {session_id} not found, event not added")

    async def get_session_events(self, session_id: str) -> List[MemoryEvent]:
        """Get all events for a session.

        Args:
            session_id: The session ID

        Returns:
            List of events, or empty list if session not found
        """
        session = await self.get_session(session_id)
        return session.events if session else []

    def create_event(
        self,
        event_type: str,
        content: Any,
        metadata: Dict[str, Any] = None
    ) -> MemoryEvent:
        """Create a memory event.

        Args:
            event_type: Type of event (e.g., "user_message", "agent_response")
            content: Event content/data
            metadata: Optional metadata dictionary

        Returns:
            MemoryEvent instance
        """
        return MemoryEvent(
            event_id=f"event_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            event_type=event_type,
            content=content,
            metadata=metadata or {}
        )

    async def list_sessions(self) -> List[str]:
        """Get list of all session IDs.

        Returns:
            List of session IDs
        """
        return list(self._sessions.keys())

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: The session ID

        Returns:
            True if deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(f"Deleted session: {session_id}")
            return True
        return False
