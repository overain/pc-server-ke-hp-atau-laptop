# PC Server ke HP atau Laptop

Ubah PC Windows menjadi server file lokal. Laptop atau HP di jaringan yang sama mengaksesnya lewat browser, misalnya `http://rain:8000`.

## Fitur
- Login multi-user (password di-hash scrypt, batas percobaan login)
- Folder pribadi per user + folder bersama
- Bagikan folder mana pun di PC lewat web (panel Admin), per user, opsi baca-saja
- Upload (seret-lepas), download file, unduh seluruh folder sebagai ZIP (streaming, tanpa batas ukuran), buat folder, ubah nama, hapus
- Tambah/hapus user dari web

## Mulai
1. Instal Python 3.10+ (centang "Add to PATH").
2. Jalankan `setup.bat` sebagai Administrator (buat venv, admin pertama, buka port 8000 di firewall jaringan privat).
3. Jalankan `jalankan.bat`, lalu buka alamat yang tercetak dari laptop/HP.
4. Login sebagai admin, klik ⚙ Admin untuk membagikan folder dan menambah user.

## Domain `rain`
- Di PC server: `nama-pc-rain.bat` (Administrator, lalu restart) agar nama PC jadi `rain`.
- Cadangan di laptop: `hosts-laptop.bat` (Administrator) lalu isi IP PC.
- Disarankan reservasi IP (DHCP) di router.

## Keamanan
Tanpa HTTPS, hanya untuk jaringan rumah/kantor tepercaya. Jangan buka port ke internet; untuk akses luar pakai Tailscale atau WireGuard. `users.json` dan `folders.json` tidak pernah ditampilkan lewat web.
