"""MODÜL 6 — Telifsiz görsel toplama.

Sıra: Pexels (ücretsiz anahtar) -> Pixabay (ücretsiz anahtar) -> Openverse (anahtarsız, CC0)
      -> otomatik yazı kartı. Bir kaynak sonuç verirse sonrakiler hiç çağrılmaz.
Videolar yerine fotoğraf + Ken Burns efekti kullanılır: indirme ve montaj 5-10 kat
daha hızlıdır, GitHub Actions'ın ücretsiz dakikaları korunur.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

from . import gorsel
from .ayarlar import CIKTI, Ayarlar, gizli, json_yaz, log

ONBELLEK = CIKTI / "_onbellek"
# Bazı görsel sunucuları varsayılan araç kimliklerini (python-requests, curl) engeller;
# sistemi dürüstçe tanıtan bir istemci adı kullanılır.
BASLIK = {"User-Agent": "otonom-icerik-sistemi/1.0"}


def _turkce_mi(sorgu: str) -> bool:
    """Model arama ifadesini Türkçe yazdıysa kaynaklara Türkçe dil ayarıyla sorulur."""
    return any(c in "çğıöşüÇĞİÖŞÜ" for c in sorgu)


def _pexels(sorgu: str, dikey: bool) -> list[dict]:
    anahtar = gizli("PEXELS_API_KEY")
    if not anahtar:
        return []
    try:
        r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": anahtar}, timeout=15,
                         params={"query": sorgu, "per_page": 15, "orientation": "portrait" if dikey else "landscape",
                                 **({"locale": "tr-TR"} if _turkce_mi(sorgu) else {})})
        r.raise_for_status()
        return [{"url": p["src"]["portrait" if dikey else "large2x"], "kaynak": "Pexels",
                 "yazar": p.get("photographer", ""), "sayfa": p.get("url", "")} for p in r.json().get("photos", [])]
    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning("Pexels hatası (%s): %s", sorgu, e)
        return []


def _pixabay(sorgu: str, dikey: bool) -> list[dict]:
    anahtar = gizli("PIXABAY_API_KEY")
    if not anahtar:
        return []
    try:
        r = requests.get("https://pixabay.com/api/", timeout=15, params={
            "key": anahtar, "q": sorgu[:100], "image_type": "photo", "safesearch": "true", "per_page": 20,
            "orientation": "vertical" if dikey else "horizontal", "lang": "tr" if _turkce_mi(sorgu) else "en"})
        r.raise_for_status()
        return [{"url": h["largeImageURL"], "kaynak": "Pixabay", "yazar": h.get("user", ""),
                 "sayfa": h.get("pageURL", "")} for h in r.json().get("hits", [])]
    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning("Pixabay hatası (%s): %s", sorgu, e)
        return []


_OPENVERSE_KAPALI = False  # günlük ücretsiz sınır dolarsa bu çalıştırmada bir daha denenmez
_OPENVERSE_HATA = 0        # devre kesici: toplam 3 sunucu hatasında bu çalıştırmada kapatılır (zaman kaybı olmasın)


def _openverse(sorgu: str, dikey: bool) -> list[dict]:
    """Anahtarsız yedek kaynak: StockSnap'in CC0 (atıf zorunlu değil) stok fotoğrafları.
    Anonim sınır: dakikada 20, günde 200 istek -> istekler arası bekleme yapılır.
    Sonuç yoksa arama kısaltılarak bir kez daha denenir ("student studying tired" -> "student studying")."""
    global _OPENVERSE_KAPALI, _OPENVERSE_HATA
    kelimeler = sorgu.split()
    denemeler = list(dict.fromkeys([sorgu, " ".join(kelimeler[:2]), kelimeler[0] if kelimeler else sorgu]))
    for q in denemeler:
        if _OPENVERSE_KAPALI:
            return []
        try:
            time.sleep(3.1)
            r = requests.get("https://api.openverse.org/v1/images/", timeout=20, headers=BASLIK, params={
                "q": q, "license": "cc0,pdm", "source": "stocksnap", "page_size": 20})
            if r.status_code == 429:
                _OPENVERSE_KAPALI = True
                log.warning("Openverse günlük sınırı doldu; sıradaki görsel kaynağına geçiliyor.")
                return []
            r.raise_for_status()
            sonuc = [{"url": x["url"], "kaynak": "Openverse", "yazar": x.get("creator") or "",
                      "sayfa": x.get("foreign_landing_url") or ""} for x in r.json().get("results", [])]
            if sonuc:
                return sonuc
        except (requests.RequestException, ValueError, KeyError) as e:
            _OPENVERSE_HATA += 1
            log.warning("Openverse hatası (%s): %s", q, e)
            if _OPENVERSE_HATA >= 3:
                _OPENVERSE_KAPALI = True
                log.warning("Openverse sık hata veriyor; bu çalıştırmada yapay zekâ görseline geçiliyor.")
                return []
    return []


def _indir(url: str) -> Path | None:
    ONBELLEK.mkdir(parents=True, exist_ok=True)
    yol = ONBELLEK / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".jpg")
    if yol.exists():
        return yol
    try:
        r = requests.get(url, timeout=30, headers=BASLIK)
        r.raise_for_status()
        yol.write_bytes(r.content)
        return yol
    except requests.RequestException as e:
        log.warning("İndirilemedi: %s", e)
        return None


_YZ_KAPALI: set[str] = set()   # bu çalıştırmada kotası dolan yapay zekâ görsel servisleri


def _yapay_zeka_gorseli(ayar: Ayarlar, sorgu: str, dikey: bool, hedef: Path) -> dict | None:
    """Stok fotoğraf bulunamazsa yapay zekâyla görsel üretir.
    1) Cloudflare Workers AI (hesap bağlıysa; logosuz, ücretsiz günlük kota)  2) Pollinations (anahtarsız)."""
    import base64
    import random

    istem = (f"{sorgu}, photorealistic cinematic photograph, dramatic lighting, sharp focus, rich colors, "
             "no text, no letters, no watermark")
    model = ayar["llm"].get("cloudflare_gorsel_modeli")
    if model and "cloudflare" not in _YZ_KAPALI and gizli("CLOUDFLARE_API_TOKEN") and gizli("CLOUDFLARE_ACCOUNT_ID"):
        try:
            r = requests.post(
                f"https://api.cloudflare.com/client/v4/accounts/{gizli('CLOUDFLARE_ACCOUNT_ID')}/ai/run/{model}",
                headers={"Authorization": f"Bearer {gizli('CLOUDFLARE_API_TOKEN')}"}, timeout=120,
                json={"prompt": istem, "steps": 4})
            resim = (r.json().get("result") or {}).get("image") if r.ok else None
            if resim:
                hedef.write_bytes(base64.b64decode(resim))
                return {"url": "", "kaynak": "Yapay zekâ (Cloudflare)", "yazar": "", "sayfa": "", "sentetik": True}
            _YZ_KAPALI.add("cloudflare")
            log.warning("Cloudflare görsel üretimi kullanılamadı (kota dolmuş olabilir): %s", r.text[:200])
        except (requests.RequestException, ValueError) as e:
            log.warning("Cloudflare görsel hatası: %s", e)
    if "pollinations" not in _YZ_KAPALI:
        g, y = (1088, 1920) if dikey else (1920, 1088)  # yüksek çözünürlük: 2.5D yakın planlarda net kalsın
        try:
            r = requests.get("https://image.pollinations.ai/prompt/" + requests.utils.quote(istem), headers=BASLIK,
                             timeout=120, params={"width": g, "height": y, "nologo": "true", "model": "flux",
                                                  "seed": random.Random(sorgu).randint(1, 10**6)})
            if r.ok and r.headers.get("content-type", "").startswith("image/"):
                hedef.write_bytes(r.content)
                try:  # alt köşedeki olası küçük logoyu kırp
                    from PIL import Image
                    with Image.open(hedef) as im:
                        im.convert("RGB").crop((0, 0, im.width, int(im.height * 0.95))).save(hedef, quality=92)
                except Exception:
                    pass
                return {"url": "", "kaynak": "Yapay zekâ (Pollinations)", "yazar": "", "sayfa": "", "sentetik": True}
            if r.status_code == 429:
                _YZ_KAPALI.add("pollinations")
        except requests.RequestException as e:
            log.warning("Pollinations hatası: %s", e)
    return None


STOK_KAYNAKLARI = {"pexels": _pexels, "pixabay": _pixabay, "openverse": _openverse}


def gorsel_bul(ayar: Ayarlar, sorgu: str, hedef: Path, kullanilan: set[str], nis: str,
               dikey: bool = False, yedek_yazi: str = "", hazir_kullan: bool = True) -> dict:
    """Videoda daha önce kullanılmamış bir görsel bulur ve `hedef`e yazar.
    Sıra kanal dosyasındaki 'gorsel_kaynaklari' ile değiştirilebilir (ör. tarih kanalı için yapay zekâ önce)."""
    hazir = hedef.with_suffix(".hazir.json")
    if hazir_kullan and hazir.exists() and hedef.exists():  # hazırlık aşamasında seçilmiş en iyi aday
        try:
            return {**json.loads(hazir.read_text(encoding="utf-8")), "dosya": str(hedef)}
        except ValueError:
            pass
    if not ayar.deneme:
        sira = ayar.kanal_bilgi.get("gorsel_kaynaklari") or (
            ["pexels", "pixabay", "openverse", "yapay_zeka"] if gizli("PEXELS_API_KEY") or gizli("PIXABAY_API_KEY")
            else ["yapay_zeka", "openverse"])  # anahtarsız: yapay zekâ görseli konuya daha uygun
        for ad in sira:
            if ad == "yapay_zeka":
                bilgi = _yapay_zeka_gorseli(ayar, sorgu, dikey, hedef)
                if bilgi:
                    return {**bilgi, "dosya": str(hedef), "sorgu": sorgu}
                continue
            for aday in STOK_KAYNAKLARI.get(ad, lambda *_: [])(sorgu, dikey):
                if aday["url"] in kullanilan:
                    continue
                dosya = _indir(aday["url"])
                if dosya:
                    kullanilan.add(aday["url"])
                    hedef.write_bytes(dosya.read_bytes())
                    return {**aday, "dosya": str(hedef), "sorgu": sorgu}
    g, y = (1080, 1920) if dikey else (1920, 1080)
    gorsel.yazi_karti(yedek_yazi or sorgu, hedef, g, y, gorsel.renk(nis))
    return {"url": "", "kaynak": "Otomatik kart", "yazar": "", "sayfa": "", "dosya": str(hedef), "sorgu": sorgu}


def topla(ayar: Ayarlar, kod: str, icerik: dict) -> list[dict]:
    klasor = CIKTI / kod / "gorseller"
    klasor.mkdir(parents=True, exist_ok=True)
    nis = icerik["plan"]["nis"]
    kullanilan: set[str] = set()
    liste = []
    for i, s in enumerate(icerik["sahneler"]):
        # Görsel bulunamazsa kartta sahnenin kendi ilk cümlesi yazar (tekrar eden başlık yerine)
        ilk_cumle = s["metin"].replace("?", "?.").replace("!", "!.").split(". ")[0].rstrip(".")
        bilgi = gorsel_bul(ayar, s["gorsel_arama"], klasor / f"sahne_{i:03d}.jpg", kullanilan, nis,
                           yedek_yazi=s.get("bolum") or ilk_cumle)
        liste.append({"sahne": i, **bilgi})
    for j, sh in enumerate(icerik["shorts"]):
        bilgi = gorsel_bul(ayar, sh["gorsel_arama"], klasor / f"shorts_{j}.jpg", kullanilan, nis, dikey=True,
                           yedek_yazi=sh["baslik"])
        liste.append({"shorts": j, **bilgi})
    json_yaz(CIKTI / kod / "materyal_listesi.json", liste)
    return liste


# ------------------------------------------------------------ stok VİDEO (Shorts için gerçek hareket)

def _video_dosyasi(dosyalar: list[dict], dikey: bool) -> dict | None:
    """En uygun mp4: dikeyse dikey, yüksekliği 1280-2000 arası (gereksiz büyük dosya indirilmesin)."""
    uygun = [f for f in dosyalar if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")
             and (f["height"] > f["width"]) == dikey]
    if not uygun:
        return None
    hedef = 1920 if dikey else 1080
    return min(uygun, key=lambda f: (abs((f["height"] if dikey else f["width"] * 9 / 16) - hedef), f["height"]))


def video_bul(ayar: Ayarlar, sorgu: str, hedef: Path, kullanilan: set[str], dikey: bool = True,
              en_kisa: float = 3.0) -> dict | None:
    """Pexels'ten ücretsiz stok video (PEXELS_API_KEY varsa; atıf zorunlu değil). Yoksa None → görsel kullanılır."""
    anahtar = gizli("PEXELS_API_KEY")
    if ayar.deneme or not anahtar or not ayar["video"].get("stok_video", True):
        return None
    try:
        r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": anahtar}, timeout=15,
                         params={"query": sorgu, "per_page": 15, "orientation": "portrait" if dikey else "landscape",
                                 "size": "medium"})
        r.raise_for_status()
        videolar = r.json().get("videos", [])
    except (requests.RequestException, ValueError) as e:
        log.warning("Pexels video hatası (%s): %s", sorgu, e)
        return None
    for v in videolar:
        dosya = _video_dosyasi(v.get("video_files") or [], dikey)
        if not dosya or dosya["link"] in kullanilan or float(v.get("duration") or 0) < en_kisa:
            continue
        try:
            r = requests.get(dosya["link"], timeout=60, headers=BASLIK)
            r.raise_for_status()
            if len(r.content) > 60_000_000:
                continue
            hedef.parent.mkdir(parents=True, exist_ok=True)
            hedef.write_bytes(r.content)
        except requests.RequestException:
            continue
        kullanilan.add(dosya["link"])
        return {"url": dosya["link"], "kaynak": "Pexels (video)", "yazar": (v.get("user") or {}).get("name", ""),
                "sayfa": v.get("url", ""), "dosya": str(hedef), "sorgu": sorgu, "video": True}
    return None
