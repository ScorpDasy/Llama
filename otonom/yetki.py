"""Tek tıkla yetki — Google/YouTube anahtarlarını sistem kendisi alır; sen yalnızca "İzin ver"e basarsın.

Akış (GitHub Actions'ta, ücretsiz):
1. Sistem her gün anahtarları dener. Eksik ya da bozuk olan kanal için GitHub'da bir konu (issue) açar
   → telefonuna bildirim gelir.
2. Konuya **onay** yazarsın. Sistem, 25 dakika geçerli tek kullanımlık bir onay bağlantısı gönderir
   (PKCE + rastgele "state"; bekleyen istek özel Cloudflare KV'ye yazılır).
3. Bağlantıya dokunursun, Google'da hesabını/kanalını seçip "İzin ver"e basarsın.
4. Google seni kendi sitendeki /api/yetki sayfasına geri gönderir; sayfa tek kullanımlık kodu KV'ye bırakır.
5. Bekleyen iş kodu alır ve anahtara çevirir. Seçilen kanalın doğru kanal olup olmadığını doğrular.
   Anahtarı GitHub Secrets'a (GH_YONETICI_TOKEN varsa) ya da özel Cloudflare KV kasasına kaydeder.
6. YouTube onayından sonra kanal kurulumu kendiliğinden yapılır (açıklama, anahtar kelimeler, büyüme adımları).
   Google onayından sonra projedeki gerekli Google API'leri kendiliğinden açılır.
Bağlantı herkese açık konuda görünse bile işe yaramaz. PKCE doğrulayıcısı ve istemci sırrı yalnızca
GitHub sunucusundadır. Yanlış kanal seçilirse anahtar kaydedilmez.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from urllib.parse import quote, urlencode

import requests

from .ayarlar import (KANALLAR_VERI, VERI, Ayarlar, gizli, json_oku, json_yaz, kanal_bilgisi, kanal_listesi,
                      kisa_ad, log)

GOOGLE_YETKI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_G = "https://www.googleapis.com/auth/"
HIZMETLER = {
    # Her kanal için: yükleme, yorum/altyazı/oynatma listesi/kanal ayarı, izlenme ve gelir raporu
    "youtube": [_G + "youtube.upload", _G + "youtube.force-ssl", _G + "yt-analytics.readonly",
                _G + "yt-analytics-monetary.readonly"],
    # Bir kez, ana Google hesabı için: arama motoru kaydı + projede gerekli API'leri açma
    "google": ["openid", "email", _G + "siteverification", _G + "webmasters", _G + "service.management"],
}
GOOGLE_APILERI = ["youtube.googleapis.com", "youtubeanalytics.googleapis.com",
                  "siteverification.googleapis.com", "searchconsole.googleapis.com"]
BEKLEME_DK = 25
KANAL_RE = r"[a-z0-9][a-z0-9-]{0,39}"
ISARET = re.compile(rf"<!-- yetki kanal=({KANAL_RE}) hizmet=(youtube|google) -->")
KURULUM_ISARETI = "<!-- yetki-kurulum -->"
KASA_ONEK = "kasa:"
DURUM = VERI / "yetki.json"


# ------------------------------------------------------------ yardımcılar

def isaret(kanal: str, hizmet: str) -> str:
    return f"<!-- yetki kanal={kanal} hizmet={hizmet} -->"


def pkce() -> tuple[str, str]:
    """(doğrulayıcı, meydan okuma): kod, doğrulayıcı olmadan anahtara çevrilemez."""
    dogrulayici = secrets.token_urlsafe(64)
    meydan = base64.urlsafe_b64encode(hashlib.sha256(dogrulayici.encode()).digest()).rstrip(b"=").decode()
    return dogrulayici, meydan


def onay_baglantisi(hizmet: str, yonlendirme: str, istemci: str, durum: str, meydan: str, ipucu: str = "") -> str:
    p = {"client_id": istemci, "redirect_uri": yonlendirme, "response_type": "code",
         "scope": " ".join(HIZMETLER[hizmet]), "access_type": "offline",
         "prompt": "consent select_account",  # kanal seçme ekranı her zaman gelsin
         "state": durum, "code_challenge": meydan, "code_challenge_method": "S256"}
    if ipucu:
        p["login_hint"] = ipucu
    return GOOGLE_YETKI + "?" + urlencode(p)


def yonlendirme_adresi(ayar: Ayarlar) -> str:
    """Google'ın onaydan sonra döneceği adres: ilk alan adının Cloudflare Pages sitesi (/api/yetki)."""
    adres = str((ayar.genel.get("yetki") or {}).get("adres") or "").strip()
    if adres:
        return adres.rstrip("/")
    if not ayar.alan_adlari:
        return ""
    proje = kisa_ad(ayar.alan_adlari[0]["ad"], 58)  # mikro_site.proje_adi ile aynı
    alt = f"{proje}.pages.dev"
    from . import cloudflare_kur
    if cloudflare_kur.hazir() and not ayar.deneme:
        r = cloudflare_kur._istek("GET", f"/accounts/{gizli('CLOUDFLARE_ACCOUNT_ID')}/pages/projects/{proje}")
        alt = (r.get("result") or {}).get("subdomain") or alt
    return f"https://{alt}/api/yetki"


def eposta(id_token: str) -> str:
    """Google'dan doğrudan (TLS ile) alınan kimlik belgesinden e-posta."""
    try:
        govde = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(govde + "=" * (-len(govde) % 4))).get("email", "")
    except (IndexError, ValueError):
        return ""


# --------------------------------------------- özel kasa (Cloudflare KV)

def _kv(yontem: str, anahtar: str, **kw) -> requests.Response | None:
    from .m12_gelir import _baslik, _kv_url
    url = _kv_url(f"/values/{quote(anahtar, safe='')}")
    if not url:
        return None
    try:
        return requests.request(yontem, url, headers=_baslik(), timeout=20, **kw)
    except requests.RequestException:
        return None


def kasa_oku(ad: str) -> str:
    r = _kv("GET", KASA_ONEK + ad)
    return r.text.strip() if r is not None and r.status_code == 200 else ""


def kasa_yaz(ad: str, deger: str) -> bool:
    r = _kv("PUT", KASA_ONEK + ad, data=deger.encode())
    return bool(r is not None and r.ok)


def github_gizli_yaz(ad: str, deger: str) -> bool:
    """GH_YONETICI_TOKEN (yalnızca bu depo, 'Secrets: Read and write') varsa anahtarı GitHub Secrets'a yazar."""
    token, depo = gizli("GH_YONETICI_TOKEN"), os.environ.get("GITHUB_REPOSITORY", "")
    if not (token and depo):
        return False
    try:
        from nacl import encoding, public
    except ImportError:
        log.warning("pynacl kurulu değil; anahtar GitHub Secrets'a yazılamadı.")
        return False
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    kok = f"https://api.github.com/repos/{depo}/actions/secrets"
    try:
        r = requests.get(kok + "/public-key", headers=h, timeout=20)
        if not r.ok:
            log.warning("GitHub anahtarı alınamadı (%s): token izinlerini kontrol et.", r.status_code)
            return False
        k = r.json()
        kutu = public.SealedBox(public.PublicKey(k["key"].encode(), encoding.Base64Encoder()))
        sifreli = base64.b64encode(kutu.encrypt(deger.encode())).decode()
        r = requests.put(f"{kok}/{ad}", headers=h, timeout=20,
                         json={"encrypted_value": sifreli, "key_id": k["key_id"]})
        return r.status_code in (201, 204)
    except (requests.RequestException, ValueError, KeyError):
        return False


def kaydet(ad: str, deger: str) -> str:
    """Özel Cloudflare KV kasasına (her iş ve her kanal buradan okur) ve GH_YONETICI_TOKEN varsa GitHub Secrets'a.
    Döner: nereye kaydedildiği ('' = kaydedilemedi)."""
    yerler = []
    if kasa_yaz(ad, deger):
        yerler.append("özel Cloudflare KV kasası")
    if github_gizli_yaz(ad, deger):
        yerler.append("GitHub Secrets")
    return " ve ".join(yerler)


# ------------------------------------------------------- Google işlemleri

def _istemci_post(veri: dict) -> dict:
    try:
        r = requests.post(GOOGLE_TOKEN, timeout=30, data={
            "client_id": gizli("YT_CLIENT_ID"), "client_secret": gizli("YT_CLIENT_SECRET"), **veri})
        return r.json()
    except (requests.RequestException, ValueError) as e:
        return {"error": "baglanti", "error_description": str(e)[:200]}


def kodu_degistir(kod: str, dogrulayici: str, yonlendirme: str) -> dict:
    return _istemci_post({"code": kod, "redirect_uri": yonlendirme, "grant_type": "authorization_code",
                          "code_verifier": dogrulayici})


def anahtar_gecerli(yenileme: str) -> tuple[bool | None, str]:
    """(True=çalışıyor / False=bozuk / None=şu an denenemedi, kısa sebep)."""
    if not yenileme:
        return False, "anahtar yok"
    t = _istemci_post({"refresh_token": yenileme, "grant_type": "refresh_token"})
    if t.get("access_token"):
        return True, ""
    hata = t.get("error", "")
    if hata in ("invalid_grant", "unauthorized_client", "invalid_client"):
        return False, {"invalid_grant": "anahtarın süresi dolmuş ya da iptal edilmiş",
                       "unauthorized_client": "anahtar başka bir Google istemcisine ait",
                       "invalid_client": "YT_CLIENT_ID / YT_CLIENT_SECRET hatalı"}[hata]
    return None, hata or "bilinmeyen hata"


def youtube_kanali(erisim: str) -> dict:
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/channels", timeout=20,
                         params={"part": "snippet", "mine": "true"},
                         headers={"Authorization": f"Bearer {erisim}"})
    except requests.RequestException as e:
        return {"hata": f"YouTube'a ulaşılamadı: {e}"}
    if r.status_code == 403 and ("accessNotConfigured" in r.text or "SERVICE_DISABLED" in r.text):
        return {"hata": "Google projesinde YouTube Data API kapalı. Önce Google hesabı onayını ver "
                        "(Actions > Yetki al > kanal: google), API'ler kendiliğinden açılır."}
    ogeler = (r.json().get("items") or []) if r.ok else []
    if not ogeler:
        return {"hata": "Seçilen hesapta YouTube kanalı yok. Önce https://www.youtube.com/create_channel "
                        "adresinden kanal aç (aynı Google hesabında birden çok kanal açılabilir), sonra tekrar onay ver."}
    return {"id": ogeler[0]["id"], "baslik": ogeler[0]["snippet"]["title"]}


def baglanti_sorunu(kanal: str, yt: dict, degistir: bool = False) -> str:
    """Yanlış kanal seçilmesini engeller. '' = uygun."""
    beklenen = str(kanal_bilgisi(kanal).get("youtube_kanal_id") or "")
    if beklenen and beklenen != yt["id"]:
        return f"Ayarlarda bu kanal için {beklenen} kimlikli YouTube kanalı yazıyor; “{yt['baslik']}” seçildi."
    eski = json_oku(KANALLAR_VERI / kanal / "youtube_kanali.json", {}) or {}
    if eski.get("id") and eski["id"] != yt["id"] and not degistir:
        return (f"Bu kanal daha önce “{eski.get('baslik')}” YouTube kanalına bağlıydı; şimdi “{yt['baslik']}” "
                "seçildi. Gerçekten değiştirmek istiyorsan konuya **onay değiştir** yaz.")
    for d in KANALLAR_VERI.glob("*/youtube_kanali.json"):
        if d.parent.name != kanal and (json_oku(d, {}) or {}).get("id") == yt["id"]:
            return f"“{yt['baslik']}” zaten '{d.parent.name}' kanalına bağlı. Bu kanal için başka bir YouTube kanalı seç."
    return ""


def apileri_ac(erisim: str) -> list[str]:
    """Projede gerekli Google API'lerini açar (proje numarası istemci kimliğinin başındadır)."""
    proje = gizli("YT_CLIENT_ID").split("-")[0]
    if not proje.isdigit():
        return []
    try:
        r = requests.post(f"https://serviceusage.googleapis.com/v1/projects/{proje}/services:batchEnable",
                          headers={"Authorization": f"Bearer {erisim}"}, json={"serviceIds": GOOGLE_APILERI},
                          timeout=60)
    except requests.RequestException:
        return []
    if not r.ok:
        log.warning("Google API'leri açılamadı (%s): %s", r.status_code, r.text[:200])
        return []
    return GOOGLE_APILERI


def api_baglantilari() -> str:
    proje = gizli("YT_CLIENT_ID").split("-")[0]
    ek = f"?project={proje}" if proje.isdigit() else ""
    return ", ".join(f"[{a.split('.')[0]}](https://console.cloud.google.com/apis/library/{a}{ek})"
                     for a in GOOGLE_APILERI)


# ------------------------------------------------------ GitHub konuları

def _github(yontem: str, yol: str, **kw):
    from .muhendis import _github as gh
    return gh(yontem, yol, **kw)


def yorum_yaz(konu: int | None, metin: str) -> None:
    log.info("Yetki: %s", re.sub(r"\(https://accounts\.google\.com[^)]*\)", "(bağlantı)", metin)[:300])
    if konu:
        _github("POST", f"/issues/{konu}/comments", json={"body": metin})


def konu_kapat(konu: int | None) -> None:
    if konu:
        _github("PATCH", f"/issues/{konu}", json={"state": "closed", "state_reason": "completed"})


def konu_ac(baslik: str, govde: str, isaret_metni: str) -> int | None:
    """Aynı işaretli açık konu varsa onu döndürür, yoksa yenisini açar."""
    acik = _github("GET", "/issues", params={"state": "open", "per_page": 100})
    if acik is not None and acik.ok:
        for i in acik.json():
            if isaret_metni in (i.get("body") or ""):
                return i["number"]
    r = _github("POST", "/issues", json={"title": baslik, "body": f"{govde}\n\n{isaret_metni}", "labels": ["yetki"]})
    return r.json().get("number") if r is not None and r.ok else None


def onay_konusu(kanal: str, hizmet: str, sebep: str = "") -> int | None:
    ad = "Google hesabı (arama motorları + API'ler)" if hizmet == "google" else f"'{kanal}' kanalı (YouTube)"
    govde = (f"{'**Sebep:** ' + sebep + chr(10) + chr(10) if sebep else ''}"
             "Bu konuya yalnızca **onay** yaz. Sistem 1 dakika içinde bir bağlantı gönderecek; bağlantıya dokun, "
             "Google'da " + ("YouTube kanalını" if hizmet == "youtube" else "hesabını") +
             " seç ve **İzin ver**'e bas. Gerisini sistem kendisi yapar (anahtarı kaydeder, kanalı kurar, "
             "bu konuyu kapatır).\n\n_Google “Bu uygulama doğrulanmadı” derse: Gelişmiş → (uygulama adı) sayfasına "
             "git. Bu senin kendi uygulaman, güvenlidir._")
    return konu_ac(f"🔑 Onay gerekiyor: {ad}", govde, isaret(kanal, hizmet))


# ----------------------------------------------------------- ana akış

def on_kosullar(ayar: Ayarlar) -> list[str]:
    """Tek tıkla onay için bir kerelik (elle) yapılması gerekenler."""
    from . import cloudflare_kur
    eksik = []
    if not (gizli("YT_CLIENT_ID") and gizli("YT_CLIENT_SECRET")):
        eksik.append("Google istemcisi (YT_CLIENT_ID, YT_CLIENT_SECRET) — README 'Tek tıkla yetki' bölümü, adım 1")
    if not cloudflare_kur.hazir():
        eksik.append("Cloudflare anahtarı (CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID) — README bölüm B")
    if not yonlendirme_adresi(ayar):
        eksik.append("En az bir alan adı (config/varliklar.yaml) ya da config/ayarlar.yaml > yetki > adres")
    return eksik


def _bekle(durum: str, dakika: int = BEKLEME_DK) -> dict | None:
    bitis = time.time() + dakika * 60
    while time.time() < bitis:
        r = _kv("GET", "yetki:" + durum)
        if r is not None and r.status_code == 200:
            _kv("DELETE", "yetki:" + durum)
            try:
                return json.loads(r.text)
            except ValueError:
                return None
        time.sleep(8)
    return None


def _site_hazir(yon: str) -> bool:
    """Dönüş sayfası yüklenmiş mi? (Bilinmeyen 'state' ile 400 + bizim sayfa beklenir.)"""
    try:
        r = requests.get(yon, params={"state": "x"}, timeout=20)
        return "onay bağlantısıyla" in r.text
    except requests.RequestException:
        return False


def kanal_kur(kanal: str, ad: str, yenileme: str) -> bool:
    """Onaydan hemen sonra kanalın büyüme/kurulum adımları (kanal açıklaması, anahtar kelimeler, yorumlar...)."""
    ortam = {**os.environ, ad: yenileme, "OTONOM_KANAL": kanal}
    try:
        return subprocess.run([sys.executable, "-m", "otonom", "buyume", "--kanal", kanal],
                              env=ortam, timeout=1200).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def onay_al(ayar: Ayarlar, kanal: str, hizmet: str, konu: int | None = None, degistir: bool = False) -> bool:
    konu = konu or onay_konusu(kanal, hizmet)  # her sonuç (eksik kurulum dahil) konuda görünsün
    eksik = on_kosullar(ayar)
    if eksik:
        yorum_yaz(konu, "⚠️ Önce bir kerelik kurulum gerekiyor:\n" + "\n".join(f"- {e}" for e in eksik))
        return False
    yon = yonlendirme_adresi(ayar)
    if not _site_hazir(yon):
        yorum_yaz(konu, f"⏳ Dönüş sayfası ({yon}) henüz yüklenmemiş. Ana iş akışı bir kez çalışınca "
                        "(Actions > Otonom sistem > Run workflow > `gunluk`) hazır olur; sonra tekrar **onay** yaz.")
        return False
    durum = secrets.token_urlsafe(32)
    dogrulayici, meydan = pkce()
    r = _kv("PUT", "yetki-bekle:" + durum, params={"expiration_ttl": BEKLEME_DK * 60 + 300}, data=b"1")
    if r is None or not r.ok:
        yorum_yaz(konu, "⚠️ Cloudflare KV'ye yazılamadı (token'da 'Workers KV Storage: Edit' izni olmalı).")
        return False
    baglanti = onay_baglantisi(hizmet, yon, gizli("YT_CLIENT_ID"), durum, meydan,
                               gizli("GOOGLE_HESAP") if hizmet == "google" else "")
    konu = konu or onay_konusu(kanal, hizmet)
    yorum_yaz(konu, f"👉 **[Onay vermek için buraya dokun]({baglanti})**\n\n"
                    + ("Açılan ekranda **bu kanalın YouTube kanalını** seç. " if hizmet == "youtube" else "")
                    + f"Bağlantı {BEKLEME_DK} dakika geçerli ve tek kullanımlık.\n\n"
                    f"<sub>Google “redirect_uri_mismatch” hatası gösterirse: Google Cloud > Kimlik bilgileri > "
                    f"OAuth istemcin > Yetkili yönlendirme URI'leri kısmına `{yon}` ekle.</sub>")
    gelen = _bekle(durum)
    if not gelen:
        yorum_yaz(konu, f"⌛ {BEKLEME_DK} dakika içinde onay gelmedi. Hazır olduğunda yeniden **onay** yaz.")
        return False
    if gelen.get("hata") or not gelen.get("kod"):
        yorum_yaz(konu, f"❌ Google'da onay verilmedi ({gelen.get('hata', 'kod yok')}). İstersen yeniden **onay** yaz.")
        return False
    t = kodu_degistir(gelen["kod"], dogrulayici, yon)
    if not t.get("refresh_token"):
        yorum_yaz(konu, f"❌ Anahtar alınamadı: {t.get('error_description') or t.get('error')}. Yeniden **onay** yaz.")
        return False

    kayit = json_oku(DURUM, {}) or {}
    if hizmet == "youtube":
        yt = youtube_kanali(t.get("access_token", ""))
        sorun = yt.get("hata") or baglanti_sorunu(kanal, yt, degistir)
        if sorun:
            yorum_yaz(konu, f"❌ {sorun}\n\nAnahtar kaydedilmedi. Yeniden **onay** yazabilirsin.")
            return False
        from .m09_youtube_yukleme import anahtar_adi
        ad = anahtar_adi(kanal)
        hedef = kaydet(ad, t["refresh_token"])
        if not hedef:
            yorum_yaz(konu, "❌ Anahtar kaydedilemedi (GH_YONETICI_TOKEN ya da Cloudflare KV gerekli).")
            return False
        json_yaz(KANALLAR_VERI / kanal / "youtube_kanali.json",
                 {"id": yt["id"], "baslik": yt["baslik"], "tarih": ayar.simdi.isoformat(timespec="minutes")})
        kurulum = kanal_kur(kanal, ad, t["refresh_token"])
        kayit[kanal] = {"durum": "bağlı", "youtube": yt["baslik"], "tarih": ayar.simdi.date().isoformat()}
        mesaj = (f"✅ **{yt['baslik']}** YouTube kanalı '{kanal}' kanalına bağlandı. Anahtar {hedef}'na kaydedildi.\n"
                 + ("- Kanal kurulumu yapıldı (açıklama, anahtar kelimeler, yorumlar, oynatma listeleri)."
                    if kurulum else "- Kanal kurulumu bir sonraki günlük çalıştırmada tamamlanacak."))
    else:
        adres = eposta(t.get("id_token", ""))
        beklenen = gizli("GOOGLE_HESAP")
        if beklenen and adres.lower() != beklenen.lower():
            yorum_yaz(konu, "❌ Farklı bir Google hesabı seçildi (GOOGLE_HESAP ile eşleşmiyor). Anahtar kaydedilmedi.")
            return False
        hedef = kaydet("GOOGLE_ARAMA_TOKEN", t["refresh_token"])
        if not hedef:
            yorum_yaz(konu, "❌ Anahtar kaydedilemedi (GH_YONETICI_TOKEN ya da Cloudflare KV gerekli).")
            return False
        acilan = apileri_ac(t.get("access_token", ""))
        from .m12_gelir import maskele
        kayit["google"] = {"durum": "bağlı", "hesap": maskele(adres), "tarih": ayar.simdi.date().isoformat()}
        mesaj = (f"✅ Google hesabı ({maskele(adres)}) bağlandı; anahtar {hedef}'na kaydedildi. "
                 "Siteler arama motorlarına sonraki çalıştırmada kaydedilecek.\n"
                 + (f"- Google API'leri açıldı: {', '.join(acilan)}" if acilan else
                    f"- API'ler kendiliğinden açılamadı; şu bağlantılardan **Etkinleştir**'e bas: {api_baglantilari()}"))
    json_yaz(DURUM, kayit)
    yorum_yaz(konu, mesaj)
    konu_kapat(konu)
    return True


def denetle(ayar: Ayarlar) -> dict:
    """Günlük: her kanalın anahtarını dener; eksik/bozuk olan için onay konusu açar (beklemeden)."""
    from .m09_youtube_yukleme import yenileme_anahtari
    eksik = on_kosullar(ayar)
    if eksik:
        konu_ac("🔧 Tek tıkla yetki için bir kerelik kurulum",
                "Sistem YouTube/Google anahtarlarını kendisi alabilsin diye bir kez şunlar gerekiyor:\n"
                + "\n".join(f"- [ ] {e}" for e in eksik) + "\n\nTamamlanınca bu konu kendiliğinden işe yaramaz hale gelir; kapatabilirsin.",
                KURULUM_ISARETI)
        return {"kurulum": eksik}
    kayit = json_oku(DURUM, {}) or {}
    for kanal in kanal_listesi():
        gecerli, sebep = anahtar_gecerli(yenileme_anahtari(kanal))
        if gecerli is None:
            continue  # ağ sorunu: yarın tekrar denenir
        onceki = kayit.get(kanal, {})
        kayit[kanal] = {**onceki, "durum": "bağlı" if gecerli else sebep,
                        "denetim": ayar.simdi.date().isoformat()}
        if not gecerli:
            onay_konusu(kanal, "youtube", sebep)
    if ayar.alan_adlari:
        gecerli, sebep = anahtar_gecerli(gizli("GOOGLE_ARAMA_TOKEN"))
        if gecerli is False:
            kayit["google"] = {**kayit.get("google", {}), "durum": sebep}
            onay_konusu("google", "google", sebep)
    json_yaz(DURUM, kayit)
    return kayit


def calistir(ayar: Ayarlar) -> None:
    if ayar.deneme:
        log.info("Deneme: yetki adımı atlandı (Google/GitHub'a bağlanılmaz).")
        return
    olay = os.environ.get("OLAY", "")
    if olay == "issue_comment":
        m = ISARET.search(os.environ.get("KONU_GOVDE", ""))
        yorum = os.environ.get("YORUM", "").strip().lower()
        if not m or not yorum.startswith("onay"):
            return
        kanal, hizmet = m[1], m[2]
        if hizmet == "youtube" and kanal not in kanal_listesi():
            yorum_yaz(int(os.environ["KONU_NO"]), f"❌ '{kanal}' adında bir kanal yok.")
            return
        onay_al(ayar, kanal, hizmet, konu=int(os.environ["KONU_NO"]),
                degistir="değiştir" in yorum or "degistir" in yorum)
    elif olay == "workflow_dispatch":
        k = (os.environ.get("GIRILEN_KANAL") or "ana").strip().lower()
        hizmet = "google" if k == "google" else "youtube"
        if not re.fullmatch(KANAL_RE, k) or (hizmet == "youtube" and k not in kanal_listesi()):
            log.error("Geçersiz kanal: %s (mevcut: %s)", k, ", ".join(kanal_listesi()))
            return
        onay_al(ayar, k, hizmet, degistir=os.environ.get("DEGISTIR") == "true")
    else:
        log.info("Yetki denetimi: %s", denetle(ayar))


def durum_bolumu() -> list[str]:
    kayit = json_oku(DURUM, {}) or {}
    if not kayit:
        return []
    md = ["", "## 🔑 Yetkiler"]
    for ad, d in sorted(kayit.items()):
        if not isinstance(d, dict):
            continue
        tamam = d.get("durum") == "bağlı"
        ek = d.get("youtube") or d.get("hesap") or ""
        md.append(f"- {'✅' if tamam else '⚠️'} **{ad}**: {d.get('durum', '?')}{' — ' + ek if ek else ''}"
                  + ("" if tamam else " → GitHub'daki “🔑 Onay gerekiyor” konusuna **onay** yaz"))
    return md
