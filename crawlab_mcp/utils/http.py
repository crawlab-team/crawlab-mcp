import json
import logging
import time
from typing import Dict, Optional

import requests

import crawlab_mcp
from crawlab_mcp.utils.constants import CRAWLAB_API_BASE_URL, CRAWLAB_PASSWORD, CRAWLAB_USERNAME

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def api_request(
    method: str,
    endpoint: str,
    data: Optional[Dict] = None,
    params: Optional[Dict] = None,
) -> Dict:
    """Make a request to the Crawlab API."""
    url = f"{CRAWLAB_API_BASE_URL}/{endpoint}"
    headers = {
        "Content-Type": "application/json",
    }

    # Log the request details
    logger.info(f"Making {method.upper()} request to {endpoint}")

    # Mask sensitive data in logs
    safe_params = params.copy() if params else {}
    safe_data = None
    if data:
        safe_data = data.copy()
        # Mask any sensitive fields like passwords, tokens, etc.
        for key in safe_data:
            if any(
                sensitive in key.lower()
                for sensitive in ["password", "token", "secret", "key", "auth"]
            ):
                safe_data[key] = "******"

    logger.debug(f"Request URL: {url}")
    logger.debug(f"Request params: {safe_params}")
    logger.debug(f"Request data: {safe_data}")

    # Add authorization if needed
    if endpoint not in ["login", "system-info"]:
        token = get_api_token()
        headers["Authorization"] = f"Bearer {token}" if token else None
        logger.debug(f"Using authorization token: {token[:5]}...{token[-5:] if token else None}")

    # Make the request with timing
    start_time = time.time()
    try:
        logger.debug(f"Sending {method.upper()} request to {url}")
        response = requests.request(
            method=method, url=url, headers=headers, json=data, params=params
        )

        # Calculate request time
        request_time = time.time() - start_time
        logger.info(
            f"Request completed in {request_time:.2f} seconds with status code: {response.status_code}"
        )

        # Log response details
        try:
            response_json = response.json()
            # Truncate response if too large
            response_str = json.dumps(response_json)
            if len(response_str) > 500:
                logger.debug(f"Response (truncated): {response_str[:497]}...")
            else:
                logger.debug(f"Response: {response_str}")
        except Exception as e:
            logger.debug(f"Could not parse response as JSON: {str(e)}")
            # Log text response if not JSON
            if len(response.text) > 500:
                logger.debug(f"Response text (truncated): {response.text[:497]}...")
            else:
                logger.debug(f"Response text: {response.text}")

        # Raise for HTTP errors
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        request_time = time.time() - start_time
        logger.error(f"Request failed after {request_time:.2f} seconds: {str(e)}", exc_info=True)
        raise


def get_api_token() -> str:
    """Get the Crawlab API token, either from cache or by logging in."""
    # Check if we already have a token
    if crawlab_mcp.utils.constants.CRAWLAB_API_TOKEN:
        logger.debug("Using cached API token")
        return crawlab_mcp.utils.constants.CRAWLAB_API_TOKEN

    # Check if we have credentials
    if not CRAWLAB_USERNAME or not CRAWLAB_PASSWORD:
        logger.error("Crawlab API token or username/password not provided")
        raise ValueError("Crawlab API token or username/password not provided")

    # Log in to get a token
    logger.info("No cached token found, logging in to get a new token")
    start_time = time.time()

    try:
        response = requests.post(
            url=CRAWLAB_API_BASE_URL + "/login",
            json={"username": CRAWLAB_USERNAME, "password": CRAWLAB_PASSWORD},
        )

        login_time = time.time() - start_time
        logger.info(
            f"Login request completed in {login_time:.2f} seconds with status code: {response.status_code}"
        )

        response.raise_for_status()
        response_data = response.json()

        if token := response_data.get("data"):
            logger.info("Successfully obtained API token")
            crawlab_mcp.utils.constants.CRAWLAB_API_TOKEN = token
            return crawlab_mcp.utils.constants.CRAWLAB_API_TOKEN
        else:
            logger.error("API token not found in login response")
            raise ValueError("Failed to get API token")
    except Exception as e:
        login_time = time.time() - start_time
        logger.error(f"Login failed after {login_time:.2f} seconds: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to get API token: {str(e)}")
