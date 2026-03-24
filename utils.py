import struct
import json
from pathlib import Path

MODES = {"sync", "thread", "select", "poll"}


class ClientState:
    def __init__(self):
        # download state
        self.dl_file = None
        self.dl_remaining = 0

        # upload state
        self.ul_file = None
        self.ul_remaining = 0
        self.ul_original_size = 0
        self.ul_filename = ""


class TCPFileServer:
    def __init__(self, mode="sync", server_dir="server_files", client_dir="client_files", addr=("127.0.0.1", 8080)):
        if mode not in MODES:
            raise ValueError(f"Invalid mode '{mode}'. Choose from: {MODES}")
        self.mode = mode
        self.server_dir = Path(server_dir)
        self.client_dir = Path(client_dir)
        self.addr = addr
        self.server_dir.mkdir(exist_ok=True)
        self.client_dir.mkdir(exist_ok=True)
        self.downloading = set()  # sockets currently mid-download
        self.uploading = set()    # sockets currently mid-upload

    def send_message(self, sock, msg_var):
        data = json.dumps(msg_var).encode("utf-8")
        sock.sendall(struct.pack("!I", len(data)) + data)

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
        msglen = struct.unpack("!I", raw_msglen)[0]
        data = self.recv_exact(sock, msglen)
        if not data:
            return None
        return json.loads(data.decode("utf-8"))

    def _broadcast(self, sender_sock, clients_list, message_dict):
        for client in clients_list:
            if client != sender_sock and client not in self.downloading and client not in self.uploading:
                try:
                    self.send_message(client, message_dict)
                except Exception:
                    pass

    def handle_upload(self, sock, msg, clients_list, addr, state=None):
        if self.mode in ("sync", "thread"):
            return self._upload_blocking(sock, msg, clients_list, addr)
        self._begin_upload(sock, msg, state)

    def _upload_blocking(self, sock, msg, clients_list, addr):
        filename = Path(msg.get("filename", "")).name
        original_size = msg.get("size", 0)
        filepath = self.server_dir / filename
        peer_str = f"{addr[0]}:{addr[1]}"

        print(f"Receiving upload: '{filename}' ({original_size} bytes) from {peer_str}")
        self.uploading.add(sock)
        try:
            with open(filepath, "wb") as f:
                remaining = original_size
                while remaining > 0:
                    chunk = self.recv_exact(sock, min(4096, remaining))
                    if not chunk:
                        return False
                    f.write(chunk)
                    remaining -= len(chunk)
        finally:
            self.uploading.discard(sock)

        print(f"Upload complete: '{filename}' from {peer_str}")
        self._broadcast(sock, clients_list, {
            "type": "broadcast",
            "msg": f"File '{filename}' ({original_size} bytes) uploaded by {peer_str}",
        })
        return True

    def _begin_upload(self, sock, msg, state):
        filename = Path(msg.get("filename", "")).name
        original_size = msg.get("size", 0)
        filepath = self.server_dir / filename

        state.ul_file = open(filepath, "wb")
        state.ul_remaining = original_size
        state.ul_original_size = original_size
        state.ul_filename = filename
        self.uploading.add(sock)
        print(f"Receiving upload: '{filename}' ({original_size} bytes)")

    def upload_chunk(self, sock, state, clients_list):
        chunk = sock.recv(min(4096, state.ul_remaining))
        if not chunk:
            raise ConnectionResetError("disconnected during upload")

        state.ul_file.write(chunk)
        state.ul_remaining -= len(chunk)

        if state.ul_remaining > 0:
            return False  # still in progress

        # Upload complete
        state.ul_file.close()
        state.ul_file = None
        self.uploading.discard(sock)

        try:
            peer = sock.getpeername()
            peer_str = f"{peer[0]}:{peer[1]}"
        except Exception:
            peer_str = "Unknown"

        print(f"Upload complete: '{state.ul_filename}' from {peer_str}")
        self._broadcast(sock, clients_list, {
            "type": "broadcast",
            "msg": f"File '{state.ul_filename}' ({state.ul_original_size} bytes) uploaded by {peer_str}",
        })
        return True  # done

    def handle_download(self, sock, msg, addr, state=None):
        if self.mode in ("sync", "thread"):
            return self._download_blocking(sock, msg, addr)
        # select / poll — delegate to _begin_download
        return self._begin_download(sock, msg, state)

    def _download_blocking(self, sock, msg, addr):
        filename = Path(msg.get("filename", "")).name
        filepath = self.server_dir / filename
        peer_str = f"{addr[0]}:{addr[1]}"

        if not filepath.exists():
            self.send_message(sock, {"type": "error", "error": "File not found"})
            return False

        size = filepath.stat().st_size
        self.send_message(sock, {"type": "download", "filename": filename, "size": size})

        self.downloading.add(sock)
        try:
            with open(filepath, "rb") as f:
                while chunk := f.read(4096):
                    sock.sendall(chunk)
        finally:
            self.downloading.discard(sock)

        print(f"Download complete: '{filename}' to {peer_str}")
        return True

    def _begin_download(self, sock, msg, state):
        filename = Path(msg.get("filename", "")).name
        filepath = self.server_dir / filename

        if not filepath.exists():
            self.send_message(sock, {"type": "error", "error": "File not found"})
            return False

        size = filepath.stat().st_size
        self.send_message(sock, {"type": "download", "filename": filename, "size": size})

        state.dl_file = open(filepath, "rb")
        state.dl_remaining = size
        self.downloading.add(sock)
        return True

    def download_chunk(self, sock, state):
        chunk = state.dl_file.read(4096)
        if chunk:
            sock.send(chunk)
            state.dl_remaining -= len(chunk)
            return False  # still in progress

        # EOF — transfer complete
        state.dl_file.close()
        state.dl_file = None
        state.dl_remaining = 0
        self.downloading.discard(sock)
        return True  # done

    def handle_client_message(self, sock, msg, clients_list):
        msg_type = msg.get("type")

        if msg_type == "command" and msg.get("cmd") == "list":
            files = [f.name for f in self.server_dir.iterdir() if f.is_file()]
            self.send_message(sock, {"type": "list", "files": files})

        elif msg_type == "broadcast":
            try:
                peer = sock.getpeername()
                peer_str = f"{peer[0]}:{peer[1]}"
            except Exception:
                peer_str = "Unknown"
            self._broadcast(sock, clients_list, {
                "type": "broadcast",
                "msg": f"[{peer_str}] {msg.get('msg')}",
            })

        else:
            self.send_message(sock, {"type": "error", "error": "Unknown command"})

        return True