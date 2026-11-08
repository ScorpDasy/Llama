"""Yerel (ücretsiz) yapay zekâ modeli — llama.cpp ile işlemcide çalışır, API anahtarı ve ücret yok.

* Model dosyası (GGUF) ilk kullanımda HuggingFace'ten bir kez indirilir; GitHub Actions'ta önbelleğe alınır.
* Çıktı, JSON şemasına dilbilgisi (grammar) ile zorlanır: bozuk JSON üretmesi mümkün değildir.
* Seçilen model ve hız ölçümleri README'de; config/ayarlar.yaml > llm.yerel_* ile değiştirilebilir.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

from .ayarlar import Ayarlar, log

_MODEL = None
_MODEL_ADI = ""


def model_dizini() -> Path:
    return Path(os.environ.get("OTONOM_MODEL_DIZINI") or Path.home() / ".cache" / "otonom-modeller")


def model_yolu(ayar: Ayarlar) -> Path:
    """GGUF dosyasını yoksa indirir (yarım kalan indirme bir sonraki çalıştırmada baştan alınır)."""
    depo, dosya = ayar["llm"]["yerel_model"], ayar["llm"]["yerel_dosya"]
    yol = model_dizini() / dosya
    if yol.exists():
        return yol
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(".part")
    url = f"https://huggingface.co/{depo}/resolve/main/{dosya}"
    log.info("Yerel model indiriliyor (bir kez): %s", url)
    with requests.get(url, stream=True, timeout=60, headers={"User-Agent": "otonom-icerik-sistemi/1.0"}) as r:
        r.raise_for_status()
        with gecici.open("wb") as f:
            for parca in r.iter_content(chunk_size=1 << 20):
                f.write(parca)
    gecici.replace(yol)
    return yol


def _yukle(ayar: Ayarlar):
    global _MODEL, _MODEL_ADI
    ad = ayar["llm"]["yerel_dosya"]
    if _MODEL is None or _MODEL_ADI != ad:
        from llama_cpp import Llama

        _MODEL = Llama(model_path=str(model_yolu(ayar)), n_ctx=int(ayar["llm"].get("yerel_baglam", 8192)),
                       n_threads=os.cpu_count() or 2, verbose=False)
        _MODEL_ADI = ad
    return _MODEL


def bosalt() -> None:
    """Modeli bellekten çıkarır (video montajı için RAM'i boşaltır; ücretsiz sunucuda 7 GB var)."""
    global _MODEL, _MODEL_ADI
    if _MODEL is not None:
        import gc

        _MODEL, _MODEL_ADI = None, ""
        gc.collect()


def json_uret(ayar: Ayarlar, sistem: str, istem: str, sema: dict, max_tokens: int) -> tuple[str, str, dict]:
    """Döner: (metin, bitiş_nedeni, kullanım). Bitiş nedeni 'length' ise çıktı yarım kalmıştır."""
    model = _yukle(ayar)
    bas = time.time()
    cevap = model.create_chat_completion(
        messages=[{"role": "system", "content": sistem}, {"role": "user", "content": istem}],
        response_format={"type": "json_object", "schema": sema},
        max_tokens=max_tokens,
        temperature=float(ayar["llm"].get("yerel_sicaklik", 0.7)),
        repeat_penalty=1.05,
    )
    kullanim = cevap.get("usage", {})
    sure = time.time() - bas
    log.info("Yerel model: %d token, %.0f sn (%.1f token/sn)", kullanim.get("completion_tokens", 0), sure,
             kullanim.get("completion_tokens", 0) / max(sure, 1e-6))
    secim = cevap["choices"][0]
    return secim["message"]["content"] or "", secim.get("finish_reason") or "", kullanim
