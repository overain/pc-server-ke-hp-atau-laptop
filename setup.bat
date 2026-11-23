@echo off
cd /d "%~dp0"
python -m venv .venv || (echo Python belum terpasang. Instal dari python.org & pause & exit /b)
.venv\Scripts\pip install -r requirements.txt
echo.
echo Buat user admin pertama:
set /p NAMA=Username: 
.venv\Scripts\python manage.py tambah %NAMA% --admin
echo Izinkan port 8000 di firewall (butuh Administrator):
netsh advfirewall firewall add rule name="PC Storage" dir=in action=allow protocol=TCP localport=8000 profile=private
pause
