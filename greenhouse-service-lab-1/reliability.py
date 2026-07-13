import logging
import time
import grpc
from pybreaker import CircuitBreaker, CircuitBreakerError

LOGGER = logging.getLogger(__name__)

# Configure the circuit breaker: opens after 3 failures, waits 30s to test again
breaker = CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    name="grpc-item-service",
)

class BackendUnavailable(Exception):
    pass

def call_with_retries(operation, attempts=3, timeout_label="gRPC"):
    delays = [0.0, 0.1, 0.2]
    last_error = None
    for index in range(attempts):
        if delays[index] > 0:
            time.sleep(delays[index])
        try:
            return operation()
        except grpc.RpcError as exc:
            last_error = exc
            LOGGER.warning("%s attempt %s/%s failed: %s", timeout_label, index + 1, attempts, exc)
    
    raise BackendUnavailable(f"{timeout_label} failed after {attempts} attempts") from last_error

def protected_call(operation):
    return breaker.call(lambda: call_with_retries(operation))