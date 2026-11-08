"""MODÜL 2 — Niş, pazar ve KONU KAYNAKLARI analizi.

Her niş, konularını kanal dosyasında seçilen kaynaklardan alır (hepsi ücretsiz, anahtarsız):
  * youtube_oneri   : YouTube otomatik tamamlama önerileri — insanların gerçekten ne aradığı.
  * google_trendler : Ülkenin günlük Google gündemi (RSS).
  * rss             : Haber/blog akışlarının son başlıkları (gündem ve teknoloji kanalları için).
  * wikipedia_bugun : Vikipedi "tarihte bugün" olayları (tarih/kültür kanalları için).
  * elle            : Kullanıcının kendi konu listesi.
Her aday konu kaynağıyla etiketlenir; laboratuvar hangi kaynağın daha iyi video çıkardığını öğrenir.
Ek sinyaller:
  * YouTube Data API (ücretsiz kota, isteğe bağlı): ilk sıradaki videoların izlenmesi ve
    kanal büyüklüğü -> rekabet. Küçük kanalların çok izlendiği konular = fırsat.
  * Trend momentumu: geçen haftaya göre yeni çıkan veya talebi artan aramalar bonus alır.
Uydurma "arama hacmi" sayısı üretilmez; tüm puanlar ölçülen sinyallerden gelir.
"""
from __future__ import annotations

import html
import math
import re
import statistics
import time
from collections import defaultdict

import requests

from .ayarlar import KANAL_VERI as VERI, Ayarlar, gizli, json_oku, json_yaz, kisa_ad, log
from .optimizasyon import trend_bonusu

EKLER = ["", " nasıl", " nedir", " için", " neden", " en iyi"]
ONERI_URL = "https://suggestqueries.google.com/complete/search"
YT_API = "https://www.googleapis.com/youtube/v3"


BASLIK = {"User-Agent": "otonom-icerik-sistemi/1.0"}
KAYNAK_TALEBI = {"rss": 0.6, "wikipedia_bugun": 0.5, "elle": 0.7}   # ölçülemeyen kaynaklar için başlangıç talebi


def oneriler(sorgu: str, dil: str = "tr", ulke: str = "tr") -> list[str]:
    try:
        r = requests.get(
            ONERI_URL, params={"client": "firefox", "ds": "yt", "hl": dil, "gl": ulke, "q": sorgu}, timeout=10
        )
        r.raise_for_status()
        return [s for s in r.json()[1] if isinstance(s, str)]
    except (requests.RequestException, ValueError, IndexError) as e:
        log.warning("Öneri alınamadı (%s): %s", sorgu, e)
        return []


def talep_puanlari(tohumlar: list[str], bekle: float = 0.25, dil: str = "tr", ulke: str = "tr") -> dict[str, float]:
    """Her öneriye sırasına göre puan verir; birden çok sorguda çıkan konu daha değerlidir."""
    puan: dict[str, float] = defaultdict(float)
    gorunen: dict[str, str] = {}
    ekler = EKLER if dil == "tr" else ["", " how to", " what is", " best", " why"]
    for tohum in tohumlar:
        for ek in ekler:
            for sira, oneri in enumerate(oneriler(tohum + ek, dil, ulke)):
                anahtar = kisa_ad(oneri, 80)
                gorunen.setdefault(anahtar, oneri)
                puan[anahtar] += (10 - min(sira, 9)) / 10
            time.sleep(bekle)
    return {gorunen[k]: v for k, v in puan.items()}


def _rekabet(konu: str, anahtar: str) -> dict:
    """~102 kota birimi. Döner: medyan izlenme, medyan abone, küçük kanal başarı oranı."""
    try:
        ara = requests.get(f"{YT_API}/search", params={
            "part": "snippet", "q": konu, "type": "video", "maxResults": 10,
            "regionCode": "TR", "relevanceLanguage": "tr", "key": anahtar}, timeout=15).json()
        vid = [i["id"]["videoId"] for i in ara.get("items", [])]
        kan = list({i["snippet"]["channelId"] for i in ara.get("items", [])})
        if not vid:
            return {}
        v = requests.get(f"{YT_API}/videos", params={
            "part": "statistics,snippet", "id": ",".join(vid), "key": anahtar}, timeout=15).json()
        c = requests.get(f"{YT_API}/channels", params={
            "part": "statistics", "id": ",".join(kan), "key": anahtar}, timeout=15).json()
        abone = {i["id"]: int(i["statistics"].get("subscriberCount", 0)) for i in c.get("items", [])}
        izl, abo, kucuk_basari = [], [], 0
        for i in v.get("items", []):
            g = int(i["statistics"].get("viewCount", 0))
            a = abone.get(i["snippet"]["channelId"], 0)
            izl.append(g)
            abo.append(a)
            if a < 20_000 and g > 5_000:
                kucuk_basari += 1
        return {
            "medyan_izlenme": int(statistics.median(izl)) if izl else 0,
            "medyan_abone": int(statistics.median(abo)) if abo else 0,
            "kucuk_kanal_orani": round(kucuk_basari / max(1, len(izl)), 2),
        }
    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning("Rekabet ölçülemedi (%s): %s", konu, e)
        return {}


def firsat_puani(talep_norm: float, rekabet: dict) -> tuple[float, str]:
    if not rekabet:
        return round(talep_norm, 3), "bilinmiyor"
    rek = min(1.0, math.log10(rekabet["medyan_abone"] + 1) / 7)   # 10M abone ≈ 1.0
    etiket = "düşük" if rek < 0.5 else "orta" if rek < 0.72 else "yüksek"
    puan = 0.5 * talep_norm + 0.3 * (1 - rek) + 0.2 * rekabet["kucuk_kanal_orani"]
    return round(puan, 3), etiket


# ------------------------------------------------------------ kaynaklar

def _metin(x: str) -> str:
    x = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", x, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", x)).strip()


def _getir(url: str) -> str:
    """En fazla 2 MB metin; XML ayrıştırıcı kullanılmaz (regex) -> zararlı XML'e karşı güvenli."""
    try:
        r = requests.get(url, headers=BASLIK, timeout=15, stream=True)
        r.raise_for_status()
        veri = r.raw.read(2_000_000, decode_content=True)
        return veri.decode(r.encoding or "utf-8", errors="replace")
    except (requests.RequestException, OSError) as e:
        log.warning("Kaynak okunamadı (%s): %s", url, e)
        return ""


def google_trendler(ulke: str = "TR") -> dict[str, float]:
    """Günlük Google gündemi: başlık -> yaklaşık arama trafiğine göre 0,5-1,0 arası talep."""
    metin = _getir(f"https://trends.google.com/trending/rss?geo={ulke.upper()}")
    sonuc = {}
    for oge in re.findall(r"<item>(.*?)</item>", metin, flags=re.S)[:20]:
        baslik = re.search(r"<title>(.*?)</title>", oge, flags=re.S)
        trafik = re.search(r"<ht:approx_traffic>([\d.,]+)", oge)
        if baslik:
            sayi = int(re.sub(r"[.,]", "", trafik.group(1))) if trafik else 100
            sonuc[_metin(baslik.group(1))] = round(min(1.0, 0.5 + math.log10(max(sayi, 10)) / 12), 3)
    return sonuc


def rss_basliklari(adresler: list[str], adet: int = 10) -> list[str]:
    """RSS ve Atom akışlarının en yeni başlıkları."""
    basliklar = []
    for url in adresler:
        metin = _getir(url)
        ogeler = re.findall(r"<item[ >].*?</item>|<entry[ >].*?</entry>", metin, flags=re.S)[:adet]
        for oge in ogeler:
            b = re.search(r"<title[^>]*>(.*?)</title>", oge, flags=re.S)
            baslik = _metin(b.group(1)) if b else ""
            if baslik and not re.search(r"sponsor|reklam|advert|kampanya", baslik, flags=re.I):
                basliklar.append(baslik[:140])
    return basliklar


def wikipedia_bugun(dil: str, gun) -> list[str]:
    """Vikipedi 'tarihte bugün' seçili olayları (yoğunlukta 429 dönebilir; o hafta atlanır)."""
    for url in (f"https://{dil}.wikipedia.org/api/rest_v1/feed/onthisday/selected/{gun:%m}/{gun:%d}",
                f"https://api.wikimedia.org/feed/v1/wikipedia/{dil}/onthisday/selected/{gun:%m}/{gun:%d}"):
        try:
            r = requests.get(url, headers=BASLIK, timeout=15)
            if r.ok:
                return [f"{o.get('year', '')}: {o.get('text', '')}"[:160] for o in r.json().get("selected", [])[:12]]
        except (requests.RequestException, ValueError):
            continue
    log.warning("Vikipedi 'tarihte bugün' okunamadı; bu hafta atlandı.")
    return []


# Reklamverene uygun olmayan / hukuki risk taşıyan gündem konuları (ölüm, suç, kumar, yetişkin içerik vb.)
YASAK = re.compile(r"(öldü|ölü|ölüm|cinayet|öldür|saldırı|terör|tecavüz|taciz|istismar|intihar|yaralı|"
                   r"gözaltı|tutuklan|şüpheli|cesed|ceset|bahis|kumar|casino|porno|\+18|seks|uyuşturucu|"
                   r"silah|bomba|patlama|katliam|murder|killed|dead|suicide|terror|porn|casino|betting)", re.I)


def guvenli_konu(konu: str) -> str:
    """Dış kaynaktan (gündem, RSS, Vikipedi) gelen başlığı temizler: link/komut kalıpları çıkarılır,
    uzunluk sınırlanır, reklamverene uygun olmayan konular elenir. Boş dönerse konu kullanılmaz."""
    konu = re.sub(r"https?://\S+|[<>{}\[\]`]", " ", konu)
    konu = re.sub(r"\s+", " ", konu).strip()[:140]
    if not konu or YASAK.search(konu):
        return ""
    if re.search(r"(talimat|instruction|ignore|önceki|system prompt|yok say)", konu, re.I):
        return ""   # yapay zekâya komut sokma girişimi gibi görünen başlıklar
    return konu


def kaynak_adaylari(ayar: Ayarlar, nis: dict) -> dict[str, tuple[float, str]]:
    """Nişin tüm kaynaklarından adaylar: konu -> (talep 0-1, kaynak türü). Aynı konu en yüksek talebi alır."""
    dil = ayar.kanal_bilgi.get("dil", "tr")
    ulke = ayar.kanal_bilgi.get("ulke", "tr" if dil == "tr" else "us")
    aday: dict[str, tuple[str, float, str]] = {}   # normal_ad -> (konu, talep, kaynak)

    def ekle(konu: str, talep: float, tur: str) -> None:
        konu = guvenli_konu(konu) if tur != "youtube_oneri" else konu
        if not konu:
            return
        anahtar = kisa_ad(konu, 80)
        if anahtar and (anahtar not in aday or aday[anahtar][1] < talep):
            aday[anahtar] = (konu, talep, tur)

    for k in nis.get("kaynaklar") or [{"tur": "youtube_oneri"}]:
        tur = k.get("tur", "youtube_oneri")
        if ayar.deneme:
            for i in range(3):
                ekle(f"{nis['ad']} {tur} konusu {i + 1}", 0.9 - i * 0.2, tur)
            continue
        if tur == "youtube_oneri" and nis.get("tohum_kelimeler"):
            ham = talep_puanlari(nis["tohum_kelimeler"], dil=dil, ulke=ulke)
            enb = max(ham.values(), default=1)
            for konu, v in ham.items():
                ekle(konu, round(v / enb, 3), tur)
        elif tur == "google_trendler":
            for konu, v in google_trendler(ulke).items():
                ekle(konu, v, tur)
        elif tur == "rss":
            for konu in rss_basliklari(k.get("adresler") or []):
                ekle(konu, KAYNAK_TALEBI["rss"], tur)
        elif tur == "wikipedia_bugun":
            for konu in wikipedia_bugun(dil, ayar.simdi):
                ekle(konu, KAYNAK_TALEBI["wikipedia_bugun"], tur)
        elif tur == "elle":
            for konu in k.get("konular") or []:
                ekle(str(konu), KAYNAK_TALEBI["elle"], tur)
    return {konu: (talep, tur) for konu, talep, tur in aday.values()}


def calistir(ayar: Ayarlar, konu_basina_rekabet: int = 5) -> dict[str, list[dict]]:
    anahtar = "" if ayar.deneme else gizli("YOUTUBE_API_KEY")
    gecmis = json_oku(VERI / "oneri_gecmisi.json", {})
    yeni_gecmis: dict[str, dict[str, float]] = {}
    sonuc: dict[str, list[dict]] = {}
    for nis in ayar.nisler:
        aday = kaynak_adaylari(ayar, nis)
        if not aday:
            continue
        talep = {k: v[0] for k, v in aday.items()}
        kaynak = {k: v[1] for k, v in aday.items()}
        bonus = trend_bonusu(talep, gecmis.get(nis["kod"], {}))   # yeni çıkan / yükselen aramalar
        yeni_gecmis[nis["kod"]] = talep
        adaylar = sorted(talep.items(), key=lambda x: -(x[1] + bonus.get(x[0], 0)))[:30]
        liste = []
        for sira, (konu, t) in enumerate(adaylar):
            rek = _rekabet(konu, anahtar) if (anahtar and sira < konu_basina_rekabet) else {}
            firsat, etiket = firsat_puani(t, rek)
            b = bonus.get(konu, 0.0)
            liste.append({"konu": konu, "kaynak": kaynak[konu], "talep": t, "rekabet": etiket,
                          "firsat": round(firsat + b, 3),
                          "trend": "yeni" if b == 0.15 and konu not in gecmis.get(nis["kod"], {}) else
                                   ("yükselen" if b > 0 else ""), **rek})
        liste.sort(key=lambda x: -x["firsat"])
        sonuc[nis["kod"]] = liste
        log.info("Niş %s: %d aday konu (%s), %d trend", nis["kod"], len(liste),
                 ", ".join(sorted({x["kaynak"] for x in liste})), sum(1 for x in liste if x["trend"]))
    json_yaz(VERI / "nis_analizi.json", sonuc)
    if yeni_gecmis:
        json_yaz(VERI / "oneri_gecmisi.json", yeni_gecmis)
    return sonuc
