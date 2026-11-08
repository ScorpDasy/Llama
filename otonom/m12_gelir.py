"""MODÜL 12 — Gelir akışı: teklifler, ortaklık tıklamaları, aylık gelir raporu.

Cloudflare KV'deki teklifleri ve link tıklamalarını ücretsiz REST API ile okur.
"""
from __future__ import annotations

import json
import smtplib
from collections import Counter
from email.message import EmailMessage
from urllib.parse import quote

import requests

from . import llm
from .ayarlar import KANALLAR_VERI, VERI, Ayarlar, csv_ekle, csv_oku, gizli, log, ozet_yaz

TEKLIF_ALANLARI = ["tarih", "alan_adi", "ad", "eposta", "teklif", "tur", "mesaj", "ulke", "anahtar"]


def _kv_url(yol: str = "") -> str | None:
    from .cloudflare_kur import kv_kimligi

    hesap, ns = gizli("CLOUDFLARE_ACCOUNT_ID"), kv_kimligi()
    if not (hesap and ns and gizli("CLOUDFLARE_API_TOKEN")):
        return None
    return f"https://api.cloudflare.com/client/v4/accounts/{hesap}/storage/kv/namespaces/{ns}{yol}"


def _baslik() -> dict:
    return {"Authorization": f"Bearer {gizli('CLOUDFLARE_API_TOKEN')}"}


def kv_anahtarlar(onek: str) -> list[str]:
    url = _kv_url("/keys")
    if not url:
        return []
    anahtarlar, imlec = [], None
    while True:
        p = {"prefix": onek, "limit": 1000, **({"cursor": imlec} if imlec else {})}
        r = requests.get(url, headers=_baslik(), params=p, timeout=20).json()
        anahtarlar += [k["name"] for k in r.get("result", [])]
        imlec = (r.get("result_info") or {}).get("cursor")
        if not imlec:
            return anahtarlar


def kv_oku(anahtar: str) -> str:
    return requests.get(_kv_url(f"/values/{quote(anahtar, safe='')}"), headers=_baslik(), timeout=20).text


def kv_sil(anahtar: str) -> None:
    requests.delete(_kv_url(f"/values/{quote(anahtar, safe='')}"), headers=_baslik(), timeout=20)


def kv_yaz(anahtar: str, deger: str) -> None:
    requests.put(_kv_url(f"/values/{quote(anahtar, safe='')}"), headers=_baslik(), data=deger.encode(), timeout=20)


def herkese_acik_depo() -> bool:
    """Herkese açık depoda kişisel veri (e-posta, isim, mesaj) git'e açık yazılmaz."""
    import os
    return os.environ.get("REPO_OZEL", "").lower() == "false"


def maskele(eposta: str) -> str:
    """ali.veli@gmail.com -> a***@g***.com"""
    if "@" not in eposta:
        return "***"
    kul, _, alan = eposta.partition("@")
    ad, _, uzanti = alan.rpartition(".")
    return f"{kul[:1]}***@{ad[:1]}***.{uzanti}" if ad else f"{kul[:1]}***@***"


def _eposta_gonder(alici: str, konu: str, govde: str) -> bool:
    sunucu, kullanici, sifre = gizli("SMTP_SUNUCU"), gizli("SMTP_KULLANICI"), gizli("SMTP_SIFRE")
    if not (sunucu and kullanici and sifre):
        return False
    mesaj = EmailMessage()
    mesaj["From"], mesaj["To"], mesaj["Subject"] = kullanici, alici, konu
    mesaj.set_content(govde)
    with smtplib.SMTP_SSL(sunucu, int(gizli("SMTP_PORT") or 465), timeout=30) as s:
        s.login(kullanici, sifre)
        s.send_message(mesaj)
    return True


def teklifleri_isle(ayar: Ayarlar) -> list[dict]:
    if ayar.deneme or not _kv_url():
        return []
    yeni = []
    for anahtar in kv_anahtarlar("teklif:"):
        try:
            t = json.loads(kv_oku(anahtar))
        except ValueError:
            kv_sil(anahtar)
            continue
        t["anahtar"] = anahtar
        acik = herkese_acik_depo()
        kayit = dict(t)
        if acik:  # depoya maskeli yaz; tam hali özel Cloudflare KV'de 'islendi:' anahtarıyla kalır
            kayit.update({"eposta": maskele(t["eposta"]), "ad": (t.get("ad") or "")[:1] + "***" if t.get("ad") else "",
                          "mesaj": "(gizli: Cloudflare > KV > TEKLIFLER)" if t.get("mesaj") else ""})
        yeni.append(kayit)
        sablon_yolu = VERI / "alan_adlari" / t["alan_adi"].removeprefix("www.") / "teklif_yanit_sablonu.txt"
        if sablon_yolu.exists():
            yanit = (sablon_yolu.read_text(encoding="utf-8").replace("{ad}", t.get("ad") or "Merhaba")
                     .replace("{teklif}", f"{t['teklif']:,} TL".replace(",", ".")).replace("{alan_adi}", t["alan_adi"]))
            (VERI / "teklif_taslaklari").mkdir(exist_ok=True)
            (VERI / "teklif_taslaklari" / f"{anahtar.replace(':', '_')}.txt").write_text(
                f"Kime: {kayit['eposta']}\nKonu: {t['alan_adi']} teklifiniz hakkında\n\n{yanit}", encoding="utf-8")
            if ayar["teklifler"]["otomatik_yanit"]:
                try:
                    if _eposta_gonder(t["eposta"], f"{t['alan_adi']} teklifiniz hakkında", yanit):
                        log.info("Teklife otomatik yanıt gönderildi: %s", t["alan_adi"])
                except (smtplib.SMTPException, OSError) as e:
                    log.warning("E-posta gönderilemedi: %s", e)
        if acik:
            kv_yaz("islendi:" + anahtar.removeprefix("teklif:"), json.dumps(t, ensure_ascii=False))
        kv_sil(anahtar)  # bir daha işlenmesin
    if yeni:
        csv_ekle(VERI / "teklifler.csv", yeni, TEKLIF_ALANLARI)
        ozet_yaz(f"## 💰 {len(yeni)} yeni alan adı teklifi\n" + "\n".join(
            f"- **{t['alan_adi']}**: {t['teklif']:,} TL ({t['tur']})" for t in yeni))
    return yeni


def tiklamalari_topla(ayar: Ayarlar) -> int:
    """Dünkü ve önceki günlerin tıklama sayaçlarını CSV'ye aktarır (bugünkü sayaç sürüyor)."""
    if ayar.deneme or not _kv_url():
        return 0
    bugun = ayar.simdi.date().isoformat()
    satirlar = []
    for anahtar in kv_anahtarlar("tik:"):
        _, gun, kisa = anahtar.split(":", 2)
        if gun >= bugun:
            continue
        satirlar.append({"tarih": gun, "link": kisa, "tiklama": int(kv_oku(anahtar) or 0)})
        kv_sil(anahtar)
    if satirlar:
        csv_ekle(VERI / "tiklamalar.csv", satirlar, ["tarih", "link", "tiklama"])
    return len(satirlar)


def _gelir_analitik(ay_basi: str, bugun: str) -> str:
    from .m09_youtube_yukleme import kimlik_var, servis
    if not kimlik_var():
        return "-"
    try:
        r = servis("youtubeAnalytics", "v2").reports().query(
            ids="channel==MINE", startDate=ay_basi, endDate=bugun, metrics="estimatedRevenue").execute()
        return f"{r['rows'][0][0]:.2f} $" if r.get("rows") else "0"
    except Exception:
        return "henüz para kazanma yok / izin yok"


def aylik_rapor(ayar: Ayarlar) -> str:
    bugun = ayar.simdi.date()
    ay = bugun.strftime("%Y-%m")
    yayin = [s for d in sorted(KANALLAR_VERI.glob("*/yayinlananlar.csv")) for s in csv_oku(d)
             if s["tarih"].startswith(ay)]
    tik = Counter()
    for s in csv_oku(VERI / "tiklamalar.csv"):
        if s["tarih"].startswith(ay):
            tik[s["link"]] += int(s["tiklama"])
    teklif = [s for s in csv_oku(VERI / "teklifler.csv") if s["tarih"].startswith(ay)]
    maliyet = llm.toplam_maliyet()
    md = [f"# Gelir Raporu — {ay}", "",
          f"- Yayınlanan: {sum(s['tur'] == 'uzun' for s in yayin)} uzun video, {sum(s['tur'] == 'shorts' for s in yayin)} Shorts",
          f"- YouTube tahmini reklam geliri (bu ay): {'-' if ayar.deneme else _gelir_analitik(bugun.replace(day=1).isoformat(), bugun.isoformat())}",
          f"- Ortaklık link tıklamaları: {sum(tik.values())} " + (f"({', '.join(f'{k}: {v}' for k, v in tik.most_common(5))})" if tik else ""),
          f"- Alan adı teklifleri: {len(teklif)}" + (f" (en yüksek {max(int(t['teklif']) for t in teklif):,} TL)".replace(",", ".") if teklif else ""),
          f"- Yapay zekâ maliyeti (toplam, başlangıçtan beri): {maliyet:.3f} $",
          "- Diğer tüm hizmetler: 0 $ (GitHub Actions + Cloudflare ücretsiz katman)", ""]
    rapor = "\n".join(md)
    (VERI / "raporlar").mkdir(exist_ok=True)
    (VERI / "raporlar" / f"gelir-{ay}.md").write_text(rapor, encoding="utf-8")
    return rapor
