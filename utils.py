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

def handle_client_message(sock, msg, clients_list):
    msg_type = msg.get("type")

    if msg_type == "command" and msg.get("cmd") == "list":
        files = os.listdir(SERVER_DIR)
        send_message(sock, {"type": "list", "files": files})
    
    elif msg_type == "command" and msg.get("cmd") == "download":
        filename = os.path.basename(msg.get("filename", ""))
        filepath = os.path.join(SERVER_DIR, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            send_message(sock, {"type": "download", "filename": filename, "size": size})
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    sock.sendall(chunk)
        else:
            send_message(sock, {"type": "error", "error": "File not found"})

    elif msg_type == "upload":
        filename = os.path.basename(msg.get("filename", ""))
        size = msg.get("size")
        filepath = os.path.join(SERVER_DIR, filename)
        with open(filepath, 'wb') as f:
            while size > 0:
                chunk = recv_exact(sock, min(4096, size))
                if not chunk:
                    break
                f.write(chunk)
                size -= len(chunk)
        bmsg = {"type": "broadcast", "msg": f"File '{filename}' ({msg.get('size')} bytes) uploaded by {sock.getpeername()}"}
        for c in clients_list:
            if c != sock:
                try:
                    send_message(c, bmsg)
                except:
                    pass
    
    elif msg_type == "broadcast":
        try:
            peer = sock.getpeername()
            peer_str = f"{peer[0]}:{peer[1]}"
        except:
            peer_str = "Unknown"
        bmsg = {"type": "broadcast", "msg": f"[{peer_str}] {msg.get('msg')}"}
        for c in clients_list:
            if c != sock:
                try:
                    send_message(c, bmsg)
                except:
                    pass
    
    else:
        send_message(sock, {"type": "error", "error": "Unknown command"})
    
    return True