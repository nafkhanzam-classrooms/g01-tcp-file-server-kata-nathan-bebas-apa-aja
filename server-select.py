import socket
import select
import os

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 4096
SERVER_DIR = 'server_storage'

if not os.path.exists(SERVER_DIR):
    os.makedirs(SERVER_DIR)

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(5)

sockets_list = [server_socket]
clients = {}
upload_states = {} 

print(f"Select-based Server berjalan pada {HOST}:{PORT}")
print(f"Menyimpan file di: ./{SERVER_DIR}/")

def broadcast(message, sender_socket):
    for client_socket in sockets_list:
        if client_socket != server_socket and client_socket != sender_socket:
            try:
                client_socket.send(message)
            except:
                client_socket.close()
                if client_socket in sockets_list:
                    sockets_list.remove(client_socket)

while True:
    read_sockets, _, exception_sockets = select.select(sockets_list, [], sockets_list)

    for notified_socket in read_sockets:
        if notified_socket == server_socket:
            client_socket, client_address = server_socket.accept()
            sockets_list.append(client_socket)
            clients[client_socket] = client_address
            
            print(f"Accepted connection from {client_address}")
            broadcast(f"User {client_address} bergabung!\n".encode('utf-8'), client_socket)
            client_socket.send(b"Welcome! Commands: /list, /upload <filename>, /download <filename>\n")
            
        else:
            try:
                if notified_socket in upload_states:
                    state = upload_states[notified_socket]
                    data = notified_socket.recv(BUFFER_SIZE)
                    
                    if not data:
                        raise ConnectionResetError
                    
                    remaining = state['expected'] - state['received']
                    chunk = data[:remaining]
                    leftover = data[remaining:]

                    state['file'].write(chunk)
                    state['received'] += len(chunk)

                    if state['received'] >= state['expected']:
                        state['file'].close()
                        print(f"[SUCCESS] Menerima '{state['filename']}' dari {clients[notified_socket]}")
                        notified_socket.send(b"Server: Upload berhasil.\n")
                        del upload_states[notified_socket]
                        
                        if leftover:
                            msg = leftover.decode('utf-8', errors='ignore').strip()
                            if msg:
                                formatted_msg = f"[{clients[notified_socket]}]: {msg}\n".encode('utf-8')
                                broadcast(formatted_msg, notified_socket)
                    continue
                
                data = notified_socket.recv(BUFFER_SIZE)
                if not data:
                    raise ConnectionResetError

                msg = data.decode('utf-8', errors='ignore').strip()

                if msg == '/list':
                    files = os.listdir(SERVER_DIR)
                    file_list = "\n".join(files) if files else "Tidak ada files pada server."
                    notified_socket.send(f"Files di server:\n{file_list}\n".encode('utf-8'))

                elif msg.startswith('/upload'):
                    parts = msg.split()
                    if len(parts) == 3:
                        filename = parts[1]
                        filesize = int(parts[2])
                        filepath = os.path.join(SERVER_DIR, os.path.basename(filename))

                        upload_states[notified_socket] = {
                            'filename': filename,
                            'expected': filesize,
                            'received': 0,
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
                            filesize = os.path.getsize(filepath)
                            notified_socket.send(f"READY_DOWNLOAD {filename} {filesize}\n".encode('utf-8'))
                            
                            with open(filepath, 'rb') as f:
                                while (chunk := f.read(BUFFER_SIZE)):
                                    notified_socket.sendall(chunk)
                        else:
                            notified_socket.send(b"Error: File not found.\n")
                    else:
                        notified_socket.send(b"Usage: /download <filename>\n")

                else:
                    formatted_msg = f"[{clients[notified_socket]}]: {msg}\n".encode('utf-8')
                    broadcast(formatted_msg, notified_socket)

            except Exception as e:
                print(f"Memutuskan koneksi dengan {clients.get(notified_socket, 'Unknown')}")
                sockets_list.remove(notified_socket)
                if notified_socket in clients:
                    del clients[notified_socket]
                if notified_socket in upload_states:
                    upload_states[notified_socket]['file'].close()
                    del upload_states[notified_socket]
                notified_socket.close()

    for notified_socket in exception_sockets:
        sockets_list.remove(notified_socket)
        if notified_socket in clients:
            del clients[notified_socket]
        notified_socket.close()
