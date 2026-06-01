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


def _bare_server(tools, api_client=None):
    """Build a FoxESSMCPServer instance without running __init__ (no network)."""
    server = object.__new__(FoxESSMCPServer)
    server.logger = logging.getLogger("test")
    server.tools = tools
    server.api_client = api_client
    return server


@pytest.mark.asyncio
async def test_run_tool_unknown_raises():
    server = _bare_server({})
    with pytest.raises(ValueError):
        await server._run_tool("nope", {})


@pytest.mark.asyncio
async def test_run_tool_routes_to_analysis():
    tool = Mock(execute=AsyncMock(return_value={"ok": True}))
    server = _bare_server({"analysis": tool})
    out = await server._run_tool("foxess_analysis", {"device_sn": "ABCD1234EF"})
    assert out == {"ok": True}
    tool.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_tool_call_success_returns_dict():
    tool = Mock(execute=AsyncMock(return_value={"soc": 68}))
    server = _bare_server({"analysis": tool})
    out = await server._handle_tool_call("foxess_analysis", {"device_sn": "ABCD1234EF"})
    assert out == {"soc": 68}


@pytest.mark.asyncio
async def test_handle_tool_call_exception_returns_iserror():
    tool = Mock(execute=AsyncMock(side_effect=RuntimeError("boom")))
    server = _bare_server({"analysis": tool})
    # valid 10-char SN so sanitize passes and the tool's RuntimeError fires
    out = await server._handle_tool_call("foxess_analysis", {"device_sn": "ABCD1234EF"})
    assert isinstance(out, CallToolResult)
    assert out.isError is True
    assert out.content and out.content[0].type == "text"


@pytest.mark.asyncio
async def test_handle_tool_call_invalid_sn_returns_iserror():
    tool = Mock(execute=AsyncMock(return_value={"ok": True}))
    server = _bare_server({"analysis": tool})
    out = await server._handle_tool_call("foxess_analysis", {"device_sn": "X"})
    assert isinstance(out, CallToolResult)
    assert out.isError is True
    tool.execute.assert_not_awaited()  # rejected before dispatch


@pytest.mark.asyncio
async def test_handle_tool_call_injects_default_device_sn():
    tool = Mock(execute=AsyncMock(return_value={"ok": True}))
    mock_auth = Mock(get_device_sn=Mock(return_value="ABCD1234EF"))
    mock_api = Mock(auth=mock_auth)
    server = _bare_server({"analysis": tool}, api_client=mock_api)
    out = await server._handle_tool_call("foxess_analysis", {})
    assert out == {"ok": True}
    mock_auth.get_device_sn.assert_called_once()
