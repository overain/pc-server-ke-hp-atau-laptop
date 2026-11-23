@echo off
:: Jalankan di PC server sebagai Administrator, lalu RESTART PC.
powershell -Command "Rename-Computer -NewName 'rain' -Force"
echo Nama PC jadi "rain". Restart PC, lalu buka http://rain:8000 dari laptop.
pause
