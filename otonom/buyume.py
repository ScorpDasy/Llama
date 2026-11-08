"""YouTube büyüme araçları — bilinirlik için algoritmaya göre küçük, ücretsiz aksiyonlar.

Yayınlanan her video için (günlük çalıştırmada, kota elverdikçe):
  • nişine ait OYNATMA LİSTESİNE eklenir (liste yoksa kendiliğinden açılır)
  • kanal sahibi olarak SORU İÇEREN İLK YORUM yazılır (sabitleme API'de yok → DURUM.md hatırlatır)
  • uzun videolara İNGİLİZCE başlık/açıklama (yerelleştirme) eklenir
  • isteğe bağlı TELEGRAM ve BLUESKY duyurusu yapılır
Ayrıca: günlük YORUM YANITLAMA (en fazla 10), ayda bir KANAL SEO'su, yüklemeden önce İÇ BAĞLANTI satırı,
2-4 günlük zayıf videolarda ERKEN AKSİYON (yeni başlık + yeni küçük resim; 7 gün sonra m11.ab_testi karar verir).

Deneme modunda hiçbir dış servis çağrılmaz. Kota: liste/yorum/güncelleme/küçük resim 50 birim, okuma 1 birim.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from .ayarlar import CIKTI, KANAL_VERI as VERI, Ayarlar, csv_oku, gizli, json_oku, json_yaz, log

DOSYA = VERI / "buyume.json"
LISTELER = VERI / "oynatma_listeleri.json"
GUNLUK_YANIT = 10
YANIT_SEMASI = {"type": "object", "properties": {"uygun": {"type": "boolean"}, "yanit": {"type": "string"}},
                "required": ["uygun", "yanit"]}
CEVIRI_SEMASI = {"type": "object", "properties": {"baslik": {"type": "string"}, "aciklama": {"type": "string"}},
                 "required": ["baslik", "aciklama"]}
_LINK = re.compile(r"https?://|www\.|\.com\b|\.net\b|t\.me/", re.I)


# ------------------------------------------------------------------ ortak

def _durum() -> dict:
    return json_oku(DOSYA, {"videolar": {}, "yanitlanan": [], "yanit_gunu": {}, "seo_ayi": "", "notlar": []})


def _not(d: dict, metin: str) -> None:
    d["notlar"] = ([f"{date.today().isoformat()} · {metin}"] + d.get("notlar", []))[:15]
    log.info("Büyüme: %s", metin)


def _kanal_id(ayar: Ayarlar) -> str:
    return (ayar.kanal_bilgi or {}).get("kanal_id") or next(
        (k.get("kanal_id") for k in ayar.varliklar.get("youtube_kanallari", []) or [] if k.get("kanal_id")), "")


def _api_hazir(ayar: Ayarlar, birim: int) -> bool:
    from .m09_youtube_yukleme import kimlik_var, kota_yeterli
    return not ayar.deneme and ayar.yukleme and kimlik_var() and kota_yeterli(birim)


def _harca(birim: int) -> None:
    from .m09_youtube_yukleme import kota_harca
    kota_harca(birim)


def _yayinda(s: dict, simdi: datetime) -> bool:
    z = s.get("yayin_zamani")
    try:
        return not z or datetime.fromisoformat(z) <= simdi
    except ValueError:
        return True


def _gercek_yayinlar() -> list[dict]:
    return [s for s in csv_oku(VERI / "yayinlananlar.csv")
            if s.get("youtube_id") and not s["youtube_id"].startswith("DENEME")]


# ------------------------------------------------------------- iç bağlantı (kota yok)

def ic_baglanti(ayar: Ayarlar, nis: str, kod: str, tur: str) -> str:
    """Yükleme öncesi açıklamaya eklenecek satır. Shorts → aynı konunun uzun videosu;
    uzun → nişin en çok izlenen videosu (metrikler.csv). Uygun video yoksa boş."""
    yayin = _gercek_yayinlar()
    if tur == "shorts":
        uzun = next((s for s in yayin if s["kod"] == kod and s["tur"] == "uzun"), None)
        return f"▶ Videonun tamamı: https://youtu.be/{uzun['youtube_id']}" if uzun else ""
    en_iyi: dict[str, int] = {}
    for m in csv_oku(VERI / "metrikler.csv"):
        if m.get("nis") == nis and m.get("tur") == "uzun" and m.get("kod") != kod:
            en_iyi[m["youtube_id"]] = max(en_iyi.get(m["youtube_id"], 0), int(m.get("goruntulenme") or 0))
    if not en_iyi:
        return ""
    return f"▶ Şunu da izle: https://youtu.be/{max(en_iyi, key=en_iyi.get)}"


def aciklamaya_ekle(aciklama: str, satir: str) -> str:
    return (satir + "\n\n" + aciklama)[:4900] if satir else aciklama


# ------------------------------------------------------------- oynatma listeleri

def oynatma_listesi(ayar: Ayarlar, nis: str) -> str | None:
    listeler = json_oku(LISTELER, {})
    if listeler.get(nis):
        return listeler[nis]
    if not _api_hazir(ayar, 50):
        return None
    from .m09_youtube_yukleme import servis
    bilgi = ayar.nis(nis) if any(n.get("kod") == nis for n in ayar.nisler) else {}
    ad = bilgi.get("ad") or nis
    govde = {"snippet": {"title": ad[:150], "defaultLanguage": ayar.kanal_bilgi.get("dil", "tr") if ayar.kanal_bilgi else "tr",
                         "description": f"{ad} hakkındaki tüm videolar. {bilgi.get('hedef_kitle', '')}".strip()[:4900]},
             "status": {"privacyStatus": "public"}}
    cevap = servis().playlists().insert(part="snippet,status", body=govde).execute()
    _harca(50)
    listeler[nis] = cevap["id"]
    json_yaz(LISTELER, listeler)
    return cevap["id"]


def listeye_ekle(ayar: Ayarlar, vid: str, nis: str) -> bool:
    liste = oynatma_listesi(ayar, nis)
    if not liste or not _api_hazir(ayar, 50):
        return False
    from .m09_youtube_yukleme import servis
    servis().playlistItems().insert(part="snippet", body={"snippet": {
        "playlistId": liste, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
    _harca(50)
    return True


# ------------------------------------------------------------- sahip yorumu

def soru_yorumu(baslik: str, tur: str) -> str:
    konu = re.sub(r"\s*#\w+", "", baslik).strip().rstrip("?!.")
    if tur == "shorts":
        return f"Sence de öyle mi? 🤔 '{konu}' hakkında ne düşündüğünü yorumlara yaz, en iyi yorumları yanıtlıyorum 👇"
    return (f"İzlediğin için teşekkürler! 🙏 '{konu}' hakkında senin deneyimin ne? "
            "Bir sonraki videoda hangi soruyu cevaplayalım? Yorumlara yaz 👇")


def sahip_yorumu(ayar: Ayarlar, vid: str, baslik: str, tur: str) -> bool:
    kanal = _kanal_id(ayar)
    if not kanal or not _api_hazir(ayar, 50):
        return False
    from .m09_youtube_yukleme import servis
    servis().commentThreads().insert(part="snippet", body={"snippet": {
        "channelId": kanal, "videoId": vid,
        "topLevelComment": {"snippet": {"textOriginal": soru_yorumu(baslik, tur)}}}}).execute()
    _harca(50)
    return True


# ------------------------------------------------------------- yerelleştirme

def ingilizce(ayar: Ayarlar, baslik: str, aciklama: str) -> dict:
    from . import llm
    return llm.json_uret(
        ayar, "yerellestirme",
        "You translate YouTube titles and descriptions from Turkish to natural, click-worthy English. "
        "Keep URLs, timestamps and hashtags unchanged. Title max 100 characters.",
        f"TITLE:\n{baslik}\n\nDESCRIPTION:\n{aciklama[:3000]}", CEVIRI_SEMASI,
        sahte=lambda: {"baslik": "EN: " + baslik, "aciklama": "EN: " + aciklama[:200]}, max_tokens=2000)


def yerellestir(ayar: Ayarlar, vid: str) -> bool:
    """Uzun videoya İngilizce başlık/açıklama ekler (1 okuma + 50 güncelleme)."""
    dil = (ayar.kanal_bilgi or {}).get("dil", "tr")
    if dil != "tr" or not _api_hazir(ayar, 51):
        return False
    from .m09_youtube_yukleme import servis
    yt = servis()
    ogeler = yt.videos().list(part="snippet,localizations", id=vid).execute().get("items", [])
    _harca(1)
    if not ogeler:
        return False
    snip = ogeler[0]["snippet"]
    ceviri = ingilizce(ayar, snip["title"], snip.get("description", ""))
    yerel = {**ogeler[0].get("localizations", {}),
             "en": {"title": ceviri["baslik"][:100], "description": ceviri["aciklama"][:4900]}}
    govde = {"id": vid, "localizations": yerel,
             "snippet": {k: snip[k] for k in ("title", "description", "tags", "categoryId") if k in snip}}
    govde["snippet"]["defaultLanguage"] = snip.get("defaultLanguage") or "tr"
    yt.videos().update(part="snippet,localizations", body=govde).execute()
    _harca(50)
    return True


# ------------------------------------------------------------- paylaşım (Telegram / Bluesky)

def duyuru_metni(baslik: str, vid: str) -> str:
    temiz = re.sub(r"\s*#Shorts", "", baslik).strip()
    return f"🎬 Yeni video: {temiz}\nhttps://youtu.be/{vid}"


def telegram(metin: str) -> bool:
    jeton, kanal = gizli("TELEGRAM_BOT_TOKEN"), gizli("TELEGRAM_KANAL")
    if not (jeton and kanal):
        return False
    r = requests.post(f"https://api.telegram.org/bot{jeton}/sendMessage", timeout=30,
                      json={"chat_id": kanal, "text": metin})
    return r.ok


def bluesky(metin: str) -> bool:
    kullanici, sifre = gizli("BLUESKY_KULLANICI"), gizli("BLUESKY_SIFRE")
    if not (kullanici and sifre):
        return False
    api = "https://bsky.social/xrpc/"
    oturum = requests.post(api + "com.atproto.server.createSession", timeout=30,
                           json={"identifier": kullanici, "password": sifre})
    if not oturum.ok:
        return False
    o = oturum.json()
    metin = metin[:300]
    kayit = {"$type": "app.bsky.feed.post", "text": metin,
             "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "facets": []}
    for m in re.finditer(r"https?://\S+", metin):  # bağlantı tıklanabilir olsun (bayt konumları)
        bas, son = len(metin[:m.start()].encode()), len(metin[:m.end()].encode())
        kayit["facets"].append({"index": {"byteStart": bas, "byteEnd": son},
                                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group()}]})
    r = requests.post(api + "com.atproto.repo.createRecord", timeout=30,
                      headers={"Authorization": f"Bearer {o['accessJwt']}"},
                      json={"repo": o["did"], "collection": "app.bsky.feed.post", "record": kayit})
    return r.ok


def paylas(ayar: Ayarlar, vid: str, baslik: str) -> list[str]:
    if ayar.deneme:
        return []
    metin, yapilan = duyuru_metni(baslik, vid), []
    for ad, f in (("telegram", telegram), ("bluesky", bluesky)):
        try:
            if f(metin):
                yapilan.append(ad)
        except requests.RequestException as e:
            log.warning("%s paylaşımı başarısız: %s", ad, e)
    return yapilan


# ------------------------------------------------------------- yorum yanıtlama

def yanitlanabilir(metin: str) -> bool:
    """Bağlantı içeren, çok kısa veya çok uzun yorumlar yapay zekâya hiç gönderilmez."""
    metin = metin.strip()
    return 3 <= len(metin) <= 1500 and not _LINK.search(metin)


def yanit_uret(ayar: Ayarlar, yorum: str, baslik: str) -> dict:
    from . import llm
    return llm.json_uret(
        ayar, "yorum_yaniti",
        "Bir YouTube kanalının sahibisin. Yoruma kısa (1-2 cümle), samimi, saygılı ve videonun diliyle yanıt ver. "
        "Spam, reklam, bağlantı, hakaret, siyaset/kışkırtma veya tıbbi teşhis isteği varsa uygun=false döndür. "
        "Asla bağlantı verme, kişisel bilgi isteme, söz verme.",
        f"Video: {baslik}\nYorum: {yorum[:1500]}", YANIT_SEMASI,
        sahte=lambda: {"uygun": False, "yanit": ""}, max_tokens=300)


def yorum_yanitla(ayar: Ayarlar, en_fazla: int = GUNLUK_YANIT) -> int:
    kanal = _kanal_id(ayar)
    if not kanal or not _api_hazir(ayar, 1):
        return 0
    from .m09_youtube_yukleme import servis
    d = _durum()
    gun = ayar.simdi.date().isoformat()
    sayac = d.get("yanit_gunu", {}).get(gun, 0)
    if sayac >= en_fazla:
        return 0
    yt = servis()
    cevap = yt.commentThreads().list(part="snippet", allThreadsRelatedToChannelId=kanal, maxResults=50,
                                     order="time", textFormat="plainText").execute()
    _harca(1)
    yanitlanan = set(d.get("yanitlanan", []))
    basliklar = {s["youtube_id"]: s["baslik"] for s in csv_oku(VERI / "yayinlananlar.csv")}
    yeni = 0
    for t in cevap.get("items", []):
        if sayac >= en_fazla or not _api_hazir(ayar, 50):
            break
        sn = t["snippet"]
        ust = sn["topLevelComment"]["snippet"]
        tid = t["id"]
        if tid in yanitlanan or sn.get("totalReplyCount", 0) > 0 \
                or (ust.get("authorChannelId") or {}).get("value") == kanal:
            continue
        yanitlanan.add(tid)  # uygun bulunmasa da bir daha değerlendirilmez
        metin = ust.get("textDisplay") or ust.get("textOriginal") or ""
        if not yanitlanabilir(metin):
            continue
        karar = yanit_uret(ayar, metin, basliklar.get(sn.get("videoId", ""), ""))
        yanit = (karar.get("yanit") or "").strip()
        if not karar.get("uygun") or not yanit or _LINK.search(yanit):
            continue
        yt.comments().insert(part="snippet", body={"snippet": {"parentId": tid, "textOriginal": yanit[:500]}}).execute()
        _harca(50)
        sayac += 1
        yeni += 1
    d["yanitlanan"] = sorted(yanitlanan)[-2000:]
    d["yanit_gunu"] = {gun: sayac}
    if yeni:
        _not(d, f"{yeni} yoruma yanıt verildi")
    json_yaz(DOSYA, d)
    return yeni


# ------------------------------------------------------------- kanal SEO

def kanal_metni(ayar: Ayarlar) -> tuple[str, str]:
    """Kanal açıklaması ve anahtar kelimeleri (YouTube boşlukla ayırır; çok kelimeli olanlar tırnaklı)."""
    bilgi = ayar.kanal_bilgi or {}
    ad = bilgi.get("ad") or "Kanal"
    nisler = [n.get("ad", n.get("kod", "")) for n in ayar.nisler]
    kitle = next((n.get("hedef_kitle") for n in ayar.nisler if n.get("hedef_kitle")), "")
    aciklama = (f"{ad}: {', '.join(nisler)} hakkında kısa, anlaşılır ve kaynaklı videolar. "
                + (f"Kimin için? {kitle}. " if kitle else "")
                + "Her hafta yeni uzun videolar ve günlük Shorts. Abone ol, bildirimi aç; "
                  "merak ettiğin konuyu yorumlara yaz, sıradaki videoyu birlikte seçelim.")
    kelimeler: list[str] = []
    for n in ayar.nisler:
        kelimeler += [n.get("ad", "")] + list(n.get("tohum_kelimeler") or [])
    temiz = [k.replace('"', "").strip() for k in kelimeler if k and k.strip()]
    anahtar = " ".join(f'"{k}"' if " " in k else k for k in dict.fromkeys(temiz))
    while len(anahtar) > 480:
        anahtar = anahtar.rsplit(" ", 1)[0]
    return aciklama[:1000], anahtar


def kanal_seo(ayar: Ayarlar) -> bool:
    """Ayda bir: kanal açıklaması + anahtar kelimeler (1 okuma + 50 güncelleme)."""
    d = _durum()
    ay = ayar.simdi.strftime("%Y-%m")
    if d.get("seo_ayi") == ay or not _api_hazir(ayar, 51):
        return False
    from .m09_youtube_yukleme import servis
    yt = servis()
    ogeler = yt.channels().list(part="brandingSettings", mine=True).execute().get("items", [])
    _harca(1)
    if not ogeler:
        return False
    marka = ogeler[0].get("brandingSettings", {})
    aciklama, anahtar = kanal_metni(ayar)
    kanal = {**marka.get("channel", {}), "description": aciklama, "keywords": anahtar}
    kanal.setdefault("defaultLanguage", (ayar.kanal_bilgi or {}).get("dil", "tr"))
    yt.channels().update(part="brandingSettings",
                         body={"id": ogeler[0]["id"], "brandingSettings": {"channel": kanal}}).execute()
    _harca(50)
    d["seo_ayi"] = ay
    _not(d, "Kanal açıklaması ve anahtar kelimeleri güncellendi")
    json_yaz(DOSYA, d)
    return True


# ------------------------------------------------------------- erken aksiyon (algoritma)

def erken_adaylar(videolar: list[dict], esik: float = 25.0) -> list[dict]:
    """2-4 günlük uzun videolar içinde yaşa göre puanı çok düşük olanlar (en az 5 uzun video gerekir)."""
    from .m11_analiz import puanla
    uzun = [dict(v) for v in videolar if v.get("tur") == "uzun"]
    if len(uzun) < 5:
        return []
    puanla(uzun)
    return sorted((v for v in uzun if 2 <= v["yas_gun"] <= 4 and v["skor"] < esik), key=lambda v: v["skor"])


def _yeni_kucuk_resim(ayar: Ayarlar, v: dict, icerik: dict, yazi: str) -> Path | None:
    from . import gorsel, m06_materyal
    klasor = CIKTI / v["kod"]
    klasor.mkdir(parents=True, exist_ok=True)
    arka = klasor / "erken_arka.jpg"
    sorgu = next((s.get("gorsel_arama") for s in icerik.get("sahneler", []) if s.get("gorsel_arama")), yazi)
    if not m06_materyal._yapay_zeka_gorseli(ayar, sorgu, False, arka):
        gorsel.yazi_karti("", arka, 1280, 720, gorsel.renk(v["nis"]))
    return gorsel.kucuk_resim(arka, yazi, klasor / "thumbnail_erken.jpg", gorsel.renk(v["nis"]))


def erken_aksiyon(ayar: Ayarlar, videolar: list[dict], bugun: date, en_fazla: int = 1) -> list[str]:
    """Zayıf başlayan videoda başlığı ikinci alternatifle değiştirir ve yeni küçük resim yükler.
    Kayıt m11 A/B dosyasına 'test' olarak eklenir: 7 gün sonra ab_testi kazananı seçer/geri alır."""
    from . import m11_analiz
    from .m09_youtube_yukleme import kimlik_var
    if ayar.deneme or not kimlik_var():
        return []
    testler = m11_analiz.csv_oku(m11_analiz.AB_DOSYASI)
    denenen = {t["youtube_id"] for t in testler}
    notlar = []
    for v in [v for v in erken_adaylar(videolar) if v["youtube_id"] not in denenen][:en_fazla]:
        icerik = json_oku(VERI / "videolar" / v["kod"] / "icerik.json", {})
        alt = icerik.get("alternatif_basliklar") or []
        yeni = alt[1] if len(alt) > 1 else (alt[0] if alt else "")
        if not yeni or not _api_hazir(ayar, 101) or not m11_analiz._baslik_degistir(v["youtube_id"], yeni):
            continue
        resim_notu = ""
        try:
            resim = _yeni_kucuk_resim(ayar, v, icerik, yeni[:40])
            from googleapiclient.http import MediaFileUpload

            from .m09_youtube_yukleme import servis
            if resim and _api_hazir(ayar, 50):
                servis().thumbnails().set(videoId=v["youtube_id"], media_body=MediaFileUpload(str(resim))).execute()
                _harca(50)
                resim_notu = " + yeni küçük resim"
        except Exception as e:  # küçük resim isteğe bağlı: başlık testi yine sürer
            log.warning("Erken aksiyon küçük resmi yüklenemedi: %s", e)
        m11_analiz.csv_ekle(m11_analiz.AB_DOSYASI, [{
            "tarih": bugun.isoformat(), "youtube_id": v["youtube_id"], "kod": v["kod"], "eski_baslik": v["baslik"],
            "yeni_baslik": yeni, "izlenme_once": v["goruntulenme"],
            "hiz_once": f"{v['goruntulenme'] / max(1, v['yas_gun']):.1f}", "hiz_sonra": "", "durum": "test"}],
            m11_analiz.AB_ALANLARI)
        notlar.append(f"⚡ Erken aksiyon: '{v['baslik']}' → '{yeni}'{resim_notu}")
    if notlar:
        d = _durum()
        for n in notlar:
            _not(d, n)
        json_yaz(DOSYA, d)
    return notlar


# ------------------------------------------------------------- günlük akış

def yayin_sonrasi(ayar: Ayarlar) -> dict[str, int]:
    """Yayına giren her video için eksik adımları tamamlar (her adım bir kez; kota biterse yarın sürer)."""
    sayac = {"liste": 0, "yorum": 0, "yerel": 0, "paylasim": 0}
    if ayar.deneme:
        return sayac
    d = _durum()
    for s in _gercek_yayinlar():
        if not _yayinda(s, ayar.simdi):
            continue
        yapilan = set(d["videolar"].get(s["youtube_id"], []))
        adimlar = [("liste", lambda: listeye_ekle(ayar, s["youtube_id"], s["nis"])),
                   ("yorum", lambda: sahip_yorumu(ayar, s["youtube_id"], s["baslik"], s["tur"])),
                   ("paylasim", lambda: bool(paylas(ayar, s["youtube_id"], s["baslik"])))]
        if s["tur"] == "uzun":
            adimlar.insert(2, ("yerel", lambda: yerellestir(ayar, s["youtube_id"])))
        for ad, f in adimlar:
            if ad in yapilan:
                continue
            try:
                if f():
                    sayac[ad] += 1
                    yapilan.add(ad)
                elif ad == "paylasim":   # anahtar yoksa tekrar denenmez
                    yapilan.add(ad)
            except Exception as e:
                log.warning("Büyüme adımı (%s, %s) başarısız: %s", ad, s["youtube_id"], e)
        d["videolar"][s["youtube_id"]] = sorted(yapilan)
    ozet = ", ".join(f"{k}: {v}" for k, v in sayac.items() if v)
    if ozet:
        _not(d, "Yayın sonrası — " + ozet)
    json_yaz(DOSYA, d)
    return sayac


def calistir(ayar: Ayarlar, videolar: list[dict] | None = None) -> dict:
    if ayar.deneme:
        log.info("Büyüme araçları: deneme modu, dış servis çağrısı yok.")
        return {}
    sonuc = {"yayin": yayin_sonrasi(ayar), "yanit": yorum_yanitla(ayar), "seo": kanal_seo(ayar)}
    if videolar:
        sonuc["erken"] = erken_aksiyon(ayar, videolar, ayar.simdi.date())
    return sonuc


# ------------------------------------------------------------- DURUM.md

def durum_bolumu(ayar: Ayarlar) -> list[str]:
    """Tüm kanalların büyüme özetini toplar (DURUM.md genel süreçte yazılır)."""
    from .ayarlar import KANALLAR_VERI, kanal_bilgisi, kanal_listesi
    paylasim = [ad for ad, k in (("Telegram", "TELEGRAM_BOT_TOKEN"), ("Bluesky", "BLUESKY_KULLANICI")) if gizli(k)]
    gun = ayar.simdi.date().isoformat()
    md = ["", "## 🚀 Büyüme",
          f"- Paylaşım: **{', '.join(paylasim) or 'kapalı (isteğe bağlı: TELEGRAM_BOT_TOKEN + TELEGRAM_KANAL, '
                                                    'BLUESKY_KULLANICI + BLUESKY_SIFRE)'}**"]
    for k in kanal_listesi():
        klasor = KANALLAR_VERI / k
        d = json_oku(klasor / "buyume.json", {})
        listeler = json_oku(klasor / "oynatma_listeleri.json", {})
        md.append(f"- **{k}** · oynatma listesi: {len(listeler)} · bugün yanıtlanan yorum: "
                  f"{d.get('yanit_gunu', {}).get(gun, 0)}/{GUNLUK_YANIT} · kanal SEO: {d.get('seo_ayi') or 'henüz yok'}")
        if not kanal_bilgisi(k).get("kanal_id"):
            md.append(f"  - ⚠️ `config/kanallar/{k}.yaml` içine `kanal_id` yazılmadı: sahip yorumu ve yorum yanıtlama kapalı.")
        yorumlu = [v for v, a in d.get("videolar", {}).items() if "yorum" in a]
        if yorumlu:
            md.append("  - 📌 Sabitlemeyi unutma (API yapamıyor): YouTube Studio'da kendi yorumunu sabitle: "
                      + ", ".join(f"[{v}](https://youtu.be/{v})" for v in yorumlu[-3:]))
        md += [f"  - {n}" for n in d.get("notlar", [])[:3]]
    return md
