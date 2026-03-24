import select
import socket
from utils import *

POLLIN  = select.POLLIN
POLLOUT = select.POLLOUT
POLLERR = select.POLLERR | select.POLLHUP | select.POLLNVAL


def remove_client(fd, fd_to_sock, states, poller, server):
    s = fd_to_sock.pop(fd, None)
    if s is None:
        return
    server.downloading.discard(s)
    server.uploading.discard(s)
    state = states.pop(s, None)
    if state:
        if state.dl_file:
            state.dl_file.close()
        if state.ul_file:
            state.ul_file.close()
    try:
        poller.unregister(fd)
    except Exception:
        pass
    try:
        s.close()
    except Exception:
        pass


def main():
    server = TCPFileServer(mode="poll")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(server.addr)
    server_sock.listen(5)
    server_sock.setblocking(False)

    poller = select.poll()
    poller.register(server_sock.fileno(), POLLIN)

    fd_to_sock = {server_sock.fileno(): server_sock}
    states = {}  # socket → ClientState

    print(f"Server (poll) started on {server.addr}")

    while True:
        events = poller.poll()  # blocks until at least one fd is ready

        for fd, event in events:
            s = fd_to_sock.get(fd)
            if s is None:
                continue

            if event & POLLERR:
                if s is server_sock:
                    print("Server socket error — exiting.")
                    return
                print(f"Error on fd {fd}")
                remove_client(fd, fd_to_sock, states, poller, server)
                continue

            if event & POLLIN:
                if s is server_sock:
                    client_sock, addr = s.accept()
                    print(f"New connection from {addr}")
                    client_sock.setblocking(False)
                    cfd = client_sock.fileno()
                    fd_to_sock[cfd] = client_sock
                    states[client_sock] = ClientState()
                    poller.register(cfd, POLLIN | POLLERR)
                    continue

                state = states.get(s)
                if not state:
                    continue

                try:
                    if s in server.uploading:
                        # Receive the next chunk of an in-progress upload
                        current_clients = [c for c in fd_to_sock.values() if c is not server_sock]
                        server.upload_chunk(s, state, current_clients)

                    else:
                        msg = server.recv_message(s)
                        if not msg:
                            raise ConnectionResetError("disconnected")

                        msg_type = msg.get("type")
                        current_clients = [c for c in fd_to_sock.values() if c is not server_sock]

                        if msg_type == "upload":
                            server.handle_upload(s, msg, current_clients, addr=None, state=state)

                        elif msg_type == "command" and msg.get("cmd") == "download":
                            started = server.handle_download(s, msg, addr=None, state=state)
                            if started:
                                # Watch for writability so we can stream the file
                                poller.modify(fd, POLLIN | POLLOUT | POLLERR)

                        else:
                            server.handle_client_message(s, msg, current_clients)

                except Exception as e:
                    print(f"Client error: {e}")
                    remove_client(fd, fd_to_sock, states, poller, server)

            elif event & POLLOUT:
                state = states.get(s)
                if not state:
                    continue

                try:
                    done = server.download_chunk(s, state)
                    if done:
                        # No more data — stop watching POLLOUT
                        poller.modify(fd, POLLIN | POLLERR)

                except Exception as e:
                    print(f"Write error: {e}")
                    remove_client(fd, fd_to_sock, states, poller, server)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting server.")