import json
import os
import time
import urllib.error
import urllib.request

BASE_URL = os.getenv("REST_BASE_URL", "http://localhost:8085")
CALLS = int(os.getenv("CALLS", "200"))

def call(method, path, body=None):
    data = None
    headers = {}
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
        with urllib.request.urlopen(request, timeout=3) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        return exc.code
    except Exception:
        return 0

for i in range(CALLS):
    if i % 10 == 0:
        # Deliberately fetch a non-existent item to generate 404 errors
        status = call("GET", "/items/999999")
    elif i % 10 == 0:
        # Create a new plant
        status = call("POST", "/items", {
            "name": f"observability-plant-{i}",
            "status": "healthy",
            "location": "Zone 1", 
        })
    else:
        # List all plants
        status = call("GET", "/items")
    
    print(f"{i + 1:03d}: HTTP {status}")
    time.sleep(0.15)