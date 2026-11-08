"""Hazırlık aşaması — video birleştirilmeden önce her parça ayrı zamanlarda, acele etmeden hazırlanır.

Neden: Ücretsiz servislerin hız sınırları var; aceleyle bulunan ilk görsel çoğu zaman en iyisi değildir.
Hazırlık her çalıştırmada (günde birkaç kez) süre sınırı kadar ilerler ve kaldığı yerden devam eder:
1. Senaryo denetimi: Shorts kuralları kontrol edilir (ilk cümle en fazla 8 kelime, toplam 50-90 kelime, kısa cümleler).
   Uymuyorsa yerel yapay zekâ düzeltir.
2. Seslendirmeler önceden üretilir ve saklanır (montaj tekrar üretmez).
3. Her görsel yuvası (uzun video sahnesi / Shorts cümlesi) için birkaç aday üretilir: farklı kaynak, farklı
   kadraj ve farklı tohum. Hepsi yerel modelle puanlanır (uygunluk + netlik, otonom/secici.py) ve en iyisi seçilir.
İçerik hazır olunca (ya da en fazla bekleme süresi dolunca) montaja geçer. Tamamen ücretsiz ve yerel.
"""
from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path

from . import llm, m04_senaryo, m05_seslendirme, m06_materyal, secici
from .ayarlar import CIKTI, Ayarlar, json_oku, json_yaz, log

KADRAJLAR = ["", "wide establishing shot", "close-up detail", "dramatic angle"]


def _durum_yolu(kod: str) -> Path:
    return CIKTI / kod / "hazirlik.json"


def yuvalar(icerik: dict, kod: str, shorts: bool = True) -> list[dict]:
    """Görsel yuvaları — yollar montajın kullandığı yollarla aynıdır (hazır görsel doğrudan kullanılır)."""
    g = CIKTI / kod / "gorseller"
    sonuc = [{"ad": f"sahne_{i:03d}", "sorgu": s["gorsel_arama"], "hedef": g / f"sahne_{i:03d}.jpg", "dikey": False}
             for i, s in enumerate(icerik["sahneler"])]
    if shorts:
        from .m07_montaj import shorts_parcala
        for j, sh in enumerate(icerik.get("shorts", [])):
            for k, p in enumerate(sh.get("parcalar") or shorts_parcala(sh["metin"], sh["gorsel_arama"])):
                sonuc.append({"ad": f"shorts_{j}_{k:02d}", "sorgu": p["gorsel_arama"] or sh["gorsel_arama"],
                              "hedef": g / f"shorts_{j}_{k:02d}.jpg", "dikey": True})
    return sonuc


def seslendirmeler(icerik: dict, kod: str) -> list[tuple]:
    from .m07_montaj import shorts_parcala
    s = CIKTI / kod / "ses"
    liste = [(x["metin"], s / f"{i:03d}.mp3", i, len(icerik["sahneler"]), 0) for i, x in enumerate(icerik["sahneler"])]
    for j, sh in enumerate(icerik.get("shorts", [])):
        parcalar = sh.get("parcalar") or shorts_parcala(sh["metin"], sh["gorsel_arama"])
        liste += [(p["metin"], s / f"shorts_{j}_{k:02d}.mp3", k, len(parcalar), 8) for k, p in enumerate(parcalar)]
    return liste


# ------------------------------------------------------------ senaryo denetimi

def shorts_sorunlari(sh: dict, en_fazla: int = 90) -> list[str]:
    parcalar = sh.get("parcalar") or []
    if not parcalar:
        return []
    sorun = []
    ilk = len(parcalar[0]["metin"].split())
    toplam = sum(len(p["metin"].split()) for p in parcalar)
    if ilk > 9:
        sorun.append(f"ilk cümle {ilk} kelime (en fazla 8 olmalı)")
    if not 50 <= toplam <= en_fazla:
        sorun.append(f"toplam {toplam} kelime (55-{min(85, en_fazla)} olmalı)")
    uzun = [p["metin"] for p in parcalar if len(p["metin"].split()) > 14]
    if uzun:
        sorun.append(f"{len(uzun)} cümle 14 kelimeden uzun")
    if len(parcalar) < 5:
        sorun.append(f"yalnızca {len(parcalar)} cümle (6-9 olmalı)")
    return sorun


DUZELTME_SEMASI = {
    "type": "object", "additionalProperties": False, "required": ["kanca_yazi", "parcalar"],
    "properties": {"kanca_yazi": {"type": "string"},
                   "parcalar": m04_senaryo.SENARYO_SEMASI["properties"]["shorts"]["items"]["properties"]["parcalar"]}}


def senaryo_denetle(ayar: Ayarlar, kod: str, icerik: dict, en_fazla: int = 90) -> int:
    """Kurala uymayan Shorts metinlerini yerel yapay zekâyla düzeltir. Döner: düzeltilen Shorts sayısı."""
    duzeltilen = 0
    for sh in icerik.get("shorts", []):
        sorunlar = shorts_sorunlari(sh, en_fazla)
        if not sorunlar:
            continue
        istem = (f"Bu YouTube Shorts metnini kurallara uydur. Sorunlar: {'; '.join(sorunlar)}.\n"
                 "Kurallar: 6-9 kısa cümle, toplam 55-85 kelime, ilk cümle en fazla 8 kelimelik şaşırtıcı bir iddia "
                 "ya da soru, her cümle yeni somut bilgi, son cümle başa bağlansın. Her cümleye İngilizce somut "
                 "görsel tarifi yaz. Anlamı ve bilgileri koru, uydurma ekleme.\n\nMevcut metin:\n"
                 + json.dumps({"kanca_yazi": sh.get("kanca_yazi", ""), "parcalar": sh["parcalar"]}, ensure_ascii=False))
        try:
            yeni = llm.json_uret(ayar, "shorts_duzeltme", "Sen kısa video metinlerini sıkılaştıran bir editörsün.",
                                 istem, DUZELTME_SEMASI, lambda: {"kanca_yazi": sh.get("kanca_yazi", ""),
                                                                  "parcalar": sh["parcalar"]}, max_tokens=2000)
        except llm.LLMHatasi as e:
            log.warning("Shorts düzeltilemedi: %s", e)
            continue
        if yeni.get("parcalar") and len(shorts_sorunlari(yeni, en_fazla)) < len(sorunlar):
            sh["parcalar"] = [{"metin": m04_senaryo._seslendirilebilir(p["metin"]),
                               "gorsel_arama": " ".join(p["gorsel_arama"].split()[:5])} for p in yeni["parcalar"]]
            sh["metin"] = " ".join(p["metin"] for p in sh["parcalar"])
            sh["kanca_yazi"] = (yeni.get("kanca_yazi") or sh.get("kanca_yazi", ""))[:48]
            duzeltilen += 1
    if duzeltilen:
        json_yaz(m04_senaryo.VERI / "videolar" / kod / "icerik.json", icerik)
        log.info("Senaryo denetimi: %d Shorts metni düzeltildi (%s)", duzeltilen, kod)
    return duzeltilen


# ------------------------------------------------------------ görsel adayları

STILLER = {"sinematik": "cinematic film still, dramatic light", "belgesel": "documentary photograph, natural light",
           "canli_renkli": "vibrant colors, high contrast, bold composition",
           # Öğrenme Mühendisi kazanan stili bulunca bu havuzdan yenilerini dener:
           "illustrasyon": "detailed digital illustration, clean shapes", "minimal": "minimalist composition, soft light"}


def aday_uret(ayar: Ayarlar, yuva: dict, n: int, nis: str, kullanilan: set[str]) -> dict | None:
    """n. aday: 0 = normal kaynak sırası; sonrakiler farklı kadraj/tohumla yapay zekâ, son çare stok."""
    klasor = yuva["hedef"].parent / "adaylar"
    klasor.mkdir(parents=True, exist_ok=True)
    hedef = klasor / f"{yuva['ad']}_{n}.jpg"
    if n == 0:
        bilgi = m06_materyal.gorsel_bul(ayar, yuva["sorgu"], hedef, kullanilan, nis, dikey=yuva["dikey"],
                                        yedek_yazi="", hazir_kullan=False)
    else:
        sorgu = ", ".join(x for x in (yuva["sorgu"], KADRAJLAR[n % len(KADRAJLAR)], STILLER.get(yuva.get("stil", ""), "")) if x)
        bilgi = m06_materyal._yapay_zeka_gorseli(ayar, sorgu, yuva["dikey"], hedef)
        if bilgi:
            bilgi = {**bilgi, "dosya": str(hedef), "sorgu": yuva["sorgu"]}
    if not bilgi or bilgi.get("kaynak") == "Otomatik kart":
        return None
    return bilgi


def _sec(yuva: dict, adaylar: list[dict]) -> dict | None:
    if not adaylar:
        return None
    en_iyi = max(adaylar, key=lambda a: a.get("puan", 0))
    yuva["hedef"].parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(en_iyi["dosya"], yuva["hedef"])
    bilgi = {**en_iyi, "dosya": str(yuva["hedef"])}
    yuva["hedef"].with_suffix(".hazir.json").write_text(json.dumps(bilgi, ensure_ascii=False), encoding="utf-8")
    return en_iyi


def hazirla(ayar: Ayarlar, kod: str, icerik: dict, sure_sn: float) -> dict:
    """Süre sınırı içinde ilerler; durum CIKTI/<kod>/hazirlik.json'da. Döner: durum."""
    bas = time.time()
    hz = ayar["hazirlik"]
    d = json_oku(_durum_yolu(kod), {}) or {}
    d.setdefault("baslangic", ayar.simdi.isoformat(timespec="minutes"))
    d.setdefault("yuvalar", {})
    nis = icerik["plan"]["nis"]
    hedef_aday = 1 if ayar.deneme else int(hz["aday_sayisi"])

    if not d.get("senaryo_denetlendi"):
        d["duzeltilen_shorts"] = senaryo_denetle(ayar, kod, icerik, 70 if d.get("kati") else 90)
        d["senaryo_denetlendi"] = True
        json_yaz(_durum_yolu(kod), d)

    for metin, yol, sira, toplam, ek in seslendirmeler(icerik, kod):
        if time.time() - bas > sure_sn:
            break
        m05_seslendirme.seslendir(ayar, metin, yol, sira, toplam, ek_hiz=ek)  # önbellekli

    kullanilan: set[str] = set()
    stil = (icerik["plan"].get("deney") or {}).get("gorsel_stili", "")
    for yuva in yuvalar(icerik, kod):
        yuva["stil"] = stil
        kayit = d["yuvalar"].setdefault(yuva["ad"], {"adaylar": [], "denenen": 0})
        while kayit["denenen"] < hedef_aday + kayit.get("hedef_ek", 0) and time.time() - bas <= sure_sn:
            n = kayit["denenen"]
            kayit["denenen"] += 1
            bilgi = aday_uret(ayar, yuva, n, nis, kullanilan)
            if bilgi:
                bilgi.update(secici.puanla(Path(bilgi["dosya"]), yuva["sorgu"]) if not ayar.deneme else {"puan": 50})
                kayit["adaylar"].append(bilgi)
            json_yaz(_durum_yolu(kod), d)
        if kayit["denenen"] >= hedef_aday + kayit.get("hedef_ek", 0) and not kayit.get("secilen"):
            secilen = _sec(yuva, kayit["adaylar"])
            kayit["secilen"] = secilen["dosya"] if secilen else ""
            kayit["puan"] = secilen.get("puan") if secilen else None
    sesler_tamam = all(Path(y).with_suffix(".json").exists() for _, y, *_ in seslendirmeler(icerik, kod))
    d["hazir"] = sesler_tamam and all(k.get("secilen") is not None and k["denenen"] >= hedef_aday + k.get("hedef_ek", 0)
                                      for k in d["yuvalar"].values())
    puanlar = [k["puan"] for k in d["yuvalar"].values() if k.get("puan") is not None]
    d["ortalama_puan"] = round(sum(puanlar) / len(puanlar), 1) if puanlar else None
    json_yaz(_durum_yolu(kod), d)
    log.info("Hazırlık %s: %s (ortalama görsel puanı %s, %.0f sn)", kod, "HAZIR" if d["hazir"] else "devam ediyor",
             d["ortalama_puan"], time.time() - bas)
    return d


def yeniden_hazirla(ayar: Ayarlar, kod: str, tur: str, sira: int, metin: bool = False) -> None:
    """Kalite Denetçisi'nden geri dönüş: zayıf görsel yuvalarına 2'şer aday daha, istenirse Shorts metnini kısalt."""
    d = json_oku(_durum_yolu(kod), {}) or {}
    d["onarim_denemesi"] = d.get("onarim_denemesi", 0) + 1
    onek = "sahne_" if tur == "uzun" else f"shorts_{sira}_"
    esik = float(ayar["denetim"]["zayif_gorsel_esigi"]) + 10
    for ad, k in (d.get("yuvalar") or {}).items():
        if ad.startswith(onek) and (k.get("puan") is None or k["puan"] < esik):
            k["hedef_ek"] = k.get("hedef_ek", 0) + 2
            k.pop("secilen", None)
            (CIKTI / kod / "gorseller" / f"{ad}.hazir.json").unlink(missing_ok=True)
    if metin:
        d["senaryo_denetlendi"], d["kati"] = False, True
    d["hazir"] = False
    d["baslangic"] = ayar.simdi.isoformat(timespec="minutes")
    json_yaz(_durum_yolu(kod), d)


def uretime_hazir(ayar: Ayarlar, kod: str) -> bool:
    """Hazırlık bittiyse ya da en fazla bekleme süresi dolduysa (eldeki en iyilerle) üretime geç."""
    if ayar.deneme or not ayar["hazirlik"]["acik"]:
        return True
    d = json_oku(_durum_yolu(kod), {}) or {}
    if d.get("hazir"):
        return True
    if not d.get("baslangic"):
        return False
    gecen = (ayar.simdi.replace(tzinfo=None) - datetime.fromisoformat(d["baslangic"]).replace(tzinfo=None))
    return gecen.total_seconds() / 3600 >= float(ayar["hazirlik"]["en_fazla_saat"])
