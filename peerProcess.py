import sys
from parse_config import load_common_config, load_peer_info
from peer import Peer

# Entry point to program, file must have this name

def main():

    # Peer ID passed in the terminal
    peer_id = int(sys.argv[1])

    # Parse the configs
    common_config = load_common_config()
    peer_info = load_peer_info()

if __name__ == "__main__":
    main()