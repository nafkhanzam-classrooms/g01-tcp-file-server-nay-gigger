import threading
import socket
import os
from utils import *

clients = []
clients_lock = threading.Lock()

def client_thread(client_sock, addr):
    with clients_lock:
        clients.append(client_sock)
    print(f"Client connected: {addr}")
    try:
        while True:
            msg = recv_message(client_sock)
            if not msg:
                break
            with clients_lock:
                current_clients = list(clients)
            handle_client_message(client_sock, msg, current_clients)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print(f"Client disconnected: {addr}")
        with clients_lock:
            if client_sock in clients:
                clients.remove(client_sock)
        try:
            client_sock.close()
        except:
            pass

def main():
    init_server()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(ADDR)
    server_sock.listen(5)
    print(f"Threaded server started on {ADDR}")
    
    while True:
        try:
            client_sock, addr = server_sock.accept()
            threading.Thread(target=client_thread, args=(client_sock, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\nExiting server.")
            break
        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting server.")
