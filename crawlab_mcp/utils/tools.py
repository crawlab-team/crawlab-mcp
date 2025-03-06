import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from mcp import Tool

from crawlab_mcp.utils.constants import (
    MODELS_WITH_TOOL_SUPPORT,
    MODEL_TOOL_SUPPORT_PATTERNS,
    PYTHON_KEYWORDS,
)
from crawlab_mcp.utils.http import api_request

tools_logger = logging.getLogger("crawlab_mcp.utils.tools")

# Simple type conversion from OpenAPI to Python types
OPENAPI_TO_PYTHON_TYPES = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}

# Define mapping from Python types to OpenAPI types
PYTHON_TO_OPENAPI_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    Dict: "object",
    List: "array",
    Any: "string",  # Default to string for Any
}


def extract_openapi_parameters(operation: Dict[str, Any]) -> Dict[str, Tuple]:
    """
    Extract parameter information from an OpenAPI operation.

    Args:
        operation: The operation object from the OpenAPI spec

    Returns:
        Dictionary mapping parameter names to tuples of:
        (type, default_value, description, is_path_param, additional_schema)
        where additional_schema contains other OpenAPI schema properties like enum, format, etc.
    """
    param_dict = {}

    def get_default_value(param_type: str, is_required: bool) -> Any:
        """Helper to get the default value for a parameter based on its type"""
        if is_required:
            return None

        # Default values for optional parameters by type
        defaults = {"string": "", "array": [], "object": {}, "boolean": False}
        # Default to 0 for number types
        if param_type in ["integer", "number"]:
            return 0

        return defaults.get(param_type, None)

    # Process path parameters and query parameters
    for param in operation.get("parameters", []):
        param_name = param.get("name")
        param_required = param.get("required", False)
        param_schema = param.get("schema", {})
        param_description = param.get("description", "")
        param_type = param_schema.get("type", "string")
        param_in = param.get("in", "")

        # Flag whether this is a path parameter
        is_path_param = param_in == "path"

        python_type = OPENAPI_TO_PYTHON_TYPES.get(param_type, str)
        default_val = get_default_value(param_type, param_required)

        # Ensure path parameters are required
        if is_path_param:
            default_val = None

        # Extract additional schema properties (enum, format, minimum, maximum, pattern, etc.)
        additional_schema = {}
        for key in [
            "enum",
            "format",
            "minimum",
            "maximum",
            "pattern",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "minLength",
            "maxLength",
            "multipleOf",
        ]:
            if key in param_schema:
                additional_schema[key] = param_schema[key]

        # Add parameter to the dictionary with path parameter flag and additional schema
        param_dict[param_name] = (
            python_type,
            default_val,
            param_description,
            is_path_param,
            additional_schema,
        )

    # Process request body if present
    request_body = operation.get("requestBody", {})
    if request_body:
        content = request_body.get("content", {})
        json_content = content.get("application/json", {})
        if json_content:
            schema = json_content.get("schema", {})
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            for prop_name, prop_schema in properties.items():
                prop_type = prop_schema.get("type", "string")
                prop_description = prop_schema.get("description", "")
                prop_required = prop_name in required

                python_type = OPENAPI_TO_PYTHON_TYPES.get(prop_type, str)
                default_val = get_default_value(prop_type, prop_required)

                # Extract additional schema properties for body parameters
                additional_schema = {}
                for key in [
                    "enum",
                    "format",
                    "minimum",
                    "maximum",
                    "pattern",
                    "exclusiveMinimum",
                    "exclusiveMaximum",
                    "minLength",
                    "maxLength",
                    "multipleOf",
                ]:
                    if key in prop_schema:
                        additional_schema[key] = prop_schema[key]

                # Add parameter to the dictionary (not a path parameter) with additional schema
                param_dict[prop_name] = (
                    python_type,
                    default_val,
                    prop_description,
                    False,
                    additional_schema,
                )

    return param_dict


def create_input_schema_from_openapi(
    operation_id: str, operation: Dict[str, Any], method: str, path: str
) -> Dict[str, Any]:
    """Create a standardized input schema from an OpenAPI operation.

    Args:
        operation_id: The operation ID in the OpenAPI spec
        operation: The operation object from the OpenAPI spec
        method: The HTTP method (GET, POST, etc.)
        path: The path for the operation

    Returns:
        A dictionary with the input schema information
    """
    # Extract path parameters from the path
    path_param_names = re.findall(r"{([^{}]+)}", path)

    # Create a basic schema structure
    input_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    # Helper function to create a property schema from a parameter schema
    def create_property_schema(param_schema: Dict[str, Any], description: str) -> Dict[str, Any]:
        """Create a property schema for the input schema."""
        property_schema = {}
        # Copy relevant fields
        for field in ["type", "format", "enum", "minimum", "maximum", "pattern"]:
            if field in param_schema:
                property_schema[field] = param_schema[field]

                # Enhance enum descriptions to make them more explicit for AI agents
                if field == "enum" and param_schema[field]:
                    enum_values = param_schema[field]
                    enum_str = ", ".join([f"'{v}'" for v in enum_values])
                    property_schema["description"] = (
                        f"{description or ''}. Valid values: [{enum_str}]"
                    )

        # Handle schema reference
        if "$ref" in param_schema:
            # For simplicity, we'll just extract the type from the reference
            # In a real implementation, you might want to resolve the reference
            ref_parts = param_schema["$ref"].split("/")
            type_name = ref_parts[-1]
            # Convert CamelCase to snake_case for readability
            type_name = re.sub(r"(?<!^)(?=[A-Z])", "_", type_name).lower()
            # Remove common suffixes
            type_name = type_name.replace("_schema", "").replace("_type", "")
            property_schema["type"] = type_name

        # Add description if not empty and we haven't already added an enum-enhanced description
        if description and "description" not in property_schema:
            property_schema["description"] = description

        return property_schema

    # Process path and query parameters
    for param in operation.get("parameters", []):
        param_name = param.get("name")
        param_schema = param.get("schema", {})
        param_description = param.get("description", "")
        param_required = param.get("required", False)
        param_in = param.get("in", "")

        # Force path parameters to be required
        if param_name in path_param_names or param_in == "path":
            param_required = True

        # Create and add the property schema
        property_schema = create_property_schema(param_schema, param_description)

        # Mark path parameters clearly in the schema
        if param_name in path_param_names or param_in == "path":
            property_schema["x-path-parameter"] = True
            property_schema["description"] = (
                f"[Path Parameter] {property_schema.get('description', '')}"
            )

        input_schema["properties"][param_name] = property_schema

        # Add to required list if needed
        if param_required and param_name not in input_schema["required"]:
            input_schema["required"].append(param_name)

    # Process request body if present
    request_body = operation.get("requestBody", {})
    if request_body:
        content = request_body.get("content", {})
        json_content = content.get("application/json", {})
        if json_content:
            schema = json_content.get("schema", {})
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            for prop_name, prop_schema in properties.items():
                prop_description = prop_schema.get("description", "")
                property_schema = create_property_schema(prop_schema, prop_description)
                input_schema["properties"][prop_name] = property_schema

                # Add to required list if needed
                if prop_name in required and prop_name not in input_schema["required"]:
                    input_schema["required"].append(prop_name)

    # If there are no required parameters, remove the required list
    if not input_schema["required"]:
        input_schema.pop("required")

    # Final schema structure
    tool_schema = {
        "name": operation_id,
        "inputSchema": input_schema,
    }

    return tool_schema


def create_tool_function(tool_name, method, path, param_dict, enable_logging=True):
    """Create a tool function that calls the Crawlab API based on OpenAPI parameters.

    Args:
        tool_name: The name of the tool/operation
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path
        param_dict: Dictionary of parameters with their types, defaults, descriptions, and schema information
            Format: {
                "param_name": (
                    param_type,       # Python type (str, int, etc.)
                    default_value,    # Default value or None if required
                    description,      # Parameter description
                    is_path_param,    # Whether this is a path parameter
                    additional_schema # Dictionary with additional schema information (enum, format, etc.)
                )
            }
        enable_logging: Whether to enable execution logging for this tool (default: True)

    Returns:
        A callable function with proper type annotations to be registered as a tool
    """
    import functools
    import inspect
    from typing import (
        Any,
        Dict,
        Literal,
    )

    # Extract path parameters from the path
    path_param_names = re.findall(r"{([^{}]+)}", path)

    # Validate inputs to prevent code injection
    if not isinstance(tool_name, str) or not tool_name.isidentifier():
        raise ValueError(f"Tool name '{tool_name}' is not a valid Python identifier")

    if not isinstance(method, str) or method.lower() not in [
        "get",
        "post",
        "put",
        "delete",
        "patch",
    ]:
        raise ValueError(f"Invalid HTTP method: {method}")

    if not isinstance(path, str):
        raise ValueError("Path must be a string")

    # Separate required and optional parameters
    required_params = []
    optional_params = []
    param_mapping = {}  # Map safe parameter names to original names
    used_param_names = set()  # Track used parameter names to avoid duplicates

    # Process parameters to handle Python keywords and reserved names
    for param_name, (
        param_type,
        default_val,
        description,
        is_path_param,
        additional_schema,
    ) in param_dict.items():
        # Validate parameter name to prevent code injection
        if not isinstance(param_name, str):
            raise ValueError(f"Parameter name must be a string, got {type(param_name)}")

        # Generate a safe parameter name if needed
        safe_param_name = param_name
        if (
            param_name in PYTHON_KEYWORDS
            or param_name == "id"
            or param_name.startswith("_")
            or not param_name.isidentifier()
        ):
            clean_name = "".join(c for c in param_name if c.isalnum() or c == "_")
            clean_name = clean_name.lstrip("_")
            if not clean_name:
                clean_name = "param"
            safe_param_name = f"param_{clean_name}"

            # Ensure the parameter name is unique
            suffix = 1
            original_safe_name = safe_param_name
            while safe_param_name in used_param_names:
                safe_param_name = f"{original_safe_name}_{suffix}"
                suffix += 1

            param_mapping[safe_param_name] = param_name

        # Add to used parameters set
        used_param_names.add(safe_param_name)

        # Ensure path parameters are required
        if is_path_param:
            tools_logger.warning(
                f"Path parameter '{param_name}' in {path} should be required. Forcing as required."
            )
            default_val = None

        # Separate required and optional parameters
        if default_val is None:
            required_params.append((safe_param_name, param_type, description, is_path_param))
        else:
            optional_params.append(
                (safe_param_name, param_type, default_val, description, is_path_param)
            )

    # Helper function to create type annotation based on parameter type and additional schema
    def create_type_annotation(param_type, additional_schema):
        # Check if enum values are provided
        if additional_schema and "enum" in additional_schema:
            enum_values = additional_schema["enum"]
            # For string enums, use Literal
            if param_type == str and all(isinstance(v, str) for v in enum_values):
                return f"Literal[{', '.join(repr(v) for v in enum_values)}]"
            # For numeric enums, use Literal
            elif param_type in (int, float) and all(
                isinstance(v, (int, float)) for v in enum_values
            ):
                return f"Literal[{', '.join(repr(v) for v in enum_values)}]"

        # For other common types, use their type annotations
        if param_type == str:
            return "str"
        elif param_type == int:
            return "int"
        elif param_type == float:
            return "float"
        elif param_type == bool:
            return "bool"
        elif param_type == list:
            return "List[Any]"
        elif param_type == dict:
            return "Dict[str, Any]"
        else:
            return "Any"

    # Helper function to create actual type objects for runtime validation
    def create_actual_type(param_type, additional_schema):
        # Check if enum values are provided
        if additional_schema and "enum" in additional_schema:
            enum_values = additional_schema["enum"]
            # For enums, use Literal
            if all(isinstance(v, (str, int, float, bool)) for v in enum_values):
                return Literal[tuple(enum_values)]

        # For other types, return the type directly
        return param_type

    # Generate function signature as string for eval
    params_str = []
    type_annotations = {}
    param_validators = {}

    # Add required parameters
    for p_name, p_type, p_desc, _ in required_params:
        orig_name = param_mapping.get(p_name, p_name)
        p_schema = param_dict.get(orig_name, (None, None, None, None, {}))[4]
        type_anno = create_type_annotation(p_type, p_schema)
        params_str.append(f"{p_name}: {type_anno}")
        type_annotations[p_name] = create_actual_type(p_type, p_schema)

        # Create validator for schema constraints
        if p_schema:
            validator = {}
            if "enum" in p_schema:
                validator["enum"] = p_schema["enum"]
            if "minimum" in p_schema and p_type in (int, float):
                validator["minimum"] = p_schema["minimum"]
            if "maximum" in p_schema and p_type in (int, float):
                validator["maximum"] = p_schema["maximum"]
            if "pattern" in p_schema and p_type == str:
                validator["pattern"] = p_schema["pattern"]
            if validator:
                param_validators[p_name] = validator

    # Add optional parameters with their default values
    for p_name, p_type, default, p_desc, _ in optional_params:
        orig_name = param_mapping.get(p_name, p_name)
        p_schema = param_dict.get(orig_name, (None, None, None, None, {}))[4]
        type_anno = create_type_annotation(p_type, p_schema)

        # Format default value correctly
        if default is None:
            default_str = "None"
        elif isinstance(default, str):
            default_str = f'"{default}"'
        elif isinstance(default, bool):
            default_str = str(default).lower()
        else:
            default_str = str(default)

        params_str.append(f"{p_name}: {type_anno} = {default_str}")
        type_annotations[p_name] = create_actual_type(p_type, p_schema)

        # Create validator for schema constraints
        if p_schema:
            validator = {}
            if "enum" in p_schema:
                validator["enum"] = p_schema["enum"]
            if "minimum" in p_schema and p_type in (int, float):
                validator["minimum"] = p_schema["minimum"]
            if "maximum" in p_schema and p_type in (int, float):
                validator["maximum"] = p_schema["maximum"]
            if "pattern" in p_schema and p_type == str:
                validator["pattern"] = p_schema["pattern"]
            if validator:
                param_validators[p_name] = validator

    # Define the function dynamically using a factory approach and safer methods
    def create_wrapper():
        # Create function documentation
        doc_lines = [f"Call {method.upper()} {path}"]

        if required_params:
            doc_lines.append("\nRequired Parameters:")
            for p_name, p_type, p_desc, is_path in required_params:
                orig_name = param_mapping.get(p_name, p_name)
                path_indicator = " (path parameter)" if is_path else ""
                doc_lines.append(f"  {p_name}: {p_desc or 'No description'}{path_indicator}")

        if optional_params:
            doc_lines.append("\nOptional Parameters:")
            for p_name, p_type, p_default, p_desc, is_path in optional_params:
                doc_lines.append(f"  {p_name}: {p_desc or 'No description'} (default: {p_default})")

        function_doc = "\n".join(doc_lines)

        # Create parameter list for the signature
        parameters = []

        # Add required parameters
        for p_name, _, _, _ in required_params:
            parameters.append(
                inspect.Parameter(
                    p_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=type_annotations.get(p_name, inspect.Parameter.empty),
                )
            )

        # Add optional parameters with their default values
        for p_name, _, default, _, _ in optional_params:
            parameters.append(
                inspect.Parameter(
                    p_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=default,
                    annotation=type_annotations.get(p_name, inspect.Parameter.empty),
                )
            )

        # Create the function signature
        sig = inspect.Signature(parameters, return_annotation=Dict[str, Any])

        # Create the actual function that will be called
        def actual_function(*args, **kwargs):
            if enable_logging:
                tools_logger.info(f"Executing tool: {tool_name} ({method.upper()} {path})")
                tools_logger.debug(f"Tool parameters: {kwargs}")
                start_time = time.time()

            try:
                # Bind the arguments to the signature to get a mapping of parameter names to values
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()  # Apply default values for missing optional parameters

                # Get the parameter values
                param_values = bound_args.arguments

                # Validate parameters against validators
                for param_name, value in param_values.items():
                    if param_name in param_validators and value is not None:
                        validator = param_validators[param_name]

                        # Check enum values
                        if "enum" in validator:
                            allowed_values = validator["enum"]
                            if value not in allowed_values:
                                allowed_str = ", ".join([repr(v) for v in allowed_values])
                                error_msg = f"Parameter '{param_name}' must be one of [{allowed_str}], got {repr(value)}"
                                if enable_logging:
                                    tools_logger.error(error_msg)
                                raise ValueError(error_msg)

                        # Check minimum constraint
                        if "minimum" in validator and isinstance(value, (int, float)):
                            minimum = validator["minimum"]
                            if value < minimum:
                                error_msg = (
                                    f"Parameter '{param_name}' must be >= {minimum}, got {value}"
                                )
                                if enable_logging:
                                    tools_logger.error(error_msg)
                                raise ValueError(error_msg)

                        # Check maximum constraint
                        if "maximum" in validator and isinstance(value, (int, float)):
                            maximum = validator["maximum"]
                            if value > maximum:
                                error_msg = (
                                    f"Parameter '{param_name}' must be <= {maximum}, got {value}"
                                )
                                if enable_logging:
                                    tools_logger.error(error_msg)
                                raise ValueError(error_msg)

                        # Check pattern constraint
                        if "pattern" in validator and isinstance(value, str):
                            pattern = validator["pattern"]
                            if not re.match(pattern, value):
                                error_msg = f"Parameter '{param_name}' must match pattern '{pattern}', got {repr(value)}"
                                if enable_logging:
                                    tools_logger.error(error_msg)
                                raise ValueError(error_msg)

                # Check for missing path parameters
                missing_path_params = []
                for path_param in path_param_names:
                    found = False
                    # Check if using original parameter name
                    if path_param in param_values:
                        found = True
                    else:
                        # Check if using safe parameter name
                        for safe_name, orig_name in param_mapping.items():
                            if orig_name == path_param and safe_name in param_values:
                                found = True
                                break

                    if not found:
                        missing_path_params.append(path_param)

                if missing_path_params:
                    error_msg = f"Missing required path parameter(s) for {path}: {', '.join(missing_path_params)}"
                    tools_logger.error(error_msg)
                    raise ValueError(error_msg)

                # Validate and transform parameters
                transformed_params = {}

                for key, value in param_values.items():
                    # Get original parameter name if it was renamed
                    orig_key = param_mapping.get(key, key)

                    # Get parameter type info (if available)
                    param_info = param_dict.get(orig_key)
                    if param_info:
                        # Extract parameter type
                        param_type = param_info[0]
                        is_path_param = orig_key in path_param_names

                        # Check if this is a path parameter and validate it's not None
                        if is_path_param and value is None:
                            error_msg = f"Path parameter '{orig_key}' cannot be None for {path}"
                            tools_logger.error(error_msg)
                            raise ValueError(error_msg)

                        # Apply type conversion if needed
                        try:
                            # Only convert if value is not None and not already the correct type
                            if value is not None and not isinstance(value, param_type):
                                transformed_params[key] = param_type(value)
                                if enable_logging:
                                    tools_logger.debug(
                                        f"Converted parameter {key} from {type(value).__name__} to {param_type.__name__}"
                                    )
                            else:
                                transformed_params[key] = value
                        except (ValueError, TypeError) as e:
                            # Special handling for path parameters - they must be valid
                            if is_path_param:
                                error_msg = (
                                    f"Invalid value for path parameter '{orig_key}': {str(e)}"
                                )
                                tools_logger.error(error_msg)
                                raise ValueError(error_msg)

                            if enable_logging:
                                tools_logger.warning(
                                    f"Failed to convert parameter {key} to {param_type.__name__}: {str(e)}. Using original value."
                                )
                            transformed_params[key] = value
                    else:
                        # If no type info, just pass through
                        transformed_params[key] = value

                # Replace path parameters and build request data
                endpoint = path
                query_params = {}
                body_data = {}

                # Process all parameters
                for key, value in transformed_params.items():
                    # Skip None values for optional parameters that aren't required
                    if value is None and key not in [p[0] for p in required_params]:
                        continue

                    # Get original parameter name if it was renamed
                    orig_key = param_mapping.get(key, key)

                    # Replace path parameters
                    if "{" + orig_key + "}" in endpoint:
                        # Convert value to string and ensure it's properly URL encoded
                        str_value = str(value)
                        endpoint = endpoint.replace("{" + orig_key + "}", str_value)
                    # Add to appropriate dictionary based on HTTP method
                    elif method.lower() in ["get", "delete"]:
                        query_params[orig_key] = value
                    else:
                        body_data[orig_key] = value

                # Make the API request
                api_response = api_request(
                    method=method.upper(),
                    endpoint=endpoint.lstrip("/"),
                    params=query_params if query_params else None,
                    data=body_data if body_data else None,
                )
                result = api_response.get("data", {})

                if enable_logging:
                    execution_time = time.time() - start_time
                    tools_logger.info(
                        f"Tool {tool_name} executed successfully in {execution_time:.2f} seconds"
                    )

                    # Log result summary (truncate if too large)
                    result_str = str(result)
                    if len(result_str) > 200:
                        tools_logger.debug(f"Result (truncated): {result_str[:197]}...")
                    else:
                        tools_logger.debug(f"Result: {result_str}")

                return result

            except Exception as e:
                if enable_logging:
                    execution_time = time.time() - start_time
                    tools_logger.error(
                        f"Tool {tool_name} failed after {execution_time:.2f} seconds: {str(e)}",
                        exc_info=True,
                    )
                raise

        # Create the wrapper function with proper signature and docstring
        @functools.wraps(actual_function)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            return actual_function(*args, **kwargs)

        # Set the signature and docstring
        wrapper.__signature__ = sig
        wrapper.__doc__ = function_doc
        wrapper.__name__ = tool_name

        # Set function annotations with complete type information
        wrapper.__annotations__ = {k: v for k, v in sig.parameters.items()}
        wrapper.__annotations__["return"] = Dict[str, Any]

        # Create input schema that includes default values for optional parameters
        input_schema = {
            "type": "object",
            "properties": {},
            "required": [p[0] for p in required_params],
        }

        # Add all parameters to the properties
        for p_name, p_type, p_desc, _ in required_params:
            orig_name = param_mapping.get(p_name, p_name)
            p_schema = param_dict.get(orig_name, (None, None, None, None, {}))[4]
            property_schema = {"type": PYTHON_TO_OPENAPI_TYPES.get(p_type, "string")}

            # Add description if available
            if p_desc:
                property_schema["description"] = p_desc

            # Add additional schema properties if available
            if p_schema:
                for key, value in p_schema.items():
                    property_schema[key] = value

            input_schema["properties"][p_name] = property_schema

        for p_name, p_type, default, p_desc, _ in optional_params:
            orig_name = param_mapping.get(p_name, p_name)
            p_schema = param_dict.get(orig_name, (None, None, None, None, {}))[4]
            property_schema = {"type": PYTHON_TO_OPENAPI_TYPES.get(p_type, "string")}

            # Add default value
            property_schema["default"] = default

            # Add description if available
            if p_desc:
                property_schema["description"] = p_desc

            # Add additional schema properties if available
            if p_schema:
                for key, value in p_schema.items():
                    property_schema[key] = value

            input_schema["properties"][p_name] = property_schema

        # Attach the input schema to the function
        wrapper.input_schema = input_schema

        return wrapper

    # Create the final function
    final_function = create_wrapper()

    return final_function


def create_tool(
    tool_name: str, method: str, path: str, param_dict: Dict[str, Any], enable_logging=True
) -> Tool:
    """Create a Tool object with schema support for required fields, enums, and other schema features.

    Args:
        tool_name: The name of the tool/operation
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path
        param_dict: Dictionary of parameters with their types, defaults, descriptions, and metadata
        enable_logging: Whether to enable execution logging for this tool (default: True)

    Returns:
        A Tool object ready to be registered with a ToolRegistry

    The param_dict should follow this format:
    {
        "param_name": (
            param_type,         # Python type (str, int, etc.)
            default_value,      # Default value or None if required
            description,        # Parameter description
            is_path_param,      # Whether this is a path parameter
            {                   # Optional dictionary with additional schema information
                "enum": [...],  # List of allowed values
                "minimum": n,   # Minimum value for numbers
                "maximum": n,   # Maximum value for numbers
                "pattern": "...",  # Regex pattern for strings
                "format": "..."    # Format for specific types (date, email, etc.)
            }
        )
    }
    """
    # Create the function for the tool
    func = create_tool_function(tool_name, method, path, param_dict, enable_logging)

    # Create the schema for the tool using the input_schema attribute
    schema = {
        "name": tool_name,
        "description": f"Call {method.upper()} {path}",
        "parameters": func.input_schema,  # Use the input_schema directly
    }

    # Create and return the Tool object
    return Tool(name=tool_name, description=schema["description"], function=func, schema=schema)


def list_tags(resolved_spec):
    """List all available tags/endpoint groups in the API."""

    def wrapper():
        tags_dict = {}

        # Extract tags from the top-level OpenAPI spec
        for tag_info in resolved_spec.get("tags", []):
            tag_name = tag_info.get("name", "")
            tags_dict[tag_name] = {"description": tag_info.get("description", ""), "tools": []}

        # If no tags are defined in the spec, initialize from operations
        if not tags_dict:
            for path, path_item in resolved_spec.get("paths", {}).items():
                for method, operation in path_item.items():
                    if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                        continue

                    operation_tags = operation.get("tags", [])
                    for tag in operation_tags:
                        if tag not in tags_dict:
                            tags_dict[tag] = {
                                "description": f"Operations tagged with {tag}",
                                "tools": [],
                            }

        # Populate tools under each tag
        for path, path_item in resolved_spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                    continue

                operation_tags = operation.get("tags", [])
                operation_id = operation.get("operationId")
                summary = operation.get("summary", "")

                if operation_id:
                    tool_info = {
                        "name": operation_id,
                        "method": method.upper(),
                        "summary": summary,
                    }

                    # Add tool to each tag it belongs to
                    for tag in operation_tags:
                        if tag in tags_dict:
                            tags_dict[tag]["tools"].append(tool_info)

        # Convert to list format for return
        tags_list = [
            {"name": name, "description": info["description"], "tools": info["tools"]}
            for name, info in tags_dict.items()
        ]

        return {"tags": tags_list}

    return wrapper


def model_supports_tools(model_name: str) -> bool:
    """
    Check if a model supports tools/function calling based on regex patterns.

    Args:
        model_name: Name of the model to check.

    Returns:
        True if the model supports tools, False otherwise.
    """
    # First check the legacy hard-coded dictionary
    if model_name in MODELS_WITH_TOOL_SUPPORT:
        return MODELS_WITH_TOOL_SUPPORT[model_name]

    # Then check regex patterns
    for pattern in MODEL_TOOL_SUPPORT_PATTERNS:
        if re.match(pattern, model_name):
            return True

    return False


def export_tool_schemas(tool_schemas, output_file=None):
    """
    Export tool schemas to a JSON file or return them as a string.

    Args:
        tool_schemas: Dictionary of tool schemas to export
        output_file: Optional path to export JSON file. If None, returns JSON string.

    Returns:
        If output_file is provided, writes to file and returns None.
        Otherwise, returns the JSON string.
    """
    # Format the schemas as properly indented JSON
    json_str = json.dumps(tool_schemas, indent=2)

    if output_file:
        with open(output_file, "w") as f:
            f.write(json_str)
        tools_logger.info(f"Tool schemas exported to {output_file}")
        return None

    return json_str


def get_tool_schemas_function(registered_tools):
    """Create a function that returns the schema definitions for tools.

    Args:
        registered_tools: Dictionary of tool definitions

    Returns:
        A callable function to be registered as a tool
    """

    # Pre-process tools to create full schema information for each tool
    tool_schemas = {}
    for tool_name, tool_info in registered_tools.items():
        # Extract info from the tool registration
        method = tool_info.get("method", "")
        path = tool_info.get("path", "")
        operation = tool_info.get("operation", {})

        # Create full schema with rich type information
        input_schema = create_input_schema_from_openapi(tool_name, operation, method, path)

        # Store the enhanced schema
        tool_schemas[tool_name] = input_schema

    def get_tool_schemas(tool_name=None):
        """Get the schema definition for one or all tools.

        Args:
            tool_name: Optional name of specific tool to get schema for.
                      If not provided, returns all tool schemas.

        Returns:
            Dictionary containing tool schema(s) with detailed parameter information
            including required parameters and enum values
        """
        if tool_name is not None:
            if tool_name not in tool_schemas:
                return {"error": f"Tool '{tool_name}' not found"}
            return {"tools": [tool_schemas[tool_name]]}

        # Return all tool schemas
        return {"tools": list(tool_schemas.values())}

    return get_tool_schemas


def list_parameter_info(registered_tools):
    """Create a function that returns detailed parameter information for tools.

    This is specifically designed to help AI agents understand what parameters
    are required and what enum values are available.

    Args:
        registered_tools: Dictionary of tool definitions

    Returns:
        A callable function to be registered as a tool
    """
    # Pre-process tools to create parameter information for quick access
    tool_param_info = {}
    for tool_name, tool_info in registered_tools.items():
        # Extract info from the tool registration
        method = tool_info.get("method", "")
        path = tool_info.get("path", "")
        operation = tool_info.get("operation", {})

        # Get parameter details
        param_info = {"required_params": [], "enum_params": {}, "path_params": []}

        # Process parameters from the operation
        for param in operation.get("parameters", []):
            param_name = param.get("name")
            param_required = param.get("required", False)
            param_schema = param.get("schema", {})
            param_in = param.get("in", "")

            # Track required parameters
            if param_required:
                param_info["required_params"].append(param_name)

            # Track path parameters
            if param_in == "path":
                param_info["path_params"].append(param_name)

            # Track enum parameters
            if "enum" in param_schema:
                param_info["enum_params"][param_name] = param_schema["enum"]

        # Process request body if present
        request_body = operation.get("requestBody", {})
        if request_body:
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            if json_content:
                schema = json_content.get("schema", {})
                properties = schema.get("properties", {})
                required = schema.get("required", [])

                # Add required body parameters
                if required:
                    param_info["required_params"].extend(required)

                # Check for enum values in body parameters
                for prop_name, prop_schema in properties.items():
                    if "enum" in prop_schema:
                        param_info["enum_params"][prop_name] = prop_schema["enum"]

        # Store parameter info for this tool
        tool_param_info[tool_name] = param_info

    def list_parameters(tool_name=None):
        """Get detailed parameter information for one or all tools.

        This function is designed to help AI agents understand
        what parameters are required and what enum values are available.

        Args:
            tool_name: Optional name of specific tool to get parameter info for.
                      If not provided, returns parameter info for all tools.

        Returns:
            Dictionary containing parameter information including:
            - required_params: List of required parameter names
            - enum_params: Dictionary mapping parameter names to their enum values
            - path_params: List of parameters that are part of the URL path
        """
        if tool_name is not None:
            if tool_name not in tool_param_info:
                return {"error": f"Tool '{tool_name}' not found"}
            return {"tool": tool_name, "parameters": tool_param_info[tool_name]}

        # Return all parameter information
        return {"tools": {name: info for name, info in tool_param_info.items()}}

    return list_parameters


def create_tools_from_openapi(
    openapi_spec: Dict[str, Any],
    filter_tags: Optional[List[str]] = None,
    filter_operations: Optional[List[str]] = None,
    enable_logging: bool = True,
) -> Dict[str, Tool]:
    """Create Tool objects from an OpenAPI specification with enhanced schema support.

    Args:
        openapi_spec: The resolved OpenAPI specification
        filter_tags: Optional list of tags to filter operations by
        filter_operations: Optional list of operation IDs to include
        enable_logging: Whether to enable logging for the created tools

    Returns:
        A dictionary mapping operation IDs to Tool objects
    """
    tools = {}

    # Get the paths from the OpenAPI spec
    paths = openapi_spec.get("paths", {})

    # Iterate through each path
    for path, path_item in paths.items():
        # Iterate through each HTTP method in the path
        for method, operation in path_item.items():
            # Skip non-HTTP methods
            if method not in ["get", "post", "put", "delete", "patch"]:
                continue

            # Get the operation ID
            operation_id = operation.get("operationId")
            if not operation_id:
                # Generate an operation ID if not provided
                path_parts = path.strip("/").split("/")
                operation_id = f"{method}_{('_'.join(path_parts)).replace('-', '_')}"

            # Check if we should filter by tags
            if filter_tags:
                operation_tags = operation.get("tags", [])
                if not any(tag in filter_tags for tag in operation_tags):
                    continue

            # Check if we should filter by operation IDs
            if filter_operations and operation_id not in filter_operations:
                continue

            # Extract the parameters
            param_dict = extract_openapi_parameters(operation)

            # Create the tool
            tools[operation_id] = create_tool(
                tool_name=operation_id,
                method=method,
                path=path,
                param_dict=param_dict,
                enable_logging=enable_logging,
            )

    return tools
