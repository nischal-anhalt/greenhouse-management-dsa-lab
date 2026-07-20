import os
import time
import logging
import grpc
from flask import Flask, jsonify, request, Response
from pybreaker import CircuitBreakerError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

import items_pb2
import items_pb2_grpc
from reliability import BackendUnavailable, protected_call

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# 1. Define the Metrics
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

# 2. Helper to avoid high-cardinality labels (e.g., tracking /items/<id> instead of /items/123)
def route_pattern():
    if request.url_rule is None:
        return "unknown"
    return request.url_rule.rule

# 3. Start the timer before each request
@app.before_request
def metrics_start_timer():
    request._metrics_start_time = time.perf_counter()

# 4. Record the metrics after each request
@app.after_request
def metrics_record(response):
    if request.endpoint != "metrics":
        endpoint = route_pattern()
        duration = time.perf_counter() - request._metrics_start_time
        
        HTTP_REQUEST_DURATION.labels(request.method, endpoint).observe(duration)
        HTTP_REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
    return response

# 5. Expose the metrics endpoint for Prometheus to scrape
@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


# Connect to the gRPC service using the Docker Compose service name
GRPC_TARGET = os.getenv("GRPC_TARGET", "grpc-service:50051")
channel = grpc.insecure_channel(GRPC_TARGET)
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