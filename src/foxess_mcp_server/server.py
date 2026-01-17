#!/usr/bin/env python3
"""
FoxESS MCP Server - Main Entry Point

This module implements the main MCP server for FoxESS solar inverters.
It provides three core tools: analysis, diagnosis, and forecast.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
)

# Local imports
from .utils.logging_config import setup_logging
from .utils.errors import FoxESSMCPError, ConfigurationError, ValidationError
from .utils.validation import SecurityValidator
from .foxess.api_client import FoxESSAPIClient
from .tools.analysis import AnalysisTool
from .tools.diagnosis import DiagnosisTool  
from .tools.forecast import ForecastTool


class FoxESSMCPServer:
    """Main MCP Server for FoxESS Solar Inverters"""
    
    def __init__(self):
        self.server = Server("foxess-mcp-server")
        self.logger = logging.getLogger(__name__)
        self.api_client = None
        self.tools = {}
        
        # Setup server handlers
        self._setup_handlers()
        
        # Initialize tools
        self._initialize_tools()
    
    def _setup_handlers(self):
        """Setup MCP server event handlers"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="foxess_analysis",
                    description="Analyze FoxESS solar inverter data with real-time, historical, and aggregated report insights",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_sn": {
                                "type": "string",
                                "description": "FoxESS device serial number"
                            },
                            "time_range": {
                                "type": "string",
                                "enum": ["realtime", "1h", "1d", "1w", "1m", "3m", "custom",
                                         "report_year", "report_month", "report_day"],
                                "description": "Time range for analysis. Use report_year for monthly breakdown of a year, report_month for daily breakdown of a month, report_day for hourly breakdown of a day"
                            },
                            "variables": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Energy variables to analyze (optional)"
                            },
                            "start_time": {
                                "type": "string",
                                "description": "Custom start time (ISO format, required for custom range)"
                            },
                            "end_time": {
                                "type": "string",
                                "description": "Custom end time (ISO format, required for custom range)"
                            },
                            "year": {
                                "type": "integer",
                                "description": "Year for report queries (defaults to current year)"
                            },
                            "month": {
                                "type": "integer",
                                "description": "Month (1-12) for report_month/report_day queries"
                            },
                            "day": {
                                "type": "integer",
                                "description": "Day (1-31) for report_day queries"
                            }
                        },
                        "required": ["device_sn", "time_range"]
                    }
                ),
                Tool(
                    name="foxess_diagnosis",
                    description="Diagnose FoxESS system health and performance issues",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_sn": {
                                "type": "string",
                                "description": "FoxESS device serial number"
                            },
                            "check_type": {
                                "type": "string",
                                "enum": ["health", "performance", "errors", "comprehensive"],
                                "description": "Type of diagnostic check"
                            },
                            "include_recommendations": {
                                "type": "boolean",
                                "default": True,
                                "description": "Include optimization recommendations"
                            }
                        },
                        "required": ["device_sn", "check_type"]
                    }
                ),
                Tool(
                    name="foxess_forecast",
                    description="Generate FoxESS energy forecasts and optimization recommendations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "device_sn": {
                                "type": "string",
                                "description": "FoxESS device serial number"
                            },
                            "forecast_type": {
                                "type": "string",
                                "enum": ["daily", "weekly", "monthly"],
                                "description": "Forecast time horizon"
                            },
                            "weather_integration": {
                                "type": "boolean",
                                "default": False,
                                "description": "Include weather data in forecast"
                            },
                            "optimization_focus": {
                                "type": "string",
                                "enum": ["yield", "cost", "battery_life", "grid_stability"],
                                "description": "Optimization objective"
                            }
                        },
                        "required": ["device_sn", "forecast_type"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool execution requests"""
            try:
                self.logger.info(f"Tool called: {name}")
                
                # Validate and sanitize arguments
                sanitized_args = SecurityValidator.sanitize_arguments(arguments)
                
                # Route to appropriate tool
                if name == "foxess_analysis":
                    result = await self.tools["analysis"].execute(sanitized_args)
                elif name == "foxess_diagnosis":
                    result = await self.tools["diagnosis"].execute(sanitized_args)
                elif name == "foxess_forecast":
                    result = await self.tools["forecast"].execute(sanitized_args)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                # Format response
                response_text = json.dumps(result, indent=2, ensure_ascii=False)
                
                return [TextContent(
                    type="text",
                    text=response_text
                )]
                
            except Exception as e:
                self.logger.error(f"Tool execution failed: {e}")
                error_response = {
                    "error": {
                        "code": "TOOL_EXECUTION_ERROR", 
                        "message": str(e),
                        "tool": name,
                        "timestamp": self._get_timestamp()
                    }
                }
                return [TextContent(
                    type="text",
                    text=json.dumps(error_response, indent=2)
                )]
    
    def _initialize_tools(self):
        """Initialize tool instances"""
        try:
            # Initialize API client
            self.api_client = FoxESSAPIClient()
            
            # Initialize tools
            self.tools = {
                "analysis": AnalysisTool(self.api_client),
                "diagnosis": DiagnosisTool(self.api_client),
                "forecast": ForecastTool(self.api_client)
            }
            
            self.logger.info("Tools initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Tool initialization failed: {e}")
            raise ConfigurationError(f"Failed to initialize tools: {e}")
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
    
    async def run(self):
        """Run the MCP server"""
        self.logger.info("Starting FoxESS MCP Server...")
        
        # Validate configuration
        self._validate_configuration()
        
        # Run server with stdio transport
        async with stdio_server() as (read_stream, write_stream):
            init_options = self.server.create_initialization_options()
            await self.server.run(
                read_stream,
                write_stream,
                init_options
            )
    
    def _validate_configuration(self):
        """Validate required configuration"""
        required_env_vars = ["FOXESS_API_KEY", "FOXESS_DEVICE_SN"]
        missing_vars = []
        
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ConfigurationError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
        
        # Validate token format
        token = os.getenv("FOXESS_API_KEY")
        if not SecurityValidator.validate_token_format(token):
            raise ConfigurationError("Invalid FoxESS API token format")
        
        # Validate device SN format
        device_sn = os.getenv("FOXESS_DEVICE_SN")
        if not SecurityValidator.validate_device_sn_format(device_sn):
            raise ConfigurationError("Invalid FoxESS device serial number format")


def main():
    """Main entry point for the FoxESS MCP Server"""
    try:
        # Setup logging
        setup_logging()
        logger = logging.getLogger(__name__)
        
        logger.info("FoxESS MCP Server starting...")
        
        # Create and run server
        server = FoxESSMCPServer()
        asyncio.run(server.run())
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
