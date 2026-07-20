# Lab 4: Observability Notes

## 1. Metrics and Labels
*   **Metrics Added:** 
    *   REST: `http_requests_total` (Counter), `http_request_duration_seconds` (Histogram).
    *   gRPC: `grpc_requests_total` (Counter), `grpc_request_duration_seconds` (Histogram).
*   **Labels Used:** `method`, `endpoint`, and `status`. 
*   **Why they are low-cardinality:** Instead of logging the raw URL (which would create a unique time-series for every UUID or item ID, crashing Prometheus), the `route_pattern()` function is used. This groups all requests under finite, static route rules (e.g., `/items/<string:item_id>`).

## 2. Prometheus Configuration
The following targets were configured in `prometheus.yml` to scrape data within the internal Docker Compose network:
*   `rest-service:5000`
*   `grpc-service:9103`

## 3. Observations from Load Testing
Based on the Grafana dashboard during the `generate_load.py` execution:

1.  **Which endpoint receives the most traffic?** 
    The `GET` endpoint receives the most traffic. The REST request rate panel shows `GET` peaking at over 3 requests per second, while `POST` peaks around 1 request per second.
2.  **Do 4xx or 5xx errors appear?** 
    Yes, 4xx errors appear. The Error Ratio panel (tracking `status=~"4.."`) registers them, and the Loki logs panel explicitly captures multiple `GET /health HTTP/1.1" 404` entries. 
3.  **Does latency change when you create items compared with listing items?** 
    Yes, the REST p95 Latency climbs steadily during the load test (moving from ~0.090 seconds up to ~0.097 seconds), indicating that the system slows down slightly as it processes the active mix of `POST` and `GET` requests.
4.  **Which gRPC method is called when the REST service creates an item?** 
    The `AddItems` method is called. The "gRPC Calls" panel clearly shows a spike for `{method="AddItems", status="OK"}` matching the exact timestamp of the `POST` requests.

## 4. Curiosity Extension
*   **Extension Chosen:** Added a centralized logging stack using Loki and Promtail. 
*   **What I learned:** By provisioning Loki as an additional data source in Grafana and mapping `promtail` to the Docker socket, I was able to correlate metric spikes directly with container logs in the same UI. For example, I could see the exact `Persisted plant/bed to DB` logs from the `grpc-service` executing alongside the metric spikes.