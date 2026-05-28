# Smart Greenhouse Management System - Lab 2 (gRPC)

This repository contains the gRPC implementation of the Smart Greenhouse Management System, allowing a comparison between REST and RPC architectures.

## Project Structure
- `proto/items.proto`: The Protocol Buffers contract defining the service and messages.
- `items_pb2.py` / `items_pb2_grpc.py`: Auto-generated gRPC stubs.
- `server.py`: The gRPC server implementation handling requests.
- `client.py`: The client script used to test the gRPC methods.
- `Dockerfile`: Instructions for containerizing the gRPC service.
- `docs/lab2-grpc-notes.md`: Architectural notes and documentation for Lab 2.

## How to Generate the Python Stubs

To regenerate the Python stubs from the `.proto` file, run the following Docker command from within the `grpc-service/` directory:

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

## How to Start the Server

1. **Build the Docker Image**
   Navigate to the `grpc-service/` directory and build the Docker image:
   ```bash
   docker build --pull -t dsa-lab2-items-grpc:1.0 .
   ```

2. **Run the Docker Container**
   Start the container and map port 50052 on your host machine to port 50051 inside the container:
   ```bash
    #Optional: remove the old container if you are re-running this
    docker rm -f dsa-lab2-items-grpc 2>/dev/null || true

    # Run the container
    docker run -d \
        --name dsa-lab2-items-grpc \
        -p 50052:50051 \
        -e SERVICE_NAME=greenhouse-grpc-service \
        dsa-lab2-items-grpc:1.0
   ```

## Running the Automated Test Client

To verify the gRPC endpoints, run the included `client.py` script. This script tests the four RPC methods: Unary, Server-Streaming, Client-Streaming, and Bidirectional Streaming.

1. Ensure the Docker container is running (see above).
2. Execute the test client:
   ```bash
   python client.py
   ```

## Client test output

```bash
(.venv) ➜  grpc-simple-service-lab-2 git:(main) ✗ python client.py 
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