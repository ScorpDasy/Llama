"""Görsel seçici — her aday görseli YEREL modelle puanlar, en iyisini seçer (ücretsiz, anahtarsız).

* Uygunluk: CLIP (OpenAI, MIT lisanslı; nicemlenmiş ONNX, ~150 MB, bir kez indirilir).
  Görsel ile sahnenin görsel tarifi aynı anlam uzayına taşınır, ne kadar örtüştüğü ölçülür.
  "Fare" denilen yerde yaprak çıkmışsa düşük puan alır.
* Kalite: netlik (bulanık değil mi), parlaklık (çok karanlık/çok açık değil mi), kontrast.
Model ya da OpenCV yoksa yalnızca kalite puanı kullanılır; o da yoksa ilk aday seçilir.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .ayarlar import log

DEPO = "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main/"
DOSYALAR = {"metin": "onnx/text_model_quantized.onnx", "gorsel": "onnx/vision_model_quantized.onnx",
            "sozluk": "tokenizer.json"}
_MODEL: dict | None = None
_KAPALI = False
_ORT = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
_SAP = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)


def _model() -> dict | None:
    global _MODEL, _KAPALI
    if _MODEL is not None or _KAPALI:
        return _MODEL
    try:
        import onnxruntime as ort
        import requests
        from tokenizers import Tokenizer

        from .yerel_llm import model_dizini
        klasor = model_dizini() / "clip"
        klasor.mkdir(parents=True, exist_ok=True)
        yollar = {}
        for ad, dosya in DOSYALAR.items():
            yol = klasor / Path(dosya).name
            if not yol.exists():
                r = requests.get(DEPO + dosya, timeout=600, headers={"User-Agent": "otonom-icerik-sistemi/1.0"})
                r.raise_for_status()
                yol.write_bytes(r.content)
            yollar[ad] = yol
        secenek = ort.SessionOptions()
        secenek.log_severity_level = 3
        sozluk = Tokenizer.from_file(str(yollar["sozluk"]))
        sozluk.enable_truncation(77)
        _MODEL = {"metin": ort.InferenceSession(str(yollar["metin"]), secenek, providers=["CPUExecutionProvider"]),
                  "gorsel": ort.InferenceSession(str(yollar["gorsel"]), secenek, providers=["CPUExecutionProvider"]),
                  "sozluk": sozluk, "onbellek": {}}
    except Exception as e:
        log.warning("Görsel uygunluk modeli kullanılamıyor (%s); yalnızca kalite puanı kullanılacak.", str(e)[:200])
        _KAPALI = True
    return _MODEL


def _normal(v: np.ndarray) -> np.ndarray:
    return v / max(1e-6, float(np.linalg.norm(v)))


def metin_vektoru(metin: str) -> np.ndarray | None:
    m = _model()
    if not m:
        return None
    if metin not in m["onbellek"]:
        kimlikler = m["sozluk"].encode(metin).ids
        cikti = m["metin"].run(None, {"input_ids": np.array([kimlikler], np.int64)})[0][0]
        m["onbellek"][metin] = _normal(cikti.astype(np.float32))
    return m["onbellek"][metin]


def gorsel_vektoru(yol: Path) -> np.ndarray | None:
    m = _model()
    if not m:
        return None
    from PIL import Image
    with Image.open(yol) as im:
        im = im.convert("RGB")
        olcek = 224 / min(im.size)
        im = im.resize((max(224, round(im.width * olcek)), max(224, round(im.height * olcek))), Image.BICUBIC)
        sol, ust = (im.width - 224) // 2, (im.height - 224) // 2
        x = (np.asarray(im.crop((sol, ust, sol + 224, ust + 224)), np.float32) / 255 - _ORT) / _SAP
    cikti = m["gorsel"].run(None, {"pixel_values": x.transpose(2, 0, 1)[None]})[0][0]
    return _normal(cikti.astype(np.float32))


def kalite(yol: Path) -> float:
    """0..1: netlik (Laplace varyansı), parlaklık ve kontrast dengesi."""
    try:
        import cv2
        gri = cv2.imread(str(yol), cv2.IMREAD_GRAYSCALE)
        if gri is None:
            return 0.0
        gri = cv2.resize(gri, (512, int(512 * gri.shape[0] / gri.shape[1])))
        netlik = min(1.0, math.log10(1 + cv2.Laplacian(gri, cv2.CV_64F).var()) / 3.0)
        parlak = gri.mean() / 255
        isik = 1.0 - min(1.0, abs(parlak - 0.45) / 0.45)
        kontrast = min(1.0, gri.std() / 64)
        return round(float(0.5 * netlik + 0.25 * isik + 0.25 * kontrast), 3)
    except Exception:
        return 0.5


def puanla(yol: Path, tarif: str) -> dict:
    """{"uygunluk": 0..1, "kalite": 0..1, "puan": 0..100}. tarif: sahnenin İngilizce görsel tarifi."""
    k = kalite(yol)
    uyg = None
    try:
        mv, gv = metin_vektoru(f"a photo of {tarif}"), gorsel_vektoru(yol)
        if mv is not None and gv is not None:
            benzerlik = float(mv @ gv)  # CLIP'te tipik aralık ~0.15 (alakasız) – 0.35 (çok uygun)
            uyg = round(min(1.0, max(0.0, (benzerlik - 0.15) / 0.18)), 3)
    except Exception as e:
        log.warning("Görsel puanlanamadı (%s): %s", yol.name, str(e)[:120])
    puan = (0.75 * uyg + 0.25 * k) * 100 if uyg is not None else k * 100
    return {"uygunluk": uyg, "kalite": float(k), "puan": round(float(puan), 1)}
