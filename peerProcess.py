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
    if len(sys.argv) != 2:
        print("Usage: python3 peerProcess.py <peer_id>")
        sys.exit(1)

    peer_id = int(sys.argv[1])

    common_config = load_common_config("Common.cfg")
    peer_info = load_peer_info("PeerInfo.cfg")

    current_peer = get_peer_by_id(peer_info, peer_id)
    if current_peer is None:
        print(f"Error: peer ID {peer_id} not found in PeerInfo.cfg")
        sys.exit(1)

    previous_peers = get_previous_peers(peer_info, peer_id)
    later_peers = get_later_peers(peer_info, peer_id)

    print("CURRENT PEER:")
    print(current_peer)

    print("\nPREVIOUS PEERS:")
    for peer in previous_peers:
        print(peer)

    print("\nLATER PEERS:")
    for peer in later_peers:
        print(peer)

    print("\nCOMMON CONFIG:")
    for key, value in common_config.items():
        print(f"{key}: {value}")

    this_peer = Peer(peer_id, common_config, peer_info)

    print("\nPeer object created successfully.")
    print(f"Peer ID: {this_peer.peer_id}")
    print("\nPeer object created successfully.")
    print(this_peer)
    print("Bitfield length:", len(this_peer.bitfield))
    print("First 10 bitfield entries:", this_peer.bitfield[:10])
    this_peer.start_server()
    input("Press Enter to exit...\n")


if __name__ == "__main__":
    main()