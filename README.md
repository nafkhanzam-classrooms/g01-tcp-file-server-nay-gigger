[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/mRmkZGKe)
# Network Programming - Assignment G01

## Anggota Kelompok
| Nama                          | NRP        | Kelas |
| ---                           | ---        | ---   |
| Muhammad Quthbi Danish Abqori | 5025241036 | C     |
| Muhammad Zaky Zein            | 5025241148 | C     |

## Link Youtube (Unlisted)
Link ditaruh di bawah ini
```

```

## Penjelasan Program

### A. Deskripsi Umum
Aplikasi ini adalah program berbasis *Client-Server* menggunakan protokol *TCP Socket* pada Python. Program ini memungkinkan banyak pengguna (klien) untuk terhubung ke satu server pusat guna melakukan pertukaran pesan teks secara *real-time* (*chatting*) dan mentransfer file (*upload* & *download*).

### B. Struktur File & Komponen Utama
#### 1. `utils.py`
File ini berisi kelas `TCPFileServer` yang menangani logika inti dan protokol komunikasi untuk sisi server. Tujuan dibuatnya file ini adalah untuk menjaga kerapian dan mengnhindari repitisi kode (prinsip *DRY* - *Don't Repeat Yourself*). Berikut merupakan penjelasan masing-masing fungsi:

- `__init__(self, ...)`: Menginisialisasi alamat server (IP dan *port*) serta menyiapkan direktori/folder (`server_files` dan `client_files`) untuk menyimpan file. Jika folder tidak ditemukan, maka ia akan otomatis membuat folder tersebut.
- `send_message(self, sock, msg_var)`: Mengirimkan pesan berisi data *dictionary* Python ke suatu *socket* tujuan. Pesan tersebut mula-mula di-*encode* ke bentuk JSON *string* dan *bytes*. Kemudian, agar batas pesan dapat diketahui oleh penerima, ia menyisipkan 4-byte *header* di awal (*prefixed*) menggunakan `struct.pack` guna memberitahu total ukuran tubuh pesannya.
- `recv_exact(self, sock, n)`: Membaca secara presisi sebesar `n` byte dari aliran data *socket*. Hal ini berguna untuk menangani jaringan paket yang terpotong-potong. Fungsi ini akan melakukan iterasi terus menerus (`while` loop) mengambil blok data yang datang hingga buffer data terkumpul sejumlah besaran `n` yang ditargetkan.
- `recv_message(self, sock)`: Berpasangan dengan `send_message()`, fungsinya yaitu untuk menerima dan merakit kembali format pesan JSON. Mula-mula membaca porsi *header* 4 byte terlebih dulu menggunakan `recv_exact()` untuk mendeteksi seberapa besar total paket yang harus dibaca, membaca sisa isi aliran datanya sampai selesai, dan mengembalikan ekstrak datanya menjadi wujud asli *dictionary* Python.
- `_broadcast(self, sender_sock, clients_list, message_dict)`: Menjalankan mekanisme penyebaran pesan tunggal ke seluruh pendengar di dalam *array* `clients_list`, dan dengan sengaja memfilter `sender_sock` agar sang pengait pesan asli tidak mendapatkan *echo* omongannya kembali.
- `handle_client_message(self, sock, msg, clients_list)`: Bertindak sebagai inti pilar layanan server untuk merespon perintah-perintah yang ada. Algoritma ini membedah *property* pesan (`msg_type`) dan berlakon semestinya, seperti mengirim daftar isi `server_files`, menumpahkan isi file ke sistem *stream* untuk menunaikan `download`, menulis file ke `server_files` guna merespon `upload`, dan menyebarkan log pesan interaktif menggunakan `_broadcast()`.

#### 2. `client.py`
Program ini akan dijalankan oleh klien (*endpoint*). Ia akan terhubung ke server dan mengirimkan pesan secara *broadcast* dan menjalankan perintah-perintah yang ada. Program ini menggunakan fitur *threading* untuk memungkinkan klien menerima dan mengirim pesan secara bersamaan tanpa membuat program menjadi *freeze*.
```py
threading.Thread(target=recv_loop, args=(sock, server), daemon=True).start()
```

#### 3. Server Implementations
Terdapat empat versi dari server yang dibuat, yaitu `server-sync.py`, `server-thread.py`, `server-select.py`, dan `server-poll.py`. Keempatnya menggunakan logika inti dari `utils.py`, namun memiliki cara kerja yang berbeda.

### C. Perbandingan Arsitektur
Walaupun keempatnya menggunakan logika inti dari `utils.py`, masing-masing server punya cara kerja yang berbeda. Berikut adalah penjelasannya.

#### 1. `server-sync.py`
Server ini berjalan secara *blocking* yang artinya dia hanya bisa melayani satu *client* dalam satu waktu karena server harus menunggu satu proses selesai sebelum mulai proses selanjutnya.

Perhatikan dua *netsted loop* `while` berikut:
```py
while True: # OUTER LOOP: Menunggu koneksi baru
        try:
            # Server akan berhenti hingga ada klien yang terhubung
            client_sock, addr = server_sock.accept() 
            clients = [client_sock]
            
            while True: # INNER LOOP: Berkomunikasi dengan klien yang terhubung
                # Server akan berhenti hingga ada pesan dari klien
                msg = recv_message(client_sock) 
                if not msg:
                    break # Berhenti hanya ketika klien memutuskan koneksi
                handle_client_message(client_sock, msg, clients)
```
Misalnya saja Klien A terhubung, server akan masuk melewati `accept()` dan masuk ke *inner loop*. Server akan terus berada di *inner loop* dan mendengarkan Klien A hingga dia memutuskan koneksi. Jika ada Klien B yang berjalan di waktu yang sama, akan muncul `Connected to server 127.0.0.1:8080` di terminal Klien B. Hal ini disebabkan karena OS secara otomatis menerima koneksi TCP dan menempatkan Klien B dalam "ruang tunggu" (`server_sock.listen(5)`). Meski begitu, Klien B tetap akan terblokir di `accept()` karena server masih terjebak di *inner loop* hingga Klien A memutuskan koneksi. 

Akibatnya adalah ketika Klien A mengirim pesan *broadcast*, dia akan berbicara pada ruangan kosong karena tidak ada klien lain yang bisa terhubung ke server dalam waktu yang sama. Sedangkan jika Klien B mengirim pesan, pesan itu akan tersalurkan ke buffer RAM server. Begitu Klien A memutuskan koneksi, server akan keluar dari *inner loop* dan masuk ke *outer loop* lagi dan mengenai `accept()`. Saat itulah server akan menangani Klien B dan memproses pesan yang dikirim Klien B sebelumnya.

#### 2. `server-thread.py`
Server ini bekerja dengan cara asinkronus sehingga dapat menangani banyak klien dalam waktu yang bersamaaan. Server ini menggunakan *thread* untuk menangani setiap klien yang terhubung. Berbeda dengan `server-sync.py` sebelumnya, server ini tidak akan memblokir klient yang terhubung karena begitu ia mengenai `accept()` ia akan membuat *thread* baru untuk menangani klien tersebut dan langsung kembali ke `accept()` untuk menunggu klien berikutnya. Hal ini membuat server dapat menangani banyak klien dalam waktu yang bersamaan dan efektif untuk berkomunikasi antar klien menggunakan *broadcast*.

```py
while True:
        try:
            client_sock, addr = server_sock.accept() # Server menerima klien baru
            threading.Thread(target=client_thread, args=(client_sock, addr, server), daemon=True).start() # Server akan membuat thread baru untuk menangani klien tersebut

            # Server kembali loop ke atas untuk menerima klien berikutnya
```

#### 3. `server-select.py`

#### 4. `server-poll.py`

### D. Fitur & Perintah Klien
* `/list` - Meminta server mengirimkan daftar file yang ada di folder `server_files`
* `/upload <filename>` - Mengirimkan file yang diminta ke server
* `/download <filename>` - Meminta Server mengirimkan byte-stream file untuk disimpan ke folder `client_files`
* `<message>` - Mengirimkan pesan ke server
* `/quit` - Memutuskan koneksi dari server

## Screenshot Hasil

#### 1. `server-sync.py`


#### 2. `server-thread.py`

#### 3. `server-select.py`

#### 4. `server-poll.py`
