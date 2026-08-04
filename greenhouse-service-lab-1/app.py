import os
import time
import logging
import grpc
import jwt
from jwt import PyJWKClient
from flask import Flask, jsonify, request, Response, g
from pybreaker import CircuitBreakerError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

import items_pb2
import items_pb2_grpc
from reliability import BackendUnavailable, protected_call

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

CA_CERT = os.getenv("CA_CERT", "/certs/ca.crt")
REST_CLIENT_CERT = os.getenv("REST_CLIENT_CERT", "/certs/rest-client.crt")
REST_CLIENT_KEY = os.getenv("REST_CLIENT_KEY", "/certs/rest-client.key")
GRPC_TARGET = os.getenv("GRPC_TARGET", "grpc-service:50051")

def read_bytes(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read()

# =========================== Auth validation logic =====================================================
JWKS_URL = os.getenv("JWKS_URL", "http://localhost:8088/realms/dsa-lab/protocol/openid-connect/certs")
JWT_ISSUER = os.getenv("JWT_ISSUER", "http://localhost:8088/realms/dsa-lab")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "rest-api")

_jwks_client = PyJWKClient(JWKS_URL)

def extract_bearer_token(auth_header: str) -> str | None:
    prefix = "Bearer "
    if not auth_header or not auth_header.startswith(prefix):
        return None
    token = auth_header[len(prefix):].strip()
    return token or None

def verify_access_token(token: str) -> dict:
    signing_key = _jwks_client.get_signing_key_from_jwt(token).key
    return jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
    )

# Start the timer before each request
@app.before_request
def metrics_start_timer():
    request._metrics_start_time = time.perf_counter()

@app.before_request
def require_valid_token():
    # Keep health and metrics endpoints public
    if request.path in ("/health", "/metrics"):
        return None
        
    token = extract_bearer_token(request.headers.get("Authorization", ""))
    if token is None:
        return error_response("missing_token", "Bearer token is required.", 401)
        
    try:
        claims = verify_access_token(token)
    except jwt.PyJWTError as exc:
        return error_response("invalid_token", str(exc), 401)
        
    # Store user info in Flask's global 'g' object for the request lifecycle
    g.user = claims.get("preferred_username", claims.get("sub"))
    g.roles = claims.get("realm_access", {}).get("roles", [])
    return None

# =========================== Auth validation logic end=====================================================

# Define the Metrics
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

# Helper to avoid high-cardinality labels (e.g., tracking /items/<id> instead of /items/123)
def route_pattern():
    if request.url_rule is None:
        return "unknown"
    return request.url_rule.rule

# Record the metrics after each request
@app.after_request
def metrics_record(response):
    if request.endpoint != "metrics":
        endpoint = route_pattern()
        
        # Safely get the start time. If it wasn't set, fallback to current time.
        start_time = getattr(request, '_metrics_start_time', time.perf_counter())
        duration = time.perf_counter() - start_time
        
        HTTP_REQUEST_DURATION.labels(request.method, endpoint).observe(duration)
        HTTP_REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
    return response

# Expose the metrics endpoint for Prometheus to scrape
@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


# Connect to the gRPC service using the Docker Compose service name
GRPC_TARGET = os.getenv("GRPC_TARGET", "grpc-service:50051")
channel_credentials = grpc.ssl_channel_credentials(
    root_certificates=read_bytes(CA_CERT),
    certificate_chain=read_bytes(REST_CLIENT_CERT),
    private_key=read_bytes(REST_CLIENT_KEY),
)

channel = grpc.secure_channel(GRPC_TARGET, channel_credentials)
stub = items_pb2_grpc.ItemServiceStub(channel)

def error_response(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status

@app.route('/items', methods=['GET'])
def list_items():
    def grpc_operation():
        # Call the Server-Streaming ListItems method
        response_stream = stub.ListItems(items_pb2.ListItemsRequest(), timeout=5.0)
        
        # Collect the streamed items into a list of dictionaries
        items_list = []
        for item in response_stream:
            items_list.append({
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "location": item.location
            })
        return items_list

    # Execute the call through the Circuit Breaker
    try:
        items = protected_call(grpc_operation)
    except CircuitBreakerError:
        return error_response("backend_unavailable", "gRPC service is temporarily unavailable (Circuit Open).", 503)
    except BackendUnavailable:
        return error_response("backend_failure", "gRPC service did not respond successfully after retries.", 502)
    except grpc.RpcError as e:
        return error_response("internal_error", str(e), 500)

    # Return the collected list as a JSON array
    return jsonify(items), 200

@app.route('/items', methods=['POST'])
def create_item():
    # --- Role-Based Access Control ---
    if "ROLE_USER" not in getattr(g, "roles", []):
        return error_response(
            "forbidden", 
            f"User {getattr(g, 'user', 'unknown')} lacks the required ROLE_USER permission.", 
            403
        )
    # --------------------------------------
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return error_response("invalid_json", "Request body must be valid JSON.", 400)
    
    # Basic validation
    if not data.get("name") or not data.get("status") or not data.get("location"):
        return error_response("validation_error", "Missing name, status, or location.", 400)

    # 1. Define the gRPC operation
    def grpc_operation():
        request_message = items_pb2.CreateItemRequest(
            name=data["name"].strip(),
            status=data["status"].strip(),
            location=data["location"].strip()
        )
        # Call the Client-Streaming AddItems method
        return stub.AddItems(iter([request_message]), timeout=2.0)
    
    # 2. Execute the call through the Circuit Breaker
    try:
        result = protected_call(grpc_operation)
    except CircuitBreakerError:
        return error_response("backend_unavailable", "gRPC service is temporarily unavailable (Circuit Open).", 503)
    except BackendUnavailable:
        return error_response("backend_failure", "gRPC service did not respond successfully after retries.", 502)

    # 3. Return success
    return jsonify({
        "message": "created through gRPC",
        "created_count": result.created_count,
        "total_count": result.total_count,
    }), 201

@app.route('/items/<string:item_id>', methods=['PUT'])
def update_item(item_id):
    data = request.get_json(silent=True)
    if not data or not data.get("name") or not data.get("status") or not data.get("location"):
        return error_response("validation_error", "Missing name, status, or location.", 400)

    def grpc_operation():
        req = items_pb2.UpdateItemRequest(
            id=item_id,
            name=data["name"].strip(),
            status=data["status"].strip(),
            location=data["location"].strip()
        )
        return stub.UpdateItem(req, timeout=2.0)

    try:
        result = protected_call(grpc_operation)
    except CircuitBreakerError:
        return error_response("backend_unavailable", "gRPC service is temporarily unavailable.", 503)
    except BackendUnavailable:
        return error_response("backend_failure", "gRPC service did not respond successfully.", 502)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return error_response("not_found", f"Item {item_id} not found.", 404)
        return error_response("internal_error", str(e), 500)

    return jsonify({
        "id": result.id,
        "name": result.name,
        "status": result.status,
        "location": result.location
    }), 200


@app.route('/items/<string:item_id>', methods=['DELETE'])
def delete_item(item_id):
    def grpc_operation():
        req = items_pb2.ItemIdRequest(id=item_id)
        return stub.DeleteItem(req, timeout=2.0)

    try:
        protected_call(grpc_operation)
    except CircuitBreakerError:
        return error_response("backend_unavailable", "gRPC service is temporarily unavailable.", 503)
    except BackendUnavailable:
        return error_response("backend_failure", "gRPC service did not respond successfully.", 502)
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return error_response("not_found", f"Item {item_id} not found.", 404)
        return error_response("internal_error", str(e), 500)

    # Return 204 No Content for a successful deletion
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)