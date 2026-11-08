"""Pillow ile görsel üretim yardımcıları: yazı kartı, kapak, Shorts karesi, küçük resim."""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FONT_ADAYLARI = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]

NIS_RENKLERI = {"noro": (124, 58, 237), "bilisim": (14, 165, 233), "turizm": (245, 158, 11)}


def font(boyut: int) -> ImageFont.FreeTypeFont:
    for yol in FONT_ADAYLARI:
        if Path(yol).exists():
            return ImageFont.truetype(yol, boyut)
    return ImageFont.load_default(boyut)


def renk(nis_kodu: str) -> tuple[int, int, int]:
    return NIS_RENKLERI.get(nis_kodu, (16, 185, 129))


def kapla(resim: Image.Image, g: int, y: int) -> Image.Image:
    """Görseli bozmadan hedef boyutu tamamen kaplayacak şekilde ölçekler ve kırpar."""
    oran = max(g / resim.width, y / resim.height)
    yeni = resim.convert("RGB").resize((max(g, round(resim.width * oran)), max(y, round(resim.height * oran))),
                                       Image.LANCZOS)
    x0, y0 = (yeni.width - g) // 2, (yeni.height - y) // 2
    return yeni.crop((x0, y0, x0 + g, y0 + y))


def _sar(ciz: ImageDraw.ImageDraw, metin: str, fnt: ImageFont.FreeTypeFont, genislik: int) -> list[str]:
    kelimeler, satirlar, satir = metin.split(), [], ""
    for k in kelimeler:
        dene = f"{satir} {k}".strip()
        if ciz.textlength(dene, font=fnt) <= genislik or not satir:
            satir = dene
        else:
            satirlar.append(satir)
            satir = k
    if satir:
        satirlar.append(satir)
    return satirlar


def ortali_yazi(resim: Image.Image, metin: str, boyut: int, merkez_y: float, genislik_orani: float = 0.86,
                dolgu=(255, 255, 255), kontur: int = 6, en_fazla_yukseklik: float = 0.4) -> None:
    """Yazıyı ortalar; sığmazsa (uzun kelime, çok satır) yazı boyutunu otomatik küçültür."""
    if not metin.strip():
        return
    ciz = ImageDraw.Draw(resim)
    genislik = int(resim.width * genislik_orani)
    while True:
        fnt = font(boyut)
        satirlar = _sar(ciz, metin, fnt, genislik)
        sigiyor = all(ciz.textlength(s, font=fnt) <= genislik for s in satirlar)
        if (sigiyor and len(satirlar) * boyut * 1.18 <= resim.height * en_fazla_yukseklik) or boyut <= 14:
            break
        boyut = int(boyut * 0.9)
    kontur = max(2, min(kontur, boyut // 12))
    yukseklik = boyut * 1.18
    y = resim.height * merkez_y - len(satirlar) * yukseklik / 2
    for s in satirlar:
        ciz.text((resim.width / 2, y), s, font=fnt, fill=dolgu, anchor="ma",
                 stroke_width=kontur, stroke_fill=(0, 0, 0))
        y += yukseklik


def yazi_karti(metin: str, yol: Path, g: int, y: int, ana_renk=(16, 185, 129)) -> Path:
    """Stok görsel bulunamazsa kullanılan degrade arka planlı kart (metin boşsa yazısız)."""
    resim = Image.new("RGB", (g, y))
    ust, alt = ana_renk, tuple(int(c * 0.25) for c in ana_renk)
    ciz = ImageDraw.Draw(resim)
    for i in range(y):
        t = i / y
        ciz.line([(0, i), (g, i)], fill=tuple(int(ust[k] * (1 - t) + alt[k] * t) for k in range(3)))
    ortali_yazi(resim, textwrap.shorten(metin, 60, placeholder="…"), max(24, min(g, y) // 9), 0.5)
    yol.parent.mkdir(parents=True, exist_ok=True)
    resim.save(yol, quality=90)
    return yol


def shorts_karesi(arka: Path, metin: str, ust_baslik: str, yol: Path, g: int, y: int) -> Path:
    """Koyulaştırılmış arka plan + üstte başlık + ortada büyük metin (Shorts, intro, outro)."""
    resim = kapla(Image.open(arka), g, y)
    resim = ImageEnhance.Brightness(resim.filter(ImageFilter.GaussianBlur(2))).enhance(0.55)
    taban = min(g, y)
    if ust_baslik:
        ortali_yazi(resim, ust_baslik, max(18, taban // 14), 0.14, kontur=4, dolgu=(255, 230, 80),
                    en_fazla_yukseklik=0.16)
    ortali_yazi(resim, metin, max(24, taban // 9), 0.55, en_fazla_yukseklik=0.45)
    resim.save(yol)
    return yol


def kucuk_resim(arka: Path, yazi: str, yol: Path, ana_renk=(16, 185, 129)) -> Path:
    """1280x720, büyük okunur yazı, sol tarafta koyu degrade, niş renginde şerit. <2 MB JPEG."""
    g, y = 1280, 720
    resim = ImageEnhance.Contrast(kapla(Image.open(arka), g, y)).enhance(1.15)
    katman = Image.new("L", (g, y))
    ciz_k = ImageDraw.Draw(katman)
    for x in range(g):
        ciz_k.line([(x, 0), (x, y)], fill=int(210 * max(0.0, 1 - x / (g * 0.75))))
    resim = Image.composite(Image.new("RGB", (g, y), (0, 0, 0)), resim, katman)
    ciz = ImageDraw.Draw(resim)
    ciz.rectangle([0, y - 22, g, y], fill=ana_renk)
    boyut = 120
    while boyut > 50:
        fnt = font(boyut)
        satirlar = _sar(ciz, yazi.upper() if len(yazi) < 18 else yazi, fnt, int(g * 0.62))
        if len(satirlar) <= 3:
            break
        boyut -= 8
    toplam = len(satirlar) * boyut * 1.1
    yy = (y - toplam) / 2
    for i, s in enumerate(satirlar):
        ciz.text((60, yy), s, font=fnt, fill=(255, 225, 60) if i == 0 else (255, 255, 255),
                 stroke_width=8, stroke_fill=(0, 0, 0))
        yy += boyut * 1.1
    resim.save(yol, "JPEG", quality=88, optimize=True)
    return yol


# ---------------------------------------------------- hareketli katmanlar (montaj v2)

def _kelime_satirlari(ciz: ImageDraw.ImageDraw, kelimeler: list[str], fnt, genislik: int) -> list[list[int]]:
    satirlar, satir, w = [], [], 0.0
    bosluk = ciz.textlength(" ", font=fnt)
    for i, k in enumerate(kelimeler):
        kw = ciz.textlength(k, font=fnt)
        if satir and w + bosluk + kw > genislik:
            satirlar.append(satir)
            satir, w = [], 0.0
        w += (bosluk if satir else 0) + kw
        satir.append(i)
    if satir:
        satirlar.append(satir)
    return satirlar


def seffaf_altyazi(kelimeler: list[str], etkin: int, yol: Path, g: int, y: int, merkez_y: float = 0.64) -> Path:
    """Shorts altyazısı (şeffaf katman): kelime grubu büyük ve ortada, o an söylenen kelime sarı."""
    resim = Image.new("RGBA", (g, y), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(resim)
    boyut = max(22, min(g, y) // 9)
    while True:
        fnt = font(boyut)
        satirlar = _kelime_satirlari(ciz, kelimeler, fnt, int(g * 0.86))
        if (all(ciz.textlength(k, font=fnt) <= g * 0.9 for k in kelimeler) and len(satirlar) <= 3) or boyut <= 16:
            break
        boyut = int(boyut * 0.9)
    yuk = boyut * 1.2
    ust = y * merkez_y - len(satirlar) * yuk / 2
    bosluk = ciz.textlength(" ", font=fnt)
    kontur = max(3, boyut // 10)
    for s, satir in enumerate(satirlar):
        genis = sum(ciz.textlength(kelimeler[i], font=fnt) for i in satir) + bosluk * (len(satir) - 1)
        x = (g - genis) / 2
        for i in satir:
            renk = (255, 221, 0) if i == etkin else (255, 255, 255)
            ciz.text((x, ust + s * yuk), kelimeler[i], font=fnt, fill=renk, stroke_width=kontur, stroke_fill=(0, 0, 0))
            x += ciz.textlength(kelimeler[i], font=fnt) + bosluk
    yol.parent.mkdir(parents=True, exist_ok=True)
    resim.save(yol)
    return yol


def seffaf_baslik(metin: str, yol: Path, g: int, y: int, merkez_y: float = 0.12) -> Path:
    resim = Image.new("RGBA", (g, y), (0, 0, 0, 0))
    ortali_yazi(resim, metin, max(18, min(g, y) // 14), merkez_y, kontur=5, dolgu=(255, 230, 80),
                en_fazla_yukseklik=0.18)
    resim.save(yol)
    return yol


def bolum_bandi(metin: str, yol: Path, g: int, y: int, ana_renk=(16, 185, 129)) -> Path:
    """Bölüm başında kayarak gelen alt bant: renkli şerit + yarı saydam koyu zemin + başlık."""
    yuk = max(36, y // 9)
    fnt = font(max(14, int(yuk * 0.42)))
    olcu = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    metin = textwrap.shorten(metin, 60, placeholder="…")
    gen = int(min(g * 0.8, olcu.textlength(metin, font=fnt) + yuk * 1.2))
    resim = Image.new("RGBA", (gen, yuk), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(resim)
    ciz.rounded_rectangle((0, 0, gen - 1, yuk - 1), radius=yuk // 5, fill=(10, 10, 14, 200))
    ciz.rounded_rectangle((0, 0, max(6, yuk // 7), yuk - 1), radius=yuk // 10, fill=(*ana_renk, 255))
    ciz.text((yuk * 0.45, yuk / 2), metin, font=fnt, fill=(255, 255, 255), anchor="lm")
    resim.save(yol)
    return yol


def abone_rozeti(yol: Path, g: int, y: int, metin: str = "▶ ABONE OL", olcek: float = 1.0) -> Path:
    yuk = max(28, int(min(g, y) // 13 * olcek))
    fnt = font(max(12, int(yuk * 0.45)))
    gen = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(metin, font=fnt) + yuk)
    resim = Image.new("RGBA", (gen, yuk), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(resim)
    ciz.rounded_rectangle((0, 0, gen - 1, yuk - 1), radius=yuk // 2, fill=(229, 9, 20, 235))
    ciz.text((gen / 2, yuk / 2), metin, font=fnt, fill=(255, 255, 255), anchor="mm")
    resim.save(yol)
    return yol


def logo_hazirla(kaynak: Path, yol: Path, kenar: int = 512) -> Path:
    """Koyu zeminli logoyu saydam zeminli küçük PNG'ye çevirir (filigran ve kapanış için)."""
    resim = Image.open(kaynak).convert("RGBA")
    r, g_, b, _ = resim.split()
    tepe = ImageChops.lighter(ImageChops.lighter(r, g_), b)  # en parlak kanal: siyah zemin -> saydam
    resim.putalpha(Image.eval(tepe, lambda v: max(0, min(255, (v - 24) * 4))))
    kutu = resim.getbbox()
    if kutu:
        resim = resim.crop(kutu)
    resim.thumbnail((kenar, kenar))
    yol.parent.mkdir(parents=True, exist_ok=True)
    resim.save(yol, optimize=True)
    return yol


# ------------------------------------------------------------ Shorts v3 (izleyiciyi tutan stil)

KALIN_FONT_ADRESI = "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf"
_KALIN: dict[int, ImageFont.FreeTypeFont] = {}


def _kalin_dosya() -> Path | None:
    """Montserrat Black (açık lisanslı, Türkçe harfli) — bir kez indirilir; olmazsa DejaVu Bold."""
    import os
    yol = Path(os.environ.get("OTONOM_FONT_DIZINI", Path.home() / ".cache" / "otonom-fontlar")) / "Montserrat.ttf"
    if not yol.exists():
        try:
            import requests
            r = requests.get(KALIN_FONT_ADRESI, timeout=30)
            if r.ok and len(r.content) > 100_000:
                yol.parent.mkdir(parents=True, exist_ok=True)
                yol.write_bytes(r.content)
        except Exception:
            return None
    return yol if yol.exists() else None


def kalin_font(boyut: int) -> ImageFont.FreeTypeFont:
    if boyut not in _KALIN:
        yol = _kalin_dosya()
        if yol:
            f = ImageFont.truetype(str(yol), boyut)
            try:
                f.set_variation_by_axes([900])  # Black
            except Exception:
                pass
            _KALIN[boyut] = f
        else:
            _KALIN[boyut] = font(boyut)
    return _KALIN[boyut]


def tr_buyuk(metin: str) -> str:
    return metin.replace("i", "İ").replace("ı", "I").upper()


def _golgeli_yazi(katman: Image.Image, xy, metin: str, fnt, dolgu, kontur: int) -> None:
    golge = Image.new("RGBA", katman.size, (0, 0, 0, 0))
    ImageDraw.Draw(golge).text((xy[0] + kontur * 0.6, xy[1] + kontur * 0.9), metin, font=fnt, fill=(0, 0, 0, 170),
                               stroke_width=kontur, stroke_fill=(0, 0, 0, 170))
    katman.alpha_composite(golge.filter(ImageFilter.GaussianBlur(kontur * 0.8)))
    ImageDraw.Draw(katman).text(xy, metin, font=fnt, fill=dolgu, stroke_width=kontur, stroke_fill=(0, 0, 0))


def shorts_altyazi(kelimeler: list[str], etkin: int, yol: Path, g: int, y: int, olcek: float = 1.0,
                   merkez_y: float = 0.58, vurgu=(255, 225, 40)) -> Path:
    """İri, kalın, BÜYÜK HARF altyazı; o an söylenen kelime renkli ve biraz büyük. olcek: zıplama animasyonu."""
    katman = Image.new("RGBA", (g, y), (0, 0, 0, 0))
    if kelimeler:
        sozler = [tr_buyuk(k) for k in kelimeler]
        boyut = int(g * 0.115 * olcek)
        olcu = ImageDraw.Draw(katman)
        while True:
            fnt = kalin_font(boyut)
            satirlar = _kelime_satirlari(olcu, sozler, fnt, int(g * 0.88))
            if len(satirlar) <= 2 and all(olcu.textlength(k, font=fnt) <= g * 0.9 for k in sozler) or boyut < 20:
                break
            boyut = int(boyut * 0.9)
        buyuk = kalin_font(int(boyut * 1.1))
        kontur = max(3, boyut // 9)
        yuk = boyut * 1.15
        ust = y * merkez_y - len(satirlar) * yuk / 2
        bosluk = olcu.textlength(" ", font=fnt)
        for s, satir in enumerate(satirlar):
            fontlar = [buyuk if i == etkin else fnt for i in satir]
            genis = sum(olcu.textlength(sozler[i], font=f) for i, f in zip(satir, fontlar)) + bosluk * (len(satir) - 1)
            x = (g - genis) / 2
            for i, f in zip(satir, fontlar):
                kay = (boyut * 1.1 - boyut) * 0.6 if i == etkin else 0
                _golgeli_yazi(katman, (x, ust + s * yuk - kay), sozler[i], f, vurgu if i == etkin else (255, 255, 255),
                              kontur)
                x += olcu.textlength(sozler[i], font=f) + bosluk
    yol.parent.mkdir(parents=True, exist_ok=True)
    katman.save(yol, compress_level=1)
    return yol


def kanca_kutusu(metin: str, yol: Path, g: int, y: int, olcek: float = 1.0, renk=(255, 214, 10)) -> Path:
    """Üstte sürekli duran başlık kutusu (izleyici konuyu hep görür): renkli zemin, siyah kalın yazı."""
    katman = Image.new("RGBA", (g, y), (0, 0, 0, 0))
    metin = tr_buyuk(textwrap.shorten(metin, 48, placeholder="…"))
    olcu = ImageDraw.Draw(katman)
    boyut = int(g * 0.072)
    while True:
        fnt = kalin_font(boyut)
        satirlar = _sar(olcu, metin, fnt, int(g * 0.8))
        if len(satirlar) <= 2 or boyut < 18:
            break
        boyut = int(boyut * 0.9)
    yuk = boyut * 1.18
    gen = max(olcu.textlength(s, font=fnt) for s in satirlar) + boyut * 1.2
    kutu_y = len(satirlar) * yuk + boyut * 0.7
    kutu = Image.new("RGBA", (int(gen), int(kutu_y)), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(kutu)
    ciz.rounded_rectangle((0, 0, kutu.width - 1, kutu.height - 1), radius=int(boyut * 0.35), fill=(*renk, 245))
    for i, s in enumerate(satirlar):
        ciz.text((kutu.width / 2, boyut * 0.35 + i * yuk), s, font=fnt, fill=(12, 12, 12), anchor="ma")
    if olcek != 1.0:
        kutu = kutu.resize((max(1, int(kutu.width * olcek)), max(1, int(kutu.height * olcek))))
    kutu = kutu.rotate(1.5, expand=True, resample=Image.BICUBIC)  # hafif eğik: el yapımı, dikkat çekici
    katman.alpha_composite(kutu, (int((g - kutu.width) / 2), int(y * 0.135 - kutu.height / 2)))
    yol.parent.mkdir(parents=True, exist_ok=True)
    katman.save(yol, compress_level=1)
    return yol
