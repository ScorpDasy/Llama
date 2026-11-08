"""YENİ KANAL SİHİRBAZI — tek cümlelik açıklamadan eksiksiz kanal yapılandırması.

Örnek: "Osmanlı tarihinden az bilinen hikâyeler anlatan, 25-45 yaş meraklı izleyiciye yönelik kanal"
Yapay zekâ şunları tasarlar: kanal adı ve üslubu, 2-4 niş, her nişin arama tohumları ve konu kaynakları
(YouTube önerileri, Google gündemi, RSS, Vikipedi "tarihte bugün"), dil, ses, video biçimi, görsel sırası.
RSS adresleri tek tek kontrol edilir; çalışmayan adres yazılmaz. Sonuç config/kanallar/<kod>.yaml olur ve
bir sonraki çalıştırmadan itibaren kanal kendi paralel işinde üretime başlar.
"""
from __future__ import annotations

import yaml

from . import llm
from .ayarlar import KANAL_CONFIG, Ayarlar, kisa_ad, log, ozet_yaz

KAYNAK_TURLERI = ["youtube_oneri", "google_trendler", "rss", "wikipedia_bugun"]
SESLER = {  # dil -> (erkek, kadın) Edge sesleri
    "tr": ("tr-TR-AhmetNeural", "tr-TR-EmelNeural"), "en": ("en-US-GuyNeural", "en-US-JennyNeural"),
    "de": ("de-DE-ConradNeural", "de-DE-KatjaNeural"), "es": ("es-ES-AlvaroNeural", "es-ES-ElviraNeural"),
    "fr": ("fr-FR-HenriNeural", "fr-FR-DeniseNeural"), "ar": ("ar-SA-HamedNeural", "ar-SA-ZariyahNeural"),
}

SEMA = {
    "type": "object",
    "properties": {
        "kod": {"type": "string", "description": "kısa kanal kodu, küçük harf, Türkçe karakter yok, ör. 'osmanli-tarih'"},
        "ad": {"type": "string", "description": "akılda kalıcı kanal adı"},
        "hedef_kitle": {"type": "string"},
        "uslup": {"type": "string", "description": "anlatım üslubu, 1-2 cümle (ör. 'merak uyandıran hikâye anlatıcısı')"},
        "dil": {"type": "string", "enum": list(SESLER)},
        "ses": {"type": "string", "enum": ["erkek", "kadin"]},
        "bicim": {"type": "string", "enum": ["uzun_ve_shorts", "sadece_shorts", "sadece_uzun"]},
        "yapay_zeka_gorsel_once": {"type": "boolean",
                                   "description": "konu stok fotoğrafla anlatılamıyorsa true (tarih, fantastik, uzay vb.)"},
        "haftalik_video": {"type": "integer", "description": "haftalık uzun video sayısı, 1-5"},
        "nisler": {
            "type": "array",
            "description": "2-4 niş",
            "items": {
                "type": "object",
                "properties": {
                    "kod": {"type": "string", "description": "kısa niş kodu, küçük harf"},
                    "ad": {"type": "string"},
                    "hedef_kitle": {"type": "string"},
                    "tohum_kelimeler": {"type": "array", "items": {"type": "string"},
                                        "description": "insanların YouTube'da arayacağı 5-8 kısa ifade"},
                    "kaynaklar": {"type": "array", "items": {"type": "string", "enum": KAYNAK_TURLERI},
                                  "description": "konu kaynakları; youtube_oneri hep olsun"},
                    "rss_adresleri": {"type": "array", "items": {"type": "string"},
                                      "description": "rss seçildiyse bilinen, gerçek RSS adresleri (yoksa boş)"},
                },
                "required": ["kod", "ad", "hedef_kitle", "tohum_kelimeler", "kaynaklar", "rss_adresleri"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["kod", "ad", "hedef_kitle", "uslup", "dil", "ses", "bicim", "yapay_zeka_gorsel_once",
                 "haftalik_video", "nisler"],
    "additionalProperties": False,
}

SISTEM = """Sen YouTube kanal stratejistisin. Verilen tarife göre, düşük rekabetli ama ilgi gören,
reklamverene uygun, özgün bir kanal tasarla. Sağlık/finans gibi hassas konularda sorumlu ol.
Nişler birbirini tamamlasın; tohum kelimeler insanların gerçekten arayacağı kısa ifadeler olsun.
Kaynak seçimi: gündem/haber kanalına google_trendler ve rss; tarih/kültür kanalına wikipedia_bugun;
her nişe youtube_oneri. Emin olmadığın RSS adresini yazma."""


def _benzersiz_kod(kod: str) -> str:
    kod = kisa_ad(kod, 20) or "kanal"
    aday, i = kod, 2
    while (KANAL_CONFIG / f"{aday}.yaml").exists():
        aday, i = f"{kod}-{i}", i + 1
    return aday


def _sahte(aciklama: str) -> dict:
    return {"kod": "deneme-kanal", "ad": "Deneme Kanalı", "hedef_kitle": "Meraklı izleyiciler",
            "uslup": "Samimi ve merak uyandıran", "dil": "tr", "ses": "kadin", "bicim": "sadece_shorts",
            "yapay_zeka_gorsel_once": True, "haftalik_video": 2,
            "nisler": [{"kod": "tarih", "ad": "Tarih Hikâyeleri", "hedef_kitle": "Tarih meraklıları",
                        "tohum_kelimeler": ["osmanlı tarihi", "bilinmeyen tarih"],
                        "kaynaklar": ["youtube_oneri", "wikipedia_bugun"], "rss_adresleri": []}]}


def yapilandirma(ayar: Ayarlar, c: dict) -> tuple[str, dict]:
    """Model çıktısını güvenli, doğrulanmış kanal yapılandırmasına çevirir."""
    from .m02_nis_analizi import rss_basliklari

    kod = _benzersiz_kod(c["kod"])
    dil = c["dil"] if c["dil"] in SESLER else "tr"
    nisler = []
    for n in c["nisler"][:4]:
        kaynaklar = [{"tur": "youtube_oneri"}]
        for tur in dict.fromkeys(n["kaynaklar"]):
            if tur == "rss":
                gecerli = [u for u in n["rss_adresleri"][:4]
                           if u.startswith("http") and (ayar.deneme or rss_basliklari([u], 2))]
                if gecerli:
                    kaynaklar.append({"tur": "rss", "adresler": gecerli})
                else:
                    log.info("Niş %s: çalışan RSS adresi bulunamadı, RSS kaynağı eklenmedi.", n["kod"])
            elif tur in KAYNAK_TURLERI and tur != "youtube_oneri":
                kaynaklar.append({"tur": tur})
        nisler.append({"kod": kisa_ad(n["kod"], 20), "ad": n["ad"], "alan_adi": "", "hedef_kitle": n["hedef_kitle"],
                       "tohum_kelimeler": [t for t in n["tohum_kelimeler"] if t.strip()][:8],
                       "kaynaklar": kaynaklar, "ortaklik_linkleri": {}})
    veri = {
        "ad": c["ad"], "aktif": True, "kanal_id": "", "dil": dil, "bicim": c["bicim"],
        "hedef_kitle": c["hedef_kitle"], "uslup": c["uslup"],
        "gorsel_kaynaklari": (["yapay_zeka", "pexels", "pixabay", "openverse"] if c["yapay_zeka_gorsel_once"]
                              else ["pexels", "pixabay", "openverse", "yapay_zeka"]),
        "ayarlar": {
            "youtube": {"haftalik_uzun_video": max(1, min(5, int(c["haftalik_video"]))),
                        "video_basina_shorts": 4 if c["bicim"] == "sadece_shorts" else 2,
                        **({"hedef_kelime": 400} if c["bicim"] == "sadece_shorts" else {})},
            "ses": {"ses_adi": SESLER[dil][1 if c["ses"] == "kadin" else 0]},
        },
        "nisler": nisler,
    }
    return kod, veri


def olustur(ayar: Ayarlar, aciklama: str) -> str:
    aciklama = (aciklama or "").strip()
    if len(aciklama) < 10:
        raise ValueError("Kanal açıklaması boş veya çok kısa. Örnek: 'Osmanlı tarihinden az bilinen hikâyeler "
                         "anlatan, 25-45 yaş meraklı izleyiciye yönelik kanal'")
    c = llm.json_uret(ayar, "yeni-kanal", SISTEM, f"Kanal tarifi: {aciklama}", SEMA, lambda: _sahte(aciklama),
                      max_tokens=4000)
    kod, veri = yapilandirma(ayar, c)
    KANAL_CONFIG.mkdir(parents=True, exist_ok=True)
    anahtar = "YT_REFRESH_TOKEN_" + kod.upper().replace("-", "_")
    baslik = (f"# KANAL: {kod} — Yeni Kanal Sihirbazı tarafından oluşturuldu.\n"
              f"# Tarif: {aciklama}\n"
              f"# YouTube'a otomatik yükleme için GitHub Secrets'a '{anahtar}' ekle\n"
              f"#   (bilgisayarında: python araclar/youtube_token_al.py {kod}). Eklemezsen videolar indirilebilir kalır.\n"
              "# Bu dosyayı serbestçe düzenleyebilirsin; 'aktif: false' kanalı durdurur.\n\n")
    (KANAL_CONFIG / f"{kod}.yaml").write_text(baslik + yaml.safe_dump(veri, allow_unicode=True, sort_keys=False),
                                              encoding="utf-8")
    ozet = (f"## ➕ Yeni kanal: {veri['ad']} (`{kod}`)\n"
            f"- Dil: {veri['dil']} · biçim: {veri['bicim']} · haftalık {veri['ayarlar']['youtube']['haftalik_uzun_video']} video\n"
            + "".join(f"- Niş **{n['ad']}**: {', '.join(k['tur'] for k in n['kaynaklar'])}\n" for n in veri["nisler"])
            + f"- Dosya: `config/kanallar/{kod}.yaml` · YouTube anahtarı: `{anahtar}`\n"
            "- Kanal bir sonraki çalıştırmada kendi paralel işinde üretime başlar.")
    ozet_yaz(ozet)
    log.info("Yeni kanal oluşturuldu: %s", kod)
    return kod
