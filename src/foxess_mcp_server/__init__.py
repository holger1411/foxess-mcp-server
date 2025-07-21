"""
FoxESS MCP Server

A Model Context Protocol server for FoxESS Solar Inverters, enabling AI assistants
to access, analyze, and optimize solar energy data.

Author: FoxESS MCP Community
License: MIT
Version: 0.1.0
"""

__version__ = "0.1.0"
__author__ = "FoxESS MCP Community"
__license__ = "MIT"

from .server import main

__all__ = ["main"]
