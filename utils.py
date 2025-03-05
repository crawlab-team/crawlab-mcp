import os
from typing import Dict, Optional

import requests


def api_request(
    method: str,
    endpoint: str,
    data: Optional[Dict] = None,
    params: Optional[Dict] = None,
) -> Dict:
    """Make a request to the Crawlab API."""
    url = f"{CRAWLAB_API_BASE_URL}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {CRAWLAB_API_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.request(method=method, url=url, headers=headers, json=data, params=params)

    response.raise_for_status()
    return response.json()


def create_tool_function(tool_name, method, path, param_dict):
    """Create a tool function that calls the Crawlab API based on OpenAPI parameters.

    Args:
        tool_name: The name of the tool/operation
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path
        param_dict: Dictionary of parameters with their types and defaults

    Returns:
        A callable function to be registered as a tool
    """
    # Separate required and optional parameters
    required_params = []
    optional_params = []
    param_mapping = {}  # Map safe parameter names to original names
    used_param_names = set()  # Track used parameter names to avoid duplicates

    # Process parameters to handle Python keywords and reserved names
    for param_name, (param_type, default_val, _) in param_dict.items():
        # Generate a safe parameter name if needed
        safe_param_name = param_name
        if param_name in PYTHON_KEYWORDS or param_name == "id" or param_name.startswith("_"):
            clean_name = param_name.lstrip("_")
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

        # Separate required and optional parameters
        if default_val is None:
            required_params.append((safe_param_name, param_type))
        else:
            optional_params.append((safe_param_name, param_type, default_val))

    # Define the function dynamically using a factory approach
    def create_wrapper():
        # Create the parameter signature for the function
        params = []
        for p_name, _ in required_params:
            params.append(p_name)

        for p_name, _, default in optional_params:
            params.append((p_name, default))

        # Use the parameter information captured in closure
        def wrapper(*args, **kwargs) -> Dict:
            # Build the parameter dictionary from args and kwargs
            param_values = {}

            # Process positional arguments
            for i, arg in enumerate(args):
                if i < len(required_params):
                    param_values[required_params[i][0]] = arg
                elif i < len(required_params) + len(optional_params):
                    param_values[optional_params[i - len(required_params)][0]] = arg

            # Process keyword arguments
            param_values.update(kwargs)

            # Replace path parameters and build request data
            endpoint = path
            query_params = {}
            body_data = {}

            # Process all parameters
            for key, value in param_values.items():
                # Get original parameter name if it was renamed
                orig_key = param_mapping.get(key, key)

                # Replace path parameters
                if "{" + orig_key + "}" in endpoint:
                    endpoint = endpoint.replace("{" + orig_key + "}", str(value))
                # Add to appropriate dictionary based on HTTP method
                elif method.lower() in ["get", "delete"]:
                    query_params[orig_key] = value
                else:
                    body_data[orig_key] = value

            # Make the API request
            return api_request(
                method=method.upper(),
                endpoint=endpoint.lstrip("/"),
                params=query_params if query_params else None,
                data=body_data if body_data else None,
            ).get("data", {})

        # Create a correctly formatted signature for the wrapper function
        from inspect import Parameter, signature

        # Build parameter list for function signature
        parameters = []
        for param_name, param_type in required_params:
            parameters.append(
                Parameter(param_name, Parameter.POSITIONAL_OR_KEYWORD, annotation=param_type),
            )

        for param_name, param_type, default_val in optional_params:
            parameters.append(
                Parameter(
                    param_name,
                    Parameter.POSITIONAL_OR_KEYWORD,
                    default=default_val,
                    annotation=param_type,
                ),
            )

        # Apply the correct signature to our wrapper function
        wrapper.__signature__ = signature(wrapper).replace(parameters=parameters)
        wrapper.__name__ = tool_name
        wrapper.__doc__ = f"Tool function for {tool_name} operation"

        return wrapper

    return create_wrapper()


CRAWLAB_API_BASE_URL = os.getenv("CRAWLAB_API_BASE_URL", "http://localhost:8080/api")
CRAWLAB_API_TOKEN = os.getenv("CRAWLAB_API_TOKEN", "")
PYTHON_KEYWORDS = {
    "False",
    "None",
    "True",
    "and",
    "as",
    "assert",
    "async",
    "await",
    "break",
    "class",
    "continue",
    "def",
    "del",
    "elif",
    "else",
    "except",
    "finally",
    "for",
    "from",
    "global",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "nonlocal",
    "not",
    "or",
    "pass",
    "raise",
    "return",
    "try",
    "while",
    "with",
    "yield",
}
