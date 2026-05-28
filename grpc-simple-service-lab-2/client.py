import os
import grpc
import items_pb2
import items_pb2_grpc

# Defaults to 50052 (the Docker host mapped port), but we can override it for local testing
GRPC_TARGET = os.getenv("GRPC_TARGET", "localhost:50052")

def new_items():
    # Yielding our greenhouse-specific CreateItemRequest messages
    yield items_pb2.CreateItemRequest(
        name="Orchid", 
        status="healthy", 
        location="Zone 3"
    )
    yield items_pb2.CreateItemRequest(
        name="Cactus", 
        status="dry", 
        location="Zone 4"
    )

def chat_messages():
    # Yielding a stream of chat messages
    yield items_pb2.ChatMessage(sender="Gardener", text="Hello Greenhouse Controller!", sequence=1)
    yield items_pb2.ChatMessage(sender="Gardener", text="Please water the plants in Zone 2.", sequence=2)

def run():
    print(f"Connecting to {GRPC_TARGET}...\n")
    
    # Establish a connection to the server
    with grpc.insecure_channel(GRPC_TARGET) as channel:
        stub = items_pb2_grpc.ItemServiceStub(channel)

        print("1) Unary RPC worked example")
        item = stub.GetItemById(items_pb2.ItemIdRequest(id=1))
        print(item)

        print("2) Server-streaming RPC worked example")
        for item in stub.ListItems(items_pb2.ListItemsRequest()):
            print(item)

        print("3) Client-streaming RPC (AddItems)")
        # We pass the generator function directly to the stub method
        summary = stub.AddItems(new_items())
        print(summary)

        print("4) Bidirectional-streaming RPC (ChatAboutItems)")
        # We pass a stream and iterate over the returning stream
        for response in stub.ChatAboutItems(chat_messages()):
            print(response)

        print("\n5) Expected error case worked example")
        try:
            # Requesting an ID that doesn't exist to trigger our NOT_FOUND abort
            stub.GetItemById(items_pb2.ItemIdRequest(id=9999))
        except grpc.RpcError as exc:
            print("code:", exc.code())
            print("details:", exc.details())

if __name__ == "__main__":
    run()