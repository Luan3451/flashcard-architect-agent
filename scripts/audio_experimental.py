"""Experimental offline ASR, TTS and conservative audio inspection.

Weights must already exist locally. No automatic installation/download.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave
from html import unescape
from html.parser import HTMLParser

SOUND = re.compile(r'\[sound:([^\]\r\n]+)\]')


def safe_media(root: Path, name: str) -> Path:
    if not name or name in {'.', '..'} or any(c in name for c in '/\\:\x00'):
        raise ValueError('Nome de mídia inseguro')
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Mídia fora da pasta local')
    return path


class AudioReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = []
        self.in_audio = False
    def handle_starttag(self, tag, attrs):
        if tag == 'audio':
            self.in_audio = True
        if tag == 'audio' or (tag == 'source' and self.in_audio):
            for key, value in attrs:
                if key == 'src' and value:
                    self.names.append(unescape(value))

    def handle_endtag(self, tag):
        if tag == 'audio':
            self.in_audio = False


def audio_references(html: str) -> list[str]:
    parser = AudioReferences()
    parser.feed(html)
    return sorted(set(SOUND.findall(html) + parser.names))


def inspect_audio(path: Path, timeout: int = 30) -> dict:
    """Bad means unreadable locally, not incompatibility on every Anki device."""
    if not path.exists():
        return {'status': 'missing'}
    if not path.is_file():
        return {'status': 'unknown', 'reason': 'não é arquivo'}
    if path.stat().st_size == 0:
        return {'status': 'empty'}
    if path.stat().st_size > 100 * 1024 * 1024:
        return {'status': 'unknown', 'reason': 'áudio maior que 100 MB'}
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        return {'status': 'unknown', 'reason': 'instale FFmpeg/ffprobe para validar'}
    try:
        probe = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                                '-show_streams', '-of', 'json', str(path.resolve())],
                               capture_output=True, text=True, timeout=timeout, check=False)
        if probe.returncode:
            return {'status': 'undecodable', 'reason': 'ffprobe não conseguiu ler o arquivo'}
        streams = json.loads(probe.stdout).get('streams', [])
        if not any(s.get('codec_type') == 'audio' for s in streams):
            return {'status': 'no_audio'}
        decode = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror',
                                 '-protocol_whitelist', 'file,pipe', '-i', str(path.resolve()),
                                 '-map', '0:a:0', '-f', 'null', '-'],
                                capture_output=True, timeout=timeout, check=False)
        return {'status': 'ok' if decode.returncode == 0 else 'undecodable',
                'reason': 'decodificação local com FFmpeg'}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'status': 'unknown', 'reason': 'falha ou timeout na verificação'}


class Speakable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.suppressed = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.suppressed += 1
        elif tag in {'br', 'p', 'div', 'li'}:
            self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.suppressed = max(0, self.suppressed - 1)
    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def speakable(html: str) -> str:
    parser = Speakable()
    parser.feed(SOUND.sub('', html))
    text = ' '.join(''.join(parser.parts).split())
    if '{{c' in text:
        raise ValueError('TTS de Cloze requer revisão manual para não revelar a resposta')
    if not text or len(text) > 5000:
        raise ValueError('Texto para voz vazio ou maior que 5000 caracteres')
    return text


def valid_wav(path: Path) -> None:
    with wave.open(str(path), 'rb') as wav:
        if wav.getnframes() <= 0 or wav.getframerate() <= 0:
            raise ValueError('WAV gerado vazio')
        expected = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
        if len(wav.readframes(wav.getnframes())) != expected:
            raise ValueError('WAV truncado')


def narrate(cards: list[dict], voice_path: Path, media_dir: Path, side: str = 'resposta', voice=None) -> dict[str, Path]:
    if not voice_path.is_file() or not Path(str(voice_path) + '.json').is_file():
        raise ValueError('Forneça uma voz Piper local .onnx e seu .onnx.json')
    texts = [(card, speakable(card[side])) for card in cards]
    if sum(len(text) for _, text in texts) > 500_000:
        raise ValueError('Lote de narração maior que 500 mil caracteres')
    if voice is None:
        try:
            from piper import PiperVoice
        except ImportError as exc:
            raise ValueError('Instale requirements-audio-tts.txt para Piper experimental') from exc
        voice = PiperVoice.load(str(voice_path))
    fingerprint = hashlib.sha256()
    for path in (voice_path, Path(str(voice_path) + '.json')):
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                fingerprint.update(chunk)
    media_dir.mkdir(parents=True, exist_ok=True)
    media = {}
    for card, text in texts:
        key = hashlib.sha256((fingerprint.hexdigest() + '\0' + text).encode()).hexdigest()[:20]
        name = f'fa_audio_{key}.wav'
        target = media_dir / name
        if target.is_file():
            valid_wav(target)
        else:
            with tempfile.TemporaryDirectory(dir=media_dir) as temp:
                wav_path = Path(temp) / 'voice.wav'
                with wave.open(str(wav_path), 'wb') as out:
                    voice.synthesize_wav(text, out)
                valid_wav(wav_path)
                wav_path.replace(target)
        card[side] += f'[sound:{name}]'
        card.setdefault('images', set()).add(name)  # existing package media registry
        media[name] = target
    return media


def transcribe(source: Path, model_dir: Path, output_dir: Path, device='cpu', factory=None, language=None) -> Path:
    if not source.is_file() or not model_dir.is_dir():
        raise ValueError('Áudio e diretório local de pesos ASR são obrigatórios')
    if output_dir.exists():
        raise ValueError('Pasta de transcrição já existe; escolha uma nova')
    if source.stat().st_size > 600 * 1024 * 1024:
        raise ValueError('Entrada maior que 600 MB')
    if factory is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ValueError('Instale requirements-audio-asr.txt para transcrição experimental') from exc
        factory = WhisperModel
    model = factory(str(model_dir), device=device,
                    compute_type='int8' if device == 'cpu' else 'int8_float16', local_files_only=True)
    segments, info = model.transcribe(str(source), vad_filter=True, beam_size=5, language=language)
    records = []
    for segment in segments:
        if not all(math.isfinite(v) for v in (segment.start, segment.end)) or segment.start < 0 or segment.end < segment.start:
            raise ValueError('Timestamp inválido na transcrição')
        if segment.text.strip():
            records.append({'start': segment.start, 'end': segment.end, 'text': segment.text.strip()})
    if not records:
        raise ValueError('Nenhuma fala reconhecida; nenhum arquivo criado')
    output_dir.mkdir(parents=True, exist_ok=False)
    source_hash = hashlib.sha256()
    with source.open('rb') as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b''):
            source_hash.update(chunk)
    manifest = {'experimental': True, 'source': source.name, 'source_sha256': source_hash.hexdigest(), 'language': info.language,
                'model': model_dir.name, 'segments': records, 'review_required': True}
    (output_dir / 'transcript.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    text_path = output_dir / 'transcript.txt'
    text_path.write_text('\n\n'.join(f"[Áudio {r['start']:.2f}s–{r['end']:.2f}s]\n{r['text']}" for r in records), encoding='utf-8')
    return text_path


def main():
    parser = argparse.ArgumentParser(description='ASR local EXPERIMENTAL: revise a transcrição antes de gerar cartões')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--language', help='Código do idioma, por exemplo pt; padrão: detectar')
    args = parser.parse_args()
    try:
        print(transcribe(args.input, args.model_dir, args.output_dir, args.device, language=args.language))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'Falha: {exc}\n')


if __name__ == '__main__':
    main()
