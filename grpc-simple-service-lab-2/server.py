import logging
import os
from concurrent import futures

import grpc
import items_pb2
import items_pb2_grpc

logging.basicConfig(level=logging.INFO)

SERVICE_NAME = os.getenv("SERVICE_NAME", "greenhouse-grpc-service")
GRPC_PORT = int(os.getenv("GRPC_PORT", "50051"))

# Initial in-memory data 
items = {
    1: {"id": 1, "name": "Tomato Bed A", "status": "healthy", "location": "Zone 1"},
    2: {"id": 2, "name": "Monstera Deliciosa", "status": "needs_water", "location": "Zone 2"},
}
next_id = 3

def to_proto(item):
    """Convert one Python dictionary into a Protobuf Item message."""
    return items_pb2.Item(
        id=item["id"],
        name=item["name"],
        status=item["status"],
        location=item["location"],
    )

def validate_create_request(request):
    """Return None if valid; otherwise return an error message."""
    if not request.name.strip():
        return "Field 'name' is required."
    if not request.status.strip():
        return "Field 'status' is required."
    if not request.location.strip():
        return "Field 'location' is required."
    return None

class ItemService(items_pb2_grpc.ItemServiceServicer):

    def GetItemById(self, request, context):
        # Worked unary example: one request -> one response.
        logging.info("GetItemById id=%s", request.id)
        item = items.get(request.id)
        if item is None:
            # Proper use of gRPC status codes for missing items
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Item with id {request.id} does not exist.",
            )
        return to_proto(item)

    def ListItems(self, request, context):
        # Worked server-streaming example: one request -> many responses.
        logging.info("ListItems")
        for item in items.values():
            yield to_proto(item)

    def AddItems(self, request_iterator, context):
        # Client-streaming: many requests -> one response.
        global next_id
        logging.info("AddItems stream started")
        created_count = 0

        # Read all CreateItemRequest messages from the stream
        for create_req in request_iterator:
            
            # Validate input
            error = validate_create_request(create_req)
            if error:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, error)

            # Store the new item
            item = {
                "id": next_id,
                "name": create_req.name.strip(),
                "status": create_req.status.strip(),
                "location": create_req.location.strip(),
            }
            items[next_id] = item
            logging.info("Created plant/bed: %s", item["name"])
            
            next_id += 1
            created_count += 1

        # Return the summary once the client finishes sending
        return items_pb2.AddItemsResult(
            created_count=created_count,
            total_count=len(items)
        )

    def ChatAboutItems(self, request_iterator, context):
        # Bidirectional-streaming: many requests <-> many responses.
        logging.info("ChatAboutItems stream started")
        
        # For every incoming message, yield a response immediately
        for chat_msg in request_iterator:
            logging.info("Received chat from %s: %s", chat_msg.sender, chat_msg.text)
            
            yield items_pb2.ChatMessage(
                sender=SERVICE_NAME,
                text=f"Server echoing: {chat_msg.text}",
                sequence=chat_msg.sequence
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    items_pb2_grpc.add_ItemServiceServicer_to_server(ItemService(), server)
    server.add_insecure_port(f"[::]:{GRPC_PORT}")
    server.start()
    logging.info("%s listening on port %s", SERVICE_NAME, GRPC_PORT)
    server.wait_for_termination()

if __name__ == "__main__":
    serve()