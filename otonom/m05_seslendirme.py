"""MODÜL 5 — Seslendirme + otomatik altyazı zamanlaması.

Ana ses: Microsoft Edge TTS (ücretsiz, çok doğal). Edge engellenir/sınırlanırsa iş durmaz:
çevrimdışı, ücretsiz Piper Türkçe sesine geçilir (model ilk kullanımda bir kez indirilir).
"""
from __future__ import annotations

import asyncio
import json
import os
import ssl
import subprocess
import time
from pathlib import Path

from .ayarlar import Ayarlar, log

TIK = 10_000_000  # edge-tts zaman birimi: 100 ns


def sure(yol: Path) -> float:
    cikti = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(yol)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(cikti)


def tonlama(sira: int, toplam: int, metin: str, temel_hiz: str = "+5%") -> tuple[str, str]:
    """Doğal ve canlı anlatım: kanca enerjik, sorular hafif yüksek perdeden, kapanış sakin;
    aradaki cümlelerde küçük hız/perde dalgalanması (tekdüze robot sesi olmasın). Döner: (hız, perde)."""
    try:
        hiz = int(temel_hiz.strip().rstrip("%"))
    except ValueError:
        hiz = 5
    perde = 0
    if sira == 0:
        hiz, perde = hiz + 5, 2
    elif sira >= toplam - 1:
        hiz, perde = hiz - 4, -1
    else:
        hiz += (-2, 1, 3, 0)[sira % 4]
    if metin.rstrip().endswith("?"):
        perde += 3
    elif metin.rstrip().endswith("!"):
        hiz, perde = hiz + 2, perde + 1
    return f"{hiz:+d}%", f"{perde:+d}Hz"


async def _seslendir(metin: str, yol: Path, ses: str, hiz: str, perde: str = "+0Hz") -> list[tuple[float, float, str]]:
    import aiohttp
    import edge_tts

    ek: dict = {}
    # Kurumsal proxy / özel sertifika ortamları için (GitHub Actions'ta gerekmez)
    if os.environ.get("SSL_CERT_FILE"):
        ek["connector"] = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"]))
    if os.environ.get("HTTPS_PROXY"):
        ek["proxy"] = os.environ["HTTPS_PROXY"]
    iletisim = edge_tts.Communicate(metin, ses, rate=hiz, pitch=perde, boundary="WordBoundary", **ek)
    kelimeler = []
    with yol.open("wb") as f:
        async for parca in iletisim.stream():
            if parca["type"] == "audio":
                f.write(parca["data"])
            elif parca["type"] == "WordBoundary":
                bas = parca["offset"] / TIK
                kelimeler.append((bas, bas + parca["duration"] / TIK, parca["text"]))
    return kelimeler


def _sessiz(yol: Path, saniye: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", f"{saniye:.2f}", "-q:a", "9", str(yol)], check=True)


# Çevrimdışı yedek sesler (dil -> HuggingFace rhasspy/piper-voices yolu)
PIPER_SESLERI = {
    "tr": "tr/tr_TR/dfki/medium/tr_TR-dfki-medium",
    "en": "en/en_US/lessac/medium/en_US-lessac-medium",
    "de": "de/de_DE/thorsten/medium/de_DE-thorsten-medium",
    "es": "es/es_ES/davefx/medium/es_ES-davefx-medium",
    "fr": "fr/fr_FR/siwis/medium/fr_FR-siwis-medium",
}


def _piper_modeli(dil: str = "tr") -> Path:
    import requests

    from .yerel_llm import model_dizini

    yol = PIPER_SESLERI.get(dil, PIPER_SESLERI["tr"])
    klasor = model_dizini() / "piper"
    klasor.mkdir(parents=True, exist_ok=True)
    ad = yol.rsplit("/", 1)[1]
    for ek in (".onnx.json", ".onnx"):
        dosya = klasor / (ad + ek)
        if not dosya.exists():
            r = requests.get(f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{yol}{ek}", timeout=120,
                             headers={"User-Agent": "otonom-icerik-sistemi/1.0"})
            r.raise_for_status()
            dosya.write_bytes(r.content)
    return klasor / (ad + ".onnx")


def _piper(metin: str, yol: Path, dil: str = "tr") -> list[tuple[float, float, str]]:
    """Çevrimdışı Türkçe ses. Kelime zamanları harf sayısına göre orantılı tahmin edilir."""
    import wave

    from piper import PiperVoice

    wav = yol.with_suffix(".wav")
    yol.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav), "wb") as w:
        PiperVoice.load(_piper_modeli(dil)).synthesize_wav(metin, w)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-q:a", "4", str(yol)], check=True)
    wav.unlink(missing_ok=True)
    toplam, kelimeler = sure(yol), metin.split()
    harf = sum(len(k) + 1 for k in kelimeler) or 1
    sonuc, an = [], 0.0
    for k in kelimeler:
        d = toplam * (len(k) + 1) / harf
        sonuc.append((an, an + d * 0.92, k))
        an += d
    return sonuc


def seslendir(ayar: Ayarlar, metin: str, yol: Path, sira: int = 1, toplam: int = 3, ek_hiz: int = 0) -> dict:
    """Döner: {"ses": yol, "sure": saniye, "kelimeler": [(baş, son, kelime), ...]}
    Önbellekli: aynı metin aynı yola daha önce seslendirildiyse (hazırlık aşaması) tekrar üretilmez."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    yan = yol.with_suffix(".json")
    if yol.exists() and yan.exists():
        try:
            k = json.loads(yan.read_text(encoding="utf-8"))
            if k.get("metin") == metin and k.get("ek_hiz", 0) == ek_hiz:
                return {"ses": yol, "sure": k["sure"], "kelimeler": [tuple(x) for x in k["kelimeler"]]}
        except (ValueError, KeyError):
            pass
    sonuc = _seslendir_yeni(ayar, metin, yol, sira, toplam, ek_hiz)
    yan.write_text(json.dumps({"metin": metin, "ek_hiz": ek_hiz, "sure": sonuc["sure"],
                               "kelimeler": sonuc["kelimeler"]}, ensure_ascii=False), encoding="utf-8")
    return sonuc


def _seslendir_yeni(ayar: Ayarlar, metin: str, yol: Path, sira: int, toplam: int, ek_hiz: int) -> dict:
    if ayar.deneme:
        kelime = metin.split()
        s = max(1.5, len(kelime) / 2.6)
        _sessiz(yol, s)
        adim = s / max(1, len(kelime))
        return {"ses": yol, "sure": s, "kelimeler": [(i * adim, (i + 1) * adim, k) for i, k in enumerate(kelime)]}
    hata = None
    for deneme in range(3):
        try:
            temel = f"{int(str(ayar['ses']['hiz']).rstrip('%')) + ek_hiz:+d}%"
            hiz, perde = (tonlama(sira, toplam, metin, temel) if ayar["ses"].get("tonlama")
                          else (ayar["ses"]["hiz"], "+0Hz"))
            kel = asyncio.run(_seslendir(metin, yol, ayar["ses"]["ses_adi"], hiz, perde))
            if kel and yol.stat().st_size > 1000:
                return {"ses": yol, "sure": sure(yol), "kelimeler": kel}
            hata = "boş ses döndü"
        except Exception as e:  # ağ kesintisi, sınır, engel — tekrar dene
            hata = e
        log.warning("Edge seslendirme denemesi %d başarısız: %s", deneme + 1, hata)
        time.sleep(2 * (deneme + 1))
    from .ayarlar import uyari_ekle
    uyari_ekle("seslendirme", f"Edge TTS kullanılamadı ({hata}); çevrimdışı Piper Türkçe sesiyle devam edildi.")
    kel = _piper(metin, yol, ayar.kanal_bilgi.get("dil", "tr"))
    return {"ses": yol, "sure": sure(yol), "kelimeler": kel}


# ------------------------------------------------------------------ altyazı

def _zaman(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def gruplar(kelimeler: list[tuple[float, float, str]], en_fazla: int = 7) -> list[tuple[float, float, str]]:
    """Kelimeleri okunabilir altyazı satırlarına böler.

    Bölme noktaları: noktalama, seslendirmedeki duraklama (>0,3 sn) veya en_fazla kelime.
    """
    satirlar, grup = [], []
    for i, k in enumerate(kelimeler):
        grup.append(k)
        sonraki = kelimeler[i + 1] if i + 1 < len(kelimeler) else None
        duraklama = sonraki is not None and sonraki[0] - k[1] > 0.3
        if len(grup) >= en_fazla or duraklama or k[2].endswith((".", "!", "?", ",", ":", ";")):
            satirlar.append((grup[0][0], grup[-1][1], " ".join(x[2] for x in grup)))
            grup = []
    if grup:
        satirlar.append((grup[0][0], grup[-1][1], " ".join(x[2] for x in grup)))
    return satirlar


def srt(satirlar: list[tuple[float, float, str]]) -> str:
    return "\n".join(f"{i}\n{_zaman(b)} --> {_zaman(s)}\n{m}\n" for i, (b, s, m) in enumerate(satirlar, 1))
