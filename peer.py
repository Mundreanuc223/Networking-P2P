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

    def setup_directory(self):
        os.makedirs(f"peer_{self.peer_id}", exist_ok=True)

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Peer {self.peer_id} listening on {self.host}:{self.port}")

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