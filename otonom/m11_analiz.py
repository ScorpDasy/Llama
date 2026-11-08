"""MODÜL 11 — Performans analizi ve LABORATUVAR.

Orijinal formül (Görüntülenme×0.5 + CTR×0.3 + Süre×0.2) farklı ölçekleri topladığı için
izlenme sayısı her şeyi ezer. Burada her metrik önce kanal içi YÜZDELİK SIRAYA
çevrilir (0-100), sonra ağırlıklandırılır; Shorts ve uzun videolar ayrı karşılaştırılır.
Sonuçlar Thompson örneklemesine (optimizasyon.py) gözlem olarak verilir: niş, başlık stili,
video uzunluğu ve yayın saati seçimleri buna göre her hafta yeniden yapılır.
Veriler Google Sheets yerine git'teki CSV'de tutulur (ek hesap/izin gerekmez).
"""
from __future__ import annotations

import statistics
from datetime import date, datetime

import requests

from .ayarlar import KANAL_VERI as VERI, Ayarlar, csv_ekle, csv_oku, gizli, json_oku, json_yaz, log, ozet_yaz

METRIK_ALANLARI = ["tarih", "youtube_id", "kod", "nis", "tur", "goruntulenme", "begeni", "yorum",
                   "izlenme_dakika", "ort_izlenme_sn", "ort_izlenme_yuzde", "abone_kazanimi"]


def _istatistik(idler: list[str]) -> dict[str, dict]:
    """Herkese açık sayılar: 50 video başına 1 kota birimi."""
    anahtar = gizli("YOUTUBE_API_KEY")
    sonuc: dict[str, dict] = {}
    for i in range(0, len(idler), 50):
        parca = idler[i:i + 50]
        try:
            if anahtar:
                r = requests.get("https://www.googleapis.com/youtube/v3/videos", timeout=20,
                                 params={"part": "statistics", "id": ",".join(parca), "key": anahtar}).json()
                ogeler = r.get("items", [])
            else:
                from .m09_youtube_yukleme import kimlik_var, servis
                if not kimlik_var():
                    return {}
                ogeler = servis().videos().list(part="statistics", id=",".join(parca)).execute().get("items", [])
            for o in ogeler:
                s = o["statistics"]
                sonuc[o["id"]] = {"goruntulenme": int(s.get("viewCount", 0)), "begeni": int(s.get("likeCount", 0)),
                                  "yorum": int(s.get("commentCount", 0))}
        except Exception as e:  # ağ/kota hatası analizi durdurmasın
            log.warning("İstatistik alınamadı: %s", e)
    return sonuc


def _analitik(idler: list[str], baslangic: str) -> dict[str, dict]:
    """İzlenme süresi metrikleri (YouTube Analytics API, OAuth gerekir; yoksa atlanır)."""
    from .m09_youtube_yukleme import kimlik_var, servis
    if not (idler and kimlik_var()):
        return {}
    try:
        cevap = servis("youtubeAnalytics", "v2").reports().query(
            ids="channel==MINE", startDate=baslangic, endDate=date.today().isoformat(),
            metrics="estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained",
            dimensions="video", filters="video==" + ",".join(idler[:200]), maxResults=200).execute()
        return {r[0]: {"izlenme_dakika": r[1], "ort_izlenme_sn": r[2], "ort_izlenme_yuzde": r[3],
                       "abone_kazanimi": r[4]} for r in cevap.get("rows", [])}
    except Exception as e:
        log.warning("Analytics alınamadı (refresh token'da yt-analytics izni olmalı): %s", e)
        return {}


def yuzdelik(degerler: list[float]) -> list[float]:
    """Her değerin listede kaçıncı yüzdelikte olduğunu (0-100) döner; eşitlere ortalama sıra."""
    if len(degerler) <= 1:
        return [50.0] * len(degerler)
    sirali = sorted(degerler)
    sonuc = []
    for d in degerler:
        alt = sum(1 for x in sirali if x < d)
        esit = sum(1 for x in sirali if x == d)
        sonuc.append(100 * (alt + (esit - 1) / 2) / (len(degerler) - 1))
    return sonuc


def puanla(videolar: list[dict]) -> list[dict]:
    """Aynı türdeki (uzun/shorts) videolar arasında 0-100 performans puanı.
    İzlenme bileşeni yaşa göre düzeltilmiştir (kanalın izlenme-yaş eğrisinden sapma)."""
    from .optimizasyon import yas_duzeltilmis

    for tur in {v["tur"] for v in videolar}:
        grup = [v for v in videolar if v["tur"] == tur]
        hiz = yuzdelik(yas_duzeltilmis(grup))
        tutma = yuzdelik([float(v.get("ort_izlenme_yuzde") or 0) for v in grup])
        etk = yuzdelik([(v["begeni"] + 2 * v["yorum"]) / max(1, v["goruntulenme"]) for v in grup])
        tutma_var = any(v.get("ort_izlenme_yuzde") for v in grup)
        for v, h, t, e in zip(grup, hiz, tutma, etk):
            v["skor"] = round(0.4 * h + 0.4 * t + 0.2 * e if tutma_var else 0.65 * h + 0.35 * e, 1)
    return videolar


def ogrenim(ayar: Ayarlar, olgun: list[dict], bugun: date) -> dict:
    """Thompson gözlemlerini ve her seçeneğin 'en iyi olma' olasılığını veri/optimizasyon.json'a yazar."""
    from . import m04_senaryo, optimizasyon as opt

    gozlem = opt.gozlemleri_topla(olgun, m04_senaryo.yukle)
    yo = float(ayar["optimizasyon"]["yari_omur_gun"])
    kaynaklar = sorted({k.get("tur", "youtube_oneri") for n in ayar.nisler for k in n.get("kaynaklar") or []} | {"model"})
    deneyler = {"nis": [n["kod"] for n in ayar.nisler], **ayar["optimizasyon"]["deneyler"], "kaynak": kaynaklar}
    olasilik = {ad: opt.kazanma_olasiligi(opt.posterior(opt.yasli(gozlem.get(ad, []), bugun), kollar, yo))
                for ad, kollar in deneyler.items() if kollar}
    veri = {"guncelleme": bugun.isoformat(), "gozlemler": gozlem, "olasiliklar": olasilik}
    json_yaz(VERI / "optimizasyon.json", veri)
    return veri


def ortak_ozellikler(videolar: list[dict]) -> list[str]:
    if len(videolar) < 6:
        return ["Yeterli veri yok (en az 6 değerlendirilmiş video gerekir)."]
    sirali = sorted(videolar, key=lambda v: -v["skor"])
    ust, alt = sirali[:3], sirali[3:]
    def ort(liste, f):
        return statistics.mean(f(v) for v in liste)
    bulgular = [
        f"En iyi 3'ün nişleri: {', '.join(v['nis'] for v in ust)}",
        f"Başlık uzunluğu: en iyiler {ort(ust, lambda v: len(v['baslik'])):.0f} karakter, diğerleri {ort(alt, lambda v: len(v['baslik'])):.0f}",
        f"Başlıkta sayı: en iyilerde %{100 * ort(ust, lambda v: any(c.isdigit() for c in v['baslik'])):.0f}, diğerlerinde %{100 * ort(alt, lambda v: any(c.isdigit() for c in v['baslik'])):.0f}",
        f"Soru başlığı: en iyilerde %{100 * ort(ust, lambda v: '?' in v['baslik']):.0f}, diğerlerinde %{100 * ort(alt, lambda v: '?' in v['baslik']):.0f}",
    ]
    sureler = [v for v in ust if v.get("sure_sn")]
    if sureler:
        bulgular.append(f"En iyilerin ortalama süresi: {ort(sureler, lambda v: float(v['sure_sn'])) / 60:.1f} dk")
    return bulgular


# ------------------------------------------------------------ A/B başlık testi
AB_DOSYASI = VERI / "ab_testleri.csv"
AB_ALANLARI = ["tarih", "youtube_id", "kod", "eski_baslik", "yeni_baslik", "izlenme_once", "hiz_once",
               "hiz_sonra", "durum"]


def _baslik_degistir(youtube_id: str, baslik: str) -> bool:
    """snippet güncellenirken açıklama/etiket silinmesin diye önce mevcut snippet okunur (1 + 50 birim)."""
    from .m09_youtube_yukleme import kota_harca, kota_yeterli, servis
    if not kota_yeterli(51):
        return False
    yt = servis()
    ogeler = yt.videos().list(part="snippet", id=youtube_id).execute().get("items", [])
    if not ogeler:
        return False
    snip = ogeler[0]["snippet"]
    govde = {"id": youtube_id, "snippet": {k: snip[k] for k in ("title", "description", "tags", "categoryId",
                                                               "defaultLanguage") if k in snip}}
    govde["snippet"]["title"] = baslik[:100]
    yt.videos().update(part="snippet", body=govde).execute()
    kota_harca(51)
    return True


def ab_testi(ayar: Ayarlar, olgun: list[dict], bugun: date, haftalik_yeni: int = 2) -> list[str]:
    """Zayıf uzun videolarda alternatif başlığı dener; 7 gün sonra izlenme hızına göre karar verir."""
    from .m09_youtube_yukleme import kimlik_var
    if ayar.deneme or not kimlik_var():
        return []
    testler = csv_oku(AB_DOSYASI)
    v_by_id = {v["youtube_id"]: v for v in olgun}
    notlar = []
    for t in testler:  # 1) biten testleri değerlendir
        v = v_by_id.get(t["youtube_id"])
        gun = (bugun - date.fromisoformat(t["tarih"])).days
        if t["durum"] != "test" or not v or gun < 7:
            continue
        hiz_sonra = (v["goruntulenme"] - int(t["izlenme_once"])) / gun
        t["hiz_sonra"] = f"{hiz_sonra:.1f}"
        if hiz_sonra >= float(t["hiz_once"]):
            t["durum"] = "kazandi"
            notlar.append(f"✅ Yeni başlık kazandı: {t['yeni_baslik']} ({t['hiz_once']} → {hiz_sonra:.1f} izlenme/gün)")
        elif _baslik_degistir(t["youtube_id"], t["eski_baslik"]):
            t["durum"] = "geri_alindi"
            notlar.append(f"↩️ Eski başlığa dönüldü: {t['eski_baslik']}")
    denenen = {t["youtube_id"] for t in testler}
    adaylar = sorted((v for v in olgun if v["tur"] == "uzun" and 7 <= v["yas_gun"] <= 45
                      and v.get("skor", 100) < 40 and v["youtube_id"] not in denenen), key=lambda v: v["skor"])
    for v in adaylar[:haftalik_yeni]:  # 2) yeni testler başlat
        icerik = json_oku(VERI / "videolar" / v["kod"] / "icerik.json", {})
        alternatif = (icerik.get("alternatif_basliklar") or [""])[0]
        if alternatif and _baslik_degistir(v["youtube_id"], alternatif):
            testler.append({"tarih": bugun.isoformat(), "youtube_id": v["youtube_id"], "kod": v["kod"],
                            "eski_baslik": v["baslik"], "yeni_baslik": alternatif,
                            "izlenme_once": v["goruntulenme"],
                            "hiz_once": f"{v['goruntulenme'] / max(1, v['yas_gun']):.1f}", "hiz_sonra": "",
                            "durum": "test"})
            notlar.append(f"🧪 Başlık testi başladı: '{v['baslik']}' → '{alternatif}'")
    if testler:
        import csv
        with AB_DOSYASI.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=AB_ALANLARI)
            w.writeheader()
            w.writerows(testler)
    return notlar


def video_kimligi(link: str) -> str:
    """youtu.be/ID, watch?v=ID, shorts/ID veya çıplak 11 karakterlik kimliği ayıklar."""
    import re

    m = re.search(r"(?:youtu\.be/|v=|shorts/|embed/)([A-Za-z0-9_-]{11})", link or "")
    if m:
        return m.group(1)
    link = (link or "").strip()
    return link if re.fullmatch(r"[A-Za-z0-9_-]{11}", link) else ""


def elle_yuklenenleri_ekle(ayar: Ayarlar) -> int:
    """config/elle_yuklenenler.yaml'daki linkleri yayın kaydına ekler (öğrenme motoru bunları da kullanır)."""
    import yaml

    from . import m04_senaryo
    from .ayarlar import CONFIG
    from .orkestrator import DURUM, YAYIN_ALANLARI

    dosya = CONFIG / "elle_yuklenenler.yaml"
    if not dosya.exists():
        return 0
    try:
        girdiler = (yaml.safe_load(dosya.read_text(encoding="utf-8")) or {}).get("videolar") or {}
    except yaml.YAMLError as e:
        from .ayarlar import uyari_ekle
        uyari_ekle("ayar", f"elle_yuklenenler.yaml okunamadı: {str(e).splitlines()[0]}")
        return 0
    mevcut = {s["youtube_id"] for s in csv_oku(VERI / "yayinlananlar.csv")}
    durum = json_oku(DURUM, {"kuyruk": []})
    eklenen = 0
    for anahtar, link in girdiler.items():
        kod, _, ek = str(anahtar).partition("#")
        vid = video_kimligi(str(link))
        icerik = m04_senaryo.yukle(kod)
        if not vid or vid in mevcut or not icerik:
            continue
        shorts = ek.startswith("shorts")
        sira = int(ek[6:] or 0) if shorts else 0
        csv_ekle(VERI / "yayinlananlar.csv", [{
            "tarih": ayar.simdi.isoformat(timespec="seconds"), "kod": kod, "nis": icerik["plan"]["nis"],
            "tur": "shorts" if shorts else "uzun", "sira": sira, "youtube_id": vid,
            "baslik": icerik["shorts"][sira]["baslik"] if shorts and sira < len(icerik["shorts"]) else icerik["baslik"],
            "yayin_zamani": "", "sure_sn": 0, "kelime": icerik.get("kelime", 0)}], YAYIN_ALANLARI)
        for i in durum["kuyruk"]:
            if i["kod"] == kod and i["tur"] == ("shorts" if shorts else "uzun") and i["sira"] == sira:
                i["durum"], i["youtube_id"] = "yuklendi", vid
        mevcut.add(vid)
        eklenen += 1
    if eklenen:
        json_yaz(DURUM, durum)
        log.info("Elle yüklenen %d video kayda eklendi.", eklenen)
    return eklenen


def calistir(ayar: Ayarlar, tam_rapor: bool = True) -> dict:
    elle_yuklenenleri_ekle(ayar)
    yayin = [s for s in csv_oku(VERI / "yayinlananlar.csv")
             if s.get("youtube_id") and not s["youtube_id"].startswith("DENEME")]
    if not yayin:
        log.info("Analiz: henüz yayınlanmış video yok.")
        return {}
    idler = [s["youtube_id"] for s in yayin]
    ist = _istatistik(idler)
    ilk = min(s["tarih"][:10] for s in yayin)
    ana = _analitik([s["youtube_id"] for s in yayin if s["tur"] == "uzun"], ilk)
    bugun = ayar.simdi.date()

    videolar = []
    for s in yayin:
        v = {**s, **{"goruntulenme": 0, "begeni": 0, "yorum": 0}, **ist.get(s["youtube_id"], {}),
             **ana.get(s["youtube_id"], {})}
        v["yas_gun"] = (bugun - datetime.fromisoformat(s["tarih"]).date()).days
        videolar.append(v)
    if tam_rapor:  # haftalık anlık görüntü (depo küçük kalsın diye günlük değil)
        csv_ekle(VERI / "metrikler.csv", [{**v, "tarih": bugun.isoformat()} for v in videolar], METRIK_ALANLARI)

    # Laboratuvar tetikleyicisi: viral video -> devam videosu kuyruğa
    oncelik = json_oku(VERI / "oncelikli_konular.json", [])
    takip = {o.get("kaynak") for o in oncelik} | set(json_oku(VERI / "viral_takip.json", []))
    for v in videolar:
        if v["goruntulenme"] >= int(ayar["laboratuvar"]["viral_esik"]) and v["youtube_id"] not in takip:
            oncelik.append({"nis": v["nis"], "konu": f"'{v['baslik']}' videosunun devamı / daha derin versiyonu",
                            "kaynak": v["youtube_id"]})
            takip.add(v["youtube_id"])
            log.info("Viral video bulundu, devam videosu planlandı: %s", v["baslik"])
    json_yaz(VERI / "oncelikli_konular.json", oncelik)
    json_yaz(VERI / "viral_takip.json", sorted(t for t in takip if t))

    olgun = [v for v in videolar if v["yas_gun"] >= int(ayar["laboratuvar"]["min_veri_gunu"])]
    if not (tam_rapor and olgun):
        return {"videolar": videolar}
    puanla(olgun)
    ogren = ogrenim(ayar, olgun, bugun)

    sirali = sorted(olgun, key=lambda v: -v["skor"])
    zayif = [v for v in sirali if v["yas_gun"] >= 28][-max(1, len(sirali) // 5):] if len(sirali) >= 5 else []
    md = [f"# Laboratuvar Raporu — {bugun}", "",
          "| Video | Tür | Niş | Görüntülenme | İzlenme % | Puan |", "|---|---|---|---|---|---|"]
    md += [f"| [{v['baslik'][:50]}](https://youtu.be/{v['youtube_id']}) | {v['tur']} | {v['nis']} | "
           f"{v['goruntulenme']} | {v.get('ort_izlenme_yuzde') or '-'} | {v['skor']} |" for v in sirali[:25]]
    md += ["", "## En başarılı videoların ortak özellikleri", *[f"- {b}" for b in ortak_ozellikler(olgun)],
           "", "## Laboratuvar öğrenimi (her seçeneğin en iyi olma olasılığı)",
           *[f"- **{ad}**: " + ", ".join(f"{k} %{100 * p:.0f}" for k, p in sorted(o.items(), key=lambda x: -x[1]))
             for ad, o in ogren["olasiliklar"].items()]]
    if zayif:
        md += ["", "## Yeniden düzenlenecekler (başlık + küçük resim değiştirin; silmeyin, izlenme saatini korur)",
               *[f"- {v['baslik']} — puan {v['skor']}" for v in zayif]]
    ab = ab_testi(ayar, olgun, bugun)
    if ab:
        md += ["", "## A/B başlık testleri", *[f"- {n}" for n in ab]]
    md.append("\n> CTR (tıklama oranı) API'de yok: YouTube Studio > Analytics > Erişim sekmesinden bakın.")
    rapor = "\n".join(md) + "\n"
    (VERI / "raporlar").mkdir(exist_ok=True)
    (VERI / "raporlar" / f"lab-{bugun}.md").write_text(rapor, encoding="utf-8")
    ozet_yaz(rapor)
    return {"videolar": videolar, "ogrenim": ogren}
