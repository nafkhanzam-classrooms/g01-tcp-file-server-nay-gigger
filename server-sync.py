import socket
from utils import *


def main():
    server = TCPFileServer(mode="sync")
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(server.addr)
    server_sock.listen(5)
    print(f"Synchronous server started on {server.addr}")
    print("This server handles one client at a time sequentially.")

    while True:
        client_sock, addr = None, None
        try:
            client_sock, addr = server_sock.accept()
            print(f"Client connected: {addr}")
            clients = [client_sock]

            while True:
                msg = server.recv_message(client_sock)
                if not msg:
                    break

                msg_type = msg.get("type")

                if msg_type == "upload":
                    server.handle_upload(client_sock, msg, clients, addr)

                elif msg_type == "command" and msg.get("cmd") == "download":
                    server.handle_download(client_sock, msg, addr)

                else:
                    server.handle_client_message(client_sock, msg, clients)

        except Exception as e:
            print(f"Error: {e}")
        finally:
            if client_sock:
                client_sock.close()
                if addr:
                    print(f"Client disconnected: {addr}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting server.")