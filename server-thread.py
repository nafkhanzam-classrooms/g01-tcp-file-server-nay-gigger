import threading
import socket
from utils import *

clients = []
clients_lock = threading.Lock()


def client_thread(client_sock, addr, server):
    with clients_lock:
        clients.append(client_sock)
    print(f"Client connected: {addr}")
    try:
        while True:
            msg = server.recv_message(client_sock)
            if not msg:
                break

            with clients_lock:
                current_clients = list(clients)

            msg_type = msg.get("type")

            if msg_type == "upload":
                server.handle_upload(client_sock, msg, current_clients, addr)

            elif msg_type == "command" and msg.get("cmd") == "download":
                server.handle_download(client_sock, msg, addr)

            else:
                server.handle_client_message(client_sock, msg, current_clients)

    except Exception as e:
        print(f"Error with {addr}: {e}")
    finally:
        print(f"Client disconnected: {addr}")
        server.downloading.discard(client_sock)
        server.uploading.discard(client_sock)
        with clients_lock:
            if client_sock in clients:
                clients.remove(client_sock)
        try:
            client_sock.close()
        except Exception:
            pass


def main():
    server = TCPFileServer(mode="thread")
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(server.addr)
    server_sock.listen(5)
    print(f"Threaded server started on {server.addr}")

    while True:
        try:
            client_sock, addr = server_sock.accept()
            threading.Thread(target=client_thread, args=(client_sock, addr, server), daemon=True).start()
        except KeyboardInterrupt:
            print("\nExiting server.")
            break
        except Exception as e:
            print(f"Accept error: {e}")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting server.")