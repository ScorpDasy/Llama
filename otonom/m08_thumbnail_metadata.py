"""MODÜL 8 — Küçük resim + SEO uyumlu metadata.

Verimlilik eklemeleri:
  * Bölüm (chapter) zaman damgaları otomatik: Google aramada "önemli anlar" olarak çıkar.
  * Ortaklık linkleri kendi alan adınızdan yönlenir (/git/<ad>): link değişince eski
    videoların açıklamasını düzenlemeye gerek kalmaz ve tıklamalar sayılır.
"""
from __future__ import annotations

from pathlib import Path

from . import gorsel
from .ayarlar import CIKTI, Ayarlar, json_yaz


def _zaman(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def bolum_satirlari(bolumler: list[tuple[float, str]]) -> list[str]:
    """YouTube kuralı: ilki 00:00, en az 3 bölüm, her biri en az 10 sn."""
    temiz: list[tuple[float, str]] = []
    for t, ad in bolumler:
        if not temiz or t - temiz[-1][0] >= 10:
            temiz.append((0.0 if not temiz else t, ad))
    return [f"{_zaman(t)} {ad}" for t, ad in temiz] if len(temiz) >= 3 else []


def ortaklik_linkleri(ayar: Ayarlar, nis_kodu: str) -> list[tuple[str, str]]:
    nis = ayar.nis(nis_kodu)
    alan = ayar.varliklar.get("iletisim", {}).get("kisa_link_alan_adi") or nis.get("alan_adi")
    linkler = nis.get("ortaklik_linkleri") or {}
    return [(ad, f"https://{alan}/git/{ad}") for ad in linkler] if alan else list(linkler.items())


def site_linki(ayar: Ayarlar, icerik: dict) -> str:
    alan = ayar.nis(icerik["plan"]["nis"]).get("alan_adi")
    return f"https://{alan}/yazi/{icerik['plan']['kod']}/" if alan else ""


def aciklama(ayar: Ayarlar, icerik: dict, bolumler: list[tuple[float, str]], materyal: list[dict],
             shorts: bool = False) -> str:
    parca = [icerik["aciklama"].strip(), ""]
    link = site_linki(ayar, icerik)
    if link:
        parca += [f"📖 Detaylı yazı ve kaynaklar: {link}", ""]
    ortak = ortaklik_linkleri(ayar, icerik["plan"]["nis"])
    if ortak:
        parca += ["🔗 Önerdiklerim (ortaklık linki — size ek maliyeti yoktur):"]
        parca += [f"• {ad.replace('-', ' ').title()}: {url}" for ad, url in ortak] + [""]
    if not shorts:
        satirlar = bolum_satirlari(bolumler)
        if satirlar:
            parca += ["Bölümler:", *satirlar, ""]
    kanal = next((k.get("kanal_id") for k in ayar.varliklar.get("youtube_kanallari", []) or [] if k.get("kanal_id")), "")
    if kanal:
        parca += [f"🔔 Abone ol: https://www.youtube.com/channel/{kanal}?sub_confirmation=1", ""]
    kaynaklar = sorted({m["kaynak"] for m in materyal if m.get("kaynak") not in (None, "", "Otomatik kart")})
    if kaynaklar:
        parca.append("Görseller: " + ", ".join(kaynaklar) + " (ücretsiz lisans).")
    etiket = " ".join("#" + e.replace(" ", "") for e in icerik["etiketler"][:3])
    parca.append(("#Shorts " if shorts else "") + etiket)
    return "\n".join(parca)[:4900]


def olustur(ayar: Ayarlar, kod: str, icerik: dict, bolumler: list[tuple[float, str]],
            materyal: list[dict], kapak_gorseli: Path) -> dict:
    klasor = CIKTI / kod
    kucuk = gorsel.kucuk_resim(kapak_gorseli, icerik["thumbnail_yazi"], klasor / "thumbnail.jpg",
                               gorsel.renk(icerik["plan"]["nis"]))
    meta = {
        "baslik": icerik["baslik"][:100],
        "aciklama": aciklama(ayar, icerik, bolumler, materyal),
        "etiketler": icerik["etiketler"],
        "kategori_id": str(ayar["youtube"]["kategori_id"]),
        "thumbnail": str(kucuk),
        "alternatif_basliklar": icerik["alternatif_basliklar"],
        "shorts": [
            {"baslik": f"{sh['baslik'][:90]} #Shorts",
             "aciklama": aciklama(ayar, icerik, [], materyal, shorts=True)}
            for sh in icerik["shorts"]
        ],
    }
    json_yaz(klasor / "metadata.json", meta)
    return meta
