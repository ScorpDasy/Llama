"""Kalite Denetçisi — her video yayına çıkmadan önce yerelde muayene edilir, kusur varsa onarılır (ücretsiz).

Ölçülenler (ffmpeg ile tek geçiş):
- Ses düzeyi (LUFS) ve tepe noktası
- Uzun sessizlik
- Siyah kare
- Donmuş görüntü
- Süre (Shorts 60 sn'yi aşmamalı)

Hazırlık kayıtlarından ayrıca şunlara bakılır: görsellerin cümleye uygunluk puanı ve görselsiz (kart) kalan yuvalar.
Her kusur türünün birkaç onarım yolu vardır. Hangisinin gerçekten işe yaradığı Thompson örneklemesiyle öğrenilir.
"Birbirinize öğretin": öğrenilen onarım bilgisi kanalın kendi klasörüne yazılır ama TÜM kanallardan okunur.
Bir kanalda işe yarayan çözümü diğerleri de hemen kullanır. Sonuçlar Öğrenme Mühendisi'ne de ders olur
(ör. görsel puanı sık düşükse aday sayısı artırılır).
"""
from __future__ import annotations

import random
import re
import subprocess
from pathlib import Path

from . import optimizasyon
from .ayarlar import CIKTI, KANAL_VERI, Ayarlar, csv_ekle, csv_oku, isletme_dosyalari, json_oku, json_yaz, log

KUSURLAR = {  # kusur: (ağırlık, onarım yolları)
    "ses_duzeyi": (15, ["yeniden_uret"]),
    "kirpma": (10, ["yeniden_uret"]),
    "uzun_sessizlik": (15, ["seslendirmeyi_yenile", "yeniden_uret"]),
    "siyah_kare": (25, ["klasik_hareket", "yeniden_uret"]),
    "donuk_goruntu": (20, ["klasik_hareket", "yeniden_uret"]),
    "shorts_uzun": (30, ["hizlandir", "metni_kisalt"]),
    "zayif_gorsel": (20, ["daha_fazla_aday"]),
    "gorselsiz_yuva": (10, ["daha_fazla_aday"]),
}
ERTELEYEN = {"daha_fazla_aday", "metni_kisalt"}   # bu onarımlar hazırlık aşamasında yapılır (yükleme ertelenir)
KALITE = "kalite.csv"
ONARIM = "onarim.json"


class Ertele(Exception):
    """Video bu çalıştırmada yüklenmez; hazırlık aşaması eksikleri tamamlayınca yeniden üretilir."""


# ------------------------------------------------------------ ölçüm

def olc(video: Path) -> dict:
    sonuc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(video),
         "-af", "ebur128=peak=true,silencedetect=n=-45dB:d=1.2",
         "-vf", "blackdetect=d=0.8:pix_th=0.08,freezedetect=n=0.002:d=2.5", "-f", "null", "-"],
        capture_output=True, text=True)
    m = sonuc.stderr
    ozet = m[m.rfind("Summary:"):] if "Summary:" in m else m
    lufs = re.search(r"I:\s+(-?[\d.]+) LUFS", ozet)
    tepe = re.search(r"Peak:\s+(-?[\d.inf]+) dBFS", ozet)
    sure = re.findall(r"Duration: (\d+):(\d+):([\d.]+)", m)
    toplam = (int(sure[0][0]) * 3600 + int(sure[0][1]) * 60 + float(sure[0][2])) if sure else 0.0
    sessiz = [(float(b), float(d)) for b, d in zip(re.findall(r"silence_start: ([\d.]+)", m),
                                                   re.findall(r"silence_duration: ([\d.]+)", m))]
    siyah = [(float(b), float(d)) for b, d in re.findall(r"black_start:([\d.]+) black_end:[\d.]+ black_duration:([\d.]+)", m)]
    donuk = [float(d) for d in re.findall(r"freeze_duration: ([\d.]+)", m)]
    return {"lufs": float(lufs.group(1)) if lufs else None,
            "tepe": float(tepe.group(1)) if tepe and "inf" not in tepe.group(1) else None,
            "sure": round(toplam, 2), "sessizlik": sessiz, "siyah": siyah, "donuk": donuk}


def _gorsel_ozeti(kod: str, tur: str, sira: int) -> dict:
    d = json_oku(CIKTI / kod / "hazirlik.json", {}) or {}
    onek = "sahne_" if tur == "uzun" else f"shorts_{sira}_"
    yuvalar = [k for a, k in (d.get("yuvalar") or {}).items() if a.startswith(onek)]
    puanlar = [k["puan"] for k in yuvalar if k.get("puan") is not None]
    return {"ortalama": round(sum(puanlar) / len(puanlar), 1) if puanlar else None,
            "gorselsiz": sum(1 for k in yuvalar if k.get("secilen") == ""), "yuva": len(yuvalar)}


def denetle(ayar: Ayarlar, video: Path, kod: str, tur: str, sira: int = 0) -> dict:
    """Karne: {"puan": 0-100, "kusurlar": [ad, ...], "olcum": {...}}."""
    o = olc(video)
    g = _gorsel_ozeti(kod, tur, sira)
    kusur = []
    if o["lufs"] is not None and abs(o["lufs"] + 14) > 2.5:
        kusur.append("ses_duzeyi")
    if o["tepe"] is not None and o["tepe"] > -0.3:
        kusur.append("kirpma")
    son = o["sure"] - (6 if tur == "uzun" else 1)  # kapanıştaki doğal sessizlik sayılmaz
    if any(b < son for b, _d in o["sessizlik"]):
        kusur.append("uzun_sessizlik")
    if any(d >= 0.8 for _b, d in o["siyah"]):
        kusur.append("siyah_kare")
    if o["donuk"]:
        kusur.append("donuk_goruntu")
    if tur == "shorts" and o["sure"] > 59.5:
        kusur.append("shorts_uzun")
    if g["ortalama"] is not None and g["ortalama"] < float(ayar["denetim"]["zayif_gorsel_esigi"]):
        kusur.append("zayif_gorsel")
    if g["yuva"] and g["gorselsiz"] / g["yuva"] > 0.25:
        kusur.append("gorselsiz_yuva")
    puan = max(0, 100 - sum(KUSURLAR[k][0] for k in kusur))
    return {"puan": puan, "kusurlar": kusur, "olcum": {**o, "gorsel": g}}


# ------------------------------------------------------------ onarım öğrenimi (kanallar arası)

def _gozlemler() -> dict[str, list]:
    """Tüm kanalların onarım deneyimi (birbirinden öğrenme)."""
    havuz: dict[str, list] = {}
    for dosya in isletme_dosyalari(ONARIM):
        for kusur, liste in ((json_oku(dosya, {}) or {}).get("gozlemler") or {}).items():
            havuz.setdefault(kusur, []).extend(liste)
    return havuz


def onarim_sec(ayar: Ayarlar, kusur: str, denenen: set[str]) -> str | None:
    yollar = [y for y in KUSURLAR[kusur][1] if y not in denenen]
    if not yollar:
        return None
    gozlem = [g for g in _gozlemler().get(kusur, []) if g[0] in yollar]
    post = optimizasyon.posterior(optimizasyon.yasli(gozlem, ayar.simdi.date()), yollar, 90)
    return optimizasyon.thompson_sec(post, random.Random())


def onarim_kaydet(ayar: Ayarlar, kusur: str, yol: str, basarili: bool) -> None:
    dosya = KANAL_VERI / ONARIM
    d = json_oku(dosya, {}) or {}
    d.setdefault("gozlemler", {}).setdefault(kusur, []).append(
        [yol, 1.0 if basarili else 0.0, ayar.simdi.date().isoformat(), ayar.kanal])
    d["gozlemler"][kusur] = d["gozlemler"][kusur][-200:]
    json_yaz(dosya, d)


def onarim_uygula(ayar: Ayarlar, yol: str, kod: str, tur: str, sira: int) -> None:
    """Onarımın ayar/dosya tarafı. Ertelenen onarımlar hazırlık kaydını işaretler ve Ertele fırlatır."""
    if yol == "klasik_hareket":
        ayar.genel["video"]["paralaks"] = False
    elif yol == "hizlandir":  # Shorts anlatımı daha hızlı seslendirilir (süre kısalır)
        ayar.genel["ses"]["shorts_ek_hiz"] = 22
    elif yol == "seslendirmeyi_yenile":
        desen = "[0-9]*.json" if tur == "uzun" else f"shorts_{sira}_*.json"
        for yan in (CIKTI / kod / "ses").glob(desen):
            yan.unlink(missing_ok=True)
    elif yol in ERTELEYEN:
        from . import hazirlik
        hazirlik.yeniden_hazirla(ayar, kod, tur, sira, metin=(yol == "metni_kisalt"))
        raise Ertele(f"{kod}: {yol} için hazırlığa geri gönderildi")


def denetle_ve_onar(ayar: Ayarlar, kod: str, tur: str, sira: int, uret, sonuc):
    """uret(ayar) -> sonuç (video yolu içeren). Kusur varsa en fazla N kez onarıp yeniden üretir.
    Döner: (son sonuç, karne). Onarımın işe yarayıp yaramadığı kaydedilir (öğrenme)."""
    if ayar.deneme or not ayar["denetim"]["acik"]:
        return sonuc, None
    video = Path(sonuc["video"] if isinstance(sonuc, dict) else sonuc)
    karne = denetle(ayar, video, kod, tur, sira)
    denenen: set[str] = set()
    hazir = json_oku(CIKTI / kod / "hazirlik.json", {}) or {}
    import copy
    ayar_onarim = copy.deepcopy(ayar)  # onarım ayarları yalnızca bu videoya uygulanır
    for _ in range(int(ayar["denetim"]["en_fazla_onarim"])):
        if karne["puan"] >= float(ayar["denetim"]["gecme_puani"]) and not karne["kusurlar"]:
            break
        adaylar = sorted(karne["kusurlar"], key=lambda k: -KUSURLAR[k][0])
        kusur = next((k for k in adaylar if onarim_sec(ayar, k, denenen)), None)
        if not kusur:
            break
        yol = onarim_sec(ayar, kusur, denenen)
        if yol in ERTELEYEN and hazir.get("onarim_denemesi", 0) >= 1:
            denenen.add(yol)  # hazırlığa bir kez geri gönderildi; tekrar erteleme yok
            continue
        denenen.add(yol)
        log.info("Kalite onarımı (%s %s): %s → %s", kod, tur, kusur, yol)
        try:
            onarim_uygula(ayar_onarim, yol, kod, tur, sira)
        except Ertele:
            _karne_yaz(ayar, kod, tur, sira, karne, f"ertelendi:{yol}")
            raise
        sonuc = uret(ayar_onarim)
        video = Path(sonuc["video"] if isinstance(sonuc, dict) else sonuc)
        yeni = denetle(ayar, video, kod, tur, sira)
        onarim_kaydet(ayar, kusur, yol, kusur not in yeni["kusurlar"])
        karne = yeni
    _karne_yaz(ayar, kod, tur, sira, karne, ",".join(sorted(denenen)))
    return sonuc, karne


def _karne_yaz(ayar: Ayarlar, kod: str, tur: str, sira: int, karne: dict, onarim: str) -> None:
    o = karne["olcum"]
    csv_ekle(KANAL_VERI / KALITE, [{
        "tarih": ayar.simdi.isoformat(timespec="minutes"), "kod": kod, "tur": tur, "sira": sira,
        "puan": karne["puan"], "kusurlar": " ".join(karne["kusurlar"]), "onarim": onarim,
        "lufs": o.get("lufs"), "sure": o.get("sure"), "gorsel_puani": o["gorsel"].get("ortalama")}],
        ["tarih", "kod", "tur", "sira", "puan", "kusurlar", "onarim", "lufs", "sure", "gorsel_puani"])
    log.info("Kalite karnesi %s %s#%s: %s/100 %s", kod, tur, sira, karne["puan"], karne["kusurlar"] or "kusursuz")


def sik_kusurlar(gun: int = 30, tum_kanallar: bool = False) -> dict[str, int]:
    """Son günlerde en sık görülen kusurlar (Öğrenme Mühendisi için)."""
    from datetime import datetime, timedelta
    sinir = (datetime.now() - timedelta(days=gun)).isoformat()
    dosyalar = isletme_dosyalari(KALITE) if tum_kanallar else [KANAL_VERI / KALITE]
    sayac: dict[str, int] = {}
    for d in dosyalar:
        for r in csv_oku(d):
            if r.get("tarih", "") >= sinir:
                for k in (r.get("kusurlar") or "").split():
                    sayac[k] = sayac.get(k, 0) + 1
    return sayac


def durum_bolumu() -> list[str]:
    satirlar = [r for d in isletme_dosyalari(KALITE) for r in csv_oku(d)]
    if not satirlar:
        return []
    son = sorted(satirlar, key=lambda r: r["tarih"])[-20:]
    ort = sum(float(r["puan"]) for r in son) / len(son)
    sik = sik_kusurlar(30, tum_kanallar=True)
    ogrenilen = {k: len(v) for k, v in _gozlemler().items()}
    md = ["", "## 🩺 Kalite Denetçisi", f"- Son {len(son)} videonun ortalama kalite puanı: **{ort:.0f}/100**"]
    if sik:
        md.append("- Son 30 günün kusurları: " + ", ".join(f"{k} ×{n}" for k, n in sorted(sik.items(), key=lambda x: -x[1])))
    if ogrenilen:
        md.append("- Kanallar arası onarım deneyimi: " + ", ".join(f"{k} ({n} deneme)" for k, n in ogrenilen.items()))
    return md
