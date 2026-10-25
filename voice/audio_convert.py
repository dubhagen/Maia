import os
import shutil
import wave

from common.log import logger

try:
    import pysilk
except ImportError:
    logger.debug("import pysilk failed, silk voice format will not be supported.")

try:
    from pydub import AudioSegment
    _pydub_available = True
except ImportError:
    logger.debug("import pydub failed, voice conversion features will not be supported.")
    AudioSegment = None
    _pydub_available = False

sil_supports = [8000, 12000, 16000, 24000, 32000, 44100, 48000]  


def find_closest_sil_supports(sample_rate):
    """Nearest sample rate that silk encoding supports."""
    if sample_rate in sil_supports:
        return sample_rate
    closest = 0
    mindiff = 9999999
    for rate in sil_supports:
        diff = abs(rate - sample_rate)
        if diff < mindiff:
            closest = rate
            mindiff = diff
    return closest


def get_pcm_from_wav(wav_path):
    """PCM frames from a wav file."""
    with wave.open(wav_path, "rb") as wav:
        return wav.readframes(wav.getnframes())


def any_to_mp3(any_path, mp3_path):
    """Convert an audio file to mp3."""
    if not _pydub_available:
        raise ImportError("pydub is required for audio conversion. Please install it with: pip install pydub")
    if any_path.endswith(".mp3"):
        shutil.copy2(any_path, mp3_path)
        return
    sil_wav_path = None
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        # pysilk decodes silk into wav only, so the audio needs a wav file of
        # its own: decoding onto any_path overwrote the caller's voice file and
        # then left nothing at mp3_path to read.
        sil_wav_path = os.path.splitext(any_path)[0] + ".silk.wav"
        sil_to_wav(any_path, sil_wav_path)
        any_path = sil_wav_path
    try:
        audio = AudioSegment.from_file(any_path)
        audio.export(mp3_path, format="mp3")
    finally:
        if sil_wav_path and os.path.exists(sil_wav_path):
            os.remove(sil_wav_path)


def any_to_wav(any_path, wav_path):
    """Convert an audio file to wav."""
    if not _pydub_available:
        raise ImportError("pydub is required for audio conversion. Please install it with: pip install pydub")
    if any_path.endswith(".wav"):
        shutil.copy2(any_path, wav_path)
        return
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        return sil_to_wav(any_path, wav_path)
    
    
    
    audio = AudioSegment.from_file(any_path, parameters=["-nostdin"])
    
    
    audio = audio.set_frame_rate(16000)
    audio = audio.set_channels(1)
    audio.export(wav_path, format="wav", codec='pcm_s16le')


def any_to_sil(any_path, sil_path):
    """Convert an audio file to silk."""
    if not _pydub_available:
        raise ImportError("pydub is required for audio conversion. Please install it with: pip install pydub")
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        shutil.copy2(any_path, sil_path)
        return 10000
    audio = AudioSegment.from_file(any_path)
    rate = find_closest_sil_supports(audio.frame_rate)
    # Convert to PCM_s16
    pcm_s16 = audio.set_sample_width(2)
    pcm_s16 = pcm_s16.set_frame_rate(rate)
    wav_data = pcm_s16.raw_data
    silk_data = pysilk.encode(wav_data, data_rate=rate, sample_rate=rate)
    with open(sil_path, "wb") as f:
        f.write(silk_data)
    return audio.duration_seconds * 1000


def any_to_amr(any_path, amr_path):
    """Convert an audio file to amr."""
    if not _pydub_available:
        raise ImportError("pydub is required for audio conversion. Please install it with: pip install pydub")
    if any_path.endswith(".amr"):
        shutil.copy2(any_path, amr_path)
        return
    if any_path.endswith(".sil") or any_path.endswith(".silk") or any_path.endswith(".slk"):
        raise NotImplementedError("Not support file type: {}".format(any_path))
    audio = AudioSegment.from_file(any_path)
    audio = audio.set_frame_rate(8000)  # only support 8000
    audio.export(amr_path, format="amr")
    return audio.duration_seconds * 1000


def sil_to_wav(silk_path, wav_path, rate: int = 24000):
    """Convert a silk file to wav."""
    wav_data = pysilk.decode_file(silk_path, to_wav=True, sample_rate=rate)
    with open(wav_path, "wb") as f:
        f.write(wav_data)


def split_audio(file_path, max_segment_length_ms=60000):
    """Split an audio file into segments."""
    if not _pydub_available:
        raise ImportError("pydub is required for audio conversion. Please install it with: pip install pydub")
    audio = AudioSegment.from_file(file_path)
    audio_length_ms = len(audio)
    if audio_length_ms <= max_segment_length_ms:
        return audio_length_ms, [file_path]
    segments = []
    for start_ms in range(0, audio_length_ms, max_segment_length_ms):
        end_ms = min(audio_length_ms, start_ms + max_segment_length_ms)
        segment = audio[start_ms:end_ms]
        segments.append(segment)
    file_prefix = file_path[: file_path.rindex(".")]
    format = file_path[file_path.rindex(".") + 1 :]
    files = []
    for i, segment in enumerate(segments):
        path = f"{file_prefix}_{i+1}" + f".{format}"
        segment.export(path, format=format)
        files.append(path)
    return audio_length_ms, files
