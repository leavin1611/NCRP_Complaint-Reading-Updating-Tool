@echo off
setlocal
cd /d "%~dp0"
TITLE NCRP Portable Launcher

:: --- CONFIGURATION ---
set "PYTHON_VER=3.11.5"
set "PYTHON_ZIP=python-%PYTHON_VER%-embed-amd64.zip"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/%PYTHON_ZIP%"
set "DIR_BIN=python_bin"
set "PIP_URL=https://bootstrap.pypa.io/get-pip.py"

:: --- STEP 1: CHECK FOR LOCAL PYTHON ---
IF EXIST "%DIR_BIN%\python.exe" (
    goto :START_APP
)

echo ========================================================
echo  FIRST RUN DETECTED: SETTING UP PORTABLE ENVIRONMENT
echo  (This depends on your internet speed. Please wait...)
echo ========================================================

:: --- STEP 2: DOWNLOAD PYTHON ---
if not exist "%PYTHON_ZIP%" (
    echo [1/5] Downloading Portable Python...
    curl -L -o "%PYTHON_ZIP%" "%PYTHON_URL%"
)

:: --- STEP 3: EXTRACT PYTHON ---
echo [2/5] Extracting Python...
if not exist "%DIR_BIN%" mkdir "%DIR_BIN%"
tar -xf "%PYTHON_ZIP%" -C "%DIR_BIN%"

:: --- STEP 4: CONFIGURE PYTHON (ENABLE PIP) ---
echo [3/5] Configuring environment...
:: We need to edit the ._pth file to allow importing external modules (like Flask)
:: This powershell command uncomments "import site" in the ._pth file
powershell -Command "(Get-Content '%DIR_BIN%\python*._pth') -replace '#import site', 'import site' | Set-Content '%DIR_BIN%\python311._pth'"

:: --- STEP 5: INSTALL PIP ---
echo [4/5] Installing Pip Package Manager...
curl -L -o get-pip.py "%PIP_URL%"
"%DIR_BIN%\python.exe" get-pip.py --no-warn-script-location
del get-pip.py

:: --- STEP 6: INSTALL DEPENDENCIES ---
echo [5/5] Installing Requirements (Flask, PDFPlumber)...
"%DIR_BIN%\python.exe" -m pip install -r requirements.txt --no-warn-script-location

:: Clean up zip to save space
del "%PYTHON_ZIP%"

echo.
echo ========================================================
echo         SETUP COMPLETE! STARTING APP...
echo ========================================================
echo.

:START_APP
echo [Running] Starting NCRP Tool...
echo.
:: Start Python in background
start /B "" "%DIR_BIN%\python.exe" solution.py

:: Wait for server to wake up
timeout /t 3 /nobreak >nul

:: Open Browser
start "" "index.html"

echo Application is running. Close this window to stop.
pause