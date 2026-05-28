# Use the exact baseline image recommended in the lab
FROM python:3.13.13-slim

# Prevent Python from writing bytecode and buffer outputs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set our specific greenhouse environment variables
ENV SERVICE_NAME=greenhouse-grpc-service
ENV GRPC_PORT=50051

WORKDIR /app

# Copy and install dependencies first (for layer caching)
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

# Create a non-root user for security
RUN useradd --create-home --shell /usr/sbin/nologin appuser

# Copy the rest of the application code and set ownership
COPY --chown=appuser:appuser . .

USER appuser

# Document the internal port the gRPC server listens on
EXPOSE 50051

# Start the gRPC server
CMD ["python", "server.py"]