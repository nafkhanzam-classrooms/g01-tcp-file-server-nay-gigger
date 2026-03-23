import chunk
import socket
import os
from utils import *


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
        bmsg = {"type": "upload", "filename": filename, "size": msg.get("size")}
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


def main():
    init_server()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(ADDR)
    server_sock.listen(5)
    print(f"Server started on {ADDR}")
    print("This server handles one client at a time sequentially.")

    while True:
        try:
            client_sock, addr = server_sock.accept()
            print(f"Client connected: {addr}")
            clients = [client_sock]

            while True:
                msg = recv_message(client_sock)
                if not msg:
                    break
                handle_client_message(client_sock, msg, clients)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            if client_sock in clients:
                clients.remove(client_sock)
            client_sock.close()
            print(f"Client disconnected: {addr}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting server.")
        
    