import os
import sys
import json
import shutil
import warnings
import static_ffmpeg

warnings.filterwarnings("ignore")
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Set path for ffmpeg
static_ffmpeg.add_paths()

from clipper import (
    get_video_info,
    download_video_merged,
    analyze_viral_segments,
    clip_video_and_audio,
    load_checkpoint,
    save_checkpoint,
    clear_checkpoint,
    _file_exists_and_valid,
    add_to_history,
)
from subtitle_generator import generate_ass_file_from_faster_whisper
from layout_processor import format_video_vertical, render_subtitles_to_video

# We define default locations
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")

def select_output_directory():
    """Opens a GUI File Explorer window to select the output directory."""
    print("\n[GUI] Membuka File Explorer untuk memilih folder penyimpanan...")
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        # Hide root Tkinter window
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True) # Bring dialogue to front
        
        # Open folder dialog
        folder_selected = filedialog.askdirectory(title="Pilih Folder untuk Menyimpan Video Hasil Clip")
        root.destroy()
        
        if folder_selected:
            # Normalize path
            folder_selected = os.path.abspath(folder_selected)
            print(f"Folder terpilih: {folder_selected}")
            return folder_selected
    except Exception as e:
        print(f"Gagal membuka dialog GUI (fallback ke folder output lokal): {e}")
    
    # Fallback to local output folder inside bot installation dir
    fallback = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(fallback, exist_ok=True)
    print(f"Menggunakan folder default: {fallback}")
    return fallback

def transcribe_with_faster_whisper(audio_path, model):
    # Force language='id' (Indonesian) to prevent incorrect auto-detection (like 'vi' or others)
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        best_of=5,
        word_timestamps=True,
        language='id',              # Force Indonesian language
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=300,
            speech_pad_ms=200,
        ),
        condition_on_previous_text=True,
        no_speech_threshold=0.5,
    )

    print(f"  Bahasa dipaksa: id (Indonesian)")

    all_words = []
    full_text_parts = []
    for segment in segments:
        full_text_parts.append(segment.text.strip())
        if segment.words:
            for w in segment.words:
                all_words.append({
                    'word': w.word.strip(),
                    'start': w.start,
                    'end': w.end,
                    'probability': w.probability,
                })

    full_text = " ".join(full_text_parts)
    avg_confidence = 0
    if all_words:
        avg_confidence = sum(w['probability'] for w in all_words) / len(all_words)

    print(f"  Total kata: {len(all_words)}")
    print(f"  Rata-rata confidence: {avg_confidence:.1%}")
    print(f"  Preview: {full_text[:120]}...")

    return all_words

def _clean_temp_for_new_video():
    """Hapus SELURUH isi folder temp saat ganti video baru."""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
        print("[CLEAN] Folder temp dihapus untuk video baru.")
    os.makedirs(TEMP_DIR, exist_ok=True)

def _clean_temp_keep_download():
    """Hapus clip/subtitle/vertical di temp, tapi PERTAHANKAN download mentah (full_merged.mp4, full_audio.wav)."""
    if not os.path.exists(TEMP_DIR):
        return
    for f in os.listdir(TEMP_DIR):
        # Pertahankan file download mentah
        if f.startswith("full_"):
            continue
        filepath = os.path.join(TEMP_DIR, f)
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
        except:
            pass
    print("[CLEAN] Cache clip/subtitle dihapus (download mentah tetap tersimpan).")

def run_clip_pipeline(url, layout="crop", duration=60, num_clips=3, output_dir=None):
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    if not output_dir:
        output_dir = select_output_directory()
    os.makedirs(output_dir, exist_ok=True)

    checkpoint = load_checkpoint()

    # ── AUTO-DETECT URL CHANGE ──
    # Jika URL baru berbeda dengan URL di checkpoint lama, reset semua
    old_url = checkpoint.get('url', '')
    if old_url and old_url != url:
        print(f"\n[!] URL baru terdeteksi (berbeda dari sesi sebelumnya).")
        print(f"    Lama : {checkpoint.get('title', old_url)}")
        print(f"    Baru : {url}")
        print(f"    Mereset semua data sesi lama...")
        _clean_temp_for_new_video()
        clear_checkpoint()
        checkpoint = {}

    # ── STEP 1 — Video Info ──
    print("\n[STEP 1/6] Mendapatkan detail video...")
    info = get_video_info(url)
    title = info.get('title', 'Unknown Title')
    total_dur = info.get('duration', 0)
    print(f"  Judul  : {title}")
    print(f"  Durasi : {total_dur} detik ({total_dur//60}m {total_dur%60}s)")

    checkpoint['url'] = url
    checkpoint['title'] = title
    checkpoint['output_dir'] = output_dir
    save_checkpoint(checkpoint)

    # ── STEP 2 — Download merged video+audio ──
    print("\n[STEP 2/6] Downloading video+audio (merged, best quality)...")
    merged_path, wav_path = download_video_merged(url, TEMP_DIR)

    # ── STEP 3 — Analyze viral segments ──
    print("\n[STEP 3/6] Menganalisis bagian viral...")

    if 'segments' in checkpoint and len(checkpoint['segments']) >= num_clips:
        segments = [(s['start'], s['score']) for s in checkpoint['segments']]
        print(f"[RESUME] Menggunakan {len(segments)} segmen dari checkpoint.")
    else:
        segments = analyze_viral_segments(url, wav_path, segment_duration=duration, num_clips=num_clips)
        checkpoint['segments'] = [{'start': s, 'score': sc} for s, sc in segments]
        save_checkpoint(checkpoint)

    # ── STEP 4 — Load faster-whisper large-v3 model ──
    print("\n[STEP 4/6] Loading faster-whisper large-v3 (akurasi tertinggi)...")
    from faster_whisper import WhisperModel
    model = WhisperModel("large-v3", device="cpu", compute_type="int8")
    print("  Model loaded.")

    # Fonts directory (inside the installation folder)
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

    # ── STEP 5-6 — Process each clip ──
    completed_clips = set(checkpoint.get('completed_clips', []))
    results = []

    for i, (start_time, score) in enumerate(segments):
        clip_num = i + 1

        final_path = os.path.join(output_dir, f"viral_clip_{clip_num}.mp4")

        if clip_num in completed_clips and os.path.exists(final_path) and os.path.getsize(final_path) > 10000:
            print(f"\n{'='*55}")
            print(f"  [RESUME] Clip {clip_num}/{len(segments)} sudah selesai, skip.")
            print(f"{'='*55}")
            results.append(final_path)
            continue
        
        # Jika file dihapus manual oleh user, hapus dari completed_clips
        if clip_num in completed_clips and not os.path.exists(final_path):
            completed_clips.discard(clip_num)
            checkpoint['completed_clips'] = list(completed_clips)
            save_checkpoint(checkpoint)
            print(f"\n[!] File clip {clip_num} tidak ditemukan, akan diproses ulang.")

        end_time = start_time + duration
        print(f"\n{'='*55}")
        print(f"  PROCESSING CLIP {clip_num}/{len(segments)}")
        print(f"  Waktu : {start_time//60}:{start_time%60:02d} - {end_time//60}:{end_time%60:02d}")
        print(f"  Skor  : {score:.4f}")
        print(f"{'='*55}")

        # 5a. Clip video+audio
        print(f"\n  [Clip {clip_num}] Memotong video+audio...")
        clipped_video, clipped_audio = clip_video_and_audio(
            merged_path, wav_path, start_time, duration, TEMP_DIR, clip_index=clip_num
        )

        # 5b. Transcribe with faster-whisper
        ass_path = os.path.join(TEMP_DIR, f"subtitle_{clip_num}.ass")
        if os.path.exists(ass_path) and os.path.getsize(ass_path) > 100:
            print(f"  [RESUME] Subtitle clip {clip_num} sudah ada, skip transkripsi.")
        else:
            print(f"  [Clip {clip_num}] Transkripsi dengan faster-whisper large-v3...")
            words = transcribe_with_faster_whisper(clipped_audio, model)
            generate_ass_file_from_faster_whisper(words, ass_path)

        # 5c. Vertical layout
        vertical_video = os.path.join(TEMP_DIR, f"vertical_{clip_num}.mp4")
        print(f"  [Clip {clip_num}] Membuat layout vertikal HD...")
        format_video_vertical(clipped_video, layout_type=layout, output_path=vertical_video)

        # 5d. Burn karaoke subtitles
        print(f"  [Clip {clip_num}] Rendering subtitle karaoke...")
        render_subtitles_to_video(vertical_video, ass_path, final_path, fonts_dir=fonts_dir)

        # Save to history to avoid repeating this segment in future runs for this URL
        add_to_history(url, start_time, duration)

        # Mark completed
        completed_clips.add(clip_num)
        checkpoint['completed_clips'] = list(completed_clips)
        save_checkpoint(checkpoint)

        results.append(final_path)
        print(f"  [Clip {clip_num}] SELESAI -> {final_path}")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("  SEMUA CLIP SELESAI DIPROSES!")
    print("=" * 60)
    print(f"  Total clip : {len(results)}")
    for i, path in enumerate(results):
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            size_mb = os.path.getsize(abs_path) / (1024 * 1024)
            print(f"  {i+1}. {abs_path}  ({size_mb:.1f} MB)")
        else:
            print(f"  {i+1}. {abs_path}  (FILE NOT FOUND)")
    print("=" * 60)
    print(f"\n  Semua file tersimpan di folder: {os.path.abspath(output_dir)}")

    return results

def main():
    print("=" * 60)
    print("   YOUTUBE AUTO-CLIPPER & KARAOKE RENDERER BOT")
    print("   Multi-clip | Resume | faster-whisper large-v3")
    print("=" * 60)

    checkpoint = load_checkpoint()
    if checkpoint.get('url'):
        prev_title = checkpoint.get('title', 'Unknown')
        completed = len(checkpoint.get('completed_clips', []))
        total = len(checkpoint.get('segments', []))
        print(f"\n[!] Sesi sebelumnya terdeteksi:")
        print(f"    Video  : {prev_title}")
        print(f"    Status : {completed}/{total} clip selesai")

    if len(sys.argv) > 1:
        url = sys.argv[1]
        layout = sys.argv[2] if len(sys.argv) > 2 else "crop"
        try:
            duration = int(sys.argv[3]) if len(sys.argv) > 3 else 60
        except ValueError:
            duration = 60
        try:
            num_clips = int(sys.argv[4]) if len(sys.argv) > 4 else 3
        except ValueError:
            num_clips = 3
        
        # Select output dir via GUI explorer
        output_dir = select_output_directory()
        run_clip_pipeline(url, layout, duration, num_clips, output_dir=output_dir)
    else:
        if checkpoint.get('url'):
            print("\nPilihan:")
            print("  y = Lanjutkan sesi sebelumnya (resume)")
            print("  n = Generate clip BARU dari video yang SAMA (tanpa download ulang)")
            print("  x = Mulai dari NOL dengan video BARU (hapus semua)")
            resume_choice = input("Pilihan (y/n/x, default y): ").strip().lower()
            
            if resume_choice == 'x':
                # Ganti video baru — hapus semua total
                clear_checkpoint()
                _clean_temp_for_new_video()
                print("Semua data dihapus total. Siap untuk video baru.\n")
            elif resume_choice == 'n':
                # Video sama, tapi mau generate segmen baru
                # Simpan info download mentah, hapus sisanya
                old_checkpoint = dict(checkpoint)
                clear_checkpoint()
                _clean_temp_keep_download()
                # Restore hanya download paths supaya tidak download ulang
                new_cp = {}
                if old_checkpoint.get('merged_path'):
                    new_cp['merged_path'] = old_checkpoint['merged_path']
                if old_checkpoint.get('wav_path'):
                    new_cp['wav_path'] = old_checkpoint['wav_path']
                save_checkpoint(new_cp)
                print("Segmen lama dihapus. Bot akan mencari segmen baru (tanpa download ulang).\n")
                # Langsung lanjut ke input URL dengan URL lama
                url = old_checkpoint['url']
                # Tanyakan setting baru
                print(f"Video: {old_checkpoint.get('title', url)}")
                print("\nPilih layout video vertikal:")
                print("  1. Crop Center (Potong tengah 9:16) - Default")
                print("  2. Stack (Atas: Facecam, Bawah: Gameplay)")
                choice = input("Pilihan (1/2, default 1): ").strip()
                layout = "stack" if choice == "2" else "crop"
                duration_input = input("Durasi tiap klip (detik, default 60, maks 90): ").strip()
                try:
                    duration = int(duration_input)
                    if duration <= 0 or duration > 90:
                        duration = 60
                except ValueError:
                    duration = 60
                clips_input = input("Jumlah clip (default 3, maks 5): ").strip()
                try:
                    num_clips = int(clips_input)
                    if num_clips <= 0 or num_clips > 5:
                        num_clips = 3
                except ValueError:
                    num_clips = 3
                output_dir = select_output_directory()
                run_clip_pipeline(url, layout, duration, num_clips, output_dir=output_dir)
                return
            else:
                url = checkpoint['url']
                layout = checkpoint.get('layout', 'crop')
                duration = checkpoint.get('duration', 60)
                num_clips = checkpoint.get('num_clips', 3)
                output_dir = checkpoint.get('output_dir')
                print(f"Melanjutkan proses: {checkpoint.get('title', url)}\n")
                run_clip_pipeline(url, layout, duration, num_clips, output_dir=output_dir)
                return

        url = input("\nMasukkan link YouTube: ").strip()
        if not url:
            print("Link tidak boleh kosong!")
            return

        print("\nPilih layout video vertikal:")
        print("  1. Crop Center (Potong tengah 9:16) - Default")
        print("  2. Stack (Atas: Facecam, Bawah: Gameplay)")
        choice = input("Pilihan (1/2, default 1): ").strip()
        layout = "stack" if choice == "2" else "crop"

        duration_input = input("Durasi tiap klip (detik, default 60, maks 90): ").strip()
        try:
            duration = int(duration_input)
            if duration <= 0 or duration > 90:
                duration = 60
        except ValueError:
            duration = 60

        clips_input = input("Jumlah clip (default 3, maks 5): ").strip()
        try:
            num_clips = int(clips_input)
            if num_clips <= 0 or num_clips > 5:
                num_clips = 3
        except ValueError:
            num_clips = 3

        # Select output folder via GUI
        output_dir = select_output_directory()

        checkpoint['layout'] = layout
        checkpoint['duration'] = duration
        checkpoint['num_clips'] = num_clips
        checkpoint['output_dir'] = output_dir
        save_checkpoint(checkpoint)

        run_clip_pipeline(url, layout, duration, num_clips, output_dir=output_dir)

if __name__ == "__main__":
    main()
