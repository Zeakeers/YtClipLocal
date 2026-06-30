import os
import sys
import subprocess

def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    bat_path = os.path.join(project_dir, "clipyt.bat")
    
    # 1. Create clipyt.bat inside project directory
    print(f"Membuat file shortcut '{bat_path}'...")
    python_exe = sys.executable
    bot_py = os.path.join(project_dir, "bot.py")
    
    bat_content = f"""@echo off
"{python_exe}" "{bot_py}" %*
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    
    # 2. Add this project directory to User PATH environment variable
    print("Mendaftarkan perintah 'clipyt' ke system PATH agar bisa diakses dari mana saja...")
    try:
        # Use PowerShell to safely add path to User environment
        ps_cmd = f'[Environment]::SetEnvironmentVariable("PATH", [Environment]::GetEnvironmentVariable("PATH", "User") + ";{project_dir}", "User")'
        subprocess.run(["powershell", "-Command", ps_cmd], check=True)
        print("\n" + "=" * 60)
        print("PERINTAH 'clipyt' BERHASIL DIDAFTARKAN!")
        print("Silakan BUKA KEMBALI (RESTART) terminal/CMD/PowerShell Anda.")
        print("Setelah itu, ketik 'clipyt' di folder mana pun untuk menjalankan bot!")
        print("=" * 60)
    except Exception as e:
        print(f"\nGagal mendaftarkan PATH secara otomatis: {e}")
        print("Solusi Manual:")
        print("Tambahkan folder ini ke System Environment Variable PATH Anda:")
        print(project_dir)

if __name__ == "__main__":
    main()
