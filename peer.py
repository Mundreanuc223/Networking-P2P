# Class for initializing a peer

class Peer:
    def __init__(self, peer_id, common_config, peer_info):
        self.peer_id = peer_id
        self.common_config = common_config
        self.peer_info = peer_info

        self.setup_directory()

    # Sets up the subdirectory for a peer if it doesn't exist yet
    def setup_directory(self):
        import os
        os.makedirs(f"peer_{self.peer_id}", exist_ok=True)