import os
import subprocess

def detect_video_dimensions(video_path):
    """Retrieves width and height of the video."""
    import cv2
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return width, height

def format_video_vertical(video_path, layout_type="crop", output_path="temp/vertical_layout.mp4"):
    """
    Reformats a widescreen 16:9 video to a 9:16 vertical video (1080x1920).
    Preserves audio throughout. Uses high-quality encoding.
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"[RESUME] Vertical video sudah ada: {output_path}, skip.")
        return output_path

    w, h = detect_video_dimensions(video_path)
    print(f"Original video dimension: {w}x{h}")

    target_w = 1080
    target_h = 1920

    if layout_type == "stack":
        filter_complex = (
            "[0:v]split=2[cam][game];"
            f"[cam]crop=w=in_h*0.8:h=in_h*0.8:x=0:y=0,scale={target_w}:{target_h//2}:flags=lanczos[top];"
            f"[game]crop=w=in_h*0.9:h=in_h:x=(in_w-in_h*0.9)/2:y=0,scale={target_w}:{target_h//2}:flags=lanczos[bottom];"
            "[top][bottom]vstack=inputs=2[v]"
        )
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-filter_complex', filter_complex,
            '-map', '[v]',
            '-map', '0:a',
            '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
            '-c:a', 'aac', '-b:a', '192k',
            output_path
        ]
    else:
        crop_w = int(h * 9 / 16)
        crop_x = (w - crop_w) // 2
        if crop_w > w:
            crop_w = w
            crop_x = 0
        vf = f"crop={crop_w}:{h}:{crop_x}:0,scale={target_w}:{target_h}:flags=lanczos"
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', vf,
            '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
            '-c:a', 'aac', '-b:a', '192k',
            output_path
        ]

    print(f"Applying layout filter ({layout_type}) — HD quality...")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"Vertical video created: {output_path}")
    else:
        print(f"[ERROR] Failed to create vertical video!")
    return output_path

def render_subtitles_to_video(video_path, ass_path, output_path="final_viral_clip.mp4", fonts_dir=None):
    """
    Burns ASS karaoke subtitles into the video.
    Preserves audio + HD quality.
    Supports custom fonts_dir for loading custom .ttf fonts.
    """
    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"[RESUME] Final video sudah ada: {output_path}, skip.")
        return output_path

    print("Rendering karaoke subtitles (HD)...")

    # Build the subtitle filter string
    escaped_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")

    # If we have a custom fonts directory, use fontsdir parameter
    if fonts_dir and os.path.isdir(fonts_dir):
        escaped_fonts_dir = fonts_dir.replace("\\", "/").replace(":", "\\:")
        vf_filter = f"ass='{escaped_ass_path}':fontsdir='{escaped_fonts_dir}'"
    else:
        vf_filter = f"ass='{escaped_ass_path}'"

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', vf_filter,
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        output_path
    ]

    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    # Fallback: try 'subtitles' filter if 'ass' filter fails
    if result.returncode != 0:
        print("  ass filter gagal, mencoba subtitles filter...")
        if fonts_dir and os.path.isdir(fonts_dir):
            vf_filter = f"subtitles='{escaped_ass_path}':fontsdir='{escaped_fonts_dir}'"
        else:
            vf_filter = f"subtitles='{escaped_ass_path}'"

        cmd[5] = vf_filter
        result2 = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if result2.returncode != 0:
            print(f"  [ERROR] Subtitle rendering gagal!\n  {result2.stderr[-300:]}")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"Final video output: {output_path}")
    else:
        print(f"[ERROR] Output file not created or too small!")

    return output_path
