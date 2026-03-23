import socket
import os
from utils import *

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
        
    