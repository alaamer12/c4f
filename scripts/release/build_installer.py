import os
import shutil
import subprocess

# Clean previous builds
if os.path.exists('dist'):
    shutil.rmtree('dist')
if os.path.exists('build'):
    shutil.rmtree('build')
if os.path.exists('installer'):
    shutil.rmtree('installer')

# Create directories
os.makedirs('installer', exist_ok=True)

# Build executable
print("Building executable with PyInstaller...")
subprocess.run(['pyinstaller', '--onefile', '--name', 'c4f', '--icon=icon.ico', 'c4f/cli.py'], check=True)

# Sign the executable
print("Signing the executable...")
subprocess.run([
    'signtool', 'sign',
    '/f', 'path_to_your_certificate.pfx',
    '/p', 'your_certificate_password',
    '/tr', 'http://timestamp.digicert.com',
    '/td', 'sha256',
    '/fd', 'sha256',
    '/d', 'C4F - Commit For Free',
    'dist/c4f.exe'
], check=True)

# Copy necessary files to dist folder
shutil.copy('../../README.md', 'dist/README.md')
shutil.copy('../../LICENSE', 'dist/LICENSE')

# Build installer
print("Building installer with Inno Setup...")
subprocess.run(['iscc', 'c4f_setup.iss'], check=True)

print("Build completed! Installer is in the 'installer' folder")
