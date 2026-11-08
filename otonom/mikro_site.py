"""Mikro siteler — Cloudflare Pages'te ÜCRETSİZ (sınırsız trafik, ücretsiz SSL).

Her video senaryosundan üretilen makale ilgili alan adının sitesinde yayınlanır:
  YouTube -> site (reklam/ortaklık geliri) -> YouTube (abone) döngüsü.
Satılık/kiralık alan adlarında teklif formu otomatik eklenir.
Çıktı: site/<proje>/public (statik dosyalar) + functions/ (Pages Functions) + wrangler.toml
"""
from __future__ import annotations

import hashlib
import html
import shutil
from datetime import date

import markdown

from . import cloudflare_kur
from .ayarlar import CLOUDFLARE_SABLON, KANALLAR_VERI, SITE, VERI, Ayarlar, csv_oku, json_oku, json_yaz, kisa_ad, log

CSS = """
:root{--bg:#fff;--fg:#1f2937;--muted:#6b7280;--kart:#f3f4f6;--vurgu:#10b981}
@media (prefers-color-scheme:dark){:root{--bg:#0f172a;--fg:#e5e7eb;--muted:#94a3b8;--kart:#1e293b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main,header,footer{max-width:760px;margin:auto;padding:16px}
header a{color:var(--fg);text-decoration:none;font-weight:700;font-size:1.2rem}
a{color:var(--vurgu)}h1{line-height:1.25}.kart{background:var(--kart);border-radius:12px;padding:16px;margin:14px 0}
.kart h2{margin:0 0 4px;font-size:1.15rem}.kart p{margin:0;color:var(--muted)}
.video{position:relative;padding-top:56.25%;margin:16px 0}.video iframe{position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:12px}
form{display:grid;gap:10px}input,select,textarea,button{font:inherit;padding:10px;border-radius:8px;border:1px solid var(--muted);
background:var(--bg);color:var(--fg);width:100%}button{background:var(--vurgu);color:#fff;border:0;cursor:pointer;font-weight:700}
.gizli{position:absolute;left:-9999px}footer{color:var(--muted);font-size:.9rem}
"""


def guvenlik_basliklari(ayar: Ayarlar) -> str:
    """Cloudflare Pages güvenlik başlıkları: XSS, çerçeveleme, MIME, izin ve HTTPS koruması."""
    reklam = bool((ayar.genel.get("cloudflare") or {}).get("adsense_yayinci_id"))
    # AdSense çok sayıda alan adından içerik yükler; açıksa CSP gevşetilir, kapalıysa sıkı tutulur.
    csp = ("default-src 'self'; img-src 'self' data: https:; frame-src https://www.youtube-nocookie.com "
           "https://*.doubleclick.net https://*.google.com; script-src 'self' 'unsafe-inline' https:; "
           "style-src 'self' 'unsafe-inline'; connect-src 'self' https:; frame-ancestors 'none'" if reklam else
           "default-src 'self'; img-src 'self' data: https://i.ytimg.com; frame-src https://www.youtube-nocookie.com; "
           "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com; style-src 'self' 'unsafe-inline'; "
           "connect-src 'self' https://cloudflareinsights.com; form-action 'self'; base-uri 'self'; frame-ancestors 'none'")
    return ("/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
            "  X-Frame-Options: DENY\n  Strict-Transport-Security: max-age=31536000; includeSubDomains\n"
            "  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()\n"
            "  Cross-Origin-Opener-Policy: same-origin\n"
            f"  Content-Security-Policy: {csp}\n"
            "/yazi/*\n  Cache-Control: public, max-age=3600\n")


def proje_adi(alan_adi: str) -> str:
    return kisa_ad(alan_adi, 58)


def _sayfa(ayar: Ayarlar, alan: str, baslik: str, aciklama: str, govde: str, yol: str = "/", ekstra: str = "") -> str:
    cf = ayar.genel.get("cloudflare", {}) or {}
    analitik = (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                f'data-cf-beacon=\'{{"token": "{cf["web_analytics_token"]}"}}\'></script>'
                if cf.get("web_analytics_token") else "")
    reklam = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-{cf["adsense_yayinci_id"]}" '
              'crossorigin="anonymous"></script>' if cf.get("adsense_yayinci_id") else "")
    e = html.escape
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(baslik)}</title><meta name="description" content="{e(aciklama[:160])}">
<link rel="canonical" href="https://{alan}{yol}"><meta property="og:title" content="{e(baslik)}">
<meta property="og:description" content="{e(aciklama[:160])}">{ekstra}{reklam}<style>{CSS}</style></head>
<body><header><a href="/">{e(alan)}</a></header><main>{govde}</main>
<footer><p>© {date.today().year} {e(alan)} · <a href="/gizlilik/">Gizlilik</a></p></footer>{analitik}</body></html>"""


def _satis_kutusu(a: dict, one_cikan: bool) -> str:
    fiyat = a.get("satis_fiyati_try") or 0
    kira = a.get("kiralama_aylik_try") or 0
    bilgi = []
    if fiyat:
        bilgi.append(f"Satış: {fiyat:,} TL".replace(",", "."))
    if kira:
        bilgi.append(f"Kiralama: aylık {kira:,} TL".replace(",", "."))
    alt = " · ".join(bilgi) or "Satış ve aylık kiralama için teklifinizi bekliyoruz."
    baslik = f"<h1>{html.escape(a['ad'])} satılık veya kiralık</h1>" if one_cikan else \
        f"<h2>Bu alan adı ({html.escape(a['ad'])}) satılık veya kiralık</h2>"
    return f"""<section class="kart" id="teklif">{baslik}
<p>{html.escape(a.get('sektor', ''))} alanı için hazır, akılda kalıcı bir marka adı. {alt}</p>
<form method="post" action="/api/teklif">
<input name="ad" placeholder="Adınız / firmanız" maxlength="100">
<input name="eposta" type="email" placeholder="E-posta adresiniz" required>
<input name="teklif" inputmode="numeric" placeholder="Teklifiniz (TL)" required>
<select name="tur"><option value="satis">Satın almak istiyorum</option><option value="kiralama">Kiralamak istiyorum (aylık)</option></select>
<textarea name="mesaj" rows="3" placeholder="Mesajınız (isteğe bağlı)" maxlength="1000"></textarea>
<input class="gizli" name="web_sitesi" tabindex="-1" autocomplete="off" aria-hidden="true">
<input type="hidden" name="t" id="t"><script>document.getElementById("t").value=Date.now()</script>
<button type="submit">Teklif gönder</button>
<small>Bilgileriniz yalnızca teklifinize yanıt vermek için kullanılır.</small></form></section>"""


def _tum_nisler(ayar: Ayarlar) -> list[tuple[str, dict]]:
    """Tüm etkin kanalların nişleri: [(kanal_kodu, niş)]."""
    from .ayarlar import tum_kanallar
    return [(k.kanal, n) for k in tum_kanallar(ayar.deneme) for n in k.nisler]


def _makaleler(eslesen: set[tuple[str, str]]) -> list[dict]:
    """Bu siteye bağlı (kanal, niş) çiftlerinin tüm kanallardaki yazıları, en yeni önce."""
    yt = {s["kod"]: (s["youtube_id"], s.get("yayin_zamani") or s.get("tarih", "")) for d in sorted(KANALLAR_VERI.glob("*/yayinlananlar.csv")) for s in csv_oku(d)
          if s["tur"] == "uzun" and s.get("youtube_id") and not s["youtube_id"].startswith("DENEME")}
    liste = []
    for dosya in KANALLAR_VERI.glob("*/videolar/*/icerik.json"):
        ic = json_oku(dosya)
        kanal = ic.get("plan", {}).get("kanal") or dosya.parent.parent.parent.name if ic else ""
        if ic and (kanal, ic["plan"]["nis"]) in eslesen:
            liste.append({**ic["makale"], "kod": ic["plan"]["kod"], "youtube_id": yt.get(ic["plan"]["kod"], ("", ""))[0],
                          "yayin": yt.get(ic["plan"]["kod"], ("", ""))[1],
                          "_sira": dosya.stat().st_mtime})
    return sorted(liste, key=lambda m: -m["_sira"])


def _kisa_linkler(nisler: list[tuple[str, dict]]) -> dict[str, str]:
    linkler: dict[str, str] = {}
    for _, n in nisler:
        linkler.update({k.lower(): v for k, v in (n.get("ortaklik_linkleri") or {}).items() if v})
    return linkler


def olustur(ayar: Ayarlar) -> list[str]:
    import json

    projeler = []
    tum_nisler = _tum_nisler(ayar)
    kisa_alan = ayar.varliklar.get("iletisim", {}).get("kisa_link_alan_adi", "")
    for a in ayar.alan_adlari:
        alan, mod = a["ad"], a.get("mod", "site_ve_satis")
        proje = proje_adi(alan)
        kok = SITE / proje
        if kok.exists():
            shutil.rmtree(kok)
        pub = kok / "public"
        pub.mkdir(parents=True)
        bagli = [(k, n) for k, n in tum_nisler if n.get("alan_adi") == alan]
        nis = bagli[0][1] if bagli else None
        makaleler = (_makaleler({(k, n["kod"]) for k, n in bagli})
                     if (bagli and mod in ("site_ve_satis", "sadece_site")) else [])
        satis = mod in ("site_ve_satis", "sadece_satis", "park")
        adresler = ["/"]

        for m in makaleler:
            video = (f'<div class="video"><iframe loading="lazy" src="https://www.youtube-nocookie.com/embed/{m["youtube_id"]}" '
                     'title="Video" allowfullscreen></iframe></div>' if m["youtube_id"] else "")
            govde_html = markdown.markdown(html.escape(m["govde_md"], quote=False), extensions=["extra"])
            ld = json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": m["baslik"],
                             "description": m["meta_aciklama"], "inLanguage": "tr"},
                            ensure_ascii=False).replace("</", "<\\/")  # güvenlik: metin script etiketini kapatamasın
            ekstra = f'<script type="application/ld+json">{ld}</script>'
            if m["youtube_id"]:  # Google video sonuçları için VideoObject + paylaşım görseli
                kucuk = f"https://i.ytimg.com/vi/{m['youtube_id']}/hqdefault.jpg"
                vld = json.dumps({"@context": "https://schema.org", "@type": "VideoObject", "name": m["baslik"],
                                  "description": m["meta_aciklama"], "thumbnailUrl": [kucuk],
                                  "uploadDate": m.get("yayin") or "", "inLanguage": "tr",
                                  "embedUrl": f"https://www.youtube.com/embed/{m['youtube_id']}",
                                  "url": f"https://www.youtube.com/watch?v={m['youtube_id']}"},
                                 ensure_ascii=False).replace("</", "<\\/")
                ekstra += (f'<script type="application/ld+json">{vld}</script>'
                           f'<meta property="og:image" content="{html.escape(kucuk)}">'
                           '<meta property="og:type" content="video.other">'
                           '<meta name="twitter:card" content="summary_large_image">')
            sayfa = _sayfa(ayar, alan, m["baslik"], m["meta_aciklama"],
                           f"<article><h1>{html.escape(m['baslik'])}</h1>{video}{govde_html}</article>",
                           f"/yazi/{m['kod']}/", ekstra)
            (pub / "yazi" / m["kod"]).mkdir(parents=True)
            (pub / "yazi" / m["kod"] / "index.html").write_text(sayfa, encoding="utf-8")
            adresler.append(f"/yazi/{m['kod']}/")

        if nis and makaleler:
            liste = "".join(f'<a class="kart" style="display:block;text-decoration:none;color:inherit" href="/yazi/{m["kod"]}/">'
                            f'<h2>{html.escape(m["baslik"])}</h2><p>{html.escape(m["meta_aciklama"])}</p></a>'
                            for m in makaleler)
            govde = f"<h1>{html.escape(nis['ad'])}</h1><p>{html.escape(nis['hedef_kitle'])} için pratik rehberler ve videolar.</p>{liste}"
            if satis:
                govde += _satis_kutusu(a, one_cikan=False)
            baslik, aciklama = f"{nis['ad']} | {alan}", f"{nis['ad']} hakkında anlaşılır rehberler ve videolar."
        elif satis:
            govde, baslik = _satis_kutusu(a, one_cikan=True), f"{alan} satılık / kiralık"
            aciklama = f"{alan} alan adı satış ve kiralama için teklif kabul ediyor."
        else:
            govde, baslik, aciklama = f"<h1>{html.escape(alan)}</h1><p>Yakında.</p>", alan, alan
        (pub / "index.html").write_text(_sayfa(ayar, alan, baslik, aciklama, govde), encoding="utf-8")

        gizlilik = ("<h1>Gizlilik</h1><p>Bu site, ziyaret istatistikleri için çerezsiz Cloudflare Web Analytics "
                    "ve (varsa) Google AdSense reklamları kullanır. Teklif formuna yazdığınız bilgiler yalnızca "
                    "teklifinize yanıt vermek için saklanır ve üçüncü kişilerle paylaşılmaz. Silinmesini istemek için "
                    "teklif formundan bize yazabilirsiniz.</p>")
        (pub / "gizlilik").mkdir()
        (pub / "gizlilik" / "index.html").write_text(_sayfa(ayar, alan, "Gizlilik", "Gizlilik politikası", gizlilik, "/gizlilik/"), encoding="utf-8")
        (pub / "404.html").write_text(_sayfa(ayar, alan, "Sayfa bulunamadı", "404", "<h1>Sayfa bulunamadı</h1><p><a href='/'>Ana sayfa</a></p>"), encoding="utf-8")
        from .arama_motoru import indexnow_anahtari  # Bing/Yandex anında dizinleme doğrulama dosyası
        anahtar = indexnow_anahtari(alan)
        (pub / f"{anahtar}.txt").write_text(anahtar, encoding="utf-8")
        (pub / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: https://{alan}/sitemap.xml\n", encoding="utf-8")
        (pub / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + "".join(f"<url><loc>https://{alan}{u}</loc></url>" for u in adresler)
            + "</urlset>\n", encoding="utf-8")
        pub_id = (ayar.genel.get("cloudflare", {}) or {}).get("adsense_yayinci_id")
        if pub_id:
            (pub / "ads.txt").write_text(f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
        (pub / "_headers").write_text(guvenlik_basliklari(ayar), encoding="utf-8")

        # Pages Functions (yetki.js: tek tıkla Google/YouTube onayının dönüş sayfası)
        (kok / "functions" / "api").mkdir(parents=True)
        shutil.copy(CLOUDFLARE_SABLON / "functions" / "api" / "yetki.js", kok / "functions" / "api" / "yetki.js")
        if satis:
            shutil.copy(CLOUDFLARE_SABLON / "functions" / "api" / "teklif.js", kok / "functions" / "api" / "teklif.js")
        linkler = _kisa_linkler(tum_nisler)
        if alan == kisa_alan and linkler:
            (kok / "functions" / "git").mkdir(parents=True, exist_ok=True)
            sablon = (CLOUDFLARE_SABLON / "functions" / "git" / "[kisa].js").read_text(encoding="utf-8")
            (kok / "functions" / "git" / "[kisa].js").write_text(
                sablon.replace("__LINKLER__", json.dumps(linkler, ensure_ascii=False)).replace("__ALAN_ADI__", alan),
                encoding="utf-8")
        toml = f'name = "{proje}"\npages_build_output_dir = "public"\ncompatibility_date = "2025-01-01"\n'
        kv = "" if ayar.deneme else cloudflare_kur.kv_kimligi()
        if kv:
            toml += f'\n[[kv_namespaces]]\nbinding = "TEKLIFLER"\nid = "{kv}"\n'
        (kok / "wrangler.toml").write_text(toml, encoding="utf-8")
        projeler.append(proje)
        log.info("Site hazır: %s (%d yazı)", proje, len(makaleler))

    # Yalnızca içeriği değişen siteler yüklenir (GitHub Actions dakikası boşa gitmesin).
    # Özetler, yükleme başarılı olunca araclar/siteleri_yukle.sh tarafından veri/'ye kopyalanır.
    eski = json_oku(VERI / "site_ozetleri.json", {})
    yeni = {p: _ozet(SITE / p) for p in projeler}
    degisen = [p for p in projeler if eski.get(p) != yeni[p]]
    (SITE / "projeler.txt").write_text("".join(f"{p}\n" for p in degisen), encoding="utf-8")
    json_yaz(SITE / "ozetler.json", yeni)
    log.info("Yüklenecek (değişen) site: %d / %d", len(degisen), len(projeler))
    return degisen


def _ozet(klasor) -> str:
    h = hashlib.sha256()
    for dosya in sorted(x for x in klasor.rglob("*") if x.is_file()):
        h.update(str(dosya.relative_to(klasor)).encode())
        h.update(dosya.read_bytes())
    return h.hexdigest()
