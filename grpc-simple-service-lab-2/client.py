import os
import grpc
import items_pb2
import items_pb2_grpc

# Defaults to 50052 (the Docker host mapped port), but we can override it for local testing
GRPC_TARGET = os.getenv("GRPC_TARGET", "localhost:50052")

def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()

# Load the certs (adjust paths based on where you run the script)
ca_cert = read_bytes("../security/certs/ca.crt")
client_cert = read_bytes("../security/certs/rest-client.crt")
client_key = read_bytes("../security/certs/rest-client.key")

credentials = grpc.ssl_channel_credentials(
    root_certificates=ca_cert,
    certificate_chain=client_cert,
    private_key=client_key
)

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
    
    channel_options = (
        ('grpc.ssl_target_name_override', 'grpc-service'),
    )
    
    # Establish a secure connection with the options
    with grpc.secure_channel(GRPC_TARGET, credentials, options=channel_options) as channel:
        stub = items_pb2_grpc.ItemServiceStub(channel)

        print("1) Client-streaming RPC (AddItems)")
        # Run this first to populate the database
        summary = stub.AddItems(new_items())
        print(summary)

        print("2) Server-streaming RPC (ListItems)")
        # Fetch the list and save the ID of the first item we see
        valid_id = None
        for item in stub.ListItems(items_pb2.ListItemsRequest()):
            print(item)
            if valid_id is None:
                valid_id = item.id  # Capture the first valid UUID

        print(f"\n3) Unary RPC (GetItemById)")
        if valid_id:
            print(f"Fetching dynamically extracted ID: {valid_id}")
            single_item = stub.GetItemById(items_pb2.ItemIdRequest(id=valid_id))
            print(single_item)
        else:
            print("No items found in the database to fetch.")

        print("\n4) Bidirectional-streaming RPC (ChatAboutItems)")
        for response in stub.ChatAboutItems(chat_messages()):
            print(response)

        print("\n5) Expected error case worked example")
        try:
            # We still pass a string, but make it an obviously fake UUID
            stub.GetItemById(items_pb2.ItemIdRequest(id="9999-invalid-id-9999"))
        except grpc.RpcError as exc:
            print("code:", exc.code())
            print("details:", exc.details())

if __name__ == "__main__":
    run()