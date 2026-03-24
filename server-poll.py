import socket
import select
import os
import time

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 4096
SERVER_DIR = 'server_storage'
EOF_MARKER = b"<END_OF_FILE>"

if not os.path.exists(SERVER_DIR):
    os.makedirs(SERVER_DIR)

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(5)

fd_to_socket = {server_socket.fileno(): server_socket}
clients = {}
upload_states = {}

poller = select.poll()
poller.register(server_socket, select.POLLIN)

print(f"Server berjalan pada {HOST}:{PORT}")
print(f"Menyimpan file di: ./{SERVER_DIR}/")

def broadcast(message, sender_socket):
    for client_socket in clients.keys():
        if client_socket != sender_socket:
            try:
                client_socket.send(message)
            except:
                clean_up(client_socket)

def clean_up(sock):
    fd = sock.fileno()
    poller.unregister(fd)
    if fd in fd_to_socket:
        del fd_to_socket[fd]
    if sock in clients:
        print(f"Memutuskan koneksi dengan {clients[sock]}")
        del clients[sock]
    if sock in upload_states:
        upload_states[sock]['file'].close()
        del upload_states[sock]
    sock.close()

while True:
    events = poller.poll()

    for fd, flag in events:
        notified_socket = fd_to_socket[fd]

        if flag & (select.POLLHUP | select.POLLERR):
            clean_up(notified_socket)
            continue

        if flag & select.POLLIN:
            if notified_socket == server_socket:
                client_socket, client_address = server_socket.accept()
                
                fd_to_socket[client_socket.fileno()] = client_socket
                clients[client_socket] = client_address
                poller.register(client_socket, select.POLLIN)
                
                print(f"Accepted {client_address}")
                broadcast(f"User {client_address} bergabung!\n".encode('utf-8'), client_socket)
                client_socket.send(b"Welcome! Commands: /list, /upload <filename>, /download <filename>\n")
                
            else:
                try:
                    if notified_socket in upload_states:
                        state = upload_states[notified_socket]
                        data = notified_socket.recv(BUFFER_SIZE)
                        
                        if not data:
                            raise ConnectionResetError

                        if EOF_MARKER in data:
                            clean_data = data.replace(EOF_MARKER, b"")
                            state['file'].write(clean_data)
                            state['file'].close()
                            
                            print(f"Berhasil menerima {state['filename']} dari {clients[notified_socket]}")
                            notified_socket.send(b"Server: Upload selesai.\n")
                            del upload_states[notified_socket]
                        else:
                            state['file'].write(data)
                        continue

                    data = notified_socket.recv(BUFFER_SIZE)
                    if not data:
                        raise ConnectionResetError

                    msg = data.decode('utf-8').strip()

                    if msg == '/list':
                        files = os.listdir(SERVER_DIR)
                        file_list = "\n".join(files) if files else "Tidak ada files pada server."
                        notified_socket.send(f"Files di server:\n{file_list}\n".encode('utf-8'))

                    elif msg.startswith('/upload'):
                        parts = msg.split()
                        if len(parts) == 2:
                            filename = parts[1]
                            filepath = os.path.join(SERVER_DIR, os.path.basename(filename))

                            upload_states[notified_socket] = {
                                'filename': filename,
                                'file': open(filepath, 'wb')
                            }
                            notified_socket.send(b"READY_UPLOAD\n") 
                        else:
                            notified_socket.send(b"Usage: /upload <filename>\n")

                    elif msg.startswith('/download'):
                        parts = msg.split()
                        if len(parts) == 2:
                            filename = os.path.basename(parts[1])
                            filepath = os.path.join(SERVER_DIR, filename)
                            
                            if os.path.exists(filepath):
                                notified_socket.send(f"READY_DOWNLOAD {filename}\n".encode('utf-8'))
                                time.sleep(0.1) 
                                
                                with open(filepath, 'rb') as f:
                                    while (chunk := f.read(BUFFER_SIZE)):
                                        notified_socket.sendall(chunk)
                                
                                time.sleep(0.1) 
                                notified_socket.sendall(EOF_MARKER)
                            else:
                                notified_socket.send(b"Error: File not found.\n")
                        else:
                            notified_socket.send(b"Usage: /download <filename>\n")

                    else:
                        formatted_msg = f"[{clients[notified_socket]}]: {msg}\n".encode('utf-8')
                        broadcast(formatted_msg, notified_socket)

                except Exception as e:
                    print(f"Error with {clients[notified_socket]}: {e}")
                    clean_up(notified_socket)