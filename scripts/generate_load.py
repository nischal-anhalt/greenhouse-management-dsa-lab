import json
import os
import time
import urllib.error
import urllib.request
import urllib.parse
import ssl
import sys

# Update the Base URL to the secure Traefik Gateway
BASE_URL = os.getenv("REST_BASE_URL", "https://localhost:8443/api")
CALLS = int(os.getenv("CALLS", "200"))
KEYCLOAK_TOKEN_URL = "http://localhost:8088/realms/dsa-lab/protocol/openid-connect/token"

def get_jwt_token():
    """Authenticates with Keycloak using the Resource Owner Password flow to obtain a JWT."""
    print("Authenticating with Keycloak to obtain JWT...")
    data = urllib.parse.urlencode({
        "client_id": "rest-api",
        "grant_type": "password",
        "username": "alice",
        "password": "secret"
    }).encode('utf-8')
    
    req = urllib.request.Request(KEYCLOAK_TOKEN_URL, data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            token_data = json.loads(response.read().decode('utf-8'))
            print("Successfully obtained JWT token.\n")
            return token_data.get("access_token")
    except Exception as e:
        print(f"Failed to obtain token: {e}")
        sys.exit(1)

def get_ssl_context():
    """Creates an SSL context. Disables strict CA validation for the lab environment."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def call(method, path, token, ssl_context, body=None):
    data = None
    # Inject the Bearer token into every request
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        # Pass the relaxed SSL context to urllib
        with urllib.request.urlopen(request, timeout=3, context=ssl_context) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code
    except Exception as exc:
        print(f"Connection error: {exc}")
        return 0

if __name__ == "__main__":
    # Setup Auth and SSL exactly once before the loop
    token = get_jwt_token()
    ssl_ctx = get_ssl_context()

    print(f"Starting load generation for {CALLS} requests...\n")

    for i in range(CALLS):
        if i % 10 == 0:
            # Deliberately fetch a non-existent item to generate 404/405 errors
            status = call("GET", "/items/999999-invalid", token, ssl_ctx)
        elif i % 5 == 0: 
            # Create a new plant (Fixed logic: was previously i % 10 == 0)
            status = call("POST", "/items", token, ssl_ctx, {
                "name": f"observability-plant-{i}",
                "status": "healthy",
                "location": "Zone 1", 
            })
        else:
            # List all plants
            status = call("GET", "/items", token, ssl_ctx)
        
        print(f"{i + 1:03d}: HTTP {status}")
        time.sleep(0.15)