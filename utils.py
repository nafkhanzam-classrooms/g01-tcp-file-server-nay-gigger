import struct
import json
from pathlib import Path

class TCPFileServer:
    def __init__(self, server_dir='server_files', client_dir='client_files', addr=('127.0.0.1', 8080)):
        self.server_dir = Path(server_dir)
        self.client_dir = Path(client_dir)
        self.addr = addr
        self.server_dir.mkdir(exist_ok=True)
        self.client_dir.mkdir(exist_ok=True)

    def send_message(self, sock, msg_var):
        data = json.dumps(msg_var).encode('utf-8')
        sock.sendall(struct.pack('!I', len(data)) + data)

    def recv_exact(self, sock, n):
        data = bytearray()
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    def recv_message(self, sock):
        raw_msglen = self.recv_exact(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('!I', raw_msglen)[0]
        data = self.recv_exact(sock, msglen)
        if not data:
            return None
        return json.loads(data.decode('utf-8'))

    def _broadcast(self, sender_sock, clients_list, message_dict):
        for client in clients_list:
            if client != sender_sock:
                try:
                    self.send_message(client, message_dict)
                except:
                    pass

    def handle_client_message(self, sock, msg, clients_list):
        msg_type = msg.get("type")

        if msg_type == "command" and msg.get("cmd") == "list":
            files = [f.name for f in self.server_dir.iterdir() if f.is_file()]
            self.send_message(sock, {"type": "list", "files": files})

        elif msg_type == "command" and msg.get("cmd") == "download":
            filename = Path(msg.get("filename", "")).name
            filepath = self.server_dir / filename
            if filepath.exists():
                size = filepath.stat().st_size
                self.send_message(sock, {"type": "download", "filename": filename, "size": size})
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        sock.sendall(chunk)
            else:
                self.send_message(sock, {"type": "error", "error": "File not found"})

        elif msg_type == "upload":
            filename = Path(msg.get("filename", "")).name
            original_size = msg.get("size")
            filepath = self.server_dir / filename
            with open(filepath, 'wb') as f:
                remaining = original_size
                while remaining > 0:
                    chunk = self.recv_exact(sock, min(4096, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            try:
                peer = sock.getpeername()
                peer_str = f"{peer[0]}:{peer[1]}"
            except:
                peer_str = "Unknown"
            bmsg = {"type": "broadcast", "msg": f"File '{filename}' ({original_size} bytes) uploaded by {peer_str}"}
            self._broadcast(sock, clients_list, bmsg)

        elif msg_type == "broadcast":
            try:
                peer = sock.getpeername()
                peer_str = f"{peer[0]}:{peer[1]}"
            except:
                peer_str = "Unknown"
            bmsg = {"type": "broadcast", "msg": f"[{peer_str}] {msg.get('msg')}"}
            self._broadcast(sock, clients_list, bmsg)

        else:
            self.send_message(sock, {"type": "error", "error": "Unknown command"})

        return True