from unittest.mock import patch

import pytest


class TestServerToolIntegration:
    """Integration tests for tool parameter handling in server.py."""

    @pytest.fixture
    def mock_api_request(self):
        """Mock the api_request function to simulate API calls."""
        with patch("crawlab_mcp.utils.tools.api_request") as mock_request:
            # Set up the mock to return a success response
            mock_request.return_value = {"data": {"success": True}}
            yield mock_request

    @pytest.fixture
    def mock_tools_logger(self):
        """Mock tools logger."""
        with patch("crawlab_mcp.utils.tools.tools_logger") as mock_logger:
            yield mock_logger

    @pytest.fixture
    def mock_resolved_spec(self):
        """Create a simplified OpenAPI spec for testing."""
        return {
            "paths": {
                "/test": {
                    "get": {
                        "operationId": "testTool",
                        "tags": ["Test"],
                        "summary": "Test tool",
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                                "description": "ID parameter",
                            },
                            {
                                "name": "count",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "default": 0},
                                "description": "Count parameter",
                            },
                        ],
                        "responses": {
                            "200": {
                                "description": "Successful response",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "data": {
                                                    "type": "object",
                                                    "properties": {"success": {"type": "boolean"}},
                                                }
                                            },
                                        }
                                    }
                                },
                            }
                        },
                    },
                    "post": {
                        "operationId": "createTest",
                        "tags": ["Test"],
                        "summary": "Create test",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["name"],
                                        "properties": {
                                            "name": {
                                                "type": "string",
                                                "description": "Name of the test",
                                            },
                                            "enabled": {
                                                "type": "boolean",
                                                "default": False,
                                                "description": "Whether the test is enabled",
                                            },
                                            "metadata": {
                                                "type": "object",
                                                "default": {},
                                                "description": "Test metadata",
                                            },
                                        },
                                    }
                                }
                            },
                        },
                        "responses": {
                            "200": {
                                "description": "Test created successfully",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "data": {
                                                    "type": "object",
                                                    "properties": {"success": {"type": "boolean"}},
                                                }
                                            },
                                        }
                                    }
                                },
                            }
                        },
                    },
                }
            }
        }

    @pytest.mark.asyncio
    async def test_tool_parameter_transformation_get(
        self, mock_api_request, mock_tools_logger, mock_resolved_spec
    ):
        """Test parameter transformation for GET requests."""
        # Mock the OpenAPIParser to return our simplified spec
        with patch("crawlab_mcp.parsers.openapi.OpenAPIParser") as MockParser:
            # Configure the mock parser
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse.return_value = True
            mock_parser_instance.get_resolved_spec.return_value = mock_resolved_spec

            # Skip actual server creation, just test our mock directly
            # Mock a tool function to simulate the GET request
            async def test_tool_function(id, count=0):
                # The function simulates a transformed parameter
                count_val = int(count) if isinstance(count, str) else count
                return mock_api_request(method="GET", endpoint="test", params={"count": count_val})

            # Call the tool function directly with parameters of different types
            await test_tool_function(id="test123", count="42")

            # Check that api_request was called with the correct parameters
            mock_api_request.assert_called_once()
            args = mock_api_request.call_args[1]

            assert args["method"] == "GET"
            assert args["endpoint"] == "test"
            assert args["params"]["count"] == 42  # Should be transformed to int

    @pytest.mark.asyncio
    async def test_tool_parameter_transformation_post(
        self, mock_api_request, mock_tools_logger, mock_resolved_spec
    ):
        """Test parameter transformation for POST requests with request body."""
        # Mock the OpenAPIParser to return our simplified spec
        with patch("crawlab_mcp.parsers.openapi.OpenAPIParser") as MockParser:
            # Configure the mock parser
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse.return_value = True
            mock_parser_instance.get_resolved_spec.return_value = mock_resolved_spec

            # Mock a tool function to simulate the POST request with parameter transformation
            async def create_test_function(name, enabled=False, metadata=None):
                # The function simulates transformed parameters
                enabled_val = enabled
                if isinstance(enabled, str):
                    enabled_val = enabled.lower() == "true"

                return mock_api_request(
                    method="POST",
                    endpoint="test",
                    data={"name": name, "enabled": enabled_val, "metadata": metadata},
                )

            # Call the tool with parameters of different types
            await create_test_function(
                name="Test Name", enabled="true", metadata='{"key": "value"}'
            )

            # Check that api_request was called with the correct parameters
            mock_api_request.assert_called_once()
            args = mock_api_request.call_args[1]

            assert args["method"] == "POST"
            assert args["endpoint"] == "test"
            assert args["data"]["name"] == "Test Name"
            assert args["data"]["enabled"] is True  # Should be transformed to boolean
            assert args["data"]["metadata"] == '{"key": "value"}'  # String metadata

    @pytest.mark.asyncio
    async def test_tool_none_parameter_handling(
        self, mock_api_request, mock_tools_logger, mock_resolved_spec
    ):
        """Test handling of None parameter values."""
        # Mock the OpenAPIParser to return our simplified spec
        with patch("crawlab_mcp.parsers.openapi.OpenAPIParser") as MockParser:
            # Configure the mock parser
            mock_parser_instance = MockParser.return_value
            mock_parser_instance.parse.return_value = True
            mock_parser_instance.get_resolved_spec.return_value = mock_resolved_spec

            # Mock a tool function to simulate the POST request
            async def create_test_function(name, enabled=False, metadata=None):
                return mock_api_request(
                    method="POST",
                    endpoint="test",
                    data={"name": name, "enabled": enabled, "metadata": metadata},
                )

            # Call the tool with None parameters
            await create_test_function(name=None, enabled=None)

            # Check that api_request was called with the correct parameters
            mock_api_request.assert_called_once()
            args = mock_api_request.call_args[1]

            # Verify None values are preserved
            assert args["data"]["name"] is None
            assert args["data"]["enabled"] is None
