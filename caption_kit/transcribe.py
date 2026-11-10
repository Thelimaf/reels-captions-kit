"""
caption_kit/transcribe.py — Transcrição Palavra-por-Palavra (Word-Level Timestamps)

Suporta automaticamente (na ordem de preferência):
  1. CrisperWhisper (precisão cirúrgica de sílaba)
  2. faster-whisper (rápido e leve em GPU/CPU)
  3. openai-whisper (padrão)
"""
import json
import os
import subprocess
import tempfile


def transcribe_media(media_path: str, out_json_path: str = None, language: str = "pt"):
    """
    Transcreve um arquivo de áudio/vídeo (.wav, .mp3, .mp4) palavra por palavra
    e retorna (e opcionalmente salva em `out_json_path`) o dicionário:
      {"clip": nome, "duration": float, "text": str, "words": [{"word": str, "start": float, "end": float}]}
    """
    if not os.path.exists(media_path):
        raise FileNotFoundError(f"Arquivo de mídia não encontrado: {media_path}")

    dur_res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", media_path],
        capture_output=True, text=True,
    )
    dur = round(float(dur_res.stdout.strip() or 0.0), 3)

    with tempfile.NamedTemporaryFile(suffix=".16k.wav", delete=False) as tmp:
        wav_16k = tmp.name

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", media_path, "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", wav_16k, "-loglevel", "error"],
            check=True,
        )

        words = []
        full_text = ""

        # Tentativa 1: CrisperWhisper
        try:
            from crisperwhisper import CrisperWhisperModel
            model = CrisperWhisperModel("large", backend="transformers")
            res = model.transcribe(wav_16k, mode="intended", language=language, word_timestamps=True)
            full_text = (res.text or "").strip()
            words = [
                {"word": w.word.strip(), "start": round(float(w.start), 3), "end": round(float(w.end), 3)}
                for w in (res.words or []) if w.word.strip()
            ]
        except ImportError:
            # Tentativa 2: faster-whisper
            try:
                from faster_whisper import WhisperModel
                model = WhisperModel("large-v3", device="auto", compute_type="auto")
                segments, _ = model.transcribe(wav_16k, language=language, word_timestamps=True)
                seg_texts = []
                for seg in segments:
                    seg_texts.append(seg.text.strip())
                    for w in (seg.words or []):
                        if w.word.strip():
                            words.append({
                                "word": w.word.strip(),
                                "start": round(float(w.start), 3),
                                "end": round(float(w.end), 3),
                            })
                full_text = " ".join(seg_texts).strip()
            except ImportError:
                # Tentativa 3: openai-whisper
                import whisper
                model = whisper.load_model("base")
                res = model.transcribe(wav_16k, language=language, word_timestamps=True)
                full_text = (res.get("text") or "").strip()
                for seg in res.get("segments", []):
                    for w in seg.get("words", []):
                        if w.get("word", "").strip():
                            words.append({
                                "word": w["word"].strip(),
                                "start": round(float(w["start"]), 3),
                                "end": round(float(w["end"]), 3),
                            })
    finally:
        if os.path.exists(wav_16k):
            os.remove(wav_16k)

    payload = {
        "clip": os.path.basename(media_path),
        "duration": dur,
        "text": full_text,
        "words": words,
    }
    if out_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_json_path)), exist_ok=True)
        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload

