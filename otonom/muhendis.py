"""ÖĞRENME MÜHENDİSİ — sistemi her hafta kendi verisiyle geliştiren otonom bileşen.

Laboratuvar (Modül 11) ölçer; mühendis bu ölçümlerden SİSTEMİN KENDİSİNİ değiştirir:
  1. Deney evrimi   : başarısız seçenekleri emekliye ayırır, kazananın çevresinde yeni seçenek dener.
  2. Uyum hızı      : performans kayması algılarsa eski verinin etkisini hızlandırır (yarı ömür).
  3. Pazar keşfi    : başarılı videoların anahtar kelimelerini yeni arama tohumu yapar.
  4. Kendini onarma : tekrarlayan uyarılara göre ayar düzeltir (kota, bağlam, Shorts sayısı).
  5. Ders çıkarma   : en iyi/en kötü videoları yapay zekâyla karşılaştırır, senaryo yazarına kural ekler.
  6. Gözcülük       : kodla çözülmesi gereken sorunları ve yeni yerel model adaylarını GitHub issue yapar.
Güvenlik: tüm değişiklikler sınırlı aralıklarda, gerekçesiyle veri/muhendis_gunlugu.md'ye yazılır ve
veri/ogrenilen_ayarlar.yaml katmanında tutulur (kullanıcının config dosyalarına dokunulmaz).
Bu dosya silinirse sistem fabrika ayarlarına döner; config > muhendis > kilitli ile ayar korunabilir.
"""
from __future__ import annotations

import os
import statistics
from datetime import date, datetime, timedelta

import requests
import yaml

from . import llm, m04_senaryo, optimizasyon as opt
from .ayarlar import OGRENILEN, KANAL_VERI as VERI, Ayarlar, csv_oku, json_oku, json_yaz, log, ozet_yaz

GUNLUK = VERI / "muhendis_gunlugu.md"
DERSLER = VERI / "ogrenilen_dersler.json"
SINIRLAR = {"hedef_kelime": (500, 2000), "yari_omur_gun": (21, 120), "yerel_baglam": (8192, 16384)}
EN_FAZLA_KOL = 5


# ------------------------------------------------------------- yardımcılar

def _ogrenilen_oku() -> dict:
    return (yaml.safe_load(OGRENILEN.read_text(encoding="utf-8")) or {}) if OGRENILEN.exists() else {}


def _ogrenilen_yaz(veri: dict) -> None:
    OGRENILEN.parent.mkdir(parents=True, exist_ok=True)
    baslik = ("# Bu dosyayı Öğrenme Mühendisi yönetir (sistemin kendi verisinden öğrendiği ayarlar).\n"
              "# config/ayarlar.yaml'ın ÜZERİNE uygulanır. Silerseniz sistem fabrika ayarlarına döner.\n"
              "# Bir ayarı korumak için: config/ayarlar.yaml > muhendis > kilitli: [\"youtube.video_basina_shorts\"]\n")
    OGRENILEN.write_text(baslik + yaml.safe_dump(veri, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _ayarla(ogrenilen: dict, yol: str, deger) -> None:
    hedef = ogrenilen
    parcalar = yol.split(".")
    for p in parcalar[:-1]:
        hedef = hedef.setdefault(p, {})
    hedef[parcalar[-1]] = deger


def _saat(dk: int) -> str:
    dk = max(8 * 60, min(23 * 60, dk))
    return f"{dk // 60:02d}:{dk % 60:02d}"


def _dakika(saat: str) -> int:
    s, d = (int(x) for x in saat.split(":"))
    return s * 60 + d


# ------------------------------------------------------- 1. deney evrimi

def deneyleri_evrimlestir(ayar: Ayarlar, ogrenilen: dict, bugun: date) -> list[str]:
    gozlem = json_oku(VERI / "optimizasyon.json", {}).get("gozlemler", {})
    yo = float(ayar["optimizasyon"]["yari_omur_gun"])
    notlar = []
    for ad, kollar in ayar["optimizasyon"]["deneyler"].items():
        kollar = [str(k) for k in kollar]
        if len(kollar) < 2:
            continue
        post = opt.posterior(opt.yasli(gozlem.get(ad, []), bugun), kollar, yo)
        olas = opt.kazanma_olasiligi(post)
        yeni = list(kollar)
        # Budama: bol veriyle açıkça kaybeden kolu çıkar (en az 2 kol kalsın)
        for k in kollar:
            if olas[k] < 0.05 and post[k][2] >= 4 and len(yeni) > 2:
                yeni.remove(k)
                notlar.append(f"{ad}: '{k}' emekliye ayrıldı (en iyi olma olasılığı %{100 * olas[k]:.0f}, "
                              f"{post[k][2]:.1f} etkin gözlem)")
                if ad == "baslik_stili":  # keşif azalmasın: yerine havuzdan denenmemiş bir stil gelir
                    yedek = next((x for x in opt.BASLIK_STILLERI if x not in yeni and x not in kollar), None)
                    if yedek:
                        yeni.append(yedek)
                        notlar.append(f"{ad}: yerine yeni stil '{yedek}' denenecek")
        en_iyi = max(olas, key=olas.get)
        if olas[en_iyi] >= 0.6 and post[en_iyi][2] >= 6 and len(yeni) < EN_FAZLA_KOL:
            aday = _yeni_kol(ad, en_iyi, yeni)
            if aday is not None and str(aday) not in yeni:
                yeni.append(str(aday))
                notlar.append(f"{ad}: kazanan '{en_iyi}' (%{100 * olas[en_iyi]:.0f}) çevresinde yeni seçenek "
                              f"'{aday}' denenecek")
        if yeni != kollar:
            sayisal = ad == "hedef_kelime"
            _ayarla(ogrenilen, f"optimizasyon.deneyler.{ad}", [int(k) for k in yeni] if sayisal else yeni)
    return notlar


def _yeni_kol(ad: str, en_iyi: str, kollar: list[str]):
    if ad == "hedef_kelime":
        degerler = sorted(int(k) for k in kollar)
        b = int(en_iyi)
        alt, ust = SINIRLAR["hedef_kelime"]
        if b == degerler[-1]:
            return min(ust, b + 300)                         # en uzun kazanıyor -> daha uzunu dene
        if b == degerler[0]:
            return max(alt, b - 200)                         # en kısa kazanıyor -> daha kısayı dene
        komsu = min((d for d in degerler if d != b), key=lambda d: abs(d - b))
        return (b + komsu) // 2 // 50 * 50                   # iki iyi değerin arası
    if ad == "yayin_saati":
        b = _dakika(en_iyi)
        for fark in (90, -90, 45, -45):
            aday = _saat(b + fark)
            if aday not in kollar:
                return aday
        return None
    if ad == "baslik_stili":                                  # havuzdan denenmemiş stil
        return next((s for s in opt.BASLIK_STILLERI if s not in kollar), None)
    if ad == "gorsel_stili":
        from .hazirlik import STILLER
        return next((s for s in STILLER if s not in kollar), None)
    if ad == "muzik":
        from .ses_tasarimi import RUH_HALLERI
        return next((s for s in RUH_HALLERI if s not in kollar), None)
    return None


# ---------------------------------------------------------- 2. uyum hızı

def uyum_hizini_ayarla(ayar: Ayarlar, ogrenilen: dict, bugun: date) -> list[str]:
    gozlem = opt.yasli(json_oku(VERI / "optimizasyon.json", {}).get("gozlemler", {}).get("nis", []), bugun)
    yeni = [b for _, b, yas in gozlem if yas <= 28]
    eski = [b for _, b, yas in gozlem if yas > 28]
    if len(yeni) < 4 or len(eski) < 4:
        return []
    fark = 100 * (statistics.mean(yeni) - statistics.mean(eski))
    yo = float(ayar["optimizasyon"]["yari_omur_gun"])
    alt, ust = SINIRLAR["yari_omur_gun"]
    if abs(fark) > 15:
        hedef = max(alt, round(yo * 0.75))
        neden = f"son 4 haftada performans {fark:+.0f} puan kaydı (izleyici davranışı değişiyor)"
    elif abs(fark) < 5:
        hedef = min(ust, round(yo * 1.1))
        neden = "performans kararlı; daha uzun geçmişten öğrenilebilir"
    else:
        return []
    if hedef == round(yo):
        return []
    _ayarla(ogrenilen, "optimizasyon.yari_omur_gun", hedef)
    return [f"yarı ömür {yo:.0f} → {hedef} gün ({neden})"]


# -------------------------------------------------------- 3. pazar keşfi

def _puanlar() -> dict[str, float]:
    """video_id -> başarı (0-1), laboratuvarın son değerlendirmesinden."""
    return {g[3]: float(g[1]) for g in json_oku(VERI / "optimizasyon.json", {}).get("gozlemler", {}).get("nis", [])
            if len(g) > 3 and g[3]}


def tohumlari_evrimlestir(ayar: Ayarlar, ogrenilen: dict) -> list[str]:
    puan = _puanlar()
    if len(puan) < 6:
        return []
    esik = sorted(puan.values())[int(len(puan) * 0.8)]  # en iyi %20'lik dilim
    notlar, ek = [], ogrenilen.setdefault("nis_tohumlari", {})
    for y in csv_oku(VERI / "yayinlananlar.csv"):
        if y["tur"] != "uzun":
            continue
        icerik = m04_senaryo.yukle(y["kod"]) or {}
        kelime = (icerik.get("plan") or {}).get("anahtar_kelime", "").strip().lower()
        nis = next((n for n in ayar.nisler if n["kod"] == y["nis"]), None)
        basari = puan.get(y["youtube_id"])
        if not (kelime and nis and basari is not None and basari >= esik):
            continue
        mevcut = [t.lower() for t in nis["tohum_kelimeler"]]
        if kelime in mevcut or any(opt.benzerlik(kelime, t) >= 0.6 for t in mevcut) or len(mevcut) >= 12:
            continue
        ek.setdefault(nis["kod"], []).append(kelime)
        nis["tohum_kelimeler"].append(kelime)
        notlar.append(f"{nis['kod']}: başarılı konudan yeni arama tohumu '{kelime}'")
    if not ek:
        ogrenilen.pop("nis_tohumlari", None)
    return notlar


# ------------------------------------------------------ 4. kendini onarma

def _son_uyarilar(gun: int = 7) -> list[dict]:
    sinir = (datetime.now() - timedelta(days=gun)).strftime("%Y-%m-%d")
    return [u for u in json_oku(VERI / "uyarilar.json", []) if u.get("zaman", "") >= sinir]


def uyarilardan_onar(ayar: Ayarlar, ogrenilen: dict) -> tuple[list[str], list[str]]:
    """Döner: (uygulanan ayar değişiklikleri, insana/koda bırakılan sorunlar)."""
    uyarilar = _son_uyarilar()
    metin = " ".join(u["metin"] for u in uyarilar)
    notlar, sorunlar = [], []
    if metin.count("tamamlayamadı") + metin.count("yarıda kesildi") >= 2:
        baglam = int(ayar["llm"]["yerel_baglam"])
        hedef = min(SINIRLAR["yerel_baglam"][1], baglam + 2048)
        if hedef > baglam:
            _ayarla(ogrenilen, "llm.yerel_baglam", hedef)
            notlar.append(f"yerel model bağlamı {baglam} → {hedef} (metinler yarım kalıyordu)")
    if metin.count("kotası/yükleme sınırı doldu") >= 2:
        shorts = int(ayar["youtube"]["video_basina_shorts"])
        if shorts > 1:
            _ayarla(ogrenilen, "youtube.video_basina_shorts", shorts - 1)
            notlar.append(f"video başına Shorts {shorts} → {shorts - 1} (YouTube kotası sık doluyordu)")
    if "Openverse" in metin and not (os.environ.get("PEXELS_API_KEY") or os.environ.get("PIXABAY_API_KEY")):
        sorunlar.append("Görsel kaynağı sınırına takılıyor: ücretsiz PEXELS_API_KEY eklenmesi öneriliyor.")
    if "YouTube bağlantısı geçersiz" in metin:
        sorunlar.append("YouTube bağlantısı geçersiz: araclar/youtube_token_al.py ile yeni YT_REFRESH_TOKEN alın.")
    # Tekrarlayan bilinmeyen hatalar -> kod düzeyinde inceleme gerekir
    tekrar: dict[str, int] = {}
    for u in uyarilar:
        if u["kategori"] in ("senaryo", "hata"):
            tekrar[u["metin"][:80]] = tekrar.get(u["metin"][:80], 0) + 1
    hatalar = [i for i in json_oku(VERI / "durum.json", {}).get("kuyruk", []) if i.get("durum") == "hata"]
    if hatalar:
        sorunlar.append(f"{len(hatalar)} üretim işi 3 denemede de başarısız oldu "
                        f"(ör. {hatalar[0]['kod']}); Actions günlüğü incelenmeli.")
    sorunlar += [f"Tekrarlayan sorun ({n} kez): {m}" for m, n in tekrar.items() if n >= 3]
    return notlar, sorunlar


# -------------------------------------------------------- 5. ders çıkarma

DERS_SEMASI = {
    "type": "object",
    "properties": {
        "dersler": {"type": "array", "items": {"type": "string"},
                    "description": "en fazla 5 kısa, uygulanabilir senaryo/başlık kuralı (her biri tek cümle)"},
        "gerekce": {"type": "string", "description": "bu derslerin hangi farklardan çıkarıldığı, 2-3 cümle"},
    },
    "required": ["dersler", "gerekce"],
    "additionalProperties": False,
}


def ders_cikar(ayar: Ayarlar, bugun: date) -> list[str]:
    if not ayar["muhendis"]["ders_cikar"]:
        return []
    metrik: dict[str, dict] = {}
    for s in csv_oku(VERI / "metrikler.csv"):
        metrik[s["youtube_id"]] = s          # en son anlık görüntü kalır
    puan = _puanlar()
    videolar = []
    for y in csv_oku(VERI / "yayinlananlar.csv"):
        b = puan.get(y["youtube_id"])
        icerik = m04_senaryo.yukle(y["kod"]) if y["tur"] == "uzun" else None
        if b is None or not icerik:
            continue
        m = metrik.get(y["youtube_id"], {})
        videolar.append({"baslik": y["baslik"], "puan": round(100 * b), "kanca": icerik["sahneler"][0]["metin"][:300],
                         "deney": icerik["plan"].get("deney", {}), "izlenme_yuzde": m.get("ort_izlenme_yuzde", "-")})
    if len(videolar) < 6:
        return []
    videolar.sort(key=lambda v: -v["puan"])
    def satir(v):
        return f"- [{v['puan']}/100] {v['baslik']} | deney: {v['deney']} | izlenme %: {v['izlenme_yuzde']} | açılış: {v['kanca']}"
    istem = ("Kanalın EN İYİ videoları:\n" + "\n".join(satir(v) for v in videolar[:3])
             + "\n\nEN ZAYIF videoları:\n" + "\n".join(satir(v) for v in videolar[-3:])
             + "\n\nAradaki farklardan, gelecekteki senaryo ve başlıklar için en fazla 5 kısa kural çıkar. "
               "Sadece bu veride görülen farklara dayan; genel YouTube tavsiyesi yazma.")
    sistem = ("Sen bir YouTube içerik analistisin. Veriye dayalı, kısa ve uygulanabilir kurallar yazarsın. "
              "Yanıltıcı başlık, abartı veya platform kurallarına aykırı öneri asla verme.")
    c = llm.json_uret(ayar, f"muhendis-ders-{bugun}", sistem, istem, DERS_SEMASI,
                      lambda: {"dersler": ["Deneme dersi: açılışta soruyu ilk cümlede sor."], "gerekce": "deneme"},
                      max_tokens=3000)
    dersler = [d.strip()[:200] for d in c["dersler"] if d.strip()][:5]
    json_yaz(DERSLER, {"tarih": bugun.isoformat(), "dersler": dersler, "gerekce": c["gerekce"][:600]})
    return [f"senaryo yazarına {len(dersler)} yeni ders eklendi"]


def dersler_metni() -> str:
    """Senaryo sistem talimatına eklenir (m04). Politika kuralları her zaman önce gelir."""
    d = json_oku(DERSLER, {})
    if not d.get("dersler"):
        return ""
    return ("\n\nKANALIN KENDİ VERİSİNDEN ÖĞRENİLENLER (yukarıdaki kurallarla çelişirse yukarıdakiler geçerlidir):\n"
            + "\n".join(f"- {x}" for x in d["dersler"]))


# ----------------------------------------------------------- 6. gözcülük

def _github(yontem: str, yol: str, **kw):
    depo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (depo and token):
        return None
    try:
        return requests.request(yontem, f"https://api.github.com/repos/{depo}{yol}", timeout=20,
                                headers={"Authorization": f"Bearer {token}",
                                         "Accept": "application/vnd.github+json"}, **kw)
    except requests.RequestException:
        return None


def issue_ac(ayar: Ayarlar, baslik: str, govde: str) -> bool:
    """Aynı başlıkta açık issue varsa yenisini açmaz."""
    if ayar.deneme or not ayar["muhendis"]["github_issue"]:
        return False
    acik = _github("GET", "/issues", params={"state": "open", "per_page": 100})
    if acik is None or not acik.ok:
        return False
    if any(i.get("title") == baslik for i in acik.json()):
        return False
    r = _github("POST", "/issues", json={"title": baslik, "body": govde, "labels": ["ogrenme-muhendisi"]})
    return bool(r is not None and r.ok)


def model_gozcusu(ayar: Ayarlar, bugun: date) -> list[str]:
    """Ayda bir: son 90 günde çıkmış, çok indirilen küçük (2-4B) talimat modelleri listeler."""
    if ayar.deneme or bugun.day > 7:
        return []
    try:
        r = requests.get("https://huggingface.co/api/models", timeout=20, params={
            "search": "GGUF", "sort": "downloads", "limit": 100})
        modeller = r.json() if r.ok else []
    except (requests.RequestException, ValueError):
        return []
    sinir = (bugun - timedelta(days=90)).isoformat()
    mevcut = ayar["llm"]["yerel_model"].lower()
    adaylar = []
    for m in modeller:
        ad = m.get("id", "")
        kucuk = any(t in ad.lower() for t in ("2b", "3b", "4b", "e2b", "e4b"))
        talimat = any(t in ad.lower() for t in ("-it", "instruct", "chat"))
        if kucuk and talimat and (m.get("createdAt") or "") >= sinir and ad.lower() != mevcut:
            adaylar.append(f"- [{ad}](https://huggingface.co/{ad}) — {m.get('downloads', 0):,} indirme")
    if adaylar:
        issue_ac(ayar, f"🧪 Yeni yerel model adayları ({bugun:%Y-%m})",
                 "Öğrenme Mühendisi son 90 günde çıkan, çok indirilen küçük talimat modellerini buldu.\n"
                 "Türkçe kalitesi ve hızı mevcut model (`" + ayar["llm"]["yerel_dosya"] + "`) ile karşılaştırılmalı:\n\n"
                 + "\n".join(adaylar[:8]))
        return [f"{len(adaylar)} yeni yerel model adayı bulundu (GitHub issue)"]
    return []


# --------------------------------------------------------------- ana akış

def kalite_dersleri(ayar: Ayarlar, ogrenilen: dict) -> list[str]:
    """Kalite Denetçisi'nin bulgularından öğren: sık tekrarlayan kusuru kök nedeninden çöz (modüller birbirine öğretir)."""
    from . import denetci
    sik = denetci.sik_kusurlar(30)
    degisiklik = []
    if sik.get("zayif_gorsel", 0) + sik.get("gorselsiz_yuva", 0) >= 3:
        aday = int(ayar["hazirlik"]["aday_sayisi"])
        if aday < 6:
            _ayarla(ogrenilen, "hazirlik.aday_sayisi", aday + 1)
            degisiklik.append(f"Görsel uygunluğu sık düşük → yuva başına aday {aday} → {aday + 1}")
    if sik.get("siyah_kare", 0) + sik.get("donuk_goruntu", 0) >= 3 and ayar["video"].get("paralaks", True):
        _ayarla(ogrenilen, "video.paralaks", False)
        degisiklik.append("2.5D harekette sık görüntü kusuru → bu kanalda klasik harekete geçildi")
    if sik.get("shorts_uzun", 0) >= 2:
        _ayarla(ogrenilen, "ses.shorts_ek_hiz", min(25, int(ayar["ses"].get("shorts_ek_hiz", 8)) + 6))
        degisiklik.append("Shorts sık 60 sn'yi aşıyor → Shorts anlatımı hızlandırıldı")
    return degisiklik


def calistir(ayar: Ayarlar) -> list[str]:
    bugun = ayar.simdi.date()
    ogrenilen = _ogrenilen_oku()
    degisiklik: list[str] = []
    degisiklik += deneyleri_evrimlestir(ayar, ogrenilen, bugun)
    degisiklik += uyum_hizini_ayarla(ayar, ogrenilen, bugun)
    degisiklik += tohumlari_evrimlestir(ayar, ogrenilen)
    degisiklik += kalite_dersleri(ayar, ogrenilen)
    onarim, sorunlar = uyarilardan_onar(ayar, ogrenilen)
    degisiklik += onarim
    if ayar["muhendis"]["otomatik_uygula"] and degisiklik:
        _ogrenilen_yaz(ogrenilen)
    elif degisiklik:
        degisiklik = [f"(öneri, uygulanmadı) {d}" for d in degisiklik]
    try:
        degisiklik += ders_cikar(ayar, bugun)
    except llm.LLMHatasi as e:
        log.warning("Ders çıkarılamadı: %s", e)
    degisiklik += model_gozcusu(ayar, bugun)
    if sorunlar:
        issue_ac(ayar, f"🛠️ Öğrenme Mühendisi [{ayar.kanal}]: dikkat gereken sorunlar ({bugun:%Y-%m-%d} haftası)",
                 "Aşağıdaki sorunlar ayarla çözülemedi; insan veya kod müdahalesi gerekiyor:\n\n"
                 + "\n".join(f"- {s}" for s in sorunlar))
    satirlar = [f"## {bugun} — Öğrenme Mühendisi · kanal `{ayar.kanal}`"]
    satirlar += [f"- 🔧 {d}" for d in degisiklik] or ["- Değişiklik gerekmedi (yeterli veri yok veya sistem dengede)."]
    satirlar += [f"- ⚠️ {s}" for s in sorunlar]
    eski = GUNLUK.read_text(encoding="utf-8") if GUNLUK.exists() else "# Öğrenme Mühendisi Günlüğü\n"
    baslik, _, govde = eski.partition("\n")
    GUNLUK.write_text(baslik + "\n\n" + "\n".join(satirlar) + "\n" + govde, encoding="utf-8")  # en yeni üstte
    json_yaz(VERI / "muhendis_son.json", {"tarih": bugun.isoformat(), "degisiklik": degisiklik, "sorunlar": sorunlar})
    ozet_yaz("\n".join(satirlar))
    log.info("Öğrenme Mühendisi: %d değişiklik, %d sorun", len(degisiklik), len(sorunlar))
    return degisiklik
