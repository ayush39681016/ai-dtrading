import subprocess
import sys

def install():
    print("Installing packages...")
    process = subprocess.Popen(
        [sys.executable, "-m", "pip", "install", "pybit", "python-dotenv", "--no-cache-dir"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    for line in iter(process.stdout.readline, ''):
        print(line, end='')
    process.stdout.close()
    return_code = process.wait()
    print(f"Install finished with exit code {return_code}")

if __name__ == "__main__":
    install()
