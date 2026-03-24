import select
import socket
from utils import *


def remove_client(s, rlist, wlist, states, server):
    if s in rlist:
        rlist.remove(s)
    if s in wlist:
        wlist.remove(s)
    server.downloading.discard(s)
    server.uploading.discard(s)
    state = states.pop(s, None)
    if state:
        if state.dl_file:
            state.dl_file.close()
        if state.ul_file:
            state.ul_file.close()
    s.close()


def main():
    server = TCPFileServer(mode="select")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(server.addr)
    server_sock.listen(5)
    server_sock.setblocking(False)

    rlist = [server_sock]
    wlist = []
    states = {}  # socket → ClientState

    print(f"Server (select) started on {server.addr}")

    while True:
        readable, writable, exceptional = select.select(rlist, wlist, rlist)

        for s in readable:
            if s is server_sock:
                client_sock, addr = s.accept()
                print(f"New connection from {addr}")
                client_sock.setblocking(False)
                rlist.append(client_sock)
                states[client_sock] = ClientState()
                continue

            state = states.get(s)
            if not state:
                continue

            try:
                if s in server.uploading:
                    # Receive the next chunk of an in-progress upload
                    current_clients = [c for c in rlist if c is not server_sock]
                    done = server.upload_chunk(s, state, current_clients)
                    # Nothing extra to do — begin_upload already opened the file

                else:
                    msg = server.recv_message(s)
                    if not msg:
                        raise ConnectionResetError("disconnected")

                    msg_type = msg.get("type")
                    current_clients = [c for c in rlist if c is not server_sock]

                    if msg_type == "upload":
                        server.handle_upload(s, msg, current_clients, addr=None, state=state)

                    elif msg_type == "command" and msg.get("cmd") == "download":
                        started = server.handle_download(s, msg, addr=None, state=state)
                        if started and s not in wlist:
                            wlist.append(s)

                    else:
                        server.handle_client_message(s, msg, current_clients)

            except Exception as e:
                print(f"Client error: {e}")
                remove_client(s, rlist, wlist, states, server)

        for s in writable:
            state = states.get(s)
            if not state:
                continue

            try:
                done = server.download_chunk(s, state)
                if done and s in wlist:
                    wlist.remove(s)

            except Exception as e:
                print(f"Write error: {e}")
                remove_client(s, rlist, wlist, states, server)

        for s in exceptional:
            print("Exception on socket")
            remove_client(s, rlist, wlist, states, server)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting server.")