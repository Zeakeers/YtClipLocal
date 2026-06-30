import os
import re

def format_timestamp(seconds):
    """Formats seconds to ASS style timestamp: H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs == 100:
        s += 1
        cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def strip_punctuation(text):
    """Remove all punctuation marks — titik, koma, tanda tanya, dll."""
    return re.sub(r'[^\w\s]', '', text)

def _build_ass_header(font_name="Cooper Black"):
    """ASS header with TikTok-style karaoke styling."""
    return f"""[Script Info]
Title: Viral Karaoke Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,{font_name},100,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,3,0,1,10,5,2,60,60,350,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def _build_karaoke_events(all_words, max_words_per_line=3):
    """Build ASS karaoke dialogue events from word list."""
    # Group words into lines
    lines = []
    current_line = []
    for i, w in enumerate(all_words):
        current_line.append(w)
        if len(current_line) == max_words_per_line or i == len(all_words) - 1:
            lines.append(current_line)
            current_line = []

    events = []
    for line in lines:
        if not line:
            continue
        line_start = line[0]['start']
        line_end = line[-1]['end']

        text_parts = []
        last_time = line_start

        for w in line:
            word_dur_cs = max(10, int(round((w['end'] - w['start']) * 100)))

            gap_cs = int(round((w['start'] - last_time) * 100))
            if gap_cs > 0:
                text_parts.append(f"{{\\kf{gap_cs}}}")

            text_parts.append(f"{{\\kf{word_dur_cs}}}{w['word']} ")
            last_time = w['end']

        ass_text = "".join(text_parts).strip()
        start_str = format_timestamp(line_start)
        end_str = format_timestamp(line_end)
        events.append(f"Dialogue: 0,{start_str},{end_str},Karaoke,,0,0,0,,{ass_text}")

    return events


def generate_ass_file_from_faster_whisper(words_list, output_path, font_name="Cooper Black"):
    """
    Generate ASS karaoke subtitle from faster-whisper word list.
    
    Args:
        words_list: list of dicts [{'word': str, 'start': float, 'end': float, 'probability': float}, ...]
        output_path: path to save .ass file
        font_name: font to use in subtitle
    """
    ass_header = _build_ass_header(font_name)

    # Clean words: uppercase, strip punctuation, filter low-confidence garbage
    all_words = []
    for w in words_list:
        cleaned = strip_punctuation(w['word'].strip())
        if not cleaned:
            continue
        # Skip very low confidence words (likely hallucination)
        prob = w.get('probability', 1.0)
        if prob < 0.3:
            continue
        all_words.append({
            'word': cleaned.upper(),
            'start': w['start'],
            'end': w['end'],
        })

    if not all_words:
        print("[WARNING] Tidak ada kata yang terdeteksi untuk subtitle.")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_header)
        return output_path

    events = _build_karaoke_events(all_words)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_header)
        f.write("\n".join(events))

    print(f"Generated Karaoke Subtitle: {output_path} ({len(events)} lines)")
    return output_path


def generate_ass_file(transcription_result, output_path, font_name="Cooper Black"):
    """
    Generate ASS from stable-whisper result (legacy fallback).
    """
    ass_header = _build_ass_header(font_name)

    all_words = []
    for segment in transcription_result.segments:
        if hasattr(segment, 'words') and segment.words:
            for w in segment.words:
                word_text = strip_punctuation(w.word.strip())
                if word_text:
                    all_words.append({
                        'word': word_text.upper(),
                        'start': w.start,
                        'end': w.end
                    })
        else:
            words = segment.text.strip().split()
            duration = segment.end - segment.start
            word_duration = duration / max(1, len(words))
            for i, w_text in enumerate(words):
                cleaned = strip_punctuation(w_text.strip())
                if cleaned:
                    all_words.append({
                        'word': cleaned.upper(),
                        'start': segment.start + i * word_duration,
                        'end': segment.start + (i + 1) * word_duration
                    })

    if not all_words:
        print("[WARNING] Tidak ada kata yang terdeteksi untuk subtitle.")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_header)
        return output_path

    events = _build_karaoke_events(all_words)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_header)
        f.write("\n".join(events))

    print(f"Generated Karaoke Subtitle: {output_path} ({len(events)} lines)")
    return output_path
