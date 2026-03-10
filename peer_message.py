# This file defines the actual messages a peer can send
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

# TODO: make_bitfield function

# Interprets the received message, returns the message type and payload
def parse_message_body(data):
    msg_type = data[0]
    payload = data[1:]
    return msg_type, payload

