import subprocess
import sys
import os

def install_package(package):
    print(f"Installing {package}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def main():
    print("=" * 60)
    # Print welcome
    print("      YOUTUBE AUTO-CLIPPER DEPENDENCY INSTALLER")
    print("=" * 60)
    
    # List of required packages
    requirements = [
        "numpy==1.23.5", # stable for scientific libs on py3.10
        "yt-dlp",
        "stable-whisper",
        "opencv-python",
        "soundfile",
        "static-ffmpeg",
        "faster-whisper",
        "ctranslate2",
        "onnxruntime"
    ]
    
    # Upgrade pip first
    try:
        print("Upgrading pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    except Exception as e:
        print(f"Warning upgrading pip: {e}")
        
    # Install each requirements
    for req in requirements:
        try:
            install_package(req)
        except Exception as e:
            print(f"Error installing {req}: {e}")
            
    # Initialize static-ffmpeg to download the binaries
    try:
        print("\nConfiguring FFmpeg binaries...")
        import static_ffmpeg
        static_ffmpeg.add_paths()
        # Test ffmpeg call
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[OK] FFmpeg configured successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to configure FFmpeg: {e}")
        
    print("\n" + "=" * 60)
    print("  INSTALASI SELESAI!")
    print("  Sekarang Anda bisa menjalankan bot dengan perintah:")
    print("  python bot.py")
    print("=" * 60)

if __name__ == "__main__":
    main()
