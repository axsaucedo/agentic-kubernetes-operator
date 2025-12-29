"""Backward compatibility wrapper for agent server.

This module re-exports the app from agent.server to maintain
backward compatibility with existing test infrastructure.
"""

from agent.server import app, AgentServer, AgentServerSettings

__all__ = ["app", "AgentServer", "AgentServerSettings"]
