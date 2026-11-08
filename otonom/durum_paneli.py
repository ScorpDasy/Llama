"""DURUM.md — her çalıştırmada güncellenen, telefondan bile okunabilen Türkçe kontrol paneli.

Ne kurulu, ne eksik (ve nasıl tamamlanır), ücretsiz sınırların ne kadarı kullanıldı,
son üretilen videolar ve son uyarılar tek sayfada. Dış servise istek atmaz (kota harcamaz).
"""
from __future__ import annotations

from collections import Counter

from . import butce, buyume, denetci, llm, yetki
from .ayarlar import CONFIG, KANALLAR_VERI, VERI, Ayarlar, csv_oku, gizli, isletme_dosyalari, json_oku, ozet_yaz
from .m09_youtube_yukleme import GUNLUK_KOTA, _kota_gunu, anahtar_adi, kimlik_var

TAMAM, EKSIK, UYARI = "✅", "❌", "⚠️"


def kurulum_listesi(ayar: Ayarlar) -> list[tuple[str, str, str, str]]:
    """(simge, parça, durum, ne yapmalı) satırları."""
    s = []
    if llm.saglayici(ayar) == "claude":
        s.append((TAMAM, "Yapay zekâ", "Claude Haiku 5.5 (kredi biterse yerel modele otomatik geçer)", "—"))
    else:
        s.append((TAMAM, "Yapay zekâ", f"Ücretsiz yerel model ({ayar['llm']['yerel_dosya'].split('-Q')[0]})",
                  "İsteğe bağlı: daha kaliteli metin için `ANTHROPIC_API_KEY` (README adım 1)"))
    s.append((TAMAM, "Seslendirme", "Edge TTS (yedek: çevrimdışı Piper)", "—"))
    if gizli("PEXELS_API_KEY") or gizli("PIXABAY_API_KEY"):
        s.append((TAMAM, "Görseller", "Pexels/Pixabay (yedek: Openverse, yazı kartı)", "—"))
    else:
        s.append((UYARI, "Görseller", "Yalnızca anahtarsız Openverse + yazı kartı",
                  "Ücretsiz `PEXELS_API_KEY` ekleyin: görsel kalitesi artar (README adım 2)"))
    yt_istemci = gizli("YT_CLIENT_ID") and gizli("YT_CLIENT_SECRET")
    s.append((TAMAM if yt_istemci else EKSIK, "YouTube uygulaması (tüm kanallar için ortak)",
              "Hazır" if yt_istemci else "Yok — videolar Actions > Artifacts'tan indirilebilir",
              "—" if yt_istemci else "`YT_CLIENT_ID`, `YT_CLIENT_SECRET` (README adım C); her kanalın anahtarı aşağıdaki tabloda"))
    s.append((TAMAM if gizli("YOUTUBE_API_KEY") else UYARI, "YouTube istatistik / rekabet",
              "Açık" if gizli("YOUTUBE_API_KEY") else "Kapalı (niş analizi yalnızca arama önerileriyle)",
              "—" if gizli("YOUTUBE_API_KEY") else "`YOUTUBE_API_KEY` (README adım C.2)"))
    cf = gizli("CLOUDFLARE_API_TOKEN") and gizli("CLOUDFLARE_ACCOUNT_ID")
    s.append((TAMAM if cf else EKSIK, "Siteler + teklif formu (Cloudflare)", "Yayında" if cf else "Kurulmadı",
              "—" if cf else "`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` (README adım D)"))
    import os
    gorunurluk = os.environ.get("REPO_OZEL", "").lower()
    if gorunurluk == "false":
        s.append((UYARI, "Depo görünürlüğü", "Herkese açık: GitHub dakikası sınırsız; teklif e-postaları depoya "
                  "maskeli yazılır (tam hali Cloudflare KV'de)",
                  "İstersen Settings > General > Change visibility ile özel yap (dakika sınırı 2.000 olur)"))
    elif gorunurluk == "true":
        s.append((TAMAM, "Depo görünürlüğü", "Özel", "—"))
    muzik = list((CONFIG / "muzik").glob("*.mp3"))
    s.append((TAMAM if muzik else UYARI, "Arka plan müziği", f"{len(muzik)} parça",
              "—" if muzik else "YouTube Ses Kitaplığı'ndan mp3 → `config/muzik/`"))
    return s


def kanal_tablosu(ayar: Ayarlar) -> list[str]:
    """Her kanal için tek satır: biçim, YouTube bağlantısı, üretim durumu, son video."""
    from .ayarlar import tum_kanallar
    md = ["", "## Kanallar",
          "Yeni kanal: Actions > Run workflow > komut `yeni_kanal`, açıklama kutusuna kanalı bir cümleyle anlat.",
          "", "| Kanal | Biçim · dil | YouTube | Bekleyen · yüklendi · elle | Son video |", "|---|---|---|---|---|"]
    elle_tum, son_videolar = [], []
    for k in tum_kanallar(ayar.deneme):
        klasor = KANALLAR_VERI / k.kanal
        d = json_oku(klasor / "durum.json", {"kuyruk": []})
        say = Counter(i["durum"] for i in d.get("kuyruk", []))
        elle_tum += [i for i in d.get("kuyruk", []) if i["durum"] == "elle_yukle"]
        yayin = csv_oku(klasor / "yayinlananlar.csv")
        son_videolar += [{**y, "kanal": k.kanal} for y in yayin[-10:]]
        son = yayin[-1]["baslik"][:45] if yayin else "—"
        yt = TAMAM if kimlik_var(k.kanal) else f"{EKSIK} `{anahtar_adi(k.kanal)}`"
        bilgi = k.kanal_bilgi
        md.append(f"| **{bilgi.get('ad', k.kanal)}** (`{k.kanal}`) | {bilgi.get('bicim', 'uzun_ve_shorts')} · "
                  f"{bilgi.get('dil', 'tr')} | {yt} | {say.get('bekliyor', 0)} · {say.get('yuklendi', 0)} · "
                  f"{say.get('elle_yukle', 0)} | {son} |")
    eksikler = []
    for k in tum_kanallar(ayar.deneme):
        e = []
        if not k.kanal_bilgi.get("kanal_id"):
            e.append("kanal_id boş (abone linki için)")
        e += [f"'{n['ad']}' nişinin alan adı yok" for n in k.nisler if not n.get("alan_adi")]
        if not any(n.get("ortaklik_linkleri") for n in k.nisler):
            e.append("ortaklık linki yok (ek gelir)")
        if e:
            eksikler.append(f"- `{k.kanal}`: " + " · ".join(e) + f" → [config/kanallar/{k.kanal}.yaml](config/kanallar/{k.kanal}.yaml)")
    if eksikler:
        md += ["", "Kanal ayarlarında tamamlanabilecekler:", *eksikler]
    if elle_tum:
        md += ["", "**Elle yüklenecekler** — videoları son çalıştırmanın Artifacts bölümünden indir, YouTube'a yükle,",
               "sonra linkini [config/elle_yuklenenler.yaml](config/elle_yuklenenler.yaml) dosyasına bu kodla ekle "
               "(öğrenme motoru bu videolardan da öğrenir):", "```"]
        md += [f"{i['kod']}{'#shorts' + str(i['sira']) if i['tur'] == 'shorts' else ''}: \"https://youtu.be/...\""
               for i in elle_tum[-12:]]
        md.append("```")
    if son_videolar:
        md += ["", "| Tarih | Kanal | Tür | Başlık |", "|---|---|---|---|"]
        for y in sorted(son_videolar, key=lambda y: y["tarih"], reverse=True)[:10]:
            link = (f"[{y['baslik'][:60]}](https://youtu.be/{y['youtube_id']})"
                    if y["youtube_id"] and not y["youtube_id"].startswith("DENEME") else y["baslik"][:60])
            md.append(f"| {y['tarih'][:10]} | {y['kanal']} | {y['tur']} | {link} |")
    return md


def ogrenme_bolumu(ayar: Ayarlar) -> list[str]:
    """Kanal başına: öğrenilen en iyi seçenekler ve Öğrenme Mühendisi'nin son kararları."""
    from .ayarlar import tum_kanallar
    adlar = {"nis": "niş", "baslik_stili": "başlık", "hedef_kelime": "uzunluk", "yayin_saati": "saat",
             "kaynak": "kaynak"}
    md = ["", "## Laboratuvar ve Öğrenme Mühendisi",
          "Her seçeneğin 'en iyi' olma olasılığı (Thompson örneklemesi); veri arttıkça netleşir. "
          "Kanalın öğrendiklerini sıfırlamak için `veri/kanallar/<kanal>/ogrenilen_ayarlar.yaml` dosyasını sil."]
    for k in tum_kanallar(ayar.deneme):
        klasor = KANALLAR_VERI / k.kanal
        ogren = json_oku(klasor / "optimizasyon.json", {})
        son = json_oku(klasor / "muhendis_son.json", {})
        dersler = json_oku(klasor / "ogrenilen_dersler.json", {}).get("dersler", [])
        md.append(f"- **{k.kanal_bilgi.get('ad', k.kanal)}**")
        if ogren.get("olasiliklar"):
            enler = [f"{adlar.get(ad, ad)}: {max(o, key=o.get)} %{100 * max(o.values()):.0f}"
                     for ad, o in ogren["olasiliklar"].items() if o]
            md.append("  - En iyi: " + " · ".join(enler))
        else:
            md.append("  - Henüz yeterli veri yok (videolar yayınlanıp 7 gün geçince öğrenme başlar).")
        if son:
            md += [f"  - 🔧 {d}" for d in son.get("degisiklik", [])[:3]]
            md += [f"  - ⚠️ {x}" for x in son.get("sorunlar", [])[:2]]
        if dersler:
            md.append("  - Ders: " + " / ".join(dersler[:3]))
    return md


def depo_adresi() -> str:
    """https://github.com/<sahip>/<depo> — Actions'ta ortamdan, yerelde git ayarından."""
    import os
    import re
    import subprocess

    if os.environ.get("GITHUB_REPOSITORY"):
        return f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ['GITHUB_REPOSITORY']}"
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True,
                             timeout=5).stdout.strip()
        m = re.search(r"github\.com[/:]([^/]+/[^/.]+)", url)
        return f"https://github.com/{m.group(1)}" if m else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def hizli_erisim(ayar: Ayarlar) -> list[str]:
    """Tüm sisteme tek yerden ulaşmak için bağlantı listesi."""
    import os

    depo = depo_adresi()
    md = ["## ⚡ Hızlı erişim", ""]
    merkez = (ayar.varliklar.get("iletisim") or {}).get("kontrol_merkezi")
    if merkez:
        md.append(f"- 🧭 **Kontrol Merkezi** (tüm sistem tek sayfada): [aç]({merkez})")
    if depo:
        md.append(f"- ▶️ **Çalıştır** (beta / haftalık / günlük): [Actions > Otonom sistem > Run workflow]"
                  f"({depo}/actions/workflows/otonom.yml)")
        if os.environ.get("GITHUB_RUN_ID"):
            md.append(f"- 📥 **Bu çalıştırmanın videoları ve günlüğü**: [aç]({depo}/actions/runs/{os.environ['GITHUB_RUN_ID']})"
                      " (en altta Artifacts)")
        md.append(f"- 🔑 **Anahtarlar**: [Settings > Secrets]({depo}/settings/secrets/actions)")
        md.append(f"- ➕ **Yeni kanal aç**: [Run workflow]({depo}/actions/workflows/otonom.yml) → komut `yeni_kanal`"
                  " + açıklama · kanal dosyaları: [config/kanallar](config/kanallar)")
        md.append(f"- 🛠️ **Mühendisin açtığı iş kayıtları**: [Issues]({depo}/issues)")
    md += ["- ⚙️ **Ayarlar**: [ayarlar.yaml](config/ayarlar.yaml) · [varliklar.yaml](config/varliklar.yaml)"
           " (dosyayı açıp kalem simgesine dokunun)",
           "- 📈 **Raporlar**: [veri/raporlar](veri/raporlar) · 👷 [Mühendis günlüğü](veri/muhendis_gunlugu.md)"
           " · 🗓️ [İçerik takvimi](veri/icerik_takvimi.md)",
           "- 💰 **Teklifler**: [yanıt taslakları](veri/teklif_taslaklari) · 🏷️ [satış metinleri](veri/alan_adlari)"]
    siteler = " · ".join(f"[{a['ad']}](https://{a['ad']})" for a in ayar.alan_adlari)
    if siteler:
        md.append(f"- 🌐 **Siteler**: {siteler}")
    kanal = next((k.get("kanal_id") for k in ayar.varliklar.get("youtube_kanallari") or [] if k.get("kanal_id")), "")
    md.append("- 🎬 **YouTube Studio**: " + (f"[kanalım](https://studio.youtube.com/channel/{kanal})" if kanal
                                              else "[studio.youtube.com](https://studio.youtube.com)"))
    md.append("- ☁️ **Cloudflare**: [dash.cloudflare.com](https://dash.cloudflare.com) · 📖 [Kurulum rehberi](README.md)")
    return md + [""]


def olustur(ayar: Ayarlar, komut: str, hatalar: list[str]) -> str:
    zaman = ayar.simdi.strftime("%Y-%m-%d %H:%M")
    durum = (f"{UYARI} {len(hatalar)} adım hata verdi (aşağıda)" if hatalar else f"{TAMAM} Sorunsuz")
    md = ["# 📊 Sistem Durumu", "", f"_Son çalıştırma: {zaman} · komut: `{komut}` · {durum}_", ""]
    md += hizli_erisim(ayar)

    liste = kurulum_listesi(ayar)
    eksik = sum(1 for x in liste if x[0] != TAMAM)
    md += ["## Kurulum kontrol listesi",
           f"{'Her şey hazır.' if not eksik else f'{eksik} madde tamamlanabilir — sistem bunlar olmadan da çalışır.'}",
           "", "| | Parça | Durum | Ne yapmalı? |", "|---|---|---|---|"]
    md += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in liste]

    sinir = butce.limit(ayar)
    kota = sum(json_oku(d, {}).get(_kota_gunu(), 0) for d in isletme_dosyalari("kota.json"))
    md += ["", "## Ücretsiz sınırlar",
           f"- GitHub dakikası (bu ay): **{butce.bu_ay(ayar):.0f}** / {sinir or 'sınırsız'}"
           + (f" · ay sonu tahmini {butce.tahmin(ayar):.0f}" if sinir else "") + f" · mod: **{ayar.mod}**",
           f"- YouTube API kotası (bugün, tüm kanallar): **{kota}** / {GUNLUK_KOTA}",
           f"- Yapay zekâ harcaması (toplam): **{llm.toplam_maliyet():.3f} $**",
           "- Sınır dolarsa sistem durmaz: üretimi azaltır, yüklemeyi ertesi güne bırakır veya yedek servise geçer."]

    md += kanal_tablosu(ayar)
    ay = ayar.simdi.strftime("%Y-%m")
    teklif = [t for t in csv_oku(VERI / "teklifler.csv") if t["tarih"].startswith(ay)]
    tik = sum(int(t["tiklama"]) for t in csv_oku(VERI / "tiklamalar.csv") if t["tarih"].startswith(ay))
    md += ["", "## Gelir (bu ay)", f"- Alan adı teklifleri: **{len(teklif)}**"
           + (" → yanıt taslakları `veri/teklif_taslaklari/`" if teklif else ""),
           f"- Ortaklık link tıklamaları: **{tik}**",
           "- Ayrıntılı raporlar: `veri/raporlar/`"]

    md += ogrenme_bolumu(ayar)
    md += buyume.durum_bolumu(ayar)
    md += yetki.durum_bolumu()
    md += denetci.durum_bolumu()

    uyarilar = sorted((u for d in isletme_dosyalari("uyarilar.json") for u in json_oku(d, [])),
                      key=lambda u: u.get("zaman", ""), reverse=True)[:10]
    if hatalar or uyarilar:
        md += ["", "## Son uyarılar"]
        md += [f"- ❗ {h}" for h in hatalar]
        md += [f"- {u['zaman']} · {('**' + u['kanal'] + '** · ') if u.get('kanal') else ''}{u['kategori']}: {u['metin']}"
               for u in uyarilar]

    md += ["", "## Otomatik takvim (Türkiye saati)",
           "- Pazartesi 09:17 — her kanal kendi işinde paralel: öğrenme, plan, senaryo, video ve Shorts",
           "- Her gün 07:07 — kalan yüklemeler, viral kontrol; ardından teklifler ve siteler",
           "- Elle çalıştırmak için: GitHub > Actions > Otonom sistem > Run workflow", ""]
    return "\n".join(md)


def yaz(ayar: Ayarlar, komut: str, hatalar: list[str]) -> str:
    metin = olustur(ayar, komut, hatalar)
    (VERI.parent / "DURUM.md").write_text(metin, encoding="utf-8")
    ozet_yaz(metin)
    return metin
