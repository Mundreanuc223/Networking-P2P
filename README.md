# Networking P2P

## Group

* Christian Mundreanu
* Reid Castillo
* Nasim Boussarhane

## Files

- `Common.cfg`: Shared settings for all peers (file name, file size, piece size, unchoking intervals, number of preferred neighbors).
- `PeerInfo.cfg`: Lists every peer in the network (ID, hostname, port, and whether they start with the file).
- `peerProcess.py`: Entry point. Run with a peer ID argument, for example: `python peerProcess.py 1001`.
- `handshake.py`: Defines handshake messages between peers.
- `peer_message.py`: Defines peer protocol messages (non-handshake messages).
- `peer_[peerID]/`: Working directory for each peer, containing its copy of the file (complete or in progress).
- `log_peer_[peerID].log`: Runtime log file generated for each peer.

