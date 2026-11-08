"""Otomatik bilgi grafikleri — anlatılanı ekranda canlandırır, anlaşılırlığı artırır (yerel, Pillow).

Metinde bir sayı geçtiğinde ("yüzde altmış", "%60", "86 milyar nöron", "3 kat", "8 saat", "1928 yılında")
o cümle söylenirken ekranda kısa bir canlı grafik belirir:
- yüzde → dolan halka ve sayaç
- diğer sayılar → sayılan büyük rakam, birim ve altında dolan çizgi
- yıllar → tarih damgası
Grafik zıplayarak gelir ve yumuşakça kaybolur. Seslendirme Türkçe sayı kelimelerini de anlar.
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

from . import gorsel

BIRLER = {"sıfır": 0, "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8,
          "dokuz": 9}
ONLAR = {"on": 10, "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50, "altmış": 60, "yetmiş": 70, "seksen": 80,
         "doksan": 90}
CARPAN = {"yüz": 100, "bin": 1000, "milyon": 10 ** 6, "milyar": 10 ** 9}
BIRIMLER = {"kat": "KAT", "katı": "KAT", "katına": "KAT", "saat": "SAAT", "dakika": "DAKİKA", "saniye": "SANİYE",
            "gün": "GÜN", "hafta": "HAFTA", "ay": "AY", "yıl": "YIL", "kilo": "KİLO", "kg": "KG", "km": "KM",
            "metre": "METRE", "derece": "DERECE", "kalori": "KALORİ", "adım": "ADIM", "litre": "LİTRE",
            "kişi": "KİŞİ", "kez": "KEZ", "tl": "TL", "dolar": "DOLAR", "euro": "EURO"}
_DOLGU = {"ve", "ile", "bir", "bu", "da", "de", "ki", "için", "kadar", "daha", "en", "çok", "az"}


def _kok(k: str) -> str:
    return re.sub(r"[^\wçğıöşü%.,]", "", k.lower())


def _sayi_kelime(kelimeler: list[str], i: int) -> tuple[float | None, int]:
    """i'den başlayan rakam ya da Türkçe sayı kelimelerini okur. Döner: (değer, okunan kelime sayısı)."""
    k = _kok(kelimeler[i]).strip(".,")
    m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?", k)
    if m:
        deger = float(m.group(1).replace(".", "") + ("." + m.group(2) if m.group(2) else ""))
        j = i + 1
        if j < len(kelimeler) and _kok(kelimeler[j]).strip(".,") in CARPAN:
            deger *= CARPAN[_kok(kelimeler[j]).strip(".,")]
            j += 1
        return deger, j - i
    toplam, ara, j = 0, 0, i
    while j < len(kelimeler):
        w = _kok(kelimeler[j]).strip(".,")
        if w in BIRLER:
            ara += BIRLER[w]
        elif w in ONLAR:
            ara += ONLAR[w]
        elif w == "yüz":
            ara = max(1, ara) * 100
        elif w in ("bin", "milyon", "milyar"):
            toplam += max(1, ara) * CARPAN[w]
            ara = 0
        else:
            break
        j += 1
    if j == i:
        return None, 0
    return float(toplam + ara), j - i


def sayi_bul(metin: str) -> dict | None:
    """Cümledeki gösterilmeye değer ilk sayı: {"deger", "tur": yuzde|sayi|yil, "birim", "etiket", "sira"}."""
    kelimeler = metin.split()
    for i, ham in enumerate(kelimeler):
        w = _kok(ham)
        if w.startswith("%") and len(w) > 1:
            deger, n = _sayi_kelime([w[1:]] + kelimeler[i + 1:], 0)
            if deger is not None:
                return {"deger": deger, "tur": "yuzde", "birim": "%", "etiket": _etiket(kelimeler, i + n, i), "sira": i}
        if w == "yüzde" and i + 1 < len(kelimeler):
            deger, n = _sayi_kelime(kelimeler, i + 1)
            if deger is not None and 0 < deger <= 1000:
                return {"deger": deger, "tur": "yuzde", "birim": "%", "etiket": _etiket(kelimeler, i + 1 + n, i),
                        "sira": i}
        deger, n = _sayi_kelime(kelimeler, i)
        if deger is None or n == 0:
            continue
        sonraki = _kok(kelimeler[i + n]).strip(".,") if i + n < len(kelimeler) else ""
        rakam = bool(re.match(r"\d", w))
        if rakam and 1000 <= deger <= 2100 and float(deger).is_integer() and n == 1 and \
                (sonraki.startswith("yıl") or sonraki.startswith("'") or not sonraki or "." in ham[-1:]):
            return {"deger": deger, "tur": "yil", "birim": "", "etiket": "YILI", "sira": i}
        birim = next((v for k, v in BIRIMLER.items() if sonraki == k or sonraki.startswith(k + "'")), "")
        buyuk = deger >= 1000 and n >= 1 and (rakam or deger >= 10 ** 6)
        if birim and (deger >= 2 or rakam):
            return {"deger": deger, "tur": "sayi", "birim": birim, "etiket": _etiket(kelimeler, i + n + 1, i), "sira": i}
        if buyuk:
            return {"deger": deger, "tur": "sayi", "birim": "", "etiket": _etiket(kelimeler, i + n, i), "sira": i}
    return None


_FIIL = re.compile(r"(yor|yordu|dı|di|du|dü|tı|ti|tu|tü|mış|miş|muş|müş|malı|meli|acak|ecek|abilir|ebilir|ır|ir|ur|ür|ar|er)$")


def _ad_mi(k: str) -> bool:
    w = re.sub(r"[^\wçğıöşü]", "", k.lower())
    return bool(w) and w not in _DOLGU and w not in ("var", "yok", "kadar", "yaklaşık", "sadece", "tam") \
        and not (len(w) > 4 and _FIIL.search(w)) and not w.isdigit()


def _etiket(kelimeler: list[str], j: int, i: int | None = None) -> str:
    """Grafiğin altındaki kısa etiket: sayıdan sonraki isim (ör. "86 milyar NÖRON"); yoksa önceki 1-2 isim."""
    sonra = []
    for k in kelimeler[j:j + 2]:
        if not _ad_mi(k):
            break
        sonra.append(k)
        if k[-1:] in ".,!?":
            break
    sozler = sonra
    if not sozler and i is not None:
        once = [k for k in kelimeler[max(0, i - 3):i] if _ad_mi(k)]
        sozler = once[-2:]
    return gorsel.tr_buyuk(" ".join(re.sub(r"[^\wçğıöşüÇĞİÖŞÜ]", "", k) for k in sozler))[:22]


def bicimle(deger: float, tur: str) -> str:
    if tur == "yil":
        return str(int(deger))
    if deger >= 10 ** 9 and deger % 10 ** 9 == 0:
        return f"{deger / 10 ** 9:g} MİLYAR".replace(".", ",")
    if deger >= 10 ** 6 and deger % 10 ** 6 == 0:
        return f"{deger / 10 ** 6:g} MİLYON".replace(".", ",")
    if float(deger).is_integer():
        return f"{int(deger):,}".replace(",", ".")
    return f"{deger:.1f}".replace(".", ",")


def _yumusak_cikis(p: float) -> float:
    return 1 - (1 - min(1.0, max(0.0, p))) ** 3


def _sigdir(ciz: ImageDraw.ImageDraw, metin: str, boyut: int, en_fazla: float):
    while boyut > 12:
        fnt = gorsel.kalin_font(boyut)
        if ciz.textlength(metin, font=fnt) <= en_fazla:
            return fnt
        boyut = int(boyut * 0.92)
    return gorsel.kalin_font(boyut)


def _gosterim(bilgi: dict) -> tuple[float, str]:
    """(sayılacak değer, birim satırı): 86 milyar → (86, "MİLYAR")."""
    d = bilgi["deger"]
    for olcek, ad in ((10 ** 9, "MİLYAR"), (10 ** 6, "MİLYON")):
        if d >= olcek:
            return d / olcek, (ad + " " + bilgi["birim"]).strip()
    return d, bilgi["birim"] if bilgi["tur"] != "yuzde" else ""


def kareler(bilgi: dict, klasor: Path, boy: int, fps: int, sure: float = 2.6,
            renk=(255, 214, 10)) -> Path:
    """Grafiğin RGBA kareleri (klasor/0000.png ...). boy: kare kenarı (piksel)."""
    klasor.mkdir(parents=True, exist_ok=True)
    n = max(2, int(sure * fps))
    hedef, birim = _gosterim(bilgi)
    ondalik = not float(hedef).is_integer()
    olcu = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    ornek = (f"%{bicimle(hedef, 'sayi')}" if bilgi["tur"] == "yuzde" else
             bicimle(hedef, bilgi["tur"]) if bilgi["tur"] == "yil" else
             (f"{hedef:.1f}".replace(".", ",") if ondalik else f"{int(hedef):,}".replace(",", ".")))
    fnt_buyuk = _sigdir(olcu, ornek, int(boy * 0.24), boy * (0.42 if bilgi["tur"] == "yuzde" else 0.74))
    fnt_kucuk = _sigdir(olcu, max(birim, bilgi.get("etiket", ""), key=len) or "X", int(boy * 0.075), boy * 0.74)
    for i in range(n):
        t = i / fps
        sayim = _yumusak_cikis(t / 0.9) if bilgi["tur"] != "yil" else 1.0
        pop = 0.6 + 0.48 * _yumusak_cikis(t / 0.18) - 0.08 * _yumusak_cikis(max(0, t - 0.18) / 0.12)
        saydam = min(1.0, t / 0.12, max(0.0, (sure - t) / 0.3))
        kare = Image.new("RGBA", (boy, boy), (0, 0, 0, 0))
        ciz = ImageDraw.Draw(kare)
        m = boy * 0.08
        ciz.rounded_rectangle((m, m, boy - m, boy - m), radius=int(boy * 0.08), fill=(10, 10, 14, 205))
        deger = hedef * sayim
        sayi = (f"{deger:.1f}".replace(".", ",") if ondalik else f"{int(round(deger)):,}".replace(",", "."))
        if bilgi["tur"] == "yuzde":
            r0 = (boy * 0.2, boy * 0.14, boy * 0.8, boy * 0.74)
            kalin = int(boy * 0.05)
            ciz.arc(r0, 0, 360, fill=(255, 255, 255, 60), width=kalin)
            ciz.arc(r0, -90, -90 + 360 * min(1.0, deger / 100), fill=(*renk, 255), width=kalin)
            ciz.text((boy / 2, boy * 0.44), "%" + sayi, font=fnt_buyuk, fill=(255, 255, 255), anchor="mm")
        else:
            yazi = bicimle(hedef, "yil") if bilgi["tur"] == "yil" else sayi
            ciz.text((boy / 2, boy * 0.38), yazi, font=fnt_buyuk, fill=(255, 255, 255), anchor="mm")
            if birim:
                ciz.text((boy / 2, boy * 0.55), birim, font=fnt_kucuk, fill=(*renk, 255), anchor="mm")
            cizgi = (boy * 0.32) * _yumusak_cikis(t / 0.9)
            ciz.rounded_rectangle((boy / 2 - cizgi, boy * 0.64, boy / 2 + cizgi, boy * 0.665), radius=4,
                                  fill=(*renk, 255))
        if bilgi.get("etiket"):
            ciz.text((boy / 2, boy * 0.8), bilgi["etiket"], font=fnt_kucuk, fill=(235, 235, 235), anchor="mm")
        if pop != 1.0:
            yeni = max(1, int(boy * pop))
            kucuk = kare.resize((yeni, yeni), Image.BICUBIC)
            kare = Image.new("RGBA", (boy, boy), (0, 0, 0, 0))
            if yeni <= boy:
                kare.alpha_composite(kucuk, ((boy - yeni) // 2, (boy - yeni) // 2))
            else:
                ofs = (yeni - boy) // 2
                kare = kucuk.crop((ofs, ofs, ofs + boy, ofs + boy))
        if saydam < 1:
            kare.putalpha(kare.getchannel("A").point(lambda a, s_=saydam: int(a * s_)))
        kare.save(klasor / f"{i:04d}.png", compress_level=1)
    return klasor


def kelime_ani(kelimeler: list[tuple[float, float, str]], bilgi: dict, metin: str) -> float:
    """Sayının söylendiği an (seslendirme kelime zamanlarından; bulunamazsa cümle başı)."""
    hedef = _kok(metin.split()[bilgi["sira"]]).strip(".,%") if bilgi.get("sira") is not None else ""
    for b, _s, k in kelimeler:
        if hedef and _kok(k).strip(".,%") == hedef:
            return b
    return kelimeler[0][0] if kelimeler else 0.0


def tum_sayilar(metin: str) -> set[float]:
    """Metinde geçen bütün sayılar (rakam ya da Türkçe sayı kelimesi)."""
    kelimeler, sonuc, i = metin.split(), set(), 0
    while i < len(kelimeler):
        deger, n = _sayi_kelime(kelimeler, i)
        if deger is not None and n:
            sonuc.add(float(deger))
            i += n
        else:
            k = _kok(kelimeler[i]).lstrip("%")
            if k[:1].isdigit():
                d, n2 = _sayi_kelime([k], 0)
                if d is not None:
                    sonuc.add(float(d))
            i += 1
    return sonuc
