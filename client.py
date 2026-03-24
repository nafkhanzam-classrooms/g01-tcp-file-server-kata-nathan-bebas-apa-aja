import socket
import threading
import sys
import os

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 4096
CLIENT_DIR = 'client_download'

if not os.path.exists(CLIENT_DIR):
    os.makedirs(CLIENT_DIR)

upload_event = threading.Event()
download_state = {
    'active':   False,
    'file':     None,
    'filename': '',
    'expected': 0,
    'received': 0,
}

# fungsi untuk menerima pesan dari server
def receive_messages(sock: socket.socket):
    while True:
        try:
            data = sock.recv(BUFFER_SIZE)
            if not data:
                print("\nDisconnected dari server.")
                os._exit(0)

            # kalau lagi download, data dianggap bytes file bukan teks/command
            if download_state['active']:
                remaining = download_state['expected'] - download_state['received']
                chunk   = data[:remaining]
                leftover = data[remaining:]

                download_state['file'].write(chunk)
                download_state['received'] += len(chunk)
                
                # cek apakah file sudah selesai didownload
                if download_state['received'] >= download_state['expected']:
                    download_state['file'].close()
                    download_state['active'] = False
                    print(f"\n[SUCCESS] File '{download_state['filename']}' berhasil didownload.")
                    print("> ", end="", flush=True)

                    # sisa data setelah file selesai (misal broadcast dari server)
                    if leftover:
                        msg = leftover.decode('utf-8', errors='ignore').strip()
                        if msg:
                            print(f"\n{msg}")
                            print("> ", end="", flush=True)
                continue

            # kalau bukan download aktif, decode sebagai teks/command
            msg = data.decode('utf-8', errors='ignore').strip()
            
            # cek pesan khusus dari server untuk upload/download
            if msg == "READY_UPLOAD":
                upload_event.set()

            elif msg.startswith("READY_DOWNLOAD"):
                parts    = msg.split()
                filename = parts[1]
                filesize = int(parts[2])
                filepath = os.path.join(CLIENT_DIR, filename)

                download_state.update({
                    'active':   True,
                    'file':     open(filepath, 'wb'),
                    'filename': filename,
                    'expected': filesize,
                    'received': 0,
                })
                print(f"\n[Downloading '{filename}' ({filesize} bytes)...]")

            else:
                print(f"\n{msg}")
                print("> ", end="", flush=True)

        except Exception as e:
            print(f"\nError receiving data: {e}")
            sock.close()
            os._exit(1)

# fungsi untuk upload file ke server
def do_upload(sock: socket.socket, filename: str):
    if not os.path.exists(filename):
        print(f"[ERROR]'{filename}' tidak ditemukan.")
        return

    file_size = os.path.getsize(filename)

    # 1. kirim command upload ke server
    sock.sendall(f"/upload {filename} {file_size}\n".encode())

    # 2. tunggu server balas "READY_UPLOAD" sebelum mulai kirim file
    upload_event.wait()
    upload_event.clear()

    # 3. kirim file sebagai raw bytes
    print(f"Uploading '{filename}'...")
    with open(filename, 'rb') as f:
        while chunk := f.read(BUFFER_SIZE):
            sock.sendall(chunk)

    print("Upload selesai.")

# fungsi main
def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except ConnectionRefusedError:
        print("Gagal connect ke server.")
        sys.exit()

    print(f"--- Terhubung ke {HOST}:{PORT} ---")
    print("Commands: /list | /upload <file> | /download <file> | <broadcast pesan> | exit\n")

    # jalankan thread untuk menerima pesan dari server
    threading.Thread(target=receive_messages, args=(sock,), daemon=True).start()

    while True:
        try:
            user_input = input("> ").strip()
            if not user_input:
                continue

            if user_input.lower() == 'exit':
                print("Disconnecting...")
                break

            elif user_input.startswith('/upload'):
                parts = user_input.split()
                if len(parts) == 2:
                    do_upload(sock, parts[1])
                else:
                    print("Format salah. Gunakan: /upload <filename>")

            else:
                sock.sendall((user_input + '\n').encode())

        except KeyboardInterrupt:
            print("\nDisconnecting...")
            break

    sock.close()

if __name__ == '__main__':
    main()