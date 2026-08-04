### Normal Operation Flow

1. Generate JWT tokens

```bash
KC="http://localhost:8088/realms/dsa-lab/protocol/openid-connect"

curl -s \
  -d "client_id=rest-api" \
  -d "grant_type=password" \
  -d "username=alice" \
  -d "password=secret" \
  "${KC}/token" | jq -r .access_token > token.jwt
```

2. Curl without the Auth token.

```bash
curl --cacert security/certs/ca.crt https://localhost:8443/api/items

{"error":{"code":"missing_token","message":"Bearer token is required."}}
```

3. Curl with Auth token.

```bash
curl --cacert security/certs/ca.crt \
  -H "Authorization: Bearer $(cat token.jwt)" \
  https://localhost:8443/api/items


[{"id":"01d438e5-e9ab-4726-9c76-b9a340aca276","location":"Zone 1","name":"observability-plant-111","status":"healthy"},{"id":"023d476d-b192-4cca-adcb-0fa0319cbeb0","location":"Zone 1","name":"observability-plant-153","status":"healthy"},{"id":"03f155d5-9220-4677-bd5b-9f44cdbcb823","location":"Zone 1","name":"observability-plant-81","status":"healthy"},{"id":"040fe9b6-b530-40a4-a542-1ea5fbc6b53b","location":"Zone 1","name":"observability-plant-39","status":"healthy"},{"id":"04852b4c-9f85-433f-b8ec-61edea147345","location":"Zone 1","name":"observability-plant-48","status":"healthy"},{"id":"fdffa971-406a-4a15-b964-1b62b91c0d9b","location":"Zone 1","name":"observability-plant-78","status":"healthy"},{"id":"fef18ed1-be60-4be7-a5a8-491f6ba954e8","location":"Zone 1","name":"observability-plant-87","status":"healthy"},{"id":"fef99ea3-c7ab-49c0-b2f1-f611aa2ba70c","location":"Zone 1","name":"observability-plant-81","status":"healthy"},{"id":"ff2f81a6-9bac-4c4a-b35a-f45717a3cc67","location":"Zone 1","name":"Sunflower","status":"healthy"},{"id":"ff717237-6d32-4d47-b26b-57af3eb2af4e","location":"Zone 1","name":"observability-plant-42","status":"healthy"}]
```

### Threat Simulations

Testing if the system actively blocks requests that fail our new security checks.

---
#### Test 1: Missing Bearer Token.

```bash
curl -i --cacert security/certs/ca.crt https://localhost:8443/api/items
HTTP/2 401 
content-type: application/json
date: Mon, 03 Aug 2026 12:00:28 GMT
server: Werkzeug/3.1.8 Python/3.12.13
content-length: 73

{"error":{"code":"missing_token","message":"Bearer token is required."}}
```

***Expected Result***: 401 Unauthorized response because the token is completely missing.

--- 
#### Test 2: Tampered Bearer Token

Appending random character "x" to end of valid token:

```bash
BAD_TOKEN="$(cat token.jwt)x"

curl -i --cacert security/certs/ca.crt \
  -H "Authorization: Bearer ${BAD_TOKEN}" \
  https://localhost:8443/api/items
```

***Expected Result:*** Received 401 Unauthorized response with a "Signature verification failed" message from PyJWT.

```bash
HTTP/2 401 
content-type: application/json
date: Tue, 04 Aug 2026 08:18:12 GMT
server: Werkzeug/3.1.8 Python/3.12.13
content-length: 77

{"error":{"code":"invalid_token","message":"Signature verification failed"}}

```

#### Test 3: mTLS Failure (Missing Client Certificate)

Finally, let's test our internal gRPC defense. We will simulate a scenario where the REST service gets compromised and loses its valid mTLS client certificate, or an unauthorized container tries to call the backend.

1. Temporarily breaking the REST client certificate path.
```yml
REST_CLIENT_CERT: /certs/invalid-cert-path.crt
```

2. Restart REST service
```bash
docker compose up -d --force-recreate rest-service
```

3. Now, send a perfectly valid external request with your correct Keycloak token
```bash
curl -i --cacert security/certs/ca.crt \
  -H "Authorization: Bearer $(cat token.jwt)" \
  https://localhost:8443/api/items
```

```bash
HTTP/2 502 
content-length: 11
date: Tue, 04 Aug 2026 08:29:19 GMT

Bad Gateway%                                                                                                                                         
```

4. Checking the rest-service logs:
```bash
docker compose logs rest-service 
```

```bash
rest-service-1  | Traceback (most recent call last):
rest-service-1  |   File "/app/app.py", line 122, in <module>
rest-service-1  |     certificate_chain=read_bytes(REST_CLIENT_CERT),
rest-service-1  |                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
rest-service-1  |   File "/app/app.py", line 24, in read_bytes
rest-service-1  |     with open(path, "rb") as file:
rest-service-1  |          ^^^^^^^^^^^^^^^^
rest-service-1  | FileNotFoundError: [Errno 2] No such file or directory: '/certs/invalid-cert-path.crt'

```
