# This file handles handshake messages

# Header value specified in the doc
HANDSHAKE_HEADER = b'P2PFILESHARINGPROJ'

# Creates the handshake message to be sent
def make_handshake(peer_id):
    header = HANDSHAKE_HEADER # handshake header
    zero_bits = bytes(10) # zero bits
    peer_id_bytes = peer_id.to_bytes(4, byteorder="big")
    return header + zero_bits + peer_id_bytes

# Interprets the handshake message recieved and validates it as well
def parse_handshake(data):

    # Validate length
    if len(data) != 32:
        raise ValueError("Invalid handshake length")

    header = data[:18] # first 18 bytes is the handshake header
    zero_bits = data[18:28] # zero bits
    peer_id = int.from_bytes(data[28:32], byteorder="big") # peer id

    # Ensure it has the proper header
    if header != HANDSHAKE_HEADER:
        raise ValueError("Invalid handshake header")

    # Needs to have 10 zero bytes
    if zero_bits != bytes(10):
        raise ValueError("Invalid zero bits")

    return peer_id

