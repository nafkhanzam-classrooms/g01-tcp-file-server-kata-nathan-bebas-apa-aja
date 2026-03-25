 [![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/mRmkZGKe)
# Network Programming - Assignment G01

## Anggota Kelompok
| Nama           | NRP        | Kelas     |
| ---            | ---        | ----------|
|Nathanael Oliver Amadhika Yuswana|5025241109|D|
|Rennard Filbert Tanjaya|5025241122|D|

## Link Youtube (Unlisted)
Link ditaruh di bawah ini
```
https://youtu.be/hdirfTW6irw
```

## Penjelasan Program

### File `client.py`
- File ini merupakan program sisi pengguna yang dijalankan untuk terhubung ke server. Tugasnya menerima input dari user, mengirim command ke server, dan menampilkan response. Program ini punya 2 thread dimana satu untuk input user dan satu lagi berjalan di background untuk menerima pesan/file dari server kapan saja termasuk broadcast.

```py
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
```
- Bagian ini merupakan bagian awal dari kode client.py yang terdiri dari setup library yang dibutuhkan, alamat host dan posrt server, direktori client untuk download file, dan global state yang berfungsi sebagai jembatan komunikasi antara background thread dan main thread.

```py
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
```
- Fungsi `receive_meassages` ini berfungsi untuk menerima pesan yang dikirim oleh server. Ada 3 kemungkinan, yaitu lagi aktif download, terima sinyal "READY_UPLOAD", dan terima sinyal "READY_DOWNLOAD". Kalau lagi aktif download, maka semua data yang masuk dianggap bytes file bukan teks/command.

```py
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
```
- Fungsi `do_upload` ini adalah fungsi untuk menghandle sata client ingin mengupload sebuah file. Pertama, dia kirim command dan ukuran filenya. Lalu, tunggu sinyal dari server dan baru kirim raw bytesnya.

```py
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
```
- Ini adalah fungsi main dari kode ini. Fungsi ini yang akan membaca input dari user di terminal. Jika inputnya `/upload` maka akan ngejalankan funsgi upload yang sudah dibuat diatas. Jika printah lain maka langsung kirim ke server. Karena `/upload` perlu fungsi sendiri karena butuh handshake 2 langkah. Semua command lain (`/list`, `/download`, chat biasa) cukup dikirim sebagai teks.

### File `server-sync.py`

- FIle ini merupakan program dari sisi server yang paling sederhana diantara lainnya. Server hanya bisa melayani satu client dalam satu waktu. Tidak ada thread tambahan yang digunakan, semua diproses secara berurutan (synchronous). Client ke-2 yang mencoba connect harus menunggu sampai client pertama disconnect dulu baru bisa dilayani. Tidak ada fitur broadcast karena tidak pernah ada lebih dari 1 client aktif.

```py
import socket
import os

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 4096
SERVER_DIR = 'server_storage'

if not os.path.exists(SERVER_DIR):
    os.makedirs(SERVER_DIR)
```
- Bagian ini merupakan bagian awal dari kode server-sync.py yang terdiri dari setup library yang dibutuhkan, alamat host dan port server, dan direktori server untuk storage file yang diupload oleh client.


```py
def recv_line(sock: socket.socket) -> str:
    buf = b''
    while True:
        ch = sock.recv(1)
        if not ch or ch == b'\n':
            break
        buf += ch
    return buf.decode(errors='replace').strip()
```
- Fungsi `recv_line` ini merupakan fungsi untuk membaca satu baris teks hingga menemukan newline (\n). Byte setelahnya (mungkin awal command berikutnya) tidak ikut terbaca.

```py
def send_msg(sock: socket.socket, text: str):
    sock.sendall((text + '\n').encode())
```
- Fungsi `send_msg` ini merupakan fungsi untuk mengirim pesan ke client.

```py
def handle_list(conn: socket.socket):
    files = os.listdir(SERVER_DIR)
    if files:
        send_msg(conn, "Files di server:\n  " + "\n  ".join(files))
    else:
        send_msg(conn, "Tidak ada file di server.")
```
- Fungsi `handle_list` ini merupakan fungsi untuk menghandle perintah `/list` dari client. Program akan membuka direktori server lalu cek jika ada file ditemukan maka diprint, tapi jika tidak ada maka akan mengeluarkan output tidak ada file di server.

```py
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
```
- Funsgi `handle_upload` adalah fungsi yang menghandle perintah `/upload` dari client. Program akan kirim sinyal ke client jika sudah ready agar client mulai upload file beserta ukuran filenya. Looping akan berhenti ketika file yang diterima sudah sama dengan file_size yang dikirim.

```py
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
```
- Funsgi `handle_download` adalah fungsi yang menghandle perintah `/download` dari client. Program ini berkebalikan dengan fungsi upload. Program ini akan mengirimkan header dulu yang berisi nama file dan ukuran file baru stream bytenya. Client pakai ukuran itu untuk tahu kapan harus berhenti menerima.

```py
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
```
- Funsgi `handle_client` adalah pusat yang mengendalikan satu sesi client. Program akan terus looping sampai client kirim data kosong (tanda disconnect).

```py
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
```
- Ini adalah fungsi main dari kode ini. Di server-sync ini server hanya akan listen ke 1 client saja. Kalau ada client ke-2 yang coba connect saat client ke-1 masih aktif, dia masuk antrian sebentar tapi tidak akan dilayani sampai handle_client() selesai dan loop kembali ke server.accept().

### File `server-thread.py`

- FIle ini merupakan program dari sisi server yang yang bisa melayani banyak client sekaligus. Setiap client yang connect langsung dibuatkan thread tersendiri, jadi semua client bisa upload/download/chat secara paralel tanpa saling nunggu. Server ini melayani fitur broadcast dimana pesan dari satu client dikirim ke semua client lain yang sedang terhubung.

```py
import socket
import threading
import os

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 4096
SERVER_DIR = 'server_storage'

if not os.path.exists(SERVER_DIR):
    os.makedirs(SERVER_DIR)
```
- Bagian ini merupakan bagian awal dari kode server-sync.py yang terdiri dari setup library yang dibutuhkan, alamat host dan port server, dan direktori server untuk storage file yang diupload oleh client.

```py
clients = []
clients_lock = threading.Lock()
```
- Bagian ini merupakan shared state dimana clients merupakan list semua koneksi client yang aktif.

```py
def recv_line(sock: socket.socket) -> str:
    buf = b''
    while True:
        ch = sock.recv(1)
        if not ch or ch == b'\n':
            break
        buf += ch
    return buf.decode(errors='replace').strip()
```
- Fungsi `recv_line` ini merupakan fungsi untuk membaca satu baris teks hingga menemukan newline (\n). Byte setelahnya (mungkin awal command berikutnya) tidak ikut terbaca.

```py
def send_msg(sock: socket.socket, text: str):
    sock.sendall((text + '\n').encode())
```
- Fungsi `send_msg` ini merupakan fungsi untuk mengirim pesan ke client.

```py
def broadcast(message: str, exclude: socket.socket = None):
    with clients_lock:
        for conn, _ in clients:
            if conn is not exclude:
                try:
                    send_msg(conn, message)
                except OSError:
                    pass
```
- Fungsi `broadcast` ini merupakan fungsi untuk mengirim suatu pesan ke semua client yang sedang aktif kecuali si pengirim.

```py
def handle_list(conn: socket.socket):
    files = os.listdir(SERVER_DIR)
    if files:
        send_msg(conn, "Files di server:\n  " + "\n  ".join(files))
    else:
        send_msg(conn, "Tidak ada file di server.")
```
- Fungsi `handle_list` ini merupakan fungsi untuk menghandle perintah `/list` dari client. Program akan membuka direktori server lalu cek jika ada file ditemukan maka diprint, tapi jika tidak ada maka akan mengeluarkan output tidak ada file di server.

```py
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
        broadcast(f"[Server] {addr} mengupload file '{filename}'.", exclude=conn)
        print(f"[{addr}] Upload '{filename}' selesai.")
    else:
        send_msg(conn, f"[ERROR] Upload tidak lengkap ({received}/{file_size} bytes).")
```
- Funsgi `handle_upload` adalah fungsi yang menghandle perintah `/upload` dari client. Program akan kirim sinyal ke client jika sudah ready agar client mulai upload file beserta ukuran filenya. Looping akan berhenti ketika file yang diterima sudah sama dengan file_size yang dikirim.

```py
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
```
- Funsgi `handle_download` adalah fungsi yang menghandle perintah `/download` dari client. Program ini berkebalikan dengan fungsi upload. Program ini akan mengirimkan header dulu yang berisi nama file dan ukuran file baru stream bytenya. Client pakai ukuran itu untuk tahu kapan harus berhenti menerima.

```py
def handle_client(conn: socket.socket, addr: tuple):
    addr_str = f"{addr[0]}:{addr[1]}"
    print(f"[CONNECTED] Terhubung: {addr_str}")

    with clients_lock:
        clients.append((conn, addr_str))

    broadcast(f"[Server] {addr_str} telah bergabung.", exclude=conn)

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
                broadcast(f"[{addr_str}] {line}", exclude=conn)

    except (ConnectionResetError, BrokenPipeError, ConnectionError) as e:
        print(f"[ERROR] {addr_str}: {e}")
    finally:
        with clients_lock:
            clients[:] = [(c, n) for c, n in clients if c is not conn]
        conn.close()
        broadcast(f"[Server] {addr_str} telah disconnect.")
        print(f"[DISCONNECTED] Disconnect: {addr_str}")

```
- Funsgi `handle_client` adalah pusat yang mengendalikan satu sesi client. Program akan terus looping sampai client kirim data kosong (tanda disconnect).

```py
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[*] server-thread.py telah aktif di {HOST}:{PORT}")

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
            print(f"[*] Thread aktif: {threading.active_count() - 1}")
    except KeyboardInterrupt:
        print("\n[*] Server dimatikan.")
    finally:
        server.close()


if __name__ == '__main__':
    main()
```
- Ini adalah fungsi main dari server-thread. Di server-thread, setiap client yang connect akan langsung dibuatkan thread baru via `threading.Thread`, lalu thread itu langsung dijalankan dengan `t.start()`. Setelah thread di-start, main thread tidak nunggu thread tersebut selesai, dia langsung balik ke `server.accept()` untuk nunggu client berikutnya. Itulah kenapa server-thread bisa melayani banyak client sekaligus, karena setiap client punya thread-nya sendiri yang jalan secara paralel. `daemon=True` pada thread itu berarti semua thread client akan ikut mati otomatis saat program utama dimatikan, tanpa perlu di-stop satu per satu.

### File `server-select.py`

- File ini merupakan program sisi server yang dijalankan untuk menerima koneksi dari banyak client secara bersamaan. Tugas utamanya adalah mendengarkan permintaan masuk, memproses command atau pesan yang dikirim oleh client, dan mengirimkan _response_ atau meneruskan _message_ tersebut ke client lainnya. Server diprogram menggunakan modul select sehingga dapat memantau banyak socket sekaligus di dalam satu thread utama tanpa mengalami blocking.

```py
import socket
import select
import os

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 4096
SERVER_DIR = 'server_storage'

if not os.path.exists(SERVER_DIR):
    os.makedirs(SERVER_DIR)
```

- Bagian kode tersebut merupakan _import library_ yang akan digunakan pada program ini. Kemudian dilanjutkan dengan inisialisasi host, port, ukuran buffer dan nama direktori server yang akan digunakan.

```py
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(5)
```
- Bagian kode tersebut merupakan inisialisasi socket yang akan digunakan. Program ini menggunakan TCP Stream, serta memungkinkan server untuk menggunakan kembali port yang sama. Pada program server, jumlah client yang dapat terhubung dibatasi sebanyak 5 client.
=

```py
sockets_list = [server_socket]
clients = {}
upload_states = {}

print(f"Select-based Server berjalan pada {HOST}:{PORT}")
print(f"Menyimpan file di: ./{SERVER_DIR}/")
```
- Bagian kode tersebut merupakan inisialisasi _dictionary_ variabel yang akan digunakan.

```py
def broadcast(message, sender_socket):
    for client_socket in sockets_list:
        if client_socket != server_socket and client_socket != sender_socket:
            try:
                client_socket.send(message)
            except:
                client_socket.close()
                if client_socket in sockets_list:
                    sockets_list.remove(client_socket)
```

- Ini merupakan bagian _broadcast_, yaitu bagian dari kode yang berfungsi untuk mengirimkan _broadcast_ pada seluruh client. _Broadcast_ akan dikirimkan pada seluruh client kecuali pengirimnya atau server. Jika _broadcast_ gagal dikirim , server akan langsung menutup koneksi dan menghapus client tersebut dari _sockets_list_.

```py
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
                        
                        # Jika ada sisa data setelah file, proses sebagai pesan chat
                        if leftover:
                            msg = leftover.decode('utf-8', errors='ignore').strip()
                            if msg:
                                formatted_msg = f"[{clients[notified_socket]}]: {msg}\n".encode('utf-8')
                                broadcast(formatted_msg, notified_socket)
                    continue
                
                data = notified_socket.recv(BUFFER_SIZE)
                if not data:
                    raise ConnectionResetError
```

- Ini merupakan loop utama yang membuat server dapat berjalan terus-menerus. Fungsi `select.select` akan memblokir program sampai ada satu atau lebih socket di dalam _sockets_list_ yang siap dibaca. Hasilnya dimasukkan ke read_sockets. Looping for _notified_socket_ akan memproses satu per satu socket yang sedang aktif tersebut. Jika socket yang menyala adalah _server_socket_, server akan mencatat socket barunya ke sockets_list dan client.
- Bagian else pada potongan kode tersebut berfungsi untuk mengecek jika client yang terhubung sedang berada di dalam proses upload atau tidak. Jika sedang dalam proses upload, maka data yang masuk dibaca sebagai data biner.
- Pada potongan kode selanjutnya, yaitu pada if state selanjutnya, berfungsi untuk menangani data yang mungkin akan tertinggal atau tidak terkirim. Apabila terjadi hal seperti demikian, program akan mengirimkan ulang pesan yang belum terkirim.

```py
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
```
- Bagian ini merupakan bagian yang berisi perintah yang dapat dijalankan oleh client. Program menggunakan percabangan if-elif-else untuk menentukan tindakan berdasarkan kata pertama yang diketik user:
    - /list: Melihat isi direktori server.
    - /upload: Server mencatat status persiapan (ukuran dan nama file), lalu membalas READY_UPLOAD agar client melakukan _upload_/mengirim data biner.
    - /download: Server mencari file, jika ketemu, langsung mengirim data biner pada client untuk melakukan download.

```py
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
```

- Ini merupakan bagian yang akan menangani client jika terjadi error. Server akan langsung memutuskan koneksi dan menghapus client dari _notified_socket_

### File `server-poll.py`

- File ini merupakan program sisi server yang dijalankan untuk menerima dan melayani koneksi dari banyak client secara bersamaan. File ini sangat mirip dengan `server-select.py`. Perbedaannya, program ini menggunakan mekanisme select.poll() sebagai teknik I/O multiplexing-nya. poll adalah bentuk evolusi dari select yang dirancang untuk mengatasi beberapa kelemahan select, terutama saat server harus menangani koneksi dalam jumlah yang sangat besar.

```py
import socket
import select
import os

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 4096
SERVER_DIR = 'server_storage'

if not os.path.exists(SERVER_DIR):
    os.makedirs(SERVER_DIR)
```
- Bagian kode tersebut merupakan _import library_ yang akan digunakan pada program ini. Kemudian dilanjutkan dengan inisialisasi host, port, ukuran buffer dan nama direktori server yang akan digunakan.

```py
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(5)
```

- Bagian kode tersebut merupakan inisialisasi socket yang akan digunakan. Program ini menggunakan TCP Stream, serta memungkinkan server untuk menggunakan kembali port yang sama. Pada program server, jumlah client yang dapat terhubung dibatasi sebanyak 5 client.

```py
fd_to_socket = {server_socket.fileno(): server_socket}
clients = {}
upload_states = {}
```

- Bagian kode tersebut merupakan inisialisasi _dictionary_ variabel yang akan digunakan.

```py
poller = select.poll()
poller.register(server_socket, select.POLLIN)

print(f"Server berjalan pada {HOST}:{PORT}")
print(f"Menyimpan file di: ./{SERVER_DIR}/")
```

- Ini merupakan bagian inisialisasi poll yang akan digunakan, di mana server dan clientnya akan di-_input_ ke dalam `poller.register`.

```py
def broadcast(message, sender_socket):
    for client_socket in clients.keys():
        if client_socket != sender_socket:
            try:
                client_socket.send(message)
            except:
                clean_up(client_socket)
```

- Ini merupakan bagian _broadcast_, yaitu bagian dari kode yang berfungsi untuk mengirimkan _broadcast_ pada seluruh client. _Broadcast_ akan dikirimkan pada seluruh client kecuali pengirimnya atau server. Jika _broadcast_ gagal dikirim , server akan langsung menutup koneksi dan menghapus client tersebut dari _sockets_list_.

```py
def clean_up(sock):
    fd = sock.fileno()
    if fd in fd_to_socket:
        poller.unregister(fd)
        del fd_to_socket[fd]
    if sock in clients:
        print(f"Memutuskan koneksi dengan {clients[sock]}")
        del clients[sock]
    if sock in upload_states:
        upload_states[sock]['file'].close()
        del upload_states[sock]
    sock.close()
```

- Bagian `clean_up` berfungsi untuk memutuskan dan membersihkan koneksi dari client yang sudah tidak terhubung dengan server atau mengalami error.

```py
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
```

- Ini merupakan loop utama yang membuat server dapat berjalan terus-menerus. Fungsi `select.poll` akan memblokir program sampai ada satu atau lebih socket dengan pasangan flag dan client socket yang ready. Hasilnya dimasukkan ke read_sockets. Apabila socket mengalami _error_ atau melakukan _hang up_, maka koneksi akan diputuskan. Jika socket yang menyala adalah _server_socket_, server akan mencatat socket barunya ke sockets_list dan client.
- Bagian else pada potongan kode tersebut berfungsi untuk mengecek jika client yang terhubung sedang berada di dalam proses upload atau tidak. Jika sedang dalam proses upload, maka data yang masuk dibaca sebagai data biner.
- Pada potongan kode selanjutnya, yaitu pada if state selanjutnya, berfungsi untuk menangani data yang mungkin akan tertinggal atau tidak terkirim. Apabila terjadi hal seperti demikian, program akan mengirimkan ulang pesan yang belum terkirim.

```py
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
```

- Bagian ini merupakan bagian yang berisi perintah yang dapat dijalankan oleh client. Program menggunakan percabangan if-elif-else untuk menentukan tindakan berdasarkan kata pertama yang diketik user:
    - /list: Melihat isi direktori server.
    - /upload: Server mencatat status persiapan (ukuran dan nama file), lalu membalas READY_UPLOAD agar client melakukan _upload_/mengirim data biner.
    - /download: Server mencari file, jika ketemu, langsung mengirim data biner pada client untuk melakukan download.

```py
except Exception as e:
                    clean_up(notified_socket)
```

- Ini merupakan bagian yang akan menangani client jika terjadi error. Server akan langsung memutuskan koneksi dan menghapus client dari _notified_socket_


## Screenshot Hasil

### File `server-sync.py`
<img width="1471" height="748" alt="image" src="https://github.com/user-attachments/assets/3c74b15a-d528-42cc-8836-2e5df7d6eb0f" />


### File `server-thread.py`
<img width="1484" height="757" alt="image" src="https://github.com/user-attachments/assets/dd6663ef-52b8-45ac-9125-48d66d087ed5" />


### File `server-select.py`
<img width="717" height="346" alt="image" src="https://github.com/user-attachments/assets/fdfc5c8b-af8a-48df-b02d-0dfd7c80501b" />
<img width="734" height="422" alt="image" src="https://github.com/user-attachments/assets/27e6cef7-3d92-4f91-b449-9f397525ae48" />
<img width="716" height="412" alt="image" src="https://github.com/user-attachments/assets/afc09139-2d8e-44be-8bba-5d8b04fbf716" />


### File `server-poll.py`
<img width="733" height="360" alt="image" src="https://github.com/user-attachments/assets/2da92940-3609-4ac9-a9e3-34fceaae3b1b" />
<img width="733" height="419" alt="image" src="https://github.com/user-attachments/assets/8d369f91-7735-4b62-8866-811c8f17141f" />
<img width="836" height="467" alt="image" src="https://github.com/user-attachments/assets/06531822-bc70-416c-8838-8c3689e5aab0" />
<img width="730" height="415" alt="image" src="https://github.com/user-attachments/assets/38f50158-627a-4124-ad90-78acf614b93a" />


