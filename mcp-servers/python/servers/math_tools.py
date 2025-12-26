"""
Safe Math Tools MCP Server.

Provides safe, stateless mathematical operations without external
dependencies or network calls. Pure computation only.

This is the baseline safe server for Phase 1 - no external calls,
no file system access, no risk vectors.
"""

import logging
from typing import Dict, Any, List
import math

logger = logging.getLogger(__name__)


class MathToolsServer:
    """Safe math operations server"""

    @staticmethod
    def get_tools() -> List[Dict[str, Any]]:
        """Return list of available math tools"""
        return [
            {
                "name": "add",
                "description": "Add two numbers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "First number"},
                        "b": {"type": "number", "description": "Second number"},
                    },
                    "required": ["a", "b"]
                }
            },
            {
                "name": "subtract",
                "description": "Subtract two numbers (a - b)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "Minuend"},
                        "b": {"type": "number", "description": "Subtrahend"},
                    },
                    "required": ["a", "b"]
                }
            },
            {
                "name": "multiply",
                "description": "Multiply two numbers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "First number"},
                        "b": {"type": "number", "description": "Second number"},
                    },
                    "required": ["a", "b"]
                }
            },
            {
                "name": "divide",
                "description": "Divide two numbers (a / b)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "Dividend"},
                        "b": {"type": "number", "description": "Divisor"},
                    },
                    "required": ["a", "b"]
                }
            },
            {
                "name": "power",
                "description": "Raise a number to a power (a ** b)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "Base"},
                        "b": {"type": "number", "description": "Exponent"},
                    },
                    "required": ["a", "b"]
                }
            },
            {
                "name": "square_root",
                "description": "Calculate square root of a number",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "Number (must be >= 0)"},
                    },
                    "required": ["a"]
                }
            },
        ]

    @staticmethod
    def execute_tool(tool_name: str, params: Dict[str, Any]) -> Any:
        """Execute a math tool"""
        try:
            if tool_name == "add":
                return {"result": params["a"] + params["b"]}

            elif tool_name == "subtract":
                return {"result": params["a"] - params["b"]}

            elif tool_name == "multiply":
                return {"result": params["a"] * params["b"]}

            elif tool_name == "divide":
                if params["b"] == 0:
                    return {"error": "Division by zero"}
                return {"result": params["a"] / params["b"]}

            elif tool_name == "power":
                return {"result": params["a"] ** params["b"]}

            elif tool_name == "square_root":
                if params["a"] < 0:
                    return {"error": "Cannot take square root of negative number"}
                return {"result": math.sqrt(params["a"])}

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except KeyError as e:
            return {"error": f"Missing required parameter: {e}"}
        except TypeError as e:
            return {"error": f"Invalid parameter type: {e}"}
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}


# Global server instance
Server = MathToolsServer()
