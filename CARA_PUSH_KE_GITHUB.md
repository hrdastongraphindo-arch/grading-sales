# Panduan Mengunggah (Push) ke GitHub

Berikut adalah panduan langkah demi langkah untuk menyimpan project ini ke akun GitHub Anda.

---

### Langkah 1: Buat Repository Baru di Akun GitHub Anda
1. Buka [https://github.com/new](https://github.com/new) di browser Anda.
2. Isi **Repository name**, misalnya:
   `sales_grading_triwulan` atau `odoo16-sales-grading-triwulan`
3. Pilih **Private** (disarankan untuk sistem internal perusahaan) atau **Public**.
4. **PENTING**: **JANGAN** centang *"Add a README file"*, *"Add .gitignore"*, atau *"Choose a license"* (karena semua file ini sudah kita sediakan lengkap).
5. Klik tombol hijau **Create repository**.
6. Salin URL repository GitHub Anda, contohnya:
   `https://github.com/username-anda/sales_grading_triwulan.git`

---

### Langkah 2: Buka Terminal / PowerShell di Komputer Anda
Buka PowerShell atau Command Prompt, lalu arahkan ke folder project ini:

```powershell
cd "C:\Users\Aston Graphindo\.gemini\antigravity\scratch\sales_grading_triwulan_github"
```

---

### Langkah 3: Hubungkan ke Repository GitHub Anda dan Push

Jalankan 2 perintah berikut (ganti URL dengan URL repository yang Anda buat di Langkah 1):

```powershell
git remote add origin https://github.com/username-anda/sales_grading_triwulan.git
git push -u origin main
```

*(Jika diminta login oleh GitHub, masukkan kredensial akun GitHub Anda atau Personal Access Token)*.

---

### Alternatif: Upload Langsung via Web Browser (Tanpa Git CLI)
Jika Anda tidak ingin mengetik perintah Git, Anda juga dapat mengunggahnya langsung lewat web GitHub:
1. Ambil file arsip zip yang sudah disiapkan:
   `C:\Users\Aston Graphindo\.gemini\antigravity\scratch\grading-sales-triwulan\sales_grading_triwulan_github_ready.zip`
2. Ekstrak zip tersebut di komputer Anda.
3. Di halaman repository baru di GitHub, klik tombol **"uploading an existing file"**.
4. Drag & drop seluruh isi file hasil ekstrak ke halaman GitHub.
5. Klik **Commit changes**. Selesai!
