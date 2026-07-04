"""
Translator module: translate transcription results to Bahasa Indonesia.
Uses Google Translate (free, no API key) via googletrans library.
Preserves word-level timestamps by re-mapping timing to translated words.
"""
import re
import time
from googletrans import Translator

_translator = None

def _get_translator():
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator

def translate_text(text, src='auto', dest='id'):
    """Translate a single text string to target language."""
    if not text or not text.strip():
        return text
    try:
        t = _get_translator()
        result = t.translate(text, src=src, dest=dest)
        return result.text
    except Exception as e:
        # Fallback: coba tanpa src (auto-detect by Google)
        try:
            t = _get_translator()
            result = t.translate(text, dest=dest)
            return result.text
        except:
            print(f"  [TRANSLATE WARNING] Gagal translate: {e}")
            return text

def translate_segments_with_timestamps(words_list, source_lang='auto'):
    """
    Translate word list to Indonesian.
    
    Args:
        words_list: list of dicts [{'word': str, 'start': float, 'end': float, 'probability': float}, ...]
        source_lang: kode bahasa sumber (misal 'jw', 'en', 'ko'). 'auto' = biarkan Google detect.
    
    Returns a new list of word dicts with translated text and re-mapped timestamps.
    """
    if not words_list:
        return words_list
    
    # Group words into segments based on pauses
    segments = []
    current_segment = []
    
    for i, w in enumerate(words_list):
        current_segment.append(w)
        
        is_last = (i == len(words_list) - 1)
        has_gap = False
        if not is_last:
            gap = words_list[i + 1]['start'] - w['end']
            has_gap = gap > 1.0
        
        if is_last or has_gap or len(current_segment) >= 15:
            segments.append(current_segment)
            current_segment = []
    
    print(f"  [TRANSLATE] Menerjemahkan {len(segments)} segmen ({source_lang} -> id)...")
    
    # Translate each segment and re-map timestamps
    translated_words = []
    fail_count = 0
    
    for seg_idx, segment in enumerate(segments):
        original_text = " ".join(w['word'] for w in segment)
        seg_start = segment[0]['start']
        seg_end = segment[-1]['end']
        seg_duration = seg_end - seg_start
        
        # Translate — always use 'auto' as src to let Google figure it out
        # This avoids "invalid source language" errors
        translated_text = translate_text(original_text, src='auto', dest='id')
        
        # Small delay every 5 segments to avoid rate limiting
        if seg_idx % 5 == 4:
            time.sleep(0.5)
        
        # Check if translation actually changed something
        if translated_text == original_text:
            fail_count += 1
        
        # Split translated text into words
        trans_words = translated_text.strip().split()
        if not trans_words:
            trans_words = original_text.strip().split()
        
        # Re-map timestamps evenly across translated words
        word_duration = seg_duration / len(trans_words) if len(trans_words) > 0 else seg_duration
        
        for j, tw in enumerate(trans_words):
            w_start = seg_start + j * word_duration
            w_end = w_start + word_duration
            if j == len(trans_words) - 1:
                w_end = seg_end
            
            translated_words.append({
                'word': tw,
                'start': w_start,
                'end': w_end,
                'probability': 0.95,
            })
    
    # Summary
    original_sample = " ".join(w['word'] for w in words_list[:8])
    translated_sample = " ".join(w['word'] for w in translated_words[:8])
    print(f"  [TRANSLATE] Asli    : {original_sample}...")
    print(f"  [TRANSLATE] Terjemah: {translated_sample}...")
    print(f"  [TRANSLATE] Total: {len(translated_words)} kata, {fail_count}/{len(segments)} segmen tidak berubah")
    
    return translated_words
