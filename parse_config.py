# File to parse the required config files

# Parses the common config, storing the settings in a dictionary
def load_common_config(path):
    config = {}
    with open(path) as f:
        for line in f:
            key, value = line.split()
            config[key] = value
    return config

# Parses the peer config file, returns an array of peers with dictionaries containing each peer's metadata
def load_peer_info(path):
    peers = []
    with open(path) as f:
        for line in f:
            peer_id, host, port, has_file = line.split()
            peers.append({
                "peer_id": int(peer_id),
                "host": host,
                "port": int(port),
                "has_file": int(has_file) == 1
            })
    return peers