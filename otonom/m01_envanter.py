"""MODÜL 1 — Varlık envanteri ve durum tespiti (tamamen ücretsiz kaynaklar)."""
from __future__ import annotations

import math
import socket
from datetime import datetime

import requests

from .ayarlar import VERI, Ayarlar, gizli, json_yaz, log

ANAHTAR_KELIMELER = {
    # alıcıların aradığı ticari kelimeler (değer puanını artırır)
    "bilisim", "yazilim", "teknoloji", "tech", "ai", "yapayzeka", "bulut", "cloud", "data", "veri",
    "turizm", "tur", "tour", "travel", "seyahat", "otel", "hotel", "tatil", "rezervasyon",
    "neuro", "noro", "beyin", "brain", "psikoloji", "saglik", "health", "klinik",
    "trust", "hub", "pro", "net", "digital", "dijital", "okyanus", "ocean",
}


def alan_adi_puani(ad: str) -> dict:
    """Basit, şeffaf değer puanı (0-100). Profesyonel ekspertiz değildir."""
    govde, _, uzanti = ad.lower().partition(".")
    puan = 50.0
    puan += {"com": 20, "com.tr": 12, "net": 5, "org": 5, "io": 8, "ai": 10}.get(uzanti, 0)
    puan -= max(0, len(govde) - 8) * 2.0          # kısa = değerli
    puan -= 10 * govde.count("-")
    puan -= 8 * sum(c.isdigit() for c in govde)
    eslesen = [k for k in ANAHTAR_KELIMELER if k in govde]
    puan += min(20, 7 * len(eslesen))
    if uzanti == "com" and govde.endswith("tr"):
        puan -= 6                                   # ".com" içinde "tr" eki marka gücünü düşürür
    puan = max(0, min(100, round(puan)))
    seviye = "Yüksek" if puan >= 70 else "Orta" if puan >= 45 else "Düşük"
    return {"puan": puan, "seviye": seviye, "anahtar_kelimeler": eslesen}


def _dns_var_mi(ad: str) -> bool:
    try:
        socket.getaddrinfo(ad, 443)
        return True
    except OSError:
        return False


def _http_durumu(ad: str) -> str:
    try:
        r = requests.get(f"https://{ad}", timeout=8, allow_redirects=True)
        return str(r.status_code)
    except requests.RequestException:
        return "yanıt yok"


def _bitis_tarihi(ad: str) -> str:
    """RDAP (ücretsiz, açık standart) ile kayıt bitiş tarihi. .com.tr için desteklenmeyebilir."""
    try:
        r = requests.get(f"https://rdap.org/domain/{ad}", timeout=10)
        if r.ok:
            for olay in r.json().get("events", []):
                if olay.get("eventAction") == "expiration":
                    return olay["eventDate"][:10]
    except (requests.RequestException, ValueError):
        pass
    return "bilinmiyor (kayıt firmasından kontrol edin)"


def _kanal_istatistik(kanal_id: str) -> dict:
    anahtar = gizli("YOUTUBE_API_KEY")
    if not (anahtar and kanal_id):
        return {}
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "statistics,snippet", "id": kanal_id, "key": anahtar},
            timeout=15,
        )
        ogeler = r.json().get("items", [])
        if not ogeler:
            return {}
        s = ogeler[0]["statistics"]
        return {
            "ad": ogeler[0]["snippet"]["title"],
            "abone": int(s.get("subscriberCount", 0)),
            "goruntulenme": int(s.get("viewCount", 0)),
            "video": int(s.get("videoCount", 0)),
        }
    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning("Kanal istatistiği alınamadı: %s", e)
        return {}


def calistir(ayar: Ayarlar) -> list[dict]:
    satirlar: list[dict] = []
    for a in ayar.alan_adlari:
        ad = a["ad"]
        deger = alan_adi_puani(ad)
        if ayar.deneme:
            dns, http, bitis = True, "200", "2027-01-01"
        else:
            dns = _dns_var_mi(ad)
            http = _http_durumu(ad) if dns else "DNS yok"
            bitis = _bitis_tarihi(ad)
        potansiyel = {
            "site_ve_satis": "Mikro site (reklam+ortaklık) + satış/kiralama",
            "sadece_satis": "Satış/kiralama ilanı",
            "sadece_site": "Mikro site (reklam+ortaklık)",
            "park": "Satılık sayfası (park)",
        }.get(a.get("mod", "site_ve_satis"), "-")
        satirlar.append({
            "varlik": ad, "tur": "Alan adı",
            "durum": f"DNS {'var' if dns else 'yok'}, HTTP {http}, bitiş {bitis}",
            "deger": f"{deger['seviye']} ({deger['puan']}/100)", "potansiyel": potansiyel,
        })

    from .ayarlar import tum_kanallar
    for ka in tum_kanallar(ayar.deneme):
        k = {"ad": f"{ka.kanal_bilgi.get('ad', ka.kanal)} ({ka.kanal})", "kanal_id": ka.kanal_bilgi.get("kanal_id", "")}
        ist = {} if ayar.deneme else _kanal_istatistik(k.get("kanal_id", ""))
        if ist:
            ilerleme = min(100, math.floor(ist["abone"] / 10))
            durum = f"{ist['abone']} abone, {ist['goruntulenme']} izlenme, {ist['video']} video"
            deger = f"Para kazanma için abone hedefi: %{ilerleme}"
        else:
            durum, deger = "kanal_id veya YOUTUBE_API_KEY eksik", "-"
        satirlar.append({
            "varlik": k.get("ad", "Kanal"), "tur": "YouTube kanalı", "durum": durum,
            "deger": deger, "potansiyel": "Reklam (YPP), ortaklık linkleri, site trafiği",
        })

    tablo = ["| Varlık | Tür | Durum | Değer | Gelir Potansiyeli |", "|---|---|---|---|---|"]
    tablo += [f"| {s['varlik']} | {s['tur']} | {s['durum']} | {s['deger']} | {s['potansiyel']} |" for s in satirlar]
    md = f"# Varlık Envanteri — {datetime.now():%Y-%m-%d}\n\n" + "\n".join(tablo) + "\n"
    (VERI / "envanter.md").write_text(md, encoding="utf-8")
    json_yaz(VERI / "envanter.json", satirlar)
    log.info("Envanter: %d varlık", len(satirlar))
    return satirlar
