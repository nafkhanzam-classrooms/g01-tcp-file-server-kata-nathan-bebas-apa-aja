import socket
import os

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 4096
SERVER_DIR = 'server_storage'

if not os.path.exists(SERVER_DIR):
    os.makedirs(SERVER_DIR)

# fungsi untuk baca satu baris sampai \n
def recv_line(sock: socket.socket) -> str:
    buf = b''
    while True:
        ch = sock.recv(1)
        if not ch or ch == b'\n':
            break
        buf += ch
    return buf.decode(errors='replace').strip()

# fungsi untuk kirim pesan ke client
def send_msg(sock: socket.socket, text: str):
    sock.sendall((text + '\n').encode())

# fungsi untuk handle perintah list
def handle_list(conn: socket.socket):
    files = os.listdir(SERVER_DIR)
    if files:
        send_msg(conn, "Files di server:\n  " + "\n  ".join(files))
    else:
        send_msg(conn, "Tidak ada file di server.")

# fungsi untuk handle perintah upload
def handle_upload(conn: socket.socket, parts: list, addr: str):
    if len(parts) < 3:
        send_msg(conn, "[ERROR] Format: /upload <filename> <size>")
        return

    filename = os.path.basename(parts[1])
    try:
        file_size = int(parts[2])
    except ValueError:
        send_msg(conn, "[ERROR] Ukuran file tidak valid.")
        return

    # kasi sinyal ke client untuk mulai upload
    send_msg(conn, "READY_UPLOAD")

    # terima file sesuai ukuran yang dikirim client
    filepath = os.path.join(SERVER_DIR, filename)
    received = 0
    with open(filepath, 'wb') as f:
        while received < file_size:
            chunk = conn.recv(min(BUFFER_SIZE, file_size - received))
            if not chunk:
                break
            f.write(chunk)
            received += len(chunk)

    if received == file_size:
        send_msg(conn, f"[SUCCESS] '{filename}' berhasil diupload ({file_size} bytes).")
        print(f"[{addr}] Upload '{filename}' selesai.")
    else:
        send_msg(conn, f"[ERROR] Upload tidak lengkap ({received}/{file_size} bytes).")

# fungsi untuk handle perintah download
def handle_download(conn: socket.socket, parts: list, addr: str):
    if len(parts) < 2:
        send_msg(conn, "[ERROR] Format: /download <filename>")
        return

    filename = os.path.basename(parts[1])
    filepath = os.path.join(SERVER_DIR, filename)

    if not os.path.isfile(filepath):
        send_msg(conn, f"[ERROR] File '{filename}' tidak ditemukan di server.")
        return

    file_size = os.path.getsize(filepath)

    # kasi sinyal ke client untuk mulai download beserta ukuran file
    send_msg(conn, f"READY_DOWNLOAD {filename} {file_size}")
    with open(filepath, 'rb') as f:
        while chunk := f.read(BUFFER_SIZE):
            conn.sendall(chunk)

    print(f"[{addr}] Download '{filename}' selesai.")

# fungsi untuk handle koneksi client
def handle_client(conn: socket.socket, addr: tuple):
    addr_str = f"{addr[0]}:{addr[1]}"
    print(f"[CONNECTED] Terhubung: {addr_str}")
    send_msg(conn, "[Server] Terhubung. Kamu satu-satunya client saat ini.")

    try:
        while True:
            line = recv_line(conn)
            if not line:
                break

            print(f"[{addr_str}] {line}")
            parts = line.split()
            cmd   = parts[0].lower()

            if cmd == '/list':
                handle_list(conn)
            elif cmd == '/upload':
                handle_upload(conn, parts, addr_str)
            elif cmd == '/download':
                handle_download(conn, parts, addr_str)
            else:
                send_msg(conn, f"[Server] Pesan diterima: '{line}'")

    except (ConnectionResetError, BrokenPipeError) as e:
        print(f"[ERROR] {addr_str}: {e}")
    finally:
        conn.close()
        print(f"[DISCONNECTED] Disconnect: {addr_str}")

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"[*] server-sync.py telah aktif di {HOST}:{PORT} (satu client at a time)")

    try:
        while True:
            print("[*] Menunggu client...")
            conn, addr = server.accept()
            handle_client(conn, addr) # handle_client langsung di main thread, jadi hanya satu client yang bisa terhubung
    except KeyboardInterrupt:
        print("\n[*] Server dimatikan.")
    finally:
        server.close()

if __name__ == '__main__':
    main()