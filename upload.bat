@echo off
setlocal enabledelayedexpansion

REM --- Set colors for console output ---
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "CYAN=[96m"
set "RESET=[0m"

echo %CYAN%=======================================
echo     Python Package Upload Utility
echo =======================================%RESET%

REM --- Check if pyproject.toml exists ---
if not exist pyproject.toml (
    echo %RED%Error: pyproject.toml not found in the current directory.%RESET%
    echo Please run this script from your project root directory.
    goto :eof
)

REM --- Extract version from pyproject.toml ---
set "VERSION="
for /f "tokens=1,* delims== " %%a in ('findstr /B /C:"version = " pyproject.toml') do (
    set "VERSION_RAW=%%b"
    set "VERSION=!VERSION_RAW:"=!"
)

if "!VERSION!"=="" (
    echo %RED%Error: Could not extract version from pyproject.toml.%RESET%
    goto :eof
)

echo %CYAN%Package version from pyproject.toml: %RESET%%VERSION%

REM --- Check if dist directory exists ---
if not exist dist (
    echo %YELLOW%Dist directory not found. Building package first...%RESET%
    call :build_package
) else (
    echo %CYAN%Checking dist directory...%RESET%
    dir /b dist > nul 2>&1 || (
        echo %YELLOW%Dist directory is empty. Building package...%RESET%
        call :build_package
    )
)

REM --- Verify dist files match version ---
set "VERSION_MATCH=0"
for %%f in (dist\*!VERSION!*.whl dist\*!VERSION!*.tar.gz) do (
    set "VERSION_MATCH=1"
)

if "!VERSION_MATCH!"=="0" (
    echo %YELLOW%Warning: No dist files matching version %VERSION% found.%RESET%
    choice /c YN /m "Rebuild package with current version?"
    if errorlevel 2 goto :eof
    if errorlevel 1 call :build_package
)

REM --- Ask which tool to use for upload ---
echo.
echo %CYAN%Select upload method:%RESET%
echo 1. Twine (recommended)
echo 2. Poetry
echo 3. Build and upload with Python (build + twine)
echo 4. Exit
choice /c 1234 /m "Select option"

if errorlevel 4 goto :eof
if errorlevel 3 (
    call :build_package
    call :twine_upload
    goto :eof
)
if errorlevel 2 (
    call :poetry_upload
    goto :eof
)
if errorlevel 1 (
    call :twine_upload
    goto :eof
)

goto :eof

:build_package
echo %CYAN%Building package...%RESET%
python -m build
if errorlevel 1 (
    echo %RED%Package build failed!%RESET%
    exit /b 1
)
echo %GREEN%Package built successfully!%RESET%
exit /b 0

:twine_upload
echo %CYAN%Preparing to upload with Twine...%RESET%

REM --- Check if Twine is installed ---
python -m pip show twine >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%Twine not found, installing...%RESET%
    python -m pip install twine
    if errorlevel 1 (
        echo %RED%Failed to install Twine%RESET%
        exit /b 1
    )
)

choice /c PR /m "Upload to [P]yPI or [R]test-PyPI?"
if errorlevel 2 (
    set "REPO=testpypi"
    echo %YELLOW%Uploading to Test PyPI...%RESET%
) else (
    set "REPO=pypi"
    echo %YELLOW%Uploading to PyPI...%RESET%
)

REM --- Ask for token or use stored token ---
set "USE_STORED_TOKEN="
if exist .pypitoken (
    choice /c YN /m "Use stored token?"
    if errorlevel 1 set "USE_STORED_TOKEN=1"
)

if defined USE_STORED_TOKEN (
    for /f "tokens=*" %%t in (.pypitoken) do set "PYPI_TOKEN=%%t"
) else (
    echo Enter your PyPI token:
    set /p "PYPI_TOKEN="
    
    choice /c YN /m "Save token for future use?"
    if errorlevel 1 (
        echo !PYPI_TOKEN!> .pypitoken
        echo %GREEN%Token saved to .pypitoken (make sure to add this file to .gitignore)%RESET%
    )
)

REM --- Upload with twine ---
if "!REPO!"=="testpypi" (
    python -m twine upload --repository-url https://test.pypi.org/legacy/ dist/* -u __token__ -p !PYPI_TOKEN! --verbose
) else (
    python -m twine upload dist/* -u __token__ -p !PYPI_TOKEN! --verbose
)

if errorlevel 1 (
    echo %RED%Upload failed!%RESET%
    exit /b 1
) else (
    echo %GREEN%Upload successful!%RESET%
    exit /b 0
)

:poetry_upload
echo %CYAN%Preparing to upload with Poetry...%RESET%

REM --- Check if Poetry is installed ---
poetry --version >nul 2>&1
if errorlevel 1 (
    echo %RED%Poetry not found!%RESET%
    echo Install Poetry first: https://python-poetry.org/docs/#installation
    exit /b 1
)

choice /c PR /m "Upload to [P]yPI or [R]test-PyPI?"
if errorlevel 2 (
    echo %YELLOW%Uploading to Test PyPI...%RESET%
    poetry config repositories.testpypi https://test.pypi.org/legacy/
    poetry publish --build --repository testpypi
) else (
    echo %YELLOW%Uploading to PyPI...%RESET%
    poetry publish --build
)

if errorlevel 1 (
    echo %RED%Upload failed!%RESET%
    exit /b 1
) else (
    echo %GREEN%Upload successful!%RESET%
    exit /b 0
)

endlocal

REM ===========================================================================
REM                            USAGE INSTRUCTIONS
REM ===========================================================================
REM 
REM HOW TO USE THIS SCRIPT:
REM ---------------------
REM 1. Run the script from your project root directory (where pyproject.toml is)
REM 2. The script will automatically extract the version from pyproject.toml
REM 3. It will check if distribution files exist and match the version
REM 4. You can choose your preferred upload method:
REM    - Twine: Most common option, recommended for most cases
REM    - Poetry: If you're using Poetry for your project
REM    - Build+Twine: Rebuilds package and then uploads with Twine
REM 
REM TOKEN MANAGEMENT:
REM ----------------
REM - You will be prompted to enter your PyPI token
REM - You can choose to save the token to a .pypitoken file for future use
REM - If a saved token exists, you'll be asked if you want to use it
REM - IMPORTANT: Add .pypitoken to your .gitignore to keep tokens secure
REM 
REM REPOSITORY SELECTION:
REM -------------------
REM - The script lets you choose between PyPI and Test PyPI
REM - Use Test PyPI for testing releases before publishing to production
REM 
REM COMMON ISSUES:
REM ------------
REM - If the script can't find your version: Make sure it's properly formatted 
REM   in pyproject.toml as 'version = "x.y.z"'
REM - If uploads fail: Check your token is valid and has appropriate permissions
REM - If builds fail: Run 'python -m build' separately to see detailed errors
REM 
REM EXAMPLES:
REM --------
REM - First-time use: Simply run 'upload.bat' and follow the prompts
REM - Quick PyPI upload with Twine: Run, select option 1, select P, enter token
REM - Testing on TestPyPI: Run, select option 1, select R, enter token
REM - Using Poetry: Run, select option 2, select P
REM 
REM For more information about Python packaging, visit:
REM https://packaging.python.org/en/latest/tutorials/packaging-projects/
REM ===========================================================================