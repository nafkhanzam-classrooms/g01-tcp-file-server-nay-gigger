import socket
import struct
import json
import os

ADDR = ('127.0.0.1', 8080)
SERVER_DIR = 'server_files'
CLIENT_DIR = 'client_files'

def init_server():
    if not os.path.exists(SERVER_DIR):
        os.makedirs(SERVER_DIR)

def init_client():
    if not os.path.exists(CLIENT_DIR):
        os.makedirs(CLIENT_DIR)

def send_message(sock, msg_var):
    data = json.dumps(msg_var).encode('utf-8')
    sock.sendall(struct.pack('!I', len(data)) + data)

def recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data.extend(chunk)
    return data

def recv_message(sock):
    raw_msglen = recv_exact(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('!I', raw_msglen)[0]
    data = recv_exact(sock, msglen)
    if not data:
        return None
    return json.loads(data.decode('utf-8'))