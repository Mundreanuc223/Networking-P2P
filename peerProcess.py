import sys
from parse_config import (
    load_common_config,
    load_peer_info,
    get_peer_by_id,
    get_previous_peers,
    get_later_peers,
)
from peer import Peer


# test by putting python3 peerProcess.py 1003 in the terminal / python3 peerProcess.py 1001

# Entry point to program, file must have this name
def main():

    # Validate usage
    if len(sys.argv) != 2:
        print("Usage: python3 peerProcess.py <peer_id>")
        sys.exit(1)

    try:
        peer_id = int(sys.argv[1])
    except ValueError:
        print("Invalid peer ID, must be an integer.")
        sys.exit(1)

    # Load the configs
    common_config = load_common_config("Common.cfg")
    peer_info = load_peer_info("PeerInfo.cfg")

    current_peer = get_peer_by_id(peer_info, peer_id)
    if current_peer is None:
        print(f"Error: peer ID {peer_id} not found in PeerInfo.cfg")
        sys.exit(1)

    # Initialize that peer and begin it
    this_peer = Peer(peer_id, common_config, peer_info)
    this_peer.start()

if __name__ == "__main__":
    main()