# File to parse the required config files

# Parses the common config, storing the settings in a dictionary
def load_common_config(path):
    config = {}

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) != 2:
                raise ValueError(f"Invalid line in Common.cfg: {line}")

            key, value = parts

            if key in {
                "NumberOfPreferredNeighbors",
                "UnchokingInterval",
                "OptimisticUnchokingInterval",
                "FileSize",
                "PieceSize",
            }:
                config[key] = int(value)
            else:
                config[key] = value

    return config


# Parses the peer config file, returns an array of peers with dictionaries containing each peer's metadata
def load_peer_info(path):
    peers = []

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) != 4:
                raise ValueError(f"Invalid line in PeerInfo.cfg: {line}")

            peer_id, host, port, has_file = parts

            peers.append({
                "peer_id": int(peer_id),
                "host": host,
                "port": int(port),
                "has_file": has_file == "1"
            })

    return peers

# Returns all peers whose IDs are larger than the given peer_id.
def get_peer_by_id(peers, peer_id):
    for peer in peers:
        if peer["peer_id"] == peer_id:
            return peer
    return None

# Returns the prior peers
def get_previous_peers(peers, peer_id):
    previous = []
    for peer in peers:
        if peer["peer_id"] < peer_id:
            previous.append(peer)
    return previous

# Returns all peers whose IDs are larger than the given peer_id.
def get_later_peers(peers, peer_id):
    later = []
    for peer in peers:
        if peer["peer_id"] > peer_id:
            later.append(peer)
    return later


# little test block right here, change however ya want,the Common.cfg should print with numeric fields shown as ints,
# PeerInfo.cfg should print each peer dictionary and TEST LOOKUP should verify that helper functions work correctly

if __name__ == "__main__":
    common = load_common_config("Common.cfg")
    peers = load_peer_info("PeerInfo.cfg")

    print("COMMON CONFIG:")
    for key, value in common.items():
        print(f"{key}: {value} ({type(value).__name__})")

    print("\nPEER INFO:")
    for peer in peers:
        print(peer)

    print("\nTEST LOOKUP:")
    test_peer_id = 1003
    print("Current peer:", get_peer_by_id(peers, test_peer_id))
    print("Previous peers:", get_previous_peers(peers, test_peer_id))
    print("Later peers:", get_later_peers(peers, test_peer_id))