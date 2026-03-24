import socket
import threading
from utils import *

def recv_loop(sock, server):
    while True:
        try:
            msg = server.recv_message(sock)
            if not msg:
                print("\nServer disconnected")
                break

            msg_type = msg.get("type")
            if msg_type == "broadcast":
                print(f"\n{msg.get('msg')}")
                print("> ", end="", flush=True)
            
            elif msg_type == "list":
                files = msg.get("files", [])
                print("\nFiles on server:")
                for f in files:
                    print(f"  - {f}")
                print("> ", end="", flush=True)
            
            elif msg_type == "download":
                filename = msg.get("filename")
                size = msg.get("size")
                if size is None:
                    print(f"\nError: {msg.get('error')}")
                else:
                    print(f"\nDownloading '{filename}' ({size} bytes)...")
                    with open(server.client_dir / filename, "wb") as f:
                        while size > 0:
                            chunk = sock.recv(min(4096, size))
                            if not chunk:
                                break
                            f.write(chunk)
                            size -= len(chunk)
                    print(f"\nDownloaded '{filename}' ({msg.get('size')} bytes) successfully to {server.client_dir}/.")
                print("> ", end="", flush=True)
            
            elif msg_type == "error":
                print(f"\nError: {msg.get('error')}")
                print("> ", end="", flush=True)
            
            else:
                print(f"\nUnknown message type: {msg_type}")
                print("> ", end="", flush=True)
        
        except Exception as e:
            print(f"\nError: {e}")
            break


def main():
    server = TCPFileServer()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(server.addr)
        print(f"Connected to server {server.addr}")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return
    
    threading.Thread(target=recv_loop, args=(sock, server), daemon=True).start()

    print("Commands:")
    print("  /list               - List existing files on the server")
    print("  /upload <filename>  - Upload a local file to the server")
    print("  /download <filename>- Download a file from the server")
    print("  <message>           - Broadcast a message to other clients")
    print("  /quit               - Disconnect from server\n")

    while True:
        try:
            cmd_line = input("> ")
            if not cmd_line:
                continue
            
            if cmd_line.startswith("/quit"):
                break
            
            elif cmd_line.startswith("/list"):
                server.send_message(sock, {"type": "command", "cmd": "list"})
            
            elif cmd_line.startswith("/upload"):
                parts = cmd_line.split(" ", 1)
                if len(parts) < 2:
                    print("Usage: /upload <filename>")
                    continue
                filepath = Path(parts[1].strip())
                if not filepath.exists():
                    print(f"Error: File '{filepath.name}' not found.")
                    continue

                size = filepath.stat().st_size
                server.send_message(sock, {"type": "upload", "filename": filepath.name, "size": size})
                with open(filepath, 'rb') as f:
                    while chunk := f.read(4096):
                        sock.sendall(chunk)
                print(f"Uploaded '{filepath.name}' ({size} bytes)")
            elif cmd_line.startswith("/download"):
                parts = cmd_line.split(" ", 1)
                if len(parts) < 2:
                    print("Usage: /download <filename>")
                    continue
                filename = parts[1].strip()
                server.send_message(sock, {"type": "command", "cmd": "download", "filename": filename})
            else:
                server.send_message(sock, {"type": "broadcast", "msg": cmd_line})
        
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            break
        
    sock.close()

if __name__ == "__main__":
    main()