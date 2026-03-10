import os
import math
import socket


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
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((peer["host"], peer["port"]))
                    self.connections[peer["peer_id"]] = sock
                    print(f"Peer {self.peer_id} connected to peer {peer['peer_id']}")
                except Exception as e:
                    print(f"Peer {self.peer_id} failed to connect to peer {peer['peer_id']}: {e}")

    def __repr__(self):
        return (
            f"Peer(peer_id={self.peer_id}, host={self.host}, port={self.port}, "
            f"has_file={self.has_file}, num_pieces={self.num_pieces})"
        )