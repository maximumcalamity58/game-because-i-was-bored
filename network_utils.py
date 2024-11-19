# network_utils.py

def recvall(sock, n):
    """
    Helper function to receive n bytes or return None if EOF is hit.
    """
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data
