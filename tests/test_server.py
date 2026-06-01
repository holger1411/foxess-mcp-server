"""Tests for FoxESS MCP server tool definitions and dispatch."""

import logging

import pytest
from unittest.mock import AsyncMock, Mock

from mcp.types import CallToolResult
from foxess_mcp_server.server import FoxESSMCPServer


def test_tool_definitions_have_output_schema_and_annotations():
    tools = FoxESSMCPServer._build_tool_definitions()
    names = {t.name for t in tools}
    assert names == {"foxess_analysis", "foxess_diagnosis", "foxess_forecast"}
    for t in tools:
        assert t.outputSchema == {"type": "object"}
        assert t.annotations is not None
        assert t.annotations.readOnlyHint is True
        assert t.annotations.title  # human-readable title set
