import os
import math
import socket
from handshake import make_handshake, parse_handshake

HANDSHAKE_LENGTH = 32
SERVER_TIMEOUT = 5.0


class Peer:
    def __init__(self, peer_id, common_config, peer_info):
        self.peer_id = peer_id
        self.common_config = common_config
        self.peer_info = peer_info

        self.current_peer = self.find_current_peer()
        self.host = self.current_peer["host"]
        self.port = self.current_peer["port"]
        self.has_file = self.current_peer["has_file"]

        self.file_name = self.common_config["FileName"]
        self.file_size = self.common_config["FileSize"]
        self.piece_size = self.common_config["PieceSize"]

        self.num_pieces = math.ceil(self.file_size / self.piece_size)
        self.bitfield = self.initialize_bitfield()

        self.server_socket = None
        self.connections = {}
        self.pieces = {}
        if self.has_file:
            self.load_file_into_pieces()
        self.setup_directory()

    def find_current_peer(self):
        for peer in self.peer_info:
            if peer["peer_id"] == self.peer_id:
                return peer
        raise ValueError(f"Peer ID {self.peer_id} not found in peer_info")

    def initialize_bitfield(self):
        if self.has_file:
            return [1] * self.num_pieces
        return [0] * self.num_pieces

    def has_piece(self, piece_index):
        return self.bitfield[piece_index] == 1

    def set_piece(self, piece_index, data):
        if piece_index < 0 or piece_index >= self.num_pieces:
            raise ValueError(f"Invalid piece index: {piece_index}")

        self.pieces[piece_index] = data
        self.bitfield[piece_index] = 1

    def get_piece(self, piece_index):
        return self.pieces.get(piece_index)

    def needed_pieces_from(self, remote_bitfield):
        needed = []

        if len(remote_bitfield) != self.num_pieces:
            raise ValueError("Remote bitfield length does not match expected number of pieces")

        for i in range(self.num_pieces):
            if self.bitfield[i] == 0 and remote_bitfield[i] == 1:
                needed.append(i)

        return needed

    def is_complete(self):
        return all(bit == 1 for bit in self.bitfield)

    def setup_directory(self):
        os.makedirs(f"peer_{self.peer_id}", exist_ok=True)

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Peer {self.peer_id} listening on {self.host}:{self.port}")

    def send_bitfield(self, sock):
        from peer_message import make_bitfield
        sock.sendall(make_bitfield(self.bitfield))

    def receive_message(self, sock):
        from peer_message import bytes_to_int, parse_message_body

        length_bytes = self.receive_bytes(sock, 4)
        length = bytes_to_int(length_bytes)
        body = self.receive_bytes(sock, length)
        msg_type, payload = parse_message_body(body)
        return msg_type, payload

    def receive_bitfield(self, sock):
        from peer_message import MSG_BITFIELD, parse_bitfield

        msg_type, payload = self.receive_message(sock)
        if msg_type != MSG_BITFIELD:
            raise ValueError(f"Expected bitfield message, got type {msg_type}")

        return parse_bitfield(payload)

    def connect_to_previous_peers(self):
        for peer in self.peer_info:
            if peer["peer_id"] < self.peer_id:
                sock = None

                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(SERVER_TIMEOUT)
                    sock.connect((peer["host"], peer["port"]))
                    remote_peer_id = self.perform_outgoing_handshake(sock, peer["peer_id"])
                    self.connections[remote_peer_id] = sock
                    print(f"Peer {self.peer_id} connected to peer {peer['peer_id']}")
                except Exception as e:
                    self.close_socket(sock)
                    print(f"Peer {self.peer_id} failed to connect to peer {peer['peer_id']}: {e}")

    def receive_bytes(self, sock, size):
        buffer = bytearray()
        while len(buffer) < size:
            chunk = sock.recv(size - len(buffer))
            if not chunk:
                raise ConnectionError("Socket closed before enough bytes were received")
            buffer.extend(chunk)
        return bytes(buffer)

    def get_file_path(self):
        return os.path.join(f"peer_{self.peer_id}", self.file_name)

    def load_file_into_pieces(self):
        file_path = self.get_file_path()

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found for peer {self.peer_id}: {file_path}")

        self.pieces = {}

        with open(file_path, "rb") as f:
            piece_index = 0
            while True:
                chunk = f.read(self.piece_size)
                if not chunk:
                    break

                self.pieces[piece_index] = chunk
                self.bitfield[piece_index] = 1
                piece_index += 1

    def piece_count_loaded(self):
        return len(self.pieces)

    def is_interested_in(self, remote_bitfield):
        return len(self.needed_pieces_from(remote_bitfield)) > 0

    def choose_piece_to_request(self, remote_bitfield):
        needed = self.needed_pieces_from(remote_bitfield)
        if not needed:
            return None
        return needed[0]

    def send_interested(self, sock):
        from peer_message import make_interested
        sock.sendall(make_interested())

    def send_not_interested(self, sock):
        from peer_message import make_not_interested
        sock.sendall(make_not_interested())

    def send_interest_decision(self, sock, remote_bitfield):
        if self.is_interested_in(remote_bitfield):
            self.send_interested(sock)
            print(f"Peer {self.peer_id} sent INTERESTED")
        else:
            self.send_not_interested(sock)
            print(f"Peer {self.peer_id} sent NOT_INTERESTED")

    def send_request(self, sock, piece_index):
        from peer_message import make_request
        sock.sendall(make_request(piece_index))

    def parse_request_payload(self, payload):
        from peer_message import bytes_to_int
        if len(payload) != 4:
            raise ValueError("Request payload must be 4 bytes")
        return bytes_to_int(payload)

    def send_piece_message(self, sock, piece_index):
        from peer_message import make_piece

        piece_data = self.get_piece(piece_index)
        if piece_data is None:
            raise ValueError(f"Peer {self.peer_id} does not have piece {piece_index}")

        sock.sendall(make_piece(piece_index, piece_data))

    def parse_piece_payload(self, payload):
        from peer_message import bytes_to_int

        if len(payload) < 4:
            raise ValueError("Piece payload must include piece index and data")

        piece_index = bytes_to_int(payload[:4])
        piece_data = payload[4:]
        return piece_index, piece_data



    def perform_outgoing_handshake(self, sock, expected_peer_id):
        sock.sendall(make_handshake(self.peer_id))
        response = self.receive_bytes(sock, HANDSHAKE_LENGTH)
        remote_peer_id = parse_handshake(response)
        if remote_peer_id != expected_peer_id:
            raise ValueError(f"Expected peer {expected_peer_id}, but received handshake from {remote_peer_id}")
        return remote_peer_id

    def close_socket(self, sock):
        if sock is None:
            return
        try:
            sock.close()
        except OSError:
            pass

    def __repr__(self):
        return (
            f"Peer(peer_id={self.peer_id}, host={self.host}, port={self.port}, "
            f"has_file={self.has_file}, num_pieces={self.num_pieces})"
        )