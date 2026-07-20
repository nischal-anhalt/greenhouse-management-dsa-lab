import logging
import os
import uuid
import grpc
import time
from concurrent import futures
from pymongo import ASCENDING, DESCENDING, MongoClient
from prometheus_client import Counter, Histogram, start_http_server

import items_pb2
import items_pb2_grpc

logging.basicConfig(level=logging.INFO)

SERVICE_NAME = os.getenv("SERVICE_NAME", "greenhouse-grpc-service")
GRPC_PORT = int(os.getenv("GRPC_PORT", "50051"))

# ========================== Metrics ==========================
METRICS_PORT = int(os.getenv("METRICS_PORT", "9103"))

GRPC_REQUESTS = Counter(
    "grpc_requests_total",
    "Total gRPC requests",
    ["method", "status"],
)

GRPC_REQUEST_DURATION = Histogram(
    "grpc_request_duration_seconds",
    "gRPC request duration in seconds",
    ["method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

def begin_grpc_metrics(method_name):
    start = time.perf_counter()
    def finish(status):
        duration = time.perf_counter() - start
        GRPC_REQUEST_DURATION.labels(method_name).observe(duration)
        GRPC_REQUESTS.labels(method_name, status).inc()
    return finish
# ========================== Metrics ==========================

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "itemsdb")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "items")

# Connect to MongoDB
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]

# Ensure our custom 'id' field is indexed and unique
collection.create_index([("id", ASCENDING)], unique=True)

def check_mongo_connection():
    client.admin.command("ping")
    logging.info("Connected to MongoDB at %s", MONGO_URI)


def document_to_item(doc):
    """Converts a MongoDB document into our gRPC Protobuf Item."""
    return items_pb2.Item(
        id=doc["id"],
        name=doc["name"],
        status=doc["status"],
        location=doc["location"] # Smart Greenhouse domain field
    )

def validate_create_request(request):
    if not request.name.strip():
        return "Field 'name' is required."
    if not request.status.strip():
        return "Field 'status' is required."
    if not request.location.strip():
        return "Field 'location' is required."
    return None

class ItemService(items_pb2_grpc.ItemServiceServicer):

    def GetItemById(self, request, context):
        finish = begin_grpc_metrics("GetItemById")
        try:
            doc = collection.find_one({"id": request.id}, {"_id": False})
            if doc is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Item {request.id} not found")
                finish("NOT_FOUND")
                return items_pb2.Item()
            
            finish("OK")
            return document_to_item(doc)
        except Exception as exc:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            finish("INTERNAL")
            return items_pb2.Item()

    def AddItems(self, request_iterator, context):
        finish = begin_grpc_metrics("AddItems")
        created_count = 0
        try:
            for request in request_iterator:
                problem = validate_create_request(request)
                if problem is not None:
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details(problem)
                    finish("INVALID_ARGUMENT")
                    return items_pb2.AddItemsResult()

                document = {
                    "id": str(uuid.uuid4()), # Using the UUIDs from Lab 3!
                    "name": request.name.strip(),
                    "status": request.status.strip(),
                    "location": request.location.strip(),
                }
                collection.insert_one(document)
                created_count += 1
                logging.info("Persisted plant/bed to DB: %s", document["name"])

            total_count = collection.count_documents({})
            finish("OK")
            return items_pb2.AddItemsResult(
                created_count=created_count,
                total_count=total_count,
            )
        except Exception as exc:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            finish("INTERNAL")
            return items_pb2.AddItemsResult()

    def ListItems(self, request, context):
        for doc in collection.find({}, {"_id": False}).sort("id", ASCENDING):
            yield document_to_item(doc)

    
    def UpdateItem(self, request, context):
        # Validate the inputs
        if not request.name.strip() or not request.status.strip() or not request.location.strip():
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Name, status, and location are required.")
            
        # MongoDB find_one_and_update
        from pymongo import ReturnDocument
        updated_doc = collection.find_one_and_update(
            {"id": request.id},
            {"$set": {
                "name": request.name.strip(),
                "status": request.status.strip(),
                "location": request.location.strip()
            }},
            return_document=ReturnDocument.AFTER, # Returns the newly updated document
            projection={"_id": False}
        )
        
        if updated_doc is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Item {request.id} not found.")
            
        logging.info("Updated plant/bed: %s", updated_doc["name"])
        return document_to_item(updated_doc)

    def DeleteItem(self, request, context):
        # MongoDB delete_one
        result = collection.delete_one({"id": request.id})
        
        if result.deleted_count == 0:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Item {request.id} not found.")
            
        logging.info("Deleted plant/bed with ID: %s", request.id)
        return items_pb2.DeleteItemResponse(success=True)

    def ChatAboutItems(self, request_iterator, context):
        for message in request_iterator:
            yield items_pb2.ChatMessage(
                sender=SERVICE_NAME,
                text=f"received: {message.text}",
                sequence=message.sequence,
            )

def serve():
    check_mongo_connection()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    items_pb2_grpc.add_ItemServiceServicer_to_server(ItemService(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    server.start()
    logging.info("%s listening on port %s", SERVICE_NAME, GRPC_PORT)

    # Start the Prometheus metrics endpoint on port 9103
    start_http_server(METRICS_PORT)
    logging.info("Metrics server listening on port %s", METRICS_PORT)
    
    server.wait_for_termination()

if __name__ == "__main__":
    serve()