# This file defines the actual messages a peer can send (helper functions)
# Excluding handshakes - see handshake.py

# Constant bit values for different message types (specified in doc)
MSG_CHOKE = 0
MSG_UNCHOKE = 1
MSG_INTERESTED = 2
MSG_NOT_INTERESTED = 3
MSG_HAVE = 4
MSG_BITFIELD = 5
MSG_REQUEST = 6
MSG_PIECE = 7

# Helper functions for byte to int translations
def int_to_4_bytes(value):
    return value.to_bytes(4, byteorder="big")

def bytes_to_int(b):
    return int.from_bytes(b, byteorder="big")

# Creates a message in the format specified (length - type - payload)
# Takes in the message type, if no payload is provided defaults to 0 bytes
def make_message(msg_type, payload=bytes(0)):
    length = 1 + len(payload)
    return int_to_4_bytes(length) + bytes([msg_type]) + payload

# These four messages only contain length and message type, no payload
def make_choke():
    return make_message(MSG_CHOKE)

def make_unchoke():
    return make_message(MSG_UNCHOKE)

def make_interested():
    return make_message(MSG_INTERESTED)

def make_not_interested():
    return make_message(MSG_NOT_INTERESTED)

# The payload is the 4-byte piece index provided
def make_have(piece_index):
    return make_message(MSG_HAVE, int_to_4_bytes(piece_index))

# The payload is the piece index you want
def make_request(piece_index):
    return make_message(MSG_REQUEST, int_to_4_bytes(piece_index))

# Payload is the peice index and the content of the piece
def make_piece(piece_index, data):
    return make_message(MSG_PIECE, int_to_4_bytes(piece_index) + data)

def make_bitfield(bitfield):
    num_bytes = (len(bitfield) + 7) // 8
    result = bytearray(num_bytes) # empty array of bytes
    for i in range(len(bitfield)):
        if bitfield[i] == 1:
            byte_index = i // 8 # Byte it belongs to
            bit_position = 7 - (i % 8) # Outer left bit
            result[byte_index] |= (1 << bit_position) # sets that specific bit to 1
    return make_message(MSG_BITFIELD, bytes(result))


# Reverse of make bitfield above, converts the bytes back to list of bits
def parse_bitfield(payload, num_pieces):
    bitfield = []
    for i in range(num_pieces):
        byte_index = i // 8
        bit_position = 7 - (i % 8)
        bit = (payload[byte_index] >> bit_position) & 1
        bitfield.append(bit)
    return bitfield


# Interprets the received message, returns the message type and payload
def parse_message_body(data):
    msg_type = data[0]
    payload = data[1:]
    return msg_type, payload

def parse_full_message(data):
    length = bytes_to_int(data[:4])
    body = data[4:4 + length]
    msg_type, payload = parse_message_body(body)
    return length, msg_type, payload