"""Sınır bütçesi — ücretsiz kotalar dolmadan sistem kendini ayarlar.

GitHub Actions özel depoda ayda 2.000 ücretsiz dakika verir. Her çalıştırmanın süresi kaydedilir;
ay sonu tahmini sınıra yaklaşırsa üretim otomatik azaltılır, aşacaksa yalnızca hafif işler
(analiz, teklifler, site) yapılır. Böylece hesap asla ücretli hale gelmez ve sistem durmaz.
"""
from __future__ import annotations

import calendar
import os

from .ayarlar import ISLETME, Ayarlar, csv_ekle, csv_oku, isletme_dosyalari, uyari_ekle

DOSYA = ISLETME / "calismalar.csv"
KURULUM_PAYI_DK = 3  # her çalıştırmada kurulum adımlarının (paket, ffmpeg) yaklaşık süresi


def limit(ayar: Ayarlar) -> int:
    """0 = sınırsız (herkese açık depo)."""
    if os.environ.get("REPO_OZEL", "").lower() == "false":
        return 0
    return int((ayar.genel.get("butce") or {}).get("github_dakika_limiti", 2000))


def kaydet(ayar: Ayarlar, komut: str, saniye: float) -> None:
    if ayar.deneme or not os.environ.get("GITHUB_ACTIONS"):
        return
    csv_ekle(DOSYA, [{"tarih": ayar.simdi.isoformat(timespec="seconds"), "komut": komut,
                      "dakika": round(saniye / 60 + KURULUM_PAYI_DK, 1)}], ["tarih", "komut", "dakika"])


def bu_ay(ayar: Ayarlar) -> float:
    ay = ayar.simdi.strftime("%Y-%m")
    return sum(float(s["dakika"]) for d in isletme_dosyalari("calismalar.csv") for s in csv_oku(d)
               if s["tarih"].startswith(ay))


def tahmin(ayar: Ayarlar) -> float:
    gun = ayar.simdi.day
    gun_sayisi = calendar.monthrange(ayar.simdi.year, ayar.simdi.month)[1]
    return bu_ay(ayar) / max(gun, 1) * gun_sayisi


def uyarla(ayar: Ayarlar) -> str:
    """Döner: 'normal' | 'azaltilmis' | 'hafif'. Ayarları bu çalıştırma için yerinde değiştirir."""
    sinir = limit(ayar)
    if not sinir or ayar.deneme:
        return "normal"
    kullanilan, ay_sonu = bu_ay(ayar), tahmin(ayar)
    yt = ayar.genel["youtube"]
    if kullanilan >= 0.93 * sinir:
        uyari_ekle("bütçe", f"GitHub dakikası doldu sayılır ({kullanilan:.0f}/{sinir}); bu ay yalnızca hafif işler yapılıyor.")
        return "hafif"
    if ay_sonu > 0.85 * sinir:
        yt["haftalik_uzun_video"] = max(1, int(yt["haftalik_uzun_video"]) - 1)
        yt["video_basina_shorts"] = min(1, int(yt["video_basina_shorts"]))
        uyari_ekle("bütçe", f"Ay sonu tahmini {ay_sonu:.0f}/{sinir} dakika; üretim geçici olarak azaltıldı "
                            f"({yt['haftalik_uzun_video']} video, video başına {yt['video_basina_shorts']} Shorts).")
        return "azaltilmis"
    return "normal"
