import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
import sys

# Configuration
BASE_URL = "https://localhost:8443/api"
KEYCLOAK_TOKEN_URL = "http://localhost:8088/realms/dsa-lab/protocol/openid-connect/token"
CA_CERT_PATH = "security/certs/ca.crt"

def print_separator(title):
    print(f"\n{'='*50}")
    print(f" {title} ")
    print(f"{'='*50}")

def get_jwt_token():
    """Authenticates with Keycloak using the Resource Owner Password flow to obtain a JWT."""
    print("Authenticating with Keycloak to obtain JWT...")
    
    # URL-encoded payload for Keycloak
    data = urllib.parse.urlencode({
        "client_id": "rest-api",
        "grant_type": "password",
        "username": "alice",
        "password": "secret"
    }).encode('utf-8')
    
    req = urllib.request.Request(KEYCLOAK_TOKEN_URL, data=data, method="POST")
    
    try:
        # Keycloak is internal (HTTP), so no custom SSL context is needed here
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            token_data = json.loads(res_body)
            print("Successfully obtained JWT token.\n")
            return token_data.get("access_token")
    except urllib.error.HTTPError as e:
        print(f"Failed to obtain token (HTTP {e.code}): {e.read().decode('utf-8')}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Failed to connect to Keycloak: {e.reason}")
        sys.exit(1)

def get_ssl_context():
    """Creates an SSL context that trusts our custom offline Root CA."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    except FileNotFoundError:
        print(f"Error: Could not find CA certificate at {CA_CERT_PATH}.")
        sys.exit(1)

def test_endpoint(method, endpoint, headers, ssl_context, payload=None):
    """A generic wrapper around urllib to simulate requests-like behavior."""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n> [{method}] {url}")
    
    data = None
    if payload:
        print(f"Payload: {json.dumps(payload, indent=2)}")
        data = json.dumps(payload).encode('utf-8')
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        # Execute the request
        with urllib.request.urlopen(req, context=ssl_context) as response:
            status_code = response.getcode()
            body = response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        # urllib throws an exception for 4xx and 5xx errors, so we catch them here
        status_code = e.code
        body = e.read().decode('utf-8')
    except urllib.error.URLError as e:
        print(f"Connection Error: {e.reason}")
        return None

    print(f"Status Code: {status_code}")
    
    parsed_json = None
    if body:
        try:
            parsed_json = json.loads(body)
            print(f"Response: {json.dumps(parsed_json, indent=2)}")
        except json.JSONDecodeError:
            print(f"Response: {body}")
            
    # Return a dictionary since we aren't using the requests.Response object
    return {"status_code": status_code, "json": parsed_json, "text": body}

def run_tests():
    # 1. Setup Auth and Security
    token = get_jwt_token()
    ssl_ctx = get_ssl_context()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 2. Run Greenhouse Endpoints
    print_separator("CREATE")
    
    gh_payload = {"name": "Tropical Zone", "status": "ripe", "location": "Zone-1-east"}
    test_endpoint("POST", "/items", headers, ssl_ctx, gh_payload)
    
    res = test_endpoint("GET", "/items", headers, ssl_ctx)

    # Safely extract ID from first element using our custom dictionary return format
    gh_id = res.get("json", {})[0].get("id") if res else None

    if not gh_id:
        print("Failed to create greenhouse, aborting further tests.")
        return

    print_separator("UPDATE")
    update_payload = {"name": "Tropical Zone Updated", "status": "updated-ripe", "location": "Zone-2-west"}
    test_endpoint("PUT", f"/items/{gh_id}", headers, ssl_ctx, update_payload)

    # 4. Run Cleanup Endpoints
    print_separator("CLEANUP / DELETE ENDPOINTS")

    if gh_id:
        test_endpoint("DELETE", f"/items/{gh_id}", headers, ssl_ctx)

if __name__ == "__main__":
    run_tests()