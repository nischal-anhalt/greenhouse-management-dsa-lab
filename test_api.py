import requests
import json

BASE_URL = "http://localhost:8080"
HEADERS = {"Content-Type": "application/json"}

def print_separator(title):
    print(f"\n{'='*50}")
    print(f" {title} ")
    print(f"{'='*50}")

def test_endpoint(method, endpoint, payload=None):
    url = f"{BASE_URL}{endpoint}"
    print(f"\n> [{method}] {url}")
    
    if payload:
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
    if method == "POST":
        response = requests.post(url, json=payload, headers=HEADERS)
    elif method == "GET":
        response = requests.get(url, headers=HEADERS)
    elif method == "PUT":
        response = requests.put(url, json=payload, headers=HEADERS)
    elif method == "DELETE":
        response = requests.delete(url, headers=HEADERS)
    else:
        print("Unsupported HTTP method")
        return None

    print(f"Status Code: {response.status_code}")
    
    try:
        # Try to parse and print JSON response if available
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except requests.exceptions.JSONDecodeError:
        # If response is empty (like a 204 No Content), just print the raw text
        print(f"Response: {response.text}")
        
    return response

def run_tests():
    print_separator("GREENHOUSE ENDPOINTS")
    
    # 1. Create a Greenhouse
    gh_payload = {"name": "Tropical Zone"}
    res = test_endpoint("POST", "/greenhouses", gh_payload)
    gh_id = res.json().get("id")

    # 2. List Greenhouses
    test_endpoint("GET", "/greenhouses")

    # 3. Get Single Greenhouse
    test_endpoint("GET", f"/greenhouses/{gh_id}")

    # 4. Update Greenhouse
    update_payload = {"name": "Tropical Zone Updated"}
    test_endpoint("PUT", f"/greenhouses/{gh_id}", update_payload)

    print_separator("PLANT ENDPOINTS")
    
    # 5. Create a Plant (linking it to the greenhouse we just made)
    pl_payload = {"name": "Monstera Deliciosa", "species": "Monstera", "greenhouse_id": gh_id}
    res = test_endpoint("POST", "/plants", pl_payload)
    pl_id = res.json().get("id")

    # 6. List Plants
    test_endpoint("GET", "/plants")

    # 7. Get Single Plant
    test_endpoint("GET", f"/plants/{pl_id}")

    print_separator("CLEANUP / DELETE ENDPOINTS")
    
    # 8. Delete Plant
    test_endpoint("DELETE", f"/plants/{pl_id}")
    
    # 9. Verify Plant Deletion
    test_endpoint("GET", f"/plants/{pl_id}")

    # 10. Delete Greenhouse
    test_endpoint("DELETE", f"/greenhouses/{gh_id}")
    
    # 11. Verify Greenhouse Deletion
    test_endpoint("GET", f"/greenhouses/{gh_id}")

if __name__ == "__main__":
    try:
        run_tests()
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to {BASE_URL}. Is your Docker container running?")