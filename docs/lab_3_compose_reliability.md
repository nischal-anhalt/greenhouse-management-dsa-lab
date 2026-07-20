
## Testing with Scenarios

### 1. Startup the stack

```bash
docker compose up -d --build
```
```bash
docker compose ps
```


### 2. Normal Operation test
Using curl command to test the normal operation:

```bash
curl -i -X POST http://localhost:8085/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Sunflower", "status": "healthy", "location": "Zone 1"}'
```
Output:
```bash
HTTP/1.1 201 CREATED
Server: Werkzeug/3.1.8 Python/3.12.13
Date: Mon, 13 Jul 2026 19:33:40 GMT
Content-Type: application/json
Content-Length: 69
Connection: close

{"created_count":1,"message":"created through gRPC","total_count":7}
```

```bash
curl -i http://localhost:8085/items 
```
output:
```bash
HTTP/1.1 200 OK
Server: Werkzeug/3.1.8 Python/3.12.13
Date: Mon, 13 Jul 2026 19:33:42 GMT
Content-Type: application/json
Content-Length: 735
Connection: close

[{"id":"0a066f91-06e3-40c5-b5cc-af25fe54d047","location":"Zone 1","name":"Sunflower","status":"healthy"},{"id":"4e68c60c-f540-43fb-9c8a-882beef58e69","location":"Zone 1","name":"Sunflower-root","status":"healthy"},{"id":"89d56d32-d15b-471b-a9d0-68e50c13e2b5","location":"Zone 1","name":"Sunflower","status":"healthy"},{"id":"8ff4202b-b077-43a9-89ee-7e6c8318162f","location":"Zone 1","name":"Sunflower","status":"healthy"},{"id":"b1b689a8-b98b-4385-a37d-99962f8abe7a","location":"Zone 1","name":"Sunflower","status":"healthy"},{"id":"b9e68281-6457-4570-83f1-36c90edce159","location":"Zone 1","name":"Sunflower","status":"healthy"},{"id":"ff2f81a6-9bac-4c4a-b35a-f45717a3cc67","location":"Zone 1","name":"Sunflower","status":"healthy"}]
```

Docker compose logs:
```bash
docker compose logs -f
```

### 3. Experiment A: gRPC Container down

Stop the gRPC service:
```bash
docker compose stop grpc-service
```

Try the `curl` again
```bash
curl -i -X POST http://localhost:8085/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Sunflower", "status": "healthy", "location": "Zone 1"}'


**Outputs:**
HTTP/1.1 502 BAD GATEWAY
Server: Werkzeug/3.1.8 Python/3.12.13
Date: Mon, 13 Jul 2026 19:52:26 GMT
Content-Type: application/json
Content-Length: 106
Connection: close

{"error":{"code":"backend_failure","message":"gRPC service did not respond successfully after retries."}}
```
```bash
curl -i -X POST http://localhost:8085/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Sunflower", "status": "healthy", "location": "Zone 1"}'

HTTP/1.1 503 SERVICE UNAVAILABLE
Server: Werkzeug/3.1.8 Python/3.12.13
Date: Mon, 13 Jul 2026 20:13:57 GMT
Content-Type: application/json
Content-Length: 109
Connection: close

{"error":{"code":"backend_unavailable","message":"gRPC service is temporarily unavailable (Circuit Open)."}}
```

Restart the `grpc-service` and try again after about 30 seconds. It should work normally.
```bash
curl -i -X POST http://localhost:8085/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Sunflower", "status": "healthy", "location": "Zone 1"}'

HTTP/1.1 201 CREATED
Server: Werkzeug/3.1.8 Python/3.12.13
Date: Mon, 13 Jul 2026 20:22:03 GMT
Content-Type: application/json
Content-Length: 69
Connection: close

{"created_count":1,"message":"created through gRPC","total_count":9}

```