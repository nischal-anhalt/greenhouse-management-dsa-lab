# Smart Greenhouse Management System: Phase 2 (gRPC)

## 1. Executive Summary
This document outlines the Phase 2 implementation of the Smart Greenhouse Management System, transitioning from a standard REST API to a high-performance **gRPC** (gRPC Remote Procedure Calls) architecture. By leveraging **Protocol Buffers** (protobuf) for strict payload typing and binary serialization, this iteration introduces robust service-to-service communication, including advanced streaming paradigms that are critical for real-time IoT greenhouse sensors and automated controllers.

## 2. Project Structure & Deliverables
The repository encompasses the following core deliverables required for the gRPC integration:

*   **`proto/items.proto`**: The Protocol Buffers contract defining the service interfaces and strongly-typed message payloads.
*   **`items_pb2.py` & `items_pb2_grpc.py`**: The auto-generated Python stubs enabling strict client-server interactions.
*   **`server.py`**: The centralized gRPC server implementation handling incoming remote procedure calls.
*   **`client.py`**: A comprehensive test client validating the gRPC endpoints.
*   **`Dockerfile`**: Containerization instructions for deploying the gRPC service in isolated environments.

## 3. Implemented Communication Paradigms
To fully explore gRPC's capabilities against traditional REST, the service implements all four RPC routing paradigms:

1.  **Unary RPC (`GetItemById`)**: A standard request-response model for retrieving individual greenhouse assets (e.g., a specific plant or bed status).
2.  **Server-Streaming RPC (`ListItems`)**: The server streams a sequence of plant data back to the client, ideal for retrieving large inventories continuously without overwhelming memory.
3.  **Client-Streaming RPC (`AddItems`)**: The client pushes a continuous stream of new plant entries to the server, which responds with a single summary upon completion (e.g., bulk sensor registration).
4.  **Bidirectional-Streaming RPC (`ChatAboutItems`)**: Real-time, asynchronous two-way communication between the greenhouse controllers and the centralized server.

## 4. Development & Deployment Guide

### 4.1. Generating Protocol Buffer Stubs
To ensure cross-platform compatibility and avoid local dependency conflicts, the Python stubs are generated inside an ephemeral Docker container. Run the following command from the `grpc-service/` directory whenever the `.proto` file is updated:

```bash
docker run --rm \
  -v "$(pwd):/work" \
  -w /work \
  python:3.13.13-slim \
  sh -c "python -m pip install --no-cache-dir grpcio-tools==1.80.0 && \
         python -m grpc_tools.protoc \
         -I proto \
         --python_out=. \
         --grpc_python_out=. \
         proto/items.proto"
```

### 4.2. Containerizing and Starting the Server
The gRPC server is packaged as a lightweight Docker container for seamless deployment.

**1. Build the image:**
```bash
docker build --pull -t dsa-lab2-items-grpc:1.0 .
```

**2. Run the container:**
*This maps external host port `50052` to the container's internal gRPC port `50051`.*
```bash
# Clean up existing containers (optional)
docker rm -f dsa-lab2-items-grpc 2>/dev/null || true

# Execute the service
docker run -d \
    --name dsa-lab2-items-grpc \
    -p 50052:50051 \
    -e SERVICE_NAME=greenhouse-grpc-service \
    dsa-lab2-items-grpc:1.0
```

## 5. Automated System Verification
The included `client.py` script acts as a simulated automated watering controller and gardener, sequentially executing all four RPC methods and validating expected error handling (e.g., `NOT_FOUND` exceptions).

**Execute the test suite:**
Ensure the Docker container is running, then execute:
```bash
python client.py
```

### Expected Output Log
Upon successful execution, the client will output a structured log validating each gRPC paradigm:

```text
Connecting to localhost:50052...

1) Unary RPC worked example
id: 1
name: "Tomato Bed A"
status: "healthy"
location: "Zone 1"

2) Server-streaming RPC worked example
id: 1
name: "Tomato Bed A"
status: "healthy"
location: "Zone 1"

id: 2
name: "Monstera Deliciosa"
status: "needs_water"
location: "Zone 2"

3) Client-streaming RPC (AddItems)
created_count: 2
total_count: 4

4) Bidirectional-streaming RPC (ChatAboutItems)
sender: "greenhouse-grpc-service"
text: "Server echoing: Hello Greenhouse Controller!"
sequence: 1

sender: "greenhouse-grpc-service"
text: "Server echoing: Please water the plants in Zone 2."
sequence: 2

5) Expected error case worked example
code: StatusCode.NOT_FOUND
details: Item with id 9999 does not exist.
```

## 6. Architectural Reflections

### 6.1. Inter-Service Communication: gRPC vs. REST
*   **The Conceptual Shift:** Traditional REST (typically running over HTTP/1.1) is inherently designed for browser-to-server web interactions. It carries significant overhead, including verbose HTTP headers, text-based JSON serialization, and the need to repeatedly open new TCP connections. 
*   **Reduced Overhead:** gRPC is explicitly designed for internal, service-to-service communication. By running on HTTP/2, it leverages multiplexing (sending multiple concurrent requests over a single connection) and header compression, effectively stripping away the latency bottlenecks associated with REST.

### 6.2. Payload Efficiency (JSON vs. Protocol Buffers)
*   **Methodology:** To evaluate data transfer efficiency, we can conceptually compare a serialized JSON payload of a greenhouse asset against its Protocol Buffer binary equivalent.
*   **Observation:** A standard JSON object (e.g., `{"id": 1, "name": "Tomato Bed A", "status": "healthy"}`) transmits structural metadata (the field keys) as plain text with every request. Protocol Buffers, however, serialize the data into binary and strip away the field names, matching data only to their pre-defined field numbers (e.g., `1`, `2`, `3`).
*   **Result:** This binary framing results in a vastly smaller payload size, reducing network bandwidth usage and improving serialization/deserialization speeds during inter-service communication.

### 6.3. Developer Experience: The Contract-First Approach
*   **Strict Typing:** Developing with REST often involves loosely typed JSON dictionaries that are susceptible to runtime errors, missing fields, or typos. gRPC introduces a strict, contract-first approach via the `.proto` file, serving as a single source of truth.
*   **Auto-Generated Stubs:** While there is an additional step to executing the `protoc` compiler inside a Docker container, the payoff is substantial. The auto-generated stubs (`items_pb2.py` and `items_pb2_grpc.py`) eliminate the need to write boilerplate routing code and guarantee that the client and server data models remain perfectly synchronized.

### 6.4. Streaming Benefits for the Smart Greenhouse Use Case
The introduction of gRPC streaming fundamentally improves how the greenhouse ecosystem handles IoT device data:
*   **Client-Streaming (Sensor Ingestion):** Instead of an environmental sensor making a heavy HTTP `POST` request for every single temperature reading, it can open a single gRPC channel and stream continuous readings with minimal overhead.
*   **Server-Streaming (Bulk Data Retrieval):** When the automated watering controller requests the status of all plants, the server can stream the records back one by one, keeping memory footprints low rather than loading a massive JSON array into RAM all at once.
*   **Bidirectional-Streaming (Real-Time Control):** Controllers can continuously stream their local hardware statuses to the centralized system while simultaneously receiving real-time operational commands (like "open valve" or "turn on lights") over the exact same connection, entirely eliminating the need for inefficient REST polling.