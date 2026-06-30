import os
import re
import math
import json
import numpy as np
import yt_dlp
import static_ffmpeg
import subprocess
import cv2
import soundfile as sf

# Initialize FFmpeg paths
static_ffmpeg.add_paths()

# ---------------------------------------------------------------------------
# Checkpoint / Resume helpers
# ---------------------------------------------------------------------------
CHECKPOINT_FILE = "temp/checkpoint.json"
HISTORY_FILE = "output/clip_history.json"

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_checkpoint(data: dict):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def clear_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

# ---------------------------------------------------------------------------
# Clip History Helpers (untuk menghindari bagian yang sama di-clip ulang)
# ---------------------------------------------------------------------------
def load_history():
    """Load history of clipped segments per URL."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(history: dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)

def add_to_history(url, start_time, duration):
    """Save successfully rendered clip segment to avoid repeating it next time."""
    history = load_history()
    if url not in history:
        history[url] = []
    
    # Append the segment
    history[url].append({
        'start': start_time,
        'end': start_time + duration
    })
    save_history(history)
    print(f"[HISTORY] Menambahkan segmen {start_time//60}:{start_time%60:02d} - {(start_time+duration)//60}:{(start_time+duration)%60:02d} ke blacklist history.")

# ---------------------------------------------------------------------------
# Video info
# ---------------------------------------------------------------------------
def get_video_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

# ---------------------------------------------------------------------------
# Download with resume support — MERGED audio+video
# ---------------------------------------------------------------------------
def _file_exists_and_valid(path, min_bytes=10000):
    return os.path.exists(path) and os.path.getsize(path) > min_bytes

def download_video_merged(url, output_dir="temp"):
    os.makedirs(output_dir, exist_ok=True)
    checkpoint = load_checkpoint()

    merged_path = os.path.join(output_dir, "full_merged.mp4")
    wav_path = os.path.join(output_dir, "full_audio.wav")

    # ---- Download merged video+audio ----
    if checkpoint.get('merged_path') and _file_exists_and_valid(checkpoint['merged_path']):
        merged_path = checkpoint['merged_path']
        print("[RESUME] Video+audio sudah ada, skip download.")
    else:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(output_dir, 'full_merged.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        print("Downloading video+audio (best quality)...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(merged_path):
            for f in os.listdir(output_dir):
                if f.startswith('full_merged') and f.endswith('.mp4'):
                    merged_path = os.path.join(output_dir, f)
                    break

        checkpoint['merged_path'] = merged_path
        save_checkpoint(checkpoint)
        print(f"[OK] Video+audio downloaded: {merged_path}")

    # ---- Extract WAV for analysis ----
    if _file_exists_and_valid(wav_path, min_bytes=1000):
        print("[RESUME] WAV sudah ada, skip konversi.")
    else:
        print("Extracting audio to WAV for analysis...")
        cmd = [
            'ffmpeg', '-y',
            '-i', merged_path,
            '-vn',
            '-ac', '1',
            '-ar', '16000',
            wav_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        checkpoint['wav_path'] = wav_path
        save_checkpoint(checkpoint)
        print("[OK] WAV extracted.")

    return merged_path, wav_path

# ---------------------------------------------------------------------------
# Multi-segment viral analyzer (improved with history blacklist)
# ---------------------------------------------------------------------------
def analyze_viral_segments(url, wav_path, segment_duration=90, num_clips=3, min_gap=30):
    """
    Analyzes audio energy and speech density to select the best N segments.
    Filters out segments that overlap with previously clipped segments in history.
    """
    data, samplerate = sf.read(wav_path)

    # Compute energy per second
    downsample_factor = samplerate
    audio_energy = []
    speech_density = []

    for i in range(0, len(data), downsample_factor):
        chunk = data[i:i+downsample_factor]
        if len(chunk) == 0:
            break
        energy = np.sqrt(np.mean(chunk**2))
        audio_energy.append(energy)
        silence_threshold = 0.01
        voiced = np.sum(np.abs(chunk) > silence_threshold) / len(chunk)
        speech_density.append(voiced)

    audio_energy = np.array(audio_energy)
    speech_density = np.array(speech_density)
    total_seconds = len(audio_energy)

    if total_seconds <= segment_duration:
        print("Video terlalu pendek, hanya 1 clip yang bisa dibuat.")
        return [(0, 1.0)]

    start_margin = int(total_seconds * 0.05)
    end_margin = int(total_seconds * 0.95) - segment_duration

    if end_margin <= start_margin:
        start_margin = 0
        end_margin = max(1, total_seconds - segment_duration)

    avg_energy = np.mean(audio_energy)

    # Load history blacklist for this URL
    history = load_history()
    blacklist = history.get(url, [])
    if blacklist:
        print(f"[HISTORY] Ditemukan {len(blacklist)} segmen ter-blacklist dari sesi sebelumnya.")

    # Score every window position
    scores = []
    for start in range(start_margin, end_margin):
        # Check if this start time falls inside any blacklisted segment
        is_blacklisted = False
        for bl in blacklist:
            # Overlap condition:
            # bl['start'] to bl['end'] overlaps with start to start + segment_duration
            if not (start + segment_duration < bl['start'] or start > bl['end']):
                is_blacklisted = True
                break
        
        if is_blacklisted:
            continue

        window_e = audio_energy[start:start+segment_duration]
        window_s = speech_density[start:start+segment_duration]

        energy_mean = np.mean(window_e)
        energy_var = np.var(window_e)
        peak_ratio = np.sum(window_e > avg_energy * 1.3) / segment_duration
        speech_mean = np.mean(window_s)
        diffs = np.diff(window_e)
        spike_score = np.mean(np.abs(diffs[diffs > 0])) if np.any(diffs > 0) else 0

        score = (
            energy_mean  * 0.25 +
            energy_var   * 0.20 +
            peak_ratio   * 0.15 +
            speech_mean  * 0.25 +
            spike_score  * 0.15
        )
        scores.append((start, score))

    scores.sort(key=lambda x: x[1], reverse=True)

    # Pick top N non-overlapping
    selected = []
    for start, score in scores:
        if len(selected) >= num_clips:
            break
        overlap = False
        for sel_start, _ in selected:
            if abs(start - sel_start) < segment_duration + min_gap:
                overlap = True
                break
        if not overlap:
            selected.append((start, score))

    selected.sort(key=lambda x: x[0])

    print(f"\nDitemukan {len(selected)} segmen viral baru:")
    for i, (start, score) in enumerate(selected):
        end = start + segment_duration
        print(f"  Clip {i+1}: {start // 60}:{start % 60:02d} - {end // 60}:{end % 60:02d} (skor: {score:.4f})")

    return selected

# ---------------------------------------------------------------------------
# Clip video+audio together
# ---------------------------------------------------------------------------
def clip_video_and_audio(merged_path, wav_path, start_time, duration, output_dir="temp", clip_index=1):
    clipped_video = os.path.join(output_dir, f"clip_{clip_index}_video.mp4")
    clipped_audio = os.path.join(output_dir, f"clip_{clip_index}_audio.wav")

    # Skip if already done
    if _file_exists_and_valid(clipped_video) and _file_exists_and_valid(clipped_audio, min_bytes=1000):
        print(f"[RESUME] Clip {clip_index} sudah ada, skip clipping.")
        return clipped_video, clipped_audio

    print(f"Clipping clip_{clip_index} ({duration}s from {start_time}s)...")
    cmd_video = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-i', merged_path,
        '-t', str(duration),
        '-c:v', 'libx264',
        '-preset', 'slow',
        '-crf', '18',
        '-c:a', 'aac',
        '-b:a', '192k',
        clipped_video
    ]
    subprocess.run(cmd_video, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"Clipping audio clip_{clip_index} for transcription...")
    cmd_audio = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-i', wav_path,
        '-t', str(duration),
        clipped_audio
    ]
    subprocess.run(cmd_audio, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return clipped_video, clipped_audio
