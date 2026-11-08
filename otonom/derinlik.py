"""2.5D sinematik hareket (paralaks) — fotoğrafı video gibi canlandırır, tamamen yerel ve ücretsiz.

Tek fotoğraftan derinlik haritası çıkarılır: Depth-Anything-V2-Small modeli kullanılır (Apache-2.0, ~27 MB,
CPU'da ~1 sn). Model bir kez indirilir. Kamera hareket ederken yakın nesneler uzaktakilerden daha çok kayar
ve büyür; düz fotoğraf üç boyutlu, "çekilmiş" bir sahne gibi görünür.
Uzun sahneler sanal kamera kesmeleriyle bölünür: geniş → yakın plan → orta plan. Böylece tek görselden birkaç
çekim çıkar ve izleyicinin gözü dinlenmez. Hiçbir dış servis ve anahtar gerekmez. Bir şey eksikse
(model/OpenCV) montaj kendiliğinden eski yakınlaştırma (zoompan) yöntemine döner.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np

from .ayarlar import log

MODEL_ADRESI = ("https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/"
                "model_quantized.onnx")
_OTURUM = None
_KAPALI = False
_DERINLIK_ONBELLEK: dict[str, np.ndarray] = {}


def kullanilabilir() -> bool:
    global _KAPALI
    if _KAPALI:
        return False
    try:
        import importlib.util
        if not (importlib.util.find_spec("cv2") and importlib.util.find_spec("onnxruntime")):
            raise ImportError("opencv-python-headless / onnxruntime kurulu değil")
        return _oturum() is not None
    except Exception as e:  # paket ya da model yoksa sessizce eski yönteme dön
        log.warning("2.5D hareket kullanılamıyor (%s); klasik yakınlaştırma kullanılacak.", e)
        _KAPALI = True
        return False


def _oturum():
    global _OTURUM
    if _OTURUM is None:
        import onnxruntime as ort
        import requests

        from .yerel_llm import model_dizini
        yol = model_dizini() / "derinlik" / "depth-anything-v2-small-q.onnx"
        if not yol.exists():
            yol.parent.mkdir(parents=True, exist_ok=True)
            r = requests.get(MODEL_ADRESI, timeout=300, headers={"User-Agent": "otonom-icerik-sistemi/1.0"})
            r.raise_for_status()
            yol.write_bytes(r.content)
        secenek = ort.SessionOptions()
        secenek.log_severity_level = 3
        _OTURUM = ort.InferenceSession(str(yol), secenek, providers=["CPUExecutionProvider"])
    return _OTURUM


def derinlik_haritasi(resim: np.ndarray) -> np.ndarray:
    """BGR görüntü → 0..1 derinlik (1 = kameraya yakın), yumuşatılmış."""
    import cv2
    anahtar = f"{resim.shape}-{int(resim[::37, ::41].sum())}"
    if anahtar in _DERINLIK_ONBELLEK:
        return _DERINLIK_ONBELLEK[anahtar]
    h, w = resim.shape[:2]
    rgb = cv2.cvtColor(cv2.resize(resim, (518, 518), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
    x = (rgb.astype(np.float32) / 255 - np.array([0.485, 0.456, 0.406], np.float32)) / np.array(
        [0.229, 0.224, 0.225], np.float32)
    cikti = _oturum().run(None, {"pixel_values": x.transpose(2, 0, 1)[None]})[0][0]
    d = cv2.resize(cikti.astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    alt, ust = np.percentile(d, 2), np.percentile(d, 98)
    d = np.clip((d - alt) / max(1e-6, ust - alt), 0, 1)
    k = max(3, int(min(w, h) * 0.012) | 1)
    d = cv2.GaussianBlur(d, (k, k), 0)
    _DERINLIK_ONBELLEK.clear()
    _DERINLIK_ONBELLEK[anahtar] = d
    return d


# ------------------------------------------------------------ kamera planı

def _yumusak(p: float) -> float:
    return (1 - math.cos(math.pi * min(1.0, max(0.0, p)))) / 2


ODAKLAR = [(0.5, 0.45), (0.33, 0.38), (0.66, 0.4), (0.4, 0.62), (0.62, 0.6)]


def kamera(hareket: str, t: float, sure: float, guc: float = 1.0, fps: int = 24) -> dict:
    """Bir an için kamera: z (yakınlık), (fx, fy) odak, (sx, sy) paralaks kayması (çıktı oranı), k derinlik büyümesi."""
    p = _yumusak(t / max(sure, 1e-3))
    a = 0.10 * guc
    kam = {"z": 1.0, "fx": 0.5, "fy": 0.5, "sx": 0.0, "sy": 0.0, "k": 0.05 * guc}
    if hareket == "darbe":  # açılış: hızlı yakınlaşmadan yavaş süzülmeye
        kam.update(z=1.04 + 0.2 * math.exp(-t / 0.3) + 0.06 * p, sx=0.012 * p)
    elif hareket == "vurus":  # Shorts kesmesi: ani yakınlaşma, sonra yavaş itme
        kam.update(z=1.02 + 0.08 * p + 0.14 * math.exp(-t / 0.12), sx=0.02 * (p - 0.5))
    elif hareket == "yaklas":
        kam.update(z=1.0 + a * p, k=0.08 * guc)
    elif hareket == "uzaklas":
        kam.update(z=1.0 + a * (1 - p), k=0.08 * guc)
    elif hareket == "saga":
        kam.update(z=1.06, sx=0.035 * guc * (p - 0.5))
    elif hareket == "sola":
        kam.update(z=1.06, sx=-0.035 * guc * (p - 0.5))
    elif hareket == "yukari":
        kam.update(z=1.06, sy=-0.03 * guc * (p - 0.5))
    elif hareket == "kose":
        kam.update(z=1.0 + a * 1.4 * p, fx=0.5 - 0.17 * p, fy=0.5 - 0.12 * p)
    else:  # suzul: yakınlaşma + çapraz kayma
        kam.update(z=1.03 + a * 0.6 * p, sx=0.025 * guc * (p - 0.5), sy=0.012 * guc * (p - 0.5))
    return kam


def cekim_plani(saniye: float, hareket: str, kesme: float = 7.0) -> list[tuple[float, float, str, float, tuple]]:
    """Uzun sahneyi sanal çekimlere böler: [(başlangıç, süre, hareket, ek_yakınlık, odak)]."""
    if saniye <= kesme * 1.4:
        return [(0.0, saniye, hareket, 0.0, (0.5, 0.5))]
    adet = max(2, round(saniye / kesme))
    d = saniye / adet
    sira = [hareket, "yaklas", "saga", "uzaklas", "sola", "kose", "suzul"]
    return [(i * d, d, sira[i % len(sira)], (0.0, 0.32, 0.14)[i % 3], ODAKLAR[i % len(ODAKLAR)])
            for i in range(adet)]


# ------------------------------------------------------------ kare üretimi

def kareler(resim_yolu: Path, g: int, y: int, saniye: float, fps: int, hareket: str, guc: float = 1.0,
            kesme: float | None = 7.0):
    """Paralakslı kareleri (BGR, g×y) sırayla üretir."""
    import cv2
    kaynak = cv2.imread(str(resim_yolu), cv2.IMREAD_COLOR)
    if kaynak is None:
        raise ValueError(f"görsel okunamadı: {resim_yolu}")
    pay = 1.14  # kenar payı: kayma ve yakınlaşmada boşluk görünmesin
    W, H = int(g * pay), int(y * pay)
    olcek = max(W / kaynak.shape[1], H / kaynak.shape[0])
    buyuk = cv2.resize(kaynak, (math.ceil(kaynak.shape[1] * olcek), math.ceil(kaynak.shape[0] * olcek)),
                       interpolation=cv2.INTER_LANCZOS4 if olcek > 1 else cv2.INTER_AREA)
    ox, oy = (buyuk.shape[1] - W) // 2, (buyuk.shape[0] - H) // 2
    img = np.ascontiguousarray(buyuk[oy:oy + H, ox:ox + W])
    derin = derinlik_haritasi(img)
    # Haritalar yarım çözünürlükte hesaplanıp büyütülür (hareket yumuşak olduğu için kayıpsız, ~4 kat hızlı)
    gy, yy = (g + 1) // 2, (y + 1) // 2
    u, v = np.meshgrid(np.linspace(-g / 2, g / 2, gy, dtype=np.float32),
                       np.linspace(-y / 2, y / 2, yy, dtype=np.float32))
    plan = cekim_plani(saniye, hareket, kesme) if kesme else [(0.0, saniye, hareket, 0.0, (0.5, 0.5))]
    n = max(1, math.ceil(saniye * fps))
    for i in range(n):
        t = i / fps
        bas, d, har, ek, (ofx, ofy) = next((c for c in reversed(plan) if t >= c[0] - 1e-6), plan[0])
        kam = kamera(har, t - bas, d, guc, fps)
        z = kam["z"] + ek
        fx = kam["fx"] if (kam["fx"], kam["fy"]) != (0.5, 0.5) or not ek else ofx
        fy = kam["fy"] if (kam["fx"], kam["fy"]) != (0.5, 0.5) or not ek else ofy
        # odak noktası yakınlaştıkça merkeze gelir; görüntü sınırları aşılmaz
        cx = W / 2 + (fx - 0.5) * W * (1 - 1 / z)
        cy = H / 2 + (fy - 0.5) * H * (1 - 1 / z)
        tx, ty = cx + u / z, cy + v / z
        dd = cv2.remap(derin, tx, ty, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        olc = 1.0 / (1.0 + kam["k"] * (dd - 0.5) * (t - bas) / max(d, 1e-3))
        mx = (cx + u / z * olc - kam["sx"] * g * (dd - 0.3)).astype(np.float32)
        my = (cy + v / z * olc - kam["sy"] * y * (dd - 0.3)).astype(np.float32)
        mx = cv2.resize(mx, (g, y), interpolation=cv2.INTER_LINEAR)
        my = cv2.resize(my, (g, y), interpolation=cv2.INTER_LINEAR)
        yield cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def klip(resim: Path, cikti: Path, g: int, y: int, saniye: float, fps: int, hareket: str, guc: float,
         ffmpeg_cikis: list[str], ek_girdiler: list[str] | None = None, grafik: str | None = None,
         kesme: float | None = 7.0) -> Path:
    """Paralaks karelerini ffmpeg'e borudan verir. grafik: [0:v] boru girdisini kullanan filter_complex."""
    komut = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
             "-s", f"{g}x{y}", "-r", str(fps), "-i", "-", *(ek_girdiler or [])]
    komut += (["-filter_complex", grafik] if grafik else []) + ffmpeg_cikis + [str(cikti)]
    surec = subprocess.Popen(komut, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for kare in kareler(resim, g, y, saniye, fps, hareket, guc, kesme):
            surec.stdin.write(kare.tobytes())
    except BrokenPipeError:
        pass
    finally:
        try:
            surec.stdin.close()
        except BrokenPipeError:
            pass
    hata = surec.stderr.read().decode(errors="replace")
    if surec.wait() != 0:
        raise RuntimeError(f"ffmpeg hatası (paralaks): {hata[-1500:]}")
    return cikti
