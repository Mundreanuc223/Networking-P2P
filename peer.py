import os
import math
import random
import socket
import threading
import time

from handshake import make_handshake, parse_handshake
from peer_message import *


HANDSHAKE_LENGTH = 32
SERVER_TIMEOUT = 5.0


class Peer:
    def __init__(self, peer_id, common_config, peer_info):

        # Peer ID and configs
        self.peer_id = peer_id
        self.common_config = common_config
        self.peer_info = peer_info

        # Peer Info
        self.current_peer = self.find_current_peer()
        self.host = self.current_peer["host"]
        self.port = self.current_peer["port"]
        self.has_file = self.current_peer["has_file"]

        # Shared peer settings
        self.file_name = self.common_config["FileName"]
        self.file_size = self.common_config["FileSize"]
        self.piece_size = self.common_config["PieceSize"]
        self.num_preferred_neighbors = self.common_config["NumberOfPreferredNeighbors"]
        self.unchoking_interval = self.common_config["UnchokingInterval"]
        self.optimistic_unchoking_interval = self.common_config["OptimisticUnchokingInterval"]

        # Bitfield Init
        self.num_pieces = math.ceil(self.file_size / self.piece_size)
        self.bitfield = self.initialize_bitfield()

        # Connection/message states for neighbors
        self.server_socket = None
        self.connections = {}
        self.remote_bitfields = {}
        self.peer_choking_us = {}
        self.peers_we_choking = {}
        self.lock = threading.Lock()

        # Used for neighbor selection
        self.interested_peers = set()
        self.preferred_peers = set()
        self.opt_unchoke_peer = None

        # Downloading
        self.requested_pieces = set()
        self.download_counts = {}

        # Peers we currently believe have the complete file
        self.complete_peers = {
            peer["peer_id"] for peer in self.peer_info if peer["has_file"]
        }

        # Peers with lower ids
        self.previous_peer_ids = {
            peer["peer_id"] for peer in self.peer_info if peer["peer_id"] < self.peer_id
        }

        # Peers with higher ids
        self.later_peer_ids = {
            peer["peer_id"] for peer in self.peer_info if peer["peer_id"] > self.peer_id
        }

        # Path to this peer's required log file
        self.log_path = f"log_peer_{self.peer_id}.log"

        # Data peer currently has
        self.pieces = {}

        self.setup_directory()
        self.setup_log_file()

        if self.has_file:
            self.load_file_into_pieces()

    # Find this peer
    def find_current_peer(self):
        for peer in self.peer_info:
            if peer["peer_id"] == self.peer_id:
                return peer
        raise ValueError(f"Peer ID {self.peer_id} not found in peer_info")

    # Create this peer's starting bitfield (all 1 if it has the file, all 0 otherwise)
    def initialize_bitfield(self):
        if self.has_file:
            return [1] * self.num_pieces
        return [0] * self.num_pieces

    # Check if this peer has a specific piece
    def has_piece(self, piece_index):
        return self.bitfield[piece_index] == 1

    # Store a piece and mark the bitfield
    def set_piece(self, piece_index, data):
        if piece_index < 0 or piece_index >= self.num_pieces:
            raise ValueError(f"Invalid piece index: {piece_index}")

        self.pieces[piece_index] = data
        self.bitfield[piece_index] = 1

    def get_piece(self, piece_index):
        return self.pieces.get(piece_index)

    # Compare this peer's bitfield to another peer's, find what this peer still needs
    def needed_pieces_from(self, remote_bitfield):
        needed = []

        if len(remote_bitfield) != self.num_pieces:
            raise ValueError("Remote bitfield length does not match expected number of pieces")

        for i in range(self.num_pieces):
            if self.bitfield[i] == 0 and remote_bitfield[i] == 1:
                needed.append(i)

        return needed

    # After downloading a piece, notify all connected neighbors
    def broadcast_have(self, piece_index):
        for neighbor_id, sock in self.connections.items():
            try:
                sock.sendall(make_have(piece_index))
            except Exception as e:
                print(f"Failed to send have to peer {neighbor_id}: {e}")

    # Check if peer has every piece
    def is_complete(self):
        return all(bit == 1 for bit in self.bitfield)

    def setup_directory(self):
        os.makedirs(f"peer_{self.peer_id}", exist_ok=True)

    # Open the TCP socket for the peer
    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Peer {self.peer_id} listening on {self.host}:{self.port}")

    def send_bitfield(self, sock):
        if not any(self.bitfield):
            return
        sock.sendall(make_bitfield(self.bitfield))

    # Reads a recieved message
    def receive_message(self, sock):
        length_bytes = self.receive_bytes(sock, 4)
        length = bytes_to_int(length_bytes)
        body = self.receive_bytes(sock, length)
        msg_type, payload = parse_message_body(body)
        return msg_type, payload

    def receive_bitfield(self, sock):
        msg_type, payload = self.receive_message(sock)
        if msg_type != MSG_BITFIELD:
            raise ValueError(f"Expected bitfield message, got type {msg_type}")

        return parse_bitfield(payload, self.num_pieces)

    # Connect the peer to all peers with smaller IDs
    def connect_to_previous_peers(self):
        for peer in self.peer_info:
            if peer["peer_id"] < self.peer_id:
                sock = None

                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(SERVER_TIMEOUT)
                    sock.connect((peer["host"], peer["port"]))
                    remote_peer_id = self.perform_outgoing_handshake(sock, peer["peer_id"])

                    # After setup, don't timeout from inactivity
                    sock.settimeout(None)
                    self.register_connection(remote_peer_id, sock)
                    self.send_bitfield(sock)
                    self.start_peer_listener(remote_peer_id, sock)
                    self.log(f"Peer {self.peer_id} makes a connection to Peer {remote_peer_id}.")

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

    # Once all pieces are acquired, update its file
    def write_complete_file(self):
        file_path = self.get_file_path()

        with open(file_path, "wb") as f:
            for piece_index in range(self.num_pieces):
                piece_data = self.pieces.get(piece_index)
                if piece_data is None:
                    raise ValueError(f"Missing piece {piece_index}, cannot write complete file")

                f.write(piece_data)

    def piece_count_loaded(self):
        return len(self.pieces)

    def is_interested_in(self, remote_bitfield):
        return len(self.needed_pieces_from(remote_bitfield)) > 0

    # Selects a random piece it does not have and hasn't yet requested
    def choose_piece_to_request(self, remote_bitfield):
        needed = []

        for piece_index in self.needed_pieces_from(remote_bitfield):

            # Skip pieces already in progress
            if piece_index not in self.requested_pieces:
                needed.append(piece_index)

        if not needed:
            return None

        return random.choice(needed)

    def send_interested(self, sock):
        sock.sendall(make_interested())

    def send_not_interested(self, sock):
        sock.sendall(make_not_interested())

    def send_interest_decision(self, sock, remote_bitfield):
        if self.is_interested_in(remote_bitfield):
            self.send_interested(sock)
        else:
            self.send_not_interested(sock)

    # Reevaluate whether this peer should be interested in a neighbor
    def update_interest_for_neighbor(self, remote_peer_id):
        remote_bitfield = self.remote_bitfields.get(remote_peer_id)
        sock = self.connections.get(remote_peer_id)

        if remote_bitfield is None or sock is None:
            return

        self.send_interest_decision(sock, remote_bitfield)

    # Reevaluate interest against every connected neighbor after this peer gets a new piece
    def update_interest_for_all_neighbors(self):
        for remote_peer_id in list(self.connections.keys()):
            self.update_interest_for_neighbor(remote_peer_id)

    def send_request(self, sock, piece_index):
        self.requested_pieces.add(piece_index)
        sock.sendall(make_request(piece_index))

    def parse_request_payload(self, payload):
        if len(payload) != 4:
            raise ValueError("Request payload must be 4 bytes")
        return bytes_to_int(payload)

    def send_piece_message(self, sock, piece_index):

        piece_data = self.get_piece(piece_index)
        if piece_data is None:
            raise ValueError(f"Peer {self.peer_id} does not have piece {piece_index}")

        sock.sendall(make_piece(piece_index, piece_data))

    def parse_piece_payload(self, payload):

        if len(payload) < 4:
            raise ValueError("Piece payload must include piece index and data")

        piece_index = bytes_to_int(payload[:4])
        piece_data = payload[4:]
        return piece_index, piece_data

    # Deciphers a recieved message and acts based on what it is
    def handle_message(self, remote_peer_id, sock, msg_type, payload):
        if msg_type == MSG_BITFIELD:
            remote_bitfield = parse_bitfield(payload, self.num_pieces)
            self.remote_bitfields[remote_peer_id] = remote_bitfield
            self.update_interest_for_neighbor(remote_peer_id)
            return

        if msg_type == MSG_INTERESTED:
            self.interested_peers.add(remote_peer_id)
            self.log(f"Peer {self.peer_id} received the 'interested' message from {remote_peer_id}.")
            return

        if msg_type == MSG_NOT_INTERESTED:
            self.interested_peers.discard(remote_peer_id)
            self.log(f"Peer {self.peer_id} received the 'not interested' message from {remote_peer_id}.")
            return

        if msg_type == MSG_CHOKE:
            self.peer_choking_us[remote_peer_id] = True
            self.log(f"Peer {self.peer_id} is choked by {remote_peer_id}.")
            return

        if msg_type == MSG_UNCHOKE:
            self.peer_choking_us[remote_peer_id] = False
            self.log(f"Peer {self.peer_id} is unchoked by {remote_peer_id}.")

            remote_bitfield = self.remote_bitfields.get(remote_peer_id)
            if remote_bitfield is None:
                return

            piece_index = self.choose_piece_to_request(remote_bitfield)
            if piece_index is not None:
                self.send_request(sock, piece_index)
            return

        if msg_type == MSG_REQUEST:
            piece_index = self.parse_request_payload(payload)
            if self.has_piece(piece_index) and not self.peers_we_choking.get(remote_peer_id, True):
                self.send_piece_message(sock, piece_index)
            return

        if msg_type == MSG_PIECE:
            piece_index, piece_data = self.parse_piece_payload(payload)
            self.requested_pieces.discard(piece_index)
            self.set_piece(piece_index, piece_data)

            # Count number of bytes downloaded from neighbor
            self.download_counts[remote_peer_id] = (self.download_counts.get(remote_peer_id, 0) + len(piece_data))
            self.log(
                f"Peer {self.peer_id} has downloaded the piece {piece_index} "
                f"from {remote_peer_id}. Now the number of pieces it has is "
                f"{self.piece_count_loaded()}."
            )
            self.broadcast_have(piece_index)
            self.update_interest_for_all_neighbors()

            # If we now have all pieces, log it and update the file itself
            if self.is_complete() and self.peer_id not in self.complete_peers:
                self.write_complete_file()
                self.complete_peers.add(self.peer_id)
                self.log(f"Peer {self.peer_id} has downloaded the complete file.")

            # See what other pieces the neighbor has
            remote_bitfield = self.remote_bitfields.get(remote_peer_id)
            if remote_bitfield is None:
                return

            # If neighbor is choking us, stop requesting
            if self.peer_choking_us.get(remote_peer_id, True):
                return

            # Otherwise choose a piece we can request from this neighbor if there is one we need
            next_piece_index = self.choose_piece_to_request(remote_bitfield)
            if next_piece_index is not None:
                self.send_request(sock, next_piece_index)
            else:
                return

            return

        if msg_type == MSG_HAVE:
            piece_index = self.parse_request_payload(payload)
            remote_bitfield = self.remote_bitfields.get(remote_peer_id, [0] * self.num_pieces)
            if piece_index < 0 or piece_index >= self.num_pieces:
                raise ValueError(f"Invalid HAVE piece index: {piece_index}")

            remote_bitfield[piece_index] = 1
            self.remote_bitfields[remote_peer_id] = remote_bitfield
            if all(b == 1 for b in remote_bitfield):
                self.complete_peers.add(remote_peer_id)
            self.log(
                f"Peer {self.peer_id} received the 'have' message from "
                f"{remote_peer_id} for the piece {piece_index}."
            )
            self.update_interest_for_neighbor(remote_peer_id)
            return

    def perform_outgoing_handshake(self, sock, expected_peer_id):
        sock.sendall(make_handshake(self.peer_id))
        response = self.receive_bytes(sock, HANDSHAKE_LENGTH)
        remote_peer_id = parse_handshake(response)
        if remote_peer_id != expected_peer_id:
            raise ValueError(f"Expected peer {expected_peer_id}, but received handshake from {remote_peer_id}")
        return remote_peer_id

    def perform_incoming_handshake(self, sock):
        data = self.receive_bytes(sock, HANDSHAKE_LENGTH)
        remote_peer_id = parse_handshake(data)
        if remote_peer_id not in self.later_peer_ids:
            raise ValueError(
                f"Peer {self.peer_id} received an unexpected connection from peer {remote_peer_id}"
            )
        if remote_peer_id in self.connections:
            raise ValueError(
                f"Peer {self.peer_id} already has a connection with peer {remote_peer_id}"
            )

        sock.sendall(make_handshake(self.peer_id))
        return remote_peer_id

    def start_peer_listener(self, remote_peer_id, sock):
        listener = threading.Thread(
            target=self.peer_message_loop,
            args=(remote_peer_id, sock),
            daemon=True,
        )
        listener.start()

    def peer_message_loop(self, remote_peer_id, sock):
        while True:
            try:
                msg_type, payload = self.receive_message(sock)
                self.handle_message(remote_peer_id, sock, msg_type, payload)
            except Exception as e:
                print(f"Peer {self.peer_id} lost connection to peer {remote_peer_id}: {e}")
                self.connections.pop(remote_peer_id, None)
                # TODO
                break

    # Stores a newly established neighbor connection and initializes its state
    def register_connection(self, remote_peer_id, sock):
        self.connections[remote_peer_id] = sock
        self.peer_choking_us[remote_peer_id] = True
        self.peers_we_choking[remote_peer_id] = True
        self.download_counts[remote_peer_id] = 0

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

    # Waits for peers to connect to it
    def accept_connections(self):
        while True:
            server_socket = self.server_socket
            if server_socket is None:
                break

            sock = None

            try:
                sock, address = server_socket.accept()
                sock.settimeout(None)

                # read the peers handshake and send one back
                remote_peer_id = self.perform_incoming_handshake(sock)

                # Store the socket for later
                self.register_connection(remote_peer_id, sock)
                self.send_bitfield(sock)
                self.start_peer_listener(remote_peer_id, sock)
                self.log(f"Peer {self.peer_id} is connected from Peer {remote_peer_id}.")

            except Exception as e:
                self.close_socket(sock)
                print(f"Accept error: {e}")

    # Starts the given peer and allows it to accept connections as well as connects to lower ID peers
    def start(self):
        self.start_server() # Starts the server

        # Accept incoming connections and connect to prior peers
        accept_thread = threading.Thread(target=self.accept_connections)
        accept_thread.daemon = True
        accept_thread.start()

        # Connect to all the peers that have already been started
        self.connect_to_previous_peers()

        # Start choke/unchoke timers
        threading.Thread(target=self._run_unchoke_timer, daemon=True).start()
        threading.Thread(target=self._run_optimistic_unchoke_timer, daemon=True).start()

        while len(self.complete_peers) < len(self.peer_info):
            time.sleep(1)

    # Creates the peers log file
    def setup_log_file(self):
        with open(self.log_path, "w"):
            pass

    # Writes a log to the terminal and the peer's log file.
    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}]: {message}"
        print(line)

        with open(self.log_path, "a") as f:
            f.write(line + "\n")

    def select_preferred_neighbors(self):
        with self.lock:
            candidates = list()
            for p in self.interested_peers:
                if p in self.connections:
                    candidates.append(p)
            if self.is_complete():
                chosen = set(random.sample(candidates, min(self.num_preferred_neighbors, len(candidates))))
            else:
                random.shuffle(candidates)
                candidates.sort(key=lambda p: self.download_counts.get(p, 0), reverse=True)
                chosen = set(candidates[:self.num_preferred_neighbors])
            for p in self.download_counts:
                self.download_counts[p] = 0
            old_preferred = self.preferred_peers

            for p in chosen - old_preferred:
                if p in self.connections:
                    try:
                        self.connections[p].sendall(make_unchoke())
                        self.peers_we_choking[p] = False
                    except Exception:
                        pass

            for p in old_preferred - chosen:
                if p in self.connections and p != self.opt_unchoke_peer:
                    try:
                        self.connections[p].sendall(make_choke())
                        self.peers_we_choking[p] = True
                    except Exception:
                        pass

            self.preferred_peers = chosen

            if chosen:
                id_list = ", ".join(str(p) for p in sorted(chosen))
                self.log(f"Peer {self.peer_id} has the preferred neighbors {id_list}.")

    def select_optimistic_unchoke(self):
        with self.lock:
            # Candidates: choked, interested, connected, and not already a preferred neighbor
            candidates = [
                p for p in self.interested_peers
                if p in self.connections
                and self.peers_we_choking.get(p, True)
                and p not in self.preferred_peers
            ]

            if not candidates:
                return

            old_opt = self.opt_unchoke_peer
            new_opt = random.choice(candidates)

            # Choke the previous optimistic unchoke peer if they aren't now preferred
            if old_opt and old_opt != new_opt and old_opt not in self.preferred_peers:
                if old_opt in self.connections:
                    try:
                        self.connections[old_opt].sendall(make_choke())
                        self.peers_we_choking[old_opt] = True
                    except Exception:
                        pass

            # Unchoke the new optimistic peer
            self.opt_unchoke_peer = new_opt
            try:
                self.connections[new_opt].sendall(make_unchoke())
                self.peers_we_choking[new_opt] = False
            except Exception:
                pass

            self.log(f"Peer {self.peer_id} has the optimistically unchoked neighbor {new_opt}.")
        
    def _run_unchoke_timer(self):
        while len(self.complete_peers) < len(self.peer_info):
            time.sleep(self.unchoking_interval)
            self.select_preferred_neighbors()

    def _run_optimistic_unchoke_timer(self):
        while len(self.complete_peers) < len(self.peer_info):
            time.sleep(self.optimistic_unchoking_interval)
            self.select_optimistic_unchoke()