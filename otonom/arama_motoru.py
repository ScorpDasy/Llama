"""Arama motoru kaydı — tamamen otomatik ve ücretsiz.

* IndexNow (Bing, Yandex, Seznam, Naver): hesap/anahtar gerektirmez. Her siteye bir doğrulama dosyası
  konur, değişen sayfalar her çalıştırmada anında bildirilir.
* Google Search Console: GOOGLE_ARAMA_TOKEN varsa (araclar/youtube_token_al.py arama) alan adı
  Cloudflare DNS'e eklenen TXT kaydıyla doğrulanır, Search Console'a eklenir ve site haritası gönderilir.
Durum veri/arama_motoru.json'da tutulur; DNS yayılımı gecikirse sonraki çalıştırmada kaldığı yerden devam eder.
"""
from __future__ import annotations

import re
import secrets

import requests

from .ayarlar import SITE, VERI, Ayarlar, gizli, json_oku, json_yaz, log, ozet_yaz

ANAHTARLAR = VERI / "indexnow.json"
DURUM = VERI / "arama_motoru.json"
BASLIK = {"User-Agent": "otonom-icerik-sistemi/1.0"}


def indexnow_anahtari(alan: str) -> str:
    """Alan adı başına sabit IndexNow anahtarı (herkese açık olması tasarım gereğidir)."""
    anahtarlar = json_oku(ANAHTARLAR, {})
    if alan not in anahtarlar:
        anahtarlar[alan] = secrets.token_hex(16)
        json_yaz(ANAHTARLAR, anahtarlar)
    return anahtarlar[alan]


def _indexnow(alan: str, proje: str) -> str:
    anahtar = indexnow_anahtari(alan)
    harita = SITE / proje / "public" / "sitemap.xml"
    adresler = re.findall(r"<loc>(.*?)</loc>", harita.read_text(encoding="utf-8")) if harita.exists() else []
    if not adresler:
        return "site haritası yok"
    try:  # site yayında ve anahtar dosyası erişilebilir mi?
        if requests.get(f"https://{alan}/{anahtar}.txt", headers=BASLIK, timeout=15).text.strip() != anahtar:
            return "site henüz yayında değil"
        r = requests.post("https://api.indexnow.org/indexnow", timeout=30, json={
            "host": alan, "key": anahtar, "keyLocation": f"https://{alan}/{anahtar}.txt", "urlList": adresler[:10000]})
        return f"{len(adresler)} sayfa bildirildi" if r.status_code in (200, 202) else f"hata {r.status_code}"
    except requests.RequestException as e:
        return f"erişilemedi ({e.__class__.__name__})"


def _google(alan: str, durum: dict) -> str:
    """Adım adım: DNS TXT -> doğrulama -> Search Console'a ekleme -> site haritası. Her adım kaydedilir."""
    if not (gizli("GOOGLE_ARAMA_TOKEN") and gizli("YT_CLIENT_ID") and gizli("YT_CLIENT_SECRET")):
        return "kurulmadı (GOOGLE_ARAMA_TOKEN yok)"
    if durum.get("asama") == "tamam":
        return "doğrulandı, site haritası gönderildi"
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    from .cloudflare_kur import dns_txt_ekle

    kimlik = Credentials(None, refresh_token=gizli("GOOGLE_ARAMA_TOKEN"), client_id=gizli("YT_CLIENT_ID"),
                         client_secret=gizli("YT_CLIENT_SECRET"), token_uri="https://oauth2.googleapis.com/token")
    site = {"type": "INET_DOMAIN", "identifier": alan}
    try:
        dogrulama = build("siteVerification", "v1", credentials=kimlik, cache_discovery=False)
        if durum.get("asama") in (None, "baslangic"):
            jeton = dogrulama.webResource().getToken(body={"site": site, "verificationMethod": "DNS_TXT"}).execute()
            if not dns_txt_ekle(alan, jeton["token"]):
                return "DNS kaydı eklenemedi (alan adı Cloudflare'de olmalı)"
            durum["asama"] = "dns_eklendi"
        if durum["asama"] == "dns_eklendi":
            try:
                dogrulama.webResource().insert(verificationMethod="DNS_TXT", body={"site": site}).execute()
            except HttpError:
                return "DNS yayılımı bekleniyor (sonraki çalıştırmada tekrar denenecek)"
            durum["asama"] = "dogrulandi"
        konsol = build("searchconsole", "v1", credentials=kimlik, cache_discovery=False)
        konsol.sites().add(siteUrl=f"sc-domain:{alan}").execute()
        konsol.sitemaps().submit(siteUrl=f"sc-domain:{alan}", feedpath=f"https://{alan}/sitemap.xml").execute()
        durum["asama"] = "tamam"
        return "doğrulandı, Search Console'a eklendi, site haritası gönderildi"
    except HttpError as e:
        return f"Google hatası: {str(e)[:150]}"


def calistir(ayar: Ayarlar) -> dict:
    from .mikro_site import proje_adi

    if ayar.deneme:
        return {}
    durumlar = json_oku(DURUM, {})
    degisen = set((SITE / "projeler.txt").read_text(encoding="utf-8").split()) if (SITE / "projeler.txt").exists() else set()
    satirlar = ["## 🔎 Arama motorları"]
    for a in ayar.alan_adlari:
        alan, proje = a["ad"], proje_adi(a["ad"])
        d = durumlar.setdefault(alan, {})
        if proje in degisen or not d.get("indexnow"):
            d["indexnow"] = _indexnow(alan, proje)
        d["google"] = _google(alan, d)
        satirlar.append(f"- **{alan}** · Bing/Yandex (IndexNow): {d['indexnow']} · Google: {d['google']}")
    json_yaz(DURUM, durumlar)
    ozet_yaz("\n".join(satirlar))
    log.info("Arama motorları: %s", durumlar)
    return durumlar
