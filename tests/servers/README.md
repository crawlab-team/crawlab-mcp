# MCP Server Tests

This directory contains tests for the MCP server functionality, focusing on parameter handling and transformation
according to the OpenAPI schema.

## Test Files

### `test_server_tool_params.py`

Unit tests for the parameter transformation logic in the `create_tool_function` function:

- `test_create_tool_function_transforms_parameters`: Tests that parameters are correctly transformed to their specified
  types
- `test_create_tool_function_handles_none_values`: Tests that None values are properly preserved
- `test_create_tool_function_passes_parameters_to_api_request`: Tests that parameters are correctly passed to API
  requests
- `test_create_tool_function_handles_exception`: Tests that exceptions are properly caught and logged
- `test_create_tool_function_logs_execution_time`: Tests that execution time is properly logged

### `test_server_tool_integration.py`

Integration tests that verify the parameter handling with simulated API calls:

- `test_tool_parameter_transformation_get`: Tests parameter transformation for GET requests
- `test_tool_parameter_transformation_post`: Tests parameter transformation for POST requests with request body
- `test_tool_none_parameter_handling`: Tests handling of None parameter values

## Running the Tests

To run all tests in this directory:

```bash
pytest tests/mcp/servers
```

To run a specific test file:

```bash
pytest tests/mcp/servers/test_server_tool_params.py
```

To run a specific test case:

```bash
pytest tests/mcp/servers/test_server_tool_params.py::TestServerToolParams::test_create_tool_function_transforms_parameters
```

## Test Coverage

The tests cover the following scenarios:

1. **Parameter Type Conversion**:
    - String to integer conversion
    - String to boolean conversion
    - Integer to string conversion
    - Handling of complex types (lists, dictionaries)

2. **Edge Cases**:
    - Handling of None values
    - Parameters that cannot be converted
    - Exception handling during tool execution

3. **Integration**:
    - GET requests with query parameters
    - POST requests with request body
    - Path parameter replacement

## Notes on Test Design

The tests use pytest fixtures to set up mock objects and dependencies. The integration tests now use a more controlled
mocking approach:

1. They mock the imported functions in `server.py` to prevent actual API calls
2. They create mock tool functions and objects to simulate the MCP server's behavior
3. They test the parameter handling and transformation logic directly

This approach provides better isolation and ensures that we're testing the parameter transformation logic without
relying on the entire server implementation. 