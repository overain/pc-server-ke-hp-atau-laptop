@echo off
:: Cadangan jika http://rain:8000 tidak terbuka di laptop. Jalankan di LAPTOP sebagai Administrator.
set /p IP=Masukkan IP PC server (mis. 192.168.1.10): 
echo %IP% rain>> %SystemRoot%\System32\drivers\etc\hosts
echo Selesai. Buka http://rain:8000
pause
