
Files:

Common.cfg — shared settings for all peers (file name, file size, piece size, unchoking intervals, number of preferred neighbors)

PeerInfo.cfg — lists every peer in the network (ID, hostname, port, whether they start with the file)

peerProcess.py — entry point, run with a peer ID as argument (e.g. python peerProcess.py 1001)

handshake.py - defins handshake messages between peers

peer_message.py - defines other messages between peers

peer_[peerID]/ — working directory for each peer, contains their copy of the file (complete or in progress)

log_peer_[peerID].log — log file generated at runtime for each peer
 
