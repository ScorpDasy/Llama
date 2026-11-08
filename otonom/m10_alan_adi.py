"""MODÜL 10 — Alan adları için gelir modelleri (satış / kiralama / mikro site).

Her alan adı için bir kez üretilir (sonra kopyala-yapıştır kullanılır, tekrar maliyet yok):
  pitch.txt, ilan_metni.txt (TR), ilan_metni_en.txt (yabancı pazaryerleri),
  eposta_sablonu.txt (potansiyel alıcılara), teklif_yanit_sablonu.txt (gelen teklife),
  alici_bulma.md (alıcıyı nerede/nasıl arayacağınız).
Fiyat uydurulmaz: config'de fiyat yoksa "teklife açık" satılır.
"""
from __future__ import annotations

from . import llm
from .ayarlar import VERI, Ayarlar, log
from .m01_envanter import alan_adi_puani

SEMA = {
    "type": "object",
    "properties": {
        "pitch": {"type": "string", "description": "yaklaşık 150 kelime, Türkçe: marka değeri, sektör, kullanım fikirleri"},
        "ilan_metni": {"type": "string", "description": "pazaryeri ilanı, Türkçe, 60-90 kelime"},
        "ilan_metni_en": {"type": "string", "description": "same listing in English, 60-90 words"},
        "eposta_sablonu": {"type": "string", "description": "potansiyel alıcıya kısa, saygılı, spam olmayan tanıtım e-postası; {firma} yer tutucusu"},
        "teklif_yanit_sablonu": {"type": "string", "description": "gelen teklife nazik pazarlık yanıtı; {ad}, {teklif}, {alan_adi} yer tutucuları"},
        "alici_turleri": {"type": "array", "items": {"type": "string"}, "description": "6 alıcı türü"},
        "arama_sorgulari": {"type": "array", "items": {"type": "string"}, "description": "Google Haritalar/LinkedIn'de alıcı bulmak için 6 arama ifadesi"},
        "kullanim_fikirleri": {"type": "array", "items": {"type": "string"}, "description": "alıcının bu adla kurabileceği 5 iş/proje"},
    },
    "required": ["pitch", "ilan_metni", "ilan_metni_en", "eposta_sablonu", "teklif_yanit_sablonu",
                 "alici_turleri", "arama_sorgulari", "kullanim_fikirleri"],
    "additionalProperties": False,
}

SISTEM = """Sen alan adı satış danışmanısın. Abartısız, güven veren, somut metinler yaz.
Uydurma trafik, gelir veya fiyat rakamı verme. Yasal olarak sorunlu marka iddialarında bulunma."""


def calistir(ayar: Ayarlar, zorla: bool = False) -> list[str]:
    uretilen = []
    for a in ayar.alan_adlari:
        ad = a["ad"]
        klasor = VERI / "alan_adlari" / ad
        if (klasor / "pitch.txt").exists() and not zorla:
            continue
        puan = alan_adi_puani(ad)
        fiyat = a.get("satis_fiyati_try") or 0
        kira = a.get("kiralama_aylik_try") or 0
        istem = (f"Alan adı: {ad}\nSektör: {a.get('sektor', '')}\nHedef alıcı: {a.get('hedef_alici', '')}\n"
                 f"Değer puanı: {puan['puan']}/100 ({puan['seviye']})\n"
                 f"Satış: {f'{fiyat} TL' if fiyat else 'teklife açık'}; "
                 f"Kiralama: {f'aylık {kira} TL' if kira else 'teklife açık'}\n"
                 "Satış ve aylık kiralama seçeneklerinin ikisini de sun.")

        def sahte() -> dict:
            return {k: f"Deneme {k} — {ad}" if SEMA["properties"][k]["type"] == "string" else [f"Deneme {k}"]
                    for k in SEMA["required"]}

        c = llm.json_uret(ayar, f"alanadi-{ad}", SISTEM, istem, SEMA, sahte, max_tokens=8000)
        klasor.mkdir(parents=True, exist_ok=True)
        for alan in ("pitch", "ilan_metni", "ilan_metni_en", "eposta_sablonu", "teklif_yanit_sablonu"):
            (klasor / f"{alan}.txt").write_text(c[alan].strip() + "\n", encoding="utf-8")
        (klasor / "alici_bulma.md").write_text(
            f"# {ad} — Alıcı bulma rehberi\n\n## Alıcı türleri\n" + "".join(f"- {x}\n" for x in c["alici_turleri"])
            + "\n## Arama ifadeleri (Google Haritalar / LinkedIn)\n" + "".join(f"- {x}\n" for x in c["arama_sorgulari"])
            + "\n## Alıcının kullanım fikirleri\n" + "".join(f"- {x}\n" for x in c["kullanim_fikirleri"])
            + "\n## Ücretsiz ilan yerleri\n- Kendi sitenizdeki 'satılık' kutusu (otomatik kuruldu)\n"
            "- Sedo, Afternic gibi pazaryerleri (ilan ücretsiz, satışta komisyon; uzantı desteğini kontrol edin)\n"
            "- LinkedIn gönderisi ve sektör grupları\n", encoding="utf-8")
        uretilen.append(ad)
        log.info("Alan adı metinleri üretildi: %s", ad)
    return uretilen
