import getpass, sys, auth

def main():
    a = sys.argv[1:]
    if not a:
        print("Pakai:\n  python manage.py folder tambah <nama> <path> [--user a,b|*] [--baca-saja]\n  python manage.py folder hapus|daftar\n  python manage.py tambah <nama> [--admin]\n  python manage.py hapus <nama>\n  python manage.py daftar"); return
    if a[0] == "tambah" and len(a) >= 2:
        p = getpass.getpass("Password: ")
        if len(p) < 6: print("Minimal 6 karakter."); return
        if p != getpass.getpass("Ulangi : "): print("Tidak sama."); return
        auth.add_user(a[1], p, "--admin" in a); print("User", a[1], "disimpan.")
    elif a[0] == "hapus" and len(a) >= 2:
        auth.delete_user(a[1]); print("Dihapus.")
    elif a[0] == "folder" and len(a) >= 2:
        import os
        if a[1] == "tambah" and len(a) >= 4:
            p = a[3]
            if not os.path.isdir(p): print("Folder tidak ditemukan:", p); return
            us = ["admin"]
            if "--user" in a: us = a[a.index("--user") + 1].split(",")
            auth.add_folder(a[2], p, us, "--baca-saja" in a)
            print("Folder", a[2], "->", p, "| akses:", ",".join(us), "| baca-saja" if "--baca-saja" in a else "| tulis")
        elif a[1] == "hapus" and len(a) >= 3: auth.del_folder(a[2]); print("Dihapus dari daftar (file asli aman).")
        elif a[1] == "daftar":
            for k, v in auth.folders().items(): print(k, v)
        else: print("Pakai: folder tambah <nama> <path> [--user a,b | --user *] [--baca-saja]")
    elif a[0] == "daftar":
        for k, v in auth.list_users().items(): print(k, "(admin)" if v else "")
    else:
        print("Perintah tidak dikenal.")
main()
