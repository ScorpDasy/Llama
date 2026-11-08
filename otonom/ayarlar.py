"""Ayarlar, yollar ve ortak yardımcılar.

Gizli bilgiler yalnızca ortam değişkenlerinden okunur (GitHub Secrets / .env).
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

KOK = Path(__file__).resolve().parent.parent
CONFIG = Path(os.environ["OTONOM_CONFIG"]) if os.environ.get("OTONOM_CONFIG") else KOK / "config"
CLOUDFLARE_SABLON = KOK / "cloudflare"
# Deneme modunda gerçek verilere dokunmamak için çalışma klasörü değiştirilebilir.
_CALISMA = Path(os.environ["OTONOM_CALISMA"]) if os.environ.get("OTONOM_CALISMA") else KOK
VERI = _CALISMA / "veri"     # git'e işlenen kalıcı veriler (küçük dosyalar)
CIKTI = _CALISMA / "cikti"   # büyük üretim dosyaları (git'e işlenmez)
SITE = _CALISMA / "site"     # üretilen statik siteler (Cloudflare Pages'e yüklenir)

# ÇOK KANAL: her kanalın ayarı config/kanallar/<kod>.yaml, verisi veri/kanallar/<kod>/ altında.
# Kanal işi '--kanal <kod>' ile ayrı süreçte (GitHub'da ayrı paralel işte) çalışır; bu süreçte
# yazılan her dosya kanalın kendi klasöründedir -> paralel işler birbirinin dosyasına dokunmaz.
KANAL_CONFIG = CONFIG / "kanallar"
KANALLAR_VERI = VERI / "kanallar"
KANAL_MODU = bool(os.environ.get("OTONOM_KANAL", "").strip())
KANAL = os.environ.get("OTONOM_KANAL", "").strip() or "ana"
if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", KANAL):  # güvenlik: klasör yolu dışına çıkılamasın
    raise SystemExit(f"Geçersiz kanal kodu: {KANAL!r} (yalnızca küçük harf, rakam ve '-' kullanılabilir)")
KANAL_VERI = KANALLAR_VERI / KANAL
ISLETME = KANAL_VERI if KANAL_MODU else VERI   # kota, uyarı, maliyet, süre kayıtlarının bu süreçteki yeri

log = logging.getLogger("otonom")


def _env_dosyasi_yukle() -> None:
    """Yerel çalıştırmada .env dosyasını okur (GitHub Actions'ta gerekmez)."""
    env = KOK / ".env"
    if not env.exists():
        return
    for satir in env.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        anahtar, deger = satir.split("=", 1)
        os.environ.setdefault(anahtar.strip(), deger.strip().strip('"').strip("'"))


_env_dosyasi_yukle()


def gizli(ad: str) -> str:
    """Gizli bilgiyi ortam değişkeninden okur. GitHub'da tüm Secrets 'TUM_GIZLILER' içinde de gelir:
    böylece her yeni kanalın anahtarı (ör. YT_REFRESH_TOKEN_TARIH) iş akışını değiştirmeden okunur."""
    if _KASA_ADI.fullmatch(ad):  # tek tıkla yetkiyle alınan en yeni anahtar (özel Cloudflare KV) önce gelir
        deger = _kasadan(ad)
        if deger:
            return deger
    deger = os.environ.get(ad, "").strip()
    if not deger and os.environ.get("TUM_GIZLILER"):
        try:
            deger = str(json.loads(os.environ["TUM_GIZLILER"]).get(ad) or "").strip()
        except ValueError:
            pass
    return deger


_KASA_ADI = re.compile(r"YT_REFRESH_TOKEN(_[A-Z0-9_]+)?|GOOGLE_ARAMA_TOKEN")
_KASA: dict[str, str] = {}


def _kasadan(ad: str) -> str:
    """otonom/yetki.py'nin özel Cloudflare KV kasasına yazdığı anahtar (süreç başına bir kez okunur)."""
    if ad not in _KASA:
        _KASA[ad] = ""
        if gizli("CLOUDFLARE_API_TOKEN") and gizli("CLOUDFLARE_ACCOUNT_ID"):
            try:
                from .yetki import kasa_oku
                _KASA[ad] = kasa_oku(ad)
            except Exception as e:  # kasa okunamazsa GitHub Secrets'taki anahtarla devam
                log.warning("Anahtar kasası okunamadı: %s", e)
    return _KASA[ad]


def isletme_dosyalari(ad: str) -> list[Path]:
    """Genel + tüm kanalların aynı adlı işletme dosyaları (toplam hesapları için)."""
    return [VERI / ad] + sorted(KANALLAR_VERI.glob(f"*/{ad}"))


@dataclass
class Ayarlar:
    genel: dict[str, Any]
    varliklar: dict[str, Any]
    deneme: bool = False      # True = dış servis çağrısı yok, sahte veriyle uçtan uca test
    yukleme: bool = True      # False = videolar üretilir ama YouTube'a yüklenmez (beta)
    mod: str = "normal"       # bütçe modu: normal | azaltilmis | hafif (butce.py belirler)
    kanal: str = "ana"        # bu ayarların ait olduğu kanal
    kanal_bilgi: dict = field(default_factory=dict)
    simdi: datetime = field(default_factory=lambda: datetime.now(ZoneInfo("Europe/Istanbul")))

    def __getitem__(self, anahtar: str) -> Any:
        return self.genel[anahtar]

    @property
    def nisler(self) -> list[dict[str, Any]]:
        return [n for n in self.varliklar.get("nisler", []) if n]

    def nis(self, kod: str) -> dict[str, Any]:
        for n in self.nisler:
            if n["kod"] == kod:
                return n
        raise KeyError(f"Niş bulunamadı: {kod}")

    @property
    def alan_adlari(self) -> list[dict[str, Any]]:
        return [a for a in self.varliklar.get("alan_adlari", []) if a and a.get("aktif", True)]


# Ayar dosyasında eksik/silinmiş bir satır sistemi durdurmasın diye her ayarın varsayılanı burada.
VARSAYILAN: dict[str, Any] = {
    "saat_dilimi": "Europe/Istanbul",
    "denetim": {"acik": True, "gecme_puani": 80, "en_fazla_onarim": 2, "zayif_gorsel_esigi": 50},
    "hazirlik": {"acik": True, "aday_sayisi": 3, "dakika_siniri": 25, "en_fazla_saat": 36},
    "llm": {"nvidia_modeli": "meta/llama-3.3-70b-instruct",
            "openrouter_modeli": "meta-llama/llama-3.3-70b-instruct:free", "saglayici": "ucretsiz", "yerel_model": "unsloth/gemma-4-E2B-it-GGUF",
            "yerel_dosya": "gemma-4-E2B-it-Q4_K_M.gguf", "yerel_baglam": 10240, "yerel_sicaklik": 0.7,
            "model": "claude-haiku-5-5", "toplu_islem": True, "senaryo_efor": "medium", "kisa_is_efor": "low",
            "cloudflare_metin_modeli": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
            "cloudflare_gorsel_modeli": "@cf/black-forest-labs/flux-1-schnell"},
    "youtube": {"baslangic_odak_video": 12, "haftalik_uzun_video": 3, "video_basina_shorts": 2, "hedef_kelime": 1100, "kategori_id": "27",
                "gizlilik": "private", "yayin_gunleri": ["sali", "persembe", "cumartesi"], "yayin_saati": "18:00",
                "altyazi_yukle": True, "sentetik_medya_beyani": False},
    "ses": {"ses_adi": "tr-TR-AhmetNeural", "hiz": "+5%", "muzik_seviyesi_db": -20, "fon_muzigi": True,
            "ruh_hali": "merakli", "gecis_sesi": True, "efekt_seviyesi_db": -16, "tonlama": True},
    "video": {"genislik": 1920, "yukseklik": 1080, "fps": 24, "ken_burns": True, "crf": 23,
              "intro_saniye": 0, "outro_saniye": 5, "gecis": True, "altyazi_yak": True,
              "logo": "config/marka/logo.png", "ilerleme_cubugu": True, "abone_rozeti": True, "stok_video": True,
              "paralaks": True, "bilgi_grafikleri": True},
    "butce": {"github_dakika_limiti": 2000},
    "laboratuvar": {"viral_esik": 10000, "min_veri_gunu": 7},
    "optimizasyon": {"yari_omur_gun": 45, "benzerlik_esigi": 0.6,
                     "deneyler": {"baslik_stili": ["soru", "sayili_liste", "nasil", "carpici_gercek"],
                                  "hedef_kelime": [800, 1100, 1400],
                                  "yayin_saati": ["12:00", "18:00", "20:30"],
                                  "gorsel_stili": ["sinematik", "belgesel", "canli_renkli"],
                                  "muzik": ["merakli", "enerjik", "sakin", "gizemli"]},
                     "kanallar_arasi_oduncleme": 0.15},
    "cloudflare": {"web_analytics_token": "", "adsense_yayinci_id": ""},
    "teklifler": {"otomatik_yanit": False},
    "muhendis": {"otomatik_uygula": True, "ders_cikar": True, "github_issue": True, "kilitli": []},
}
OGRENILEN = KANAL_VERI / "ogrenilen_ayarlar.yaml"   # Öğrenme Mühendisi katmanı (kanal başına; silinirse sıfırlanır)
SECENEKLER = {
    ("llm", "saglayici"): {"ucretsiz", "otomatik", "yerel", "claude", "cloudflare"},
    ("youtube", "gizlilik"): {"private", "zamanla"},
}


class AyarHatasi(SystemExit):
    pass


def _birlestir(taban: dict, ust: dict) -> dict:
    sonuc = dict(taban)
    for k, v in (ust or {}).items():
        sonuc[k] = _birlestir(taban[k], v) if isinstance(v, dict) and isinstance(taban.get(k), dict) else v
    return sonuc


def _yaml_oku(dosya: Path) -> dict:
    try:
        veri = yaml.safe_load(dosya.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        isaret = getattr(e, "problem_mark", None)
        yer = f"{isaret.line + 1}. satır" if isaret else "bilinmeyen satır"
        raise AyarHatasi(
            f"\n❌ {dosya.name} dosyasında yazım hatası ({yer}).\n"
            "İpuçları: girintiler boşlukla yapılmalı (TAB değil), ':' işaretinden sonra bir boşluk olmalı,\n"
            "içinde ':' veya '#' geçen metinler tırnak içine alınmalı. Ayrıntı: " + str(e).splitlines()[0]) from None
    if not isinstance(veri, dict):
        raise AyarHatasi(f"\n❌ {dosya.name} beklenen biçimde değil (anahtar: değer satırları olmalı).")
    return veri


def _kilitlileri_cikar(ogrenilen: dict, kilitli: list[str]) -> dict:
    for yol in kilitli or []:
        parcalar, hedef = yol.split("."), ogrenilen
        for p in parcalar[:-1]:
            hedef = hedef.get(p, {}) if isinstance(hedef, dict) else {}
        if isinstance(hedef, dict):
            hedef.pop(parcalar[-1], None)
    return ogrenilen


def kanal_listesi(sadece_aktif: bool = True) -> list[str]:
    """config/kanallar/*.yaml içindeki kanal kodları. Hiç yoksa tek kanal: 'ana'."""
    kodlar = []
    for d in sorted(KANAL_CONFIG.glob("*.yaml")) if KANAL_CONFIG.exists() else []:
        if not sadece_aktif or _yaml_oku(d).get("aktif", True):
            kodlar.append(d.stem)
    return kodlar or ["ana"]


def kanal_bilgisi(kod: str, varliklar: dict | None = None) -> dict:
    dosya = KANAL_CONFIG / f"{kod}.yaml"
    if dosya.exists():
        return _yaml_oku(dosya)
    varliklar = varliklar or {}
    if kod == "ana" and varliklar.get("nisler"):  # eski tek kanallı yapı ile uyumluluk
        k = (varliklar.get("youtube_kanallari") or [{}])[0]
        return {"ad": k.get("ad", "Ana Kanal"), "kanal_id": k.get("kanal_id", ""), "nisler": varliklar["nisler"]}
    return {}


def yukle(deneme: bool = False, kanal: str | None = None) -> Ayarlar:
    kanal = kanal or KANAL
    genel = _birlestir(VARSAYILAN, _yaml_oku(CONFIG / "ayarlar.yaml"))
    varliklar = _yaml_oku(CONFIG / "varliklar.yaml")
    kb = kanal_bilgisi(kanal, varliklar)
    genel = _birlestir(genel, kb.get("ayarlar") or {})          # kanalın kendi ayar farkları
    nisler = [dict(n) for n in kb.get("nisler") or [] if isinstance(n, dict)]
    # Öğrenme Mühendisi katmanı (kanal başına): kullanıcının dosyalarına dokunmadan üzerine uygulanır.
    ogr_dosya = KANALLAR_VERI / kanal / "ogrenilen_ayarlar.yaml"
    ogrenilen = _yaml_oku(ogr_dosya) if ogr_dosya.exists() else {}
    if genel["muhendis"]["otomatik_uygula"] and ogrenilen:
        ogrenilen = _kilitlileri_cikar(ogrenilen, genel["muhendis"]["kilitli"])
        ek_tohum = ogrenilen.pop("nis_tohumlari", {}) or {}
        genel = _birlestir(genel, ogrenilen)
        for n in nisler:
            if ek_tohum.get(n.get("kod")):
                n["tohum_kelimeler"] = list(dict.fromkeys((n.get("tohum_kelimeler") or []) + ek_tohum[n["kod"]]))
    for (bolum, anahtar), gecerli in SECENEKLER.items():
        if genel[bolum][anahtar] not in gecerli:
            raise AyarHatasi(f"\n❌ {kanal}: {bolum}.{anahtar} = '{genel[bolum][anahtar]}' geçersiz. "
                             f"Seçenekler: {', '.join(sorted(gecerli))}")
    for n in nisler:
        if not n.get("kod"):
            raise AyarHatasi(f"\n❌ kanallar/{kanal}.yaml > nisler: her nişin bir 'kod' alanı olmalı.")
        n.setdefault("ad", n["kod"])
        n.setdefault("hedef_kitle", kb.get("hedef_kitle") or "Genel izleyici")
        n.setdefault("alan_adi", "")
        n.setdefault("tohum_kelimeler", [])
        n.setdefault("kaynaklar", [{"tur": "youtube_oneri"}])
        if not n["tohum_kelimeler"] and all(k.get("tur") == "youtube_oneri" for k in n["kaynaklar"]):
            raise AyarHatasi(f"\n❌ kanallar/{kanal}.yaml > {n['kod']}: 'tohum_kelimeler' veya başka bir kaynak gerekli.")
    varliklar["nisler"] = nisler
    varliklar["youtube_kanallari"] = [{"ad": kb.get("ad", kanal), "kanal_id": kb.get("kanal_id", "")}]
    for k in (VERI, CIKTI, KANALLAR_VERI / kanal):
        k.mkdir(parents=True, exist_ok=True)
    return Ayarlar(genel=genel, varliklar=varliklar, deneme=deneme, kanal=kanal, kanal_bilgi=kb)


def tum_kanallar(deneme: bool = False) -> list[Ayarlar]:
    return [yukle(deneme, k) for k in kanal_listesi()]


# ---------------------------------------------------------------- yardımcılar

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def kisa_ad(metin: str, uzunluk: int = 60) -> str:
    """'Beyin Sağlığı İçin 5 İpucu' -> 'beyin-sagligi-icin-5-ipucu'"""
    metin = unicodedata.normalize("NFKC", metin).translate(_TR).lower()
    metin = re.sub(r"[^a-z0-9]+", "-", metin).strip("-")
    return metin[:uzunluk].rstrip("-") or "icerik"


def json_oku(yol: Path, varsayilan: Any = None) -> Any:
    if not yol.exists():
        return varsayilan
    return json.loads(yol.read_text(encoding="utf-8"))


def json_yaz(yol: Path, veri: Any) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_oku(yol: Path) -> list[dict[str, str]]:
    if not yol.exists():
        return []
    with yol.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def csv_ekle(yol: Path, satirlar: list[dict[str, Any]], alanlar: list[str]) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yeni = not yol.exists()
    with yol.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=alanlar, extrasaction="ignore")
        if yeni:
            w.writeheader()
        w.writerows(satirlar)


def uyari_ekle(kategori: str, metin: str) -> None:
    """Sınıra takılma/yedeğe geçme gibi olayları kaydeder; DURUM.md panelinde gösterilir."""
    log.warning("[%s] %s", kategori, metin)
    yol = ISLETME / "uyarilar.json"
    liste = json_oku(yol, [])
    zaman = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d %H:%M")
    if liste and liste[-1].get("metin") == metin:   # aynı uyarıyı üst üste yazma
        liste[-1]["zaman"] = zaman
    else:
        liste.append({"zaman": zaman, "kategori": kategori, "metin": metin, "kanal": KANAL if KANAL_MODU else ""})
    json_yaz(yol, liste[-40:])


def ozet_yaz(metin: str) -> None:
    """GitHub Actions iş özetine (Summary sekmesi) Markdown yazar; yerelde ekrana basar."""
    yol = os.environ.get("GITHUB_STEP_SUMMARY")
    if yol:
        with open(yol, "a", encoding="utf-8") as f:
            f.write(metin + "\n")
    else:
        print(metin)
