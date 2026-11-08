"""MODÜL 7 — Montaj v2: akıcı, hareketli, katmanlı video (yalnızca ffmpeg + Pillow + numpy; ücretsiz).

Uzun video:
* Her sahneye farklı, yumuşak (ease-in-out) kamera hareketi: yaklaş, uzaklaş, sağa/sola/yukarı kaydır,
  üçte bir noktasına odaklan, çapraz süzül. Açılış sahnesi hızlı bir "darbe" yakınlaşmasıyla başlar.
* Sahneler arası geçişler (xfade): yumuşak kayma, çözülme, daire, bulanık, çapraz...; bölüm başlarında
  karartmalı geçiş. Her geçişte stereo "whoosh" sesi.
* Ekranda yazı: söylenen cümle alttan yumuşakça belirir (sesi kapalı izleyenler için).
  Bölüm başlığı soldan kayarak gelir.
* Logo filigranı, ilerleme çubuğu, videonun ~%30'unda kayan "Abone ol" rozeti, logolu kapanış.
* Ses: işlenmiş anlatım + her videoya özel üretken fon müziği (konuşmada kısılır) + geçiş sesleri, -14 LUFS.
Shorts: hareketli arka plan + kelime kelime vurgulanan büyük altyazı + başlık + logo + ilerleme çubuğu.

Uzun video gruplar hâlinde kodlanır (bellek dostu): sahne klipleri → geçişli gruplar → kopyalayarak birleştirme.
"""
from __future__ import annotations

import hashlib
import math
import random
import subprocess
from pathlib import Path

from . import derinlik, gorsel, grafik, ses_tasarimi
from .ayarlar import CIKTI, CONFIG, Ayarlar, log
from .m05_seslendirme import gruplar, sure

NEFES = 0.35          # sahneler arası doğal nefes payı (altyazı zamanlaması da buna göre)
GECIS = 0.5           # geçiş süresi (sn)
GRUP = 10             # tek seferde birleştirilen en fazla sahne (bellek)
HAREKETLER = ["yaklas", "saga", "uzaklas", "kose", "sola", "suzul", "yukari"]
YUMUSAK = ["fade", "smoothleft", "dissolve", "smoothright", "fade", "smoothup"]
CANLI = ["circleopen", "slideleft", "radial", "hblur", "zoomin", "diagtl", "wipeleft"]


def _ffmpeg(*args: str) -> None:
    sonuc = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
                           capture_output=True, text=True)
    if sonuc.returncode != 0:
        raise RuntimeError(f"ffmpeg hatası: {sonuc.stderr[-1500:]}")


def boyut(ayar: Ayarlar, dikey: bool = False) -> tuple[int, int, int]:
    v = ayar["video"]
    g, y, fps = int(v["genislik"]), int(v["yukseklik"]), int(v["fps"])
    if ayar.deneme:  # testte hızlı olsun
        g, y, fps = 640, 360, 12
    return (y, g, fps) if dikey else (g, y, fps)


def _kodlama(ayar: Ayarlar, ara: bool = False) -> list[str]:
    """Video kodlama ayarı. Ara dosyalar yüksek kalitede ve hızlı (sonra yeniden kodlanır)."""
    crf = "18" if ara else str(ayar["video"]["crf"])
    return ["-c:v", "libx264", "-preset", "ultrafast" if ara else "veryfast", "-crf", crf, "-pix_fmt", "yuv420p"]


def _font() -> str:
    return next((f for f in gorsel.FONT_ADAYLARI if Path(f).exists()), "")


def logo_yolu(ayar: Ayarlar) -> Path | None:
    if not ayar["video"].get("logo"):
        return None
    aday = ayar.kanal_bilgi.get("logo") or ayar["video"]["logo"]
    yol = Path(aday) if Path(aday).is_absolute() else CONFIG.parent / aday
    return yol if yol.exists() else None


# ------------------------------------------------------------ kamera hareketi

def hareket_ifadesi(tur: str, kare: int, fps: int, guc: float = 1.0) -> tuple[str, str, str]:
    """zoompan için (zoom, x, y) ifadeleri. E: 0→1 yumuşak (ease-in-out) ilerleme."""
    e = f"(1-cos(PI*on/{kare}))/2"
    a = round(0.16 * guc, 3)
    mx, my = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if tur == "darbe":  # açılış: hızlı yakınlaşmadan yavaş süzülmeye
        return f"1.06+0.22*exp(-on/{max(1, int(fps * 0.35))})+0.05*{e}", mx, my
    if tur == "yaklas":
        return f"1+{a}*{e}", mx, my
    if tur == "uzaklas":
        return f"{1 + a}-{a}*{e}", mx, my
    if tur == "saga":
        return f"{1 + a}", f"(iw-iw/zoom)*{e}", my
    if tur == "sola":
        return f"{1 + a}", f"(iw-iw/zoom)*(1-{e})", my
    if tur == "yukari":
        return f"{1 + a}", mx, f"(ih-ih/zoom)*(1-{e})"
    if tur == "kose":  # üçte bir noktasına doğru yakınlaşma
        return f"1+{round(a * 1.4, 3)}*{e}", "(iw-iw/zoom)*0.3", "(ih-ih/zoom)*0.35"
    return f"1.06+{round(a * 0.6, 3)}*{e}", f"(iw-iw/zoom)*(0.2+0.6*{e})", f"(ih-ih/zoom)*(0.6-0.2*{e})"


def _metin_dosyasi(klasor: Path, ad: str, metin: str) -> Path:
    metin = " ".join(metin.split())
    if len(metin) > 42:  # iki satıra böl
        orta = metin.rfind(" ", 0, len(metin) // 2 + 6)
        if orta > 0:
            metin = metin[:orta] + "\n" + metin[orta + 1:]
    yol = klasor / f"{ad}.txt"
    yol.write_text(metin, encoding="utf-8")
    return yol


def _altyazi_suzgecleri(ayar: Ayarlar, kelimeler: list, gecikme: float, son: float, klasor: Path, ad: str) -> list[str]:
    _, y, _ = boyut(ayar)
    font = _font()
    if not (ayar["video"].get("altyazi_yak") and font and kelimeler):
        return []
    fs, kay = max(14, int(y * 0.048)), max(6, int(y * 0.018))
    satirlar = gruplar(kelimeler, en_fazla=6)
    suz = []
    for k, (b, _s, metin) in enumerate(satirlar):
        b0 = b + gecikme
        b1 = (satirlar[k + 1][0] + gecikme) if k + 1 < len(satirlar) else son
        dosya = _metin_dosyasi(klasor, f"{ad}_{k:02d}", metin)
        suz.append(
            f"drawtext=fontfile='{font}':textfile='{dosya}':expansion=none:fontsize={fs}:fontcolor=white:"
            f"line_spacing={fs // 5}:borderw={max(2, fs // 14)}:bordercolor=black@0.9:box=1:boxcolor=black@0.38:"
            f"boxborderw={fs // 3}:x=(w-text_w)/2:y='h*0.88-text_h+{kay}*max(0,1-(t-{b0:.2f})/0.2)':"
            f"alpha='min(1,max(0,(t-{b0:.2f})/0.15))':enable='between(t,{b0:.2f},{b1:.2f})'")
    return suz


def paralaks_acik(ayar: Ayarlar) -> bool:
    """2.5D derinlikli hareket: ayar açıksa ve yerel model/OpenCV hazırsa (testte kapalı: hız)."""
    return bool(ayar["video"].get("paralaks", True)) and not ayar.deneme and derinlik.kullanilabilir()


def bilgi_grafigi(ayar: Ayarlar, metin: str, kelimeler: list, klasor: Path, ad: str, dikey: bool = False,
                  gecikme: float = 0.0) -> tuple[Path, float, int] | None:
    """Metinde gösterilmeye değer sayı varsa grafik kareleri ve başlama anı: (klasör, an, kenar)."""
    if not ayar["video"].get("bilgi_grafikleri", True):
        return None
    bilgi = grafik.sayi_bul(metin)
    if not bilgi:
        return None
    g, y, fps = boyut(ayar, dikey)
    kenar = int(min(g, y) * (0.56 if dikey else 0.36))
    an = max(0.0, grafik.kelime_ani(kelimeler, bilgi, metin) + gecikme - 0.15)
    return grafik.kareler(bilgi, klasor / f"grafik_{ad}", kenar, fps), an, kenar


def sahne_klibi(ayar: Ayarlar, resim: Path, saniye: float, cikti: Path, hareket: str = "yaklas",
                guc: float = 1.0, kelimeler: list | None = None, bant: Path | None = None,
                gecikme: float = 0.0, karar_gir: float = 0.0, karar_cik: float | None = None,
                metin: str = "") -> Path:
    """Sessiz sahne klibi: kamera hareketi (2.5D derinlikli ya da klasik) + renk + altyazı + bölüm bandı +
    (metinde sayı varsa) canlı bilgi grafiği. karar_gir / karar_cik: siyahtan açılma / siyaha kararma."""
    g, y, fps = boyut(ayar)
    paralaks = paralaks_acik(ayar)
    son_islem = ["eq=contrast=1.05:saturation=1.12", "vignette=PI/5"]
    if karar_gir:
        son_islem.append(f"fade=t=in:st=0:d={karar_gir:.2f}")
    if karar_cik is not None:
        son_islem.append(f"fade=t=out:st={max(0.0, karar_cik - 0.3):.2f}:d=0.3")
    son_islem += _altyazi_suzgecleri(ayar, kelimeler or [], gecikme, saniye, cikti.parent, cikti.stem)
    if paralaks:
        zincir = son_islem
    else:
        kare = max(1, math.ceil(saniye * fps))
        z, x, yy = hareket_ifadesi(hareket, kare, fps, guc)
        zincir = [f"scale={2 * g}:{2 * y}:force_original_aspect_ratio=increase", f"crop={2 * g}:{2 * y}",
                  f"zoompan=z='{z}':x='{x}':y='{yy}':d={kare}:s={g}x{y}:fps={fps}"] + son_islem
    ek, suz, akan, no = [], [f"[0:v]{','.join(zincir)}[v0]"], "v0", 1
    if bant:
        g0 = gecikme + 0.25
        kenar = max(12, g // 40)
        ek += ["-loop", "1", "-framerate", str(fps), "-t", f"{saniye:.3f}", "-i", str(bant)]
        suz += [f"[{no}:v]format=rgba,fade=t=out:st={g0 + 3.4:.2f}:d=0.4:alpha=1[b]",
                f"[{akan}][b]overlay=x='if(lt(t-{g0:.2f},0.45),-w+(w+{kenar})*sin(PI/2*max(0,t-{g0:.2f})/0.45),"
                f"{kenar})':y=H*0.07:enable='between(t,{g0:.2f},{g0 + 3.8:.2f})'[v1]"]
        akan, no = "v1", no + 1
    bg = bilgi_grafigi(ayar, metin, kelimeler or [], cikti.parent, cikti.stem, gecikme=gecikme) if metin else None
    if bg and bg[1] < saniye - 1.0:
        ek += ["-framerate", str(fps), "-i", str(bg[0] / "%04d.png")]
        suz += [f"[{no}:v]format=rgba,setpts=PTS+{bg[1]:.3f}/TB[gf]",
                f"[{akan}][gf]overlay=x=W-w-W*0.05:y=(H-h)*0.38:eof_action=pass[v2]"]
        akan, no = "v2", no + 1
    suz.append(f"[{akan}]format=yuv420p[o]")
    cikis = ["-map", "[o]", "-t", f"{saniye:.3f}", "-r", str(fps), "-an", *_kodlama(ayar, ara=True)]
    if paralaks:
        try:
            return derinlik.klip(resim, cikti, g, y, saniye, fps, hareket, guc, cikis, ek, ";".join(suz))
        except Exception as e:  # sorun olursa bu çalıştırmada klasik yönteme dön
            log.warning("2.5D sahne üretilemedi (%s); klasik hareketle devam.", str(e)[:200])
            derinlik._KAPALI = True
            return sahne_klibi(ayar, resim, saniye, cikti, hareket, guc, kelimeler, bant, gecikme, karar_gir,
                               karar_cik, metin)
    _ffmpeg("-i", str(resim), *ek, "-filter_complex", ";".join(suz), *cikis, str(cikti))
    return cikti


# --------------------------------------------------------------- birleştirme

def _katmanlar(ayar: Ayarlar, girdi_no: int, akan: str, ofset: float, toplam: float, sure_: float,
               klasor: Path, abone_an: float | None, dikey: bool = False) -> tuple[list[str], list[str], str]:
    """Logo filigranı, ilerleme çubuğu, abone rozeti. Döner: (ek girdiler, filtreler, son etiket)."""
    g, y, fps = boyut(ayar, dikey)
    v = ayar["video"]
    girdiler, suz = [], []
    kenar = max(10, min(g, y) // 36)
    logo = logo_yolu(ayar)
    if logo:
        girdiler += ["-loop", "1", "-framerate", str(fps), "-t", f"{sure_:.3f}", "-i", str(logo)]
        suz += [f"[{girdi_no}:v]scale=-1:{max(24, min(g, y) // (14 if dikey else 11))},format=rgba,colorchannelmixer=aa=0.7[lg]",
                f"[{akan}][lg]overlay=W-w-{kenar}:{kenar}[k1]"]
        akan, girdi_no = "k1", girdi_no + 1
    if v.get("ilerleme_cubugu"):
        cubuk = max(3, y // 200)
        girdiler += ["-f", "lavfi", "-t", f"{sure_:.3f}", "-i", f"color=c=0xE50914:s={g}x{cubuk}:r={fps}"]
        suz.append(f"[{akan}][{girdi_no}:v]overlay=x='-w+W*(t+{ofset:.3f})/{toplam:.3f}':y={'0' if dikey else 'H-h'}:eval=frame[k2]")
        akan, girdi_no = "k2", girdi_no + 1
    if abone_an is not None and ofset <= abone_an < ofset + sure_ - 4:
        a = abone_an - ofset
        rozet = gorsel.abone_rozeti(klasor / "abone.png", g, y)
        girdiler += ["-loop", "1", "-framerate", str(fps), "-t", f"{sure_:.3f}", "-i", str(rozet)]
        suz += [f"[{girdi_no}:v]format=rgba,fade=t=out:st={a + 3.6:.2f}:d=0.4:alpha=1[ab]",
                f"[{akan}][ab]overlay=x='if(lt(t-{a:.2f},0.35),-w+(w+{kenar})*max(0,t-{a:.2f})/0.35,{kenar})':"
                f"y=H*0.64:enable='between(t,{a:.2f},{a + 4:.2f})'[k3]"]
        akan = "k3"
    return girdiler, suz, akan


def _grup_birlestir(ayar: Ayarlar, klipler: list[tuple[Path, float]], gecisler: list[str], cikti: Path,
                    ofset: float, toplam: float, abone_an: float | None) -> Path:
    """Gruptaki klipleri geçişlerle birleştirir; ardından logo/ilerleme/abone katmanlarını ekler."""
    _, _, fps = boyut(ayar)
    girdiler, suz = [], []
    for i, (yol, _d) in enumerate(klipler):
        girdiler += ["-i", str(yol)]
        suz.append(f"[{i}:v]settb=AVTB,fps={fps},format=yuv420p[c{i}]")
    akan, s = "c0", klipler[0][1]
    for i in range(1, len(klipler)):
        suz.append(f"[{akan}][c{i}]xfade=transition={gecisler[i - 1]}:duration={GECIS}:"
                   f"offset={max(0.05, s - GECIS / 2):.3f}[x{i}]")
        akan, s = f"x{i}", s + klipler[i][1]
    ek, katman, akan = _katmanlar(ayar, len(klipler), akan, ofset, toplam, s, cikti.parent, abone_an)
    _ffmpeg(*girdiler, *ek, "-filter_complex", ";".join(suz + katman + [f"[{akan}]format=yuv420p[son]"]),
            "-map", "[son]", "-t", f"{s:.3f}", "-r", str(fps), "-an", *_kodlama(ayar), str(cikti))
    return cikti


def _kopyala_birlestir(parcalar: list[Path], cikti: Path) -> None:
    liste = cikti.with_suffix(".txt")
    liste.write_text("".join(f"file '{k.resolve()}'\n" for k in parcalar), encoding="utf-8")
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(liste), "-c", "copy", str(cikti))


def anlatim_izi(parcalar: list[tuple[Path | None, float]], cikti: Path) -> Path:
    """Sahne seslerini, her biri kendi süresine tamamlanmış hâlde tek iz yapar (görüntüyle birebir)."""
    girdiler, suz = [], []
    for i, (ses, d) in enumerate(parcalar):
        girdiler += (["-i", str(ses)] if ses else ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo"])
        suz.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{d:.3f},"
                   f"asetpts=PTS-STARTPTS[a{i}]")
    suz.append("".join(f"[a{i}]" for i in range(len(parcalar))) + f"concat=n={len(parcalar)}:v=0:a=1[o]")
    _ffmpeg(*girdiler, "-filter_complex", ";".join(suz), "-map", "[o]", "-c:a", "pcm_s16le", str(cikti))
    return cikti


def ses_karistir(ayar: Ayarlar, video: Path, anlatim: Path, cikti: Path, anahtar: str, gecis_anlari: list[float],
                 ruh_hali: str | None = None, ritim: bool = False, muzik_ek_db: float = 0.0) -> Path:
    """Anlatım + fon müziği (konuşmada kısılır) + geçiş sesleri → -14 LUFS; görüntü yeniden kodlanmaz."""
    s = ayar["ses"]
    toplam = sure(video)
    tohum = int(hashlib.md5(anahtar.encode()).hexdigest(), 16) % (2 ** 31)
    girdiler = ["-i", str(anlatim)]
    muzikler = sorted((CONFIG / "muzik").glob("*.mp3"))
    muzik = bool(muzikler) or bool(s.get("fon_muzigi"))
    if muzikler:
        girdiler += ["-stream_loop", "-1", "-i", str(muzikler[tohum % len(muzikler)])]
    elif muzik and ritim:  # Shorts: vuruşlu, enerjik
        girdiler += ["-i", str(ses_tasarimi.ritim_muzigi(cikti.parent / "ritim.wav", toplam, tohum)[0])]
    elif muzik:
        fon = ses_tasarimi.fon_muzigi(cikti.parent / "fon.wav", toplam, tohum, ruh_hali or s.get("ruh_hali", "merakli"))
        girdiler += ["-i", str(fon)]
    efekt = bool(s.get("gecis_sesi") and gecis_anlari)
    if efekt:
        girdiler += ["-i", str(ses_tasarimi.efekt_izi(cikti.parent / "efekt.wav", toplam, gecis_anlari, tohum))]
    vno = 1 + muzik + efekt
    grafik = ses_tasarimi.karisim_suzgeci(float(s["muzik_seviyesi_db"]) + 4 + muzik_ek_db,
                                          float(s.get("efekt_seviyesi_db", -16)),
                                          muzik, efekt)
    _ffmpeg(*girdiler, "-i", str(video), "-filter_complex", grafik, "-map", f"{vno}:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{toplam:.3f}",
            "-movflags", "+faststart", str(cikti))
    return cikti


# ---------------------------------------------------------------- uzun video

def _plan(icerik: dict, sesler: list[dict], tohum: int) -> list[dict]:
    """Her sahne için süre, hareket ve (bir öncekinden gelen) geçiş türü."""
    rng = random.Random(tohum)
    plan, onceki = [], ""
    for i, (s, ses) in enumerate(zip(icerik["sahneler"], sesler)):
        hareket = "darbe" if i == 0 else rng.choice([h for h in HAREKETLER if h != onceki])
        bolum = bool(s.get("bolum")) and i > 0
        gecis = "fadeblack" if bolum else (rng.choice(CANLI) if rng.random() < 0.2 else rng.choice(YUMUSAK))
        plan.append({"sure": ses["sure"] + NEFES, "hareket": hareket, "bolum": bolum, "gecis": gecis,
                     "guc": 1.25 if i < 3 else 1.0})  # ilk sahneler daha canlı: izleyiciyi tut
        onceki = hareket
    return plan


def uzun_video(ayar: Ayarlar, kod: str, icerik: dict, sesler: list[dict], gorseller: list[dict]) -> dict:
    klasor = CIKTI / kod / "klipler"
    klasor.mkdir(parents=True, exist_ok=True)
    g, y, _ = boyut(ayar)
    v = ayar["video"]
    tohum = int(hashlib.md5(kod.encode()).hexdigest(), 16) % (2 ** 31)
    renk = gorsel.renk(icerik["plan"]["nis"])
    plan = _plan(icerik, sesler, tohum)
    gecisli = bool(v.get("gecis", True))

    # Zaman çizelgesi: (görsel, ses, süre, ...) — intro ve kapanış dâhil
    sahneler: list[dict] = []
    if float(v["intro_saniye"]) > 0:
        kapak = gorsel.shorts_karesi(Path(gorseller[0]["dosya"]), icerik["baslik"], "", klasor / "intro.png", g, y)
        sahneler.append({"resim": kapak, "ses": None, "sure": float(v["intro_saniye"]), "hareket": "yaklas",
                         "bolum": False, "gecis": "fade", "guc": 0.6, "kelimeler": []})
    for p, s, ses, gor in zip(plan, icerik["sahneler"], sesler, gorseller):
        bant = gorsel.bolum_bandi(s["bolum"], klasor / f"bant_{len(sahneler):03d}.png", g, y, renk) \
            if s.get("bolum") and v.get("altyazi_yak") else None
        sahneler.append({**p, "resim": Path(gor["dosya"]), "ses": ses["ses"], "kelimeler": ses["kelimeler"],
                         "bant": bant, "bolum_adi": s.get("bolum"), "metin": s.get("metin", "")})
    if float(v["outro_saniye"]) > 0:
        site = ayar.nis(icerik["plan"]["nis"]).get("alan_adi") or ""
        kart = gorsel.shorts_karesi(Path(gorseller[-1]["dosya"]), f"Abone ol • {site}".strip(" •"),
                                    "İzlediğin için teşekkürler", klasor / "outro.png", g, y)
        sahneler.append({"resim": kart, "ses": None, "sure": float(v["outro_saniye"]), "hareket": "yaklas",
                         "bolum": True, "gecis": "fadeblack", "guc": 0.5, "kelimeler": [], "kapanis": True})

    # Gruplar: her bölüm başı ve her GRUP sahnede bir yeni grup (gruplar arası kopyalayarak birleşir)
    grup_bas = [i for i, s in enumerate(sahneler) if i == 0 or s["bolum"] or not gecisli]
    sinirlar = []
    for j, b in enumerate(grup_bas):
        bitis = grup_bas[j + 1] if j + 1 < len(grup_bas) else len(sahneler)
        sinirlar += [(k, min(k + GRUP, bitis)) for k in range(b, bitis, GRUP)]

    toplam = sum(s["sure"] for s in sahneler)
    abone_an = toplam * 0.3 if v.get("abone_rozeti") and toplam > 60 else None
    parcalar, bolumler, gecis_anlari, t = [], [], [], 0.0
    for gi, (a, b) in enumerate(sinirlar):
        klipler = []
        for i in range(a, b):
            s = sahneler[i]
            ilk, son = i == a, i == b - 1
            if s.get("bolum_adi"):  # YouTube bölümleri: ilki 0:00'da olmalı
                bolumler.append((0.0 if not bolumler else t, s["bolum_adi"]))
            gecikme = 0.0 if ilk else GECIS / 2         # görüntü sesten yarım geçiş önce başlar
            uzunluk = s["sure"] + (GECIS if not son else gecikme)  # geçiş için kuyruk payı
            sonraki_bolum = son and b < len(sahneler) and sahneler[b]["bolum"]
            klip = sahne_klibi(ayar, s["resim"], uzunluk, klasor / f"{i:03d}.mp4", s["hareket"], s["guc"],
                               s.get("kelimeler"), s.get("bant"), gecikme,
                               karar_gir=0.3 if ilk and s["bolum"] else 0.0,
                               karar_cik=s["sure"] + gecikme if sonraki_bolum else None, metin=s.get("metin", ""))
            if s.get("kapanis") and logo_yolu(ayar):
                klip = _kapanis_logosu(ayar, klip, uzunluk)
            klipler.append((klip, s["sure"]))
            if not ilk or gi > 0:
                gecis_anlari.append(t)
            t += s["sure"]
        gecisler = [sahneler[i]["gecis"] for i in range(a + 1, b)]
        parcalar.append(_grup_birlestir(ayar, klipler, gecisler, klasor / f"grup_{gi:03d}.mp4",
                                        t - sum(d for _, d in klipler), toplam, abone_an))

    ham = CIKTI / kod / "ham.mp4"
    _kopyala_birlestir(parcalar, ham)
    anlatim = anlatim_izi([(s.get("ses"), s["sure"]) for s in sahneler], CIKTI / kod / "anlatim.wav")
    final = CIKTI / kod / "final_video.mp4"
    ses_karistir(ayar, ham, anlatim, final, kod, gecis_anlari,
                 (icerik["plan"].get("deney") or {}).get("muzik") or ayar.nis(icerik["plan"]["nis"]).get("ruh_hali"))
    for gecici in [*klasor.glob("*.mp4"), ham, anlatim]:  # ara dosyalar diski doldurmasın
        gecici.unlink(missing_ok=True)
    log.info("Uzun video hazır: %s (%.0f sn, %d sahne, %d geçiş)", final, t, len(sahneler), len(gecis_anlari))
    return {"video": final, "sure": t, "bolumler": bolumler}


def _kapanis_logosu(ayar: Ayarlar, klip: Path, saniye: float) -> Path:
    """Kapanış kartına yukarıdan süzülen logo."""
    g, y, fps = boyut(ayar)
    cikti = klip.with_name(klip.stem + "_logo.mp4")
    boy = int(y * 0.22)  # başlık (üst %14) ile ana yazı (orta) arasına sığar
    _ffmpeg("-i", str(klip), "-loop", "1", "-framerate", str(fps), "-t", f"{saniye:.3f}", "-i", str(logo_yolu(ayar)),
            "-filter_complex",
            f"[1:v]scale=-1:{boy},format=rgba,fade=t=in:st=0.2:d=0.6:alpha=1[l];"
            f"[0:v][l]overlay=x=(W-w)/2:y='H*0.205+{boy // 4}*exp(-max(0,t-0.2)*4)'[o]",
            "-map", "[o]", "-t", f"{saniye:.3f}", "-an", *_kodlama(ayar, ara=True), str(cikti))
    return cikti


# -------------------------------------------------------------------- Shorts

def shorts_parcala(metin: str, gorsel_arama: str) -> list[dict]:
    """Eski tip Shorts metnini (tek parça) kısa cümlelere böler: her cümleye ayrı görsel/kesme."""
    import re
    parcalar = []
    for cumle in re.split(r"(?<=[.!?…])\s+", metin.strip()):
        kelime = cumle.split()
        while len(kelime) > 14:  # uzun cümle: virgülden ya da ortadan böl
            virgul = next((i + 1 for i in range(5, len(kelime) - 4) if kelime[i].endswith(",")), len(kelime) // 2)
            parcalar.append(" ".join(kelime[:virgul]))
            kelime = kelime[virgul:]
        if kelime:
            parcalar.append(" ".join(kelime))
    return [{"metin": p, "gorsel_arama": gorsel_arama} for p in parcalar if p]


def _kisa_gruplar(kelimeler: list[tuple[float, float, str]], bitisler: set[int] | None = None) -> list[list[int]]:
    """Altyazı için 1-3 kelimelik kısa gruplar: cümle/virgül sonunda, duraklamada ve uzunlukta bölünür.
    bitisler: grubun mutlaka biteceği kelime sıraları (cümle sonu; seslendirme noktalamayı vermez)."""
    bitisler = bitisler or set()
    gruplar_, grup, harf = [], [], 0
    for i, (b, _s, k) in enumerate(kelimeler):
        if grup and (len(grup) >= 3 or harf + len(k) > 16 or b - kelimeler[i - 1][1] > 0.25):
            gruplar_.append(grup)
            grup, harf = [], 0
        grup.append(i)
        harf += len(k) + 1
        if k[-1:] in ".,!?…:;" or i in bitisler:
            gruplar_.append(grup)
            grup, harf = [], 0
    if grup:
        gruplar_.append(grup)
    return gruplar_


def _sira_dosyasi(yol: Path, kareler: list[tuple[Path, float]]) -> Path:
    satir = [f"file '{p.resolve()}'\nduration {d:.3f}\n" for p, d in kareler]
    satir.append(f"file '{kareler[-1][0].resolve()}'\n")
    yol.write_text("".join(satir), encoding="utf-8")
    return yol


def shorts_video(ayar: Ayarlar, kod: str, sira: int, sh: dict, sesler: list[dict], gorseller: list[Path]) -> Path:
    """Dikey Shorts (izleyiciyi tutmak için): her cümlede yeni görsel ve 1,5-3 sn'de bir kesme (vuruş yakınlaşması,
    ara sıra beyaz flaş), iri BÜYÜK HARF altyazı (kelime kelime renk + zıplama), üstte sürekli başlık kutusu,
    sonda TAKİP ET, vuruşlu müzik (konuşmada kısılır), kesmelerde whoosh. sesler/gorseller: her parça için."""
    g, y, fps = boyut(ayar, dikey=True)
    fps = fps if ayar.deneme else 30
    klasor = CIKTI / kod / f"shorts_{sira}"
    klasor.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f"{kod}-{sira}")
    ARA = 0.08  # cümleler arası çok kısa nefes: tempo yüksek kalsın

    # 1) Sıkı anlatım: her parçanın baş/son sessizliği kırpılır; kelimeler küresel zamana taşınır
    metinler = [p["metin"] for p in (sh.get("parcalar") or shorts_parcala(sh.get("metin", ""), ""))]
    kelimeler, kesitler, bitisler, parca_kelimeleri, t = [], [], set(), [], 0.0
    girdiler, suz = [], []
    for k, ses in enumerate(sesler):
        kel = ses["kelimeler"] or [(0.0, ses["sure"], "")]
        a, b = max(0.0, kel[0][0] - 0.04), min(ses["sure"], kel[-1][1] + 0.12)
        uzunluk = (b - a) + ARA
        yeni = [(kb - a + t, ks - a + t, w) for kb, ks, w in kel if w]
        asil = metinler[k].split() if k < len(metinler) else []
        if len(asil) == len(yeni):  # seslendirme noktalamayı atar: virgülleri asıl metinden al
            bitisler |= {len(kelimeler) + i for i, w in enumerate(asil) if w[-1:] in ",;:"}
        kelimeler += yeni
        parca_kelimeleri.append(yeni)
        if kelimeler:
            bitisler.add(len(kelimeler) - 1)  # cümle sonu
        kesitler.append((t, uzunluk))
        girdiler += ["-i", str(ses["ses"])]
        suz.append(f"[{k}:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                   f"aformat=channel_layouts=stereo,apad=pad_dur={ARA}[a{k}]")
        t += uzunluk
    toplam = t + 0.25
    anlatim = klasor / "anlatim.wav"
    suz.append("".join(f"[a{k}]" for k in range(len(sesler))) + f"concat=n={len(sesler)}:v=0:a=1[o]")
    _ffmpeg(*girdiler, "-filter_complex", ";".join(suz), "-map", "[o]", "-c:a", "pcm_s16le", str(anlatim))

    # 2) Çekimler: uzun parça ikiye bölünür (aynı görsel, farklı kadraj) → 1,5-3 sn'de bir kesme
    cekimler = []
    for k, (bas, uzunluk) in enumerate(kesitler):
        if k == len(kesitler) - 1:
            uzunluk = toplam - bas
        parca = [uzunluk] if uzunluk <= 3.2 else [uzunluk / 2, uzunluk / 2]
        for j, d in enumerate(parca):
            cekimler.append({"resim": gorseller[k % len(gorseller)], "sure": d, "yakin": j == 1})
    klipler, kesmeler, an = [], [], 0.0
    for c_no, c in enumerate(cekimler):
        kare = max(1, math.ceil(c["sure"] * fps))
        yon = rng.choice([-1, 1])
        e = f"(1-cos(PI*on/{kare}))/2"
        tepe = 1.18 if c_no else 1.08
        z = f"{1.12 if c['yakin'] else 1.0}+0.10*{e}+{tepe - 1:.2f}*exp(-on/{max(1, int(fps * 0.12))})"
        x = f"(iw-iw/zoom)*(0.5+{0.3 * yon}*{e})"
        flas = c_no > 0 and c_no % 3 == 0
        vf = (f"scale={2 * g}:{2 * y}:force_original_aspect_ratio=increase,crop={2 * g}:{2 * y},"
              f"zoompan=z='{z}':x='{x}':y='ih/2-(ih/zoom/2)':d={kare}:s={g}x{y}:fps={fps},"
              f"eq=contrast=1.08:saturation=1.25:brightness=-0.03,vignette=PI/5"
              + (",fade=t=in:st=0:d=0.12:color=white" if flas else "") + ",format=yuv420p")
        klipler.append(klasor / f"c{c_no:02d}.mp4")
        if Path(c["resim"]).suffix.lower() in (".mp4", ".mov", ".webm"):  # gerçek video: kendi hareketi var
            baslangic = 0.0 if not c["yakin"] else c["sure"] * 0.9  # ikinci çekim videonun devamından
            z_v = f"1.08+0.10*exp(-on/{max(1, int(fps * 0.12))})" + ("+0.06" if c["yakin"] else "")
            vf_v = (f"fps={fps},scale={g}:{y}:force_original_aspect_ratio=increase,crop={g}:{y},"
                    f"zoompan=z='{z_v}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={g}x{y}:fps={fps},"
                    f"eq=contrast=1.06:saturation=1.18,vignette=PI/5"
                    + (",fade=t=in:st=0:d=0.12:color=white" if flas else "") + ",format=yuv420p")
            _ffmpeg("-stream_loop", "-1", "-ss", f"{baslangic:.2f}", "-i", str(c["resim"]), "-vf", vf_v,
                    "-t", f"{c['sure']:.3f}", "-r", str(fps), "-an", *_kodlama(ayar, ara=True), str(klipler[-1]))
        elif paralaks_acik(ayar):  # fotoğraf → 2.5D derinlikli hareket (yerel model)
            try:
                derinlik.klip(Path(c["resim"]), klipler[-1], g, y, c["sure"], fps, "yaklas" if c["yakin"] else "vurus",
                              2.0 if c["yakin"] else 1.0,
                              ["-map", "[o]", "-t", f"{c['sure']:.3f}", "-r", str(fps), "-an", *_kodlama(ayar, ara=True)],
                              [], "[0:v]eq=contrast=1.08:saturation=1.25:brightness=-0.03,vignette=PI/5"
                              + (",fade=t=in:st=0:d=0.12:color=white" if flas else "") + ",format=yuv420p[o]",
                              kesme=None)
            except Exception as e:
                log.warning("2.5D çekim üretilemedi (%s); klasik hareket.", str(e)[:160])
                derinlik._KAPALI = True
                _ffmpeg("-i", str(c["resim"]), "-vf", vf, "-t", f"{c['sure']:.3f}", "-r", str(fps), "-an",
                        *_kodlama(ayar, ara=True), str(klipler[-1]))
        else:
            _ffmpeg("-i", str(c["resim"]), "-vf", vf, "-t", f"{c['sure']:.3f}", "-r", str(fps), "-an",
                    *_kodlama(ayar, ara=True), str(klipler[-1]))
        if c_no:
            kesmeler.append(an)
        an += c["sure"]
    taban = klasor / "taban.mp4"
    _kopyala_birlestir(klipler, taban)

    # 3) Altyazı kareleri: grup başında zıplama (0.82 → 1.08 → 1), o an söylenen kelime renkli
    bos = gorsel.shorts_altyazi([], -1, klasor / "bos.png", g, y)
    kareler: list[tuple[Path, float]] = []
    an, n = 0.0, 0
    for gi, grup in enumerate(_kisa_gruplar(kelimeler, bitisler)):
        sozler = [kelimeler[i][2] for i in grup]
        bas = kelimeler[grup[0]][0]
        if bas > an + 0.02:
            kareler.append((kareler[-1][0] if kareler and bas - an < 0.5 else bos, bas - an))
            an = bas
        for j, i in enumerate(grup):
            bitis = kelimeler[i + 1][0] if i + 1 < len(kelimeler) else toplam
            if j == 0:
                for olcek, d in ((0.82, 0.05), (1.08, 0.05)):
                    kareler.append((gorsel.shorts_altyazi(sozler, j, klasor / f"t{n:04d}.png", g, y, olcek), d))
                    n += 1
                    an += d
            kareler.append((gorsel.shorts_altyazi(sozler, j, klasor / f"t{n:04d}.png", g, y), max(0.03, bitis - an)))
            n += 1
            an = max(an, bitis)
    altyazi = _sira_dosyasi(klasor / "altyazi.txt", kareler or [(bos, toplam)])
    kanca = sh.get("kanca_yazi") or sh.get("baslik", "")
    ust = _sira_dosyasi(klasor / "kanca.txt", [
        (gorsel.kanca_kutusu(kanca, klasor / "k0.png", g, y, 0.85), 0.06),
        (gorsel.kanca_kutusu(kanca, klasor / "k1.png", g, y, 1.06), 0.06),
        (gorsel.kanca_kutusu(kanca, klasor / "k2.png", g, y), toplam)])
    # Son 2,4 sn: izleyiciyi uzun videoya/kanala çağır (YouTube: Shorts → uzun video dönüşümü)
    takip = gorsel.abone_rozeti(klasor / "takip.png", g, y, sh.get("cagri") or "TAMAMI KANALDA ▶", 1.5)
    son = max(0.0, toplam - 2.4)

    girdiler = ["-i", str(taban), "-f", "concat", "-safe", "0", "-i", str(altyazi),
                "-f", "concat", "-safe", "0", "-i", str(ust),
                "-loop", "1", "-framerate", str(fps), "-t", f"{toplam:.3f}", "-i", str(takip)]
    suz = [f"[1:v]fps={fps},format=rgba[alt]", f"[2:v]fps={fps},format=rgba[ust]",
           "[0:v][alt]overlay=0:0:eof_action=pass[v1]", "[v1][ust]overlay=0:0:eof_action=pass[v2]",
           f"[3:v]format=rgba,fade=t=in:st={son:.2f}:d=0.25:alpha=1[tk]",
           f"[v2][tk]overlay=x=(W-w)/2:y='H*0.73+30*max(0,1-(t-{son:.2f})/0.25)':enable='gte(t,{son:.2f})'[v3]"]
    # Bilgi grafikleri: cümlede sayı varsa (en fazla 3), sayı söylenirken ortada canlanır
    grafikler = []
    for k, metin in enumerate(metinler[:len(parca_kelimeleri)]):
        bg = bilgi_grafigi(ayar, metin, parca_kelimeleri[k], klasor, f"p{k}", dikey=True)
        if bg and len(grafikler) < 3 and bg[1] < toplam - 1.5:
            grafikler.append(bg)
    akan = "v3"
    for n_g, (gk, gan, _kenar) in enumerate(grafikler):
        girdiler += ["-framerate", str(fps), "-i", str(gk / "%04d.png")]
        suz += [f"[{4 + n_g}:v]format=rgba,setpts=PTS+{gan:.3f}/TB[g{n_g}]",
                f"[{akan}][g{n_g}]overlay=x=(W-w)/2:y=H*0.2:eof_action=pass[gv{n_g}]"]
        akan = f"gv{n_g}"
    ek, katman, akan = _katmanlar(ayar, 4 + len(grafikler), akan, 0.0, toplam, toplam, klasor, None, dikey=True)
    video = klasor / "goruntu.mp4"
    _ffmpeg(*girdiler, *ek, "-filter_complex", ";".join(suz + katman + [f"[{akan}]format=yuv420p[son]"]),
            "-map", "[son]", "-t", f"{toplam:.3f}", "-r", str(fps), "-an", *_kodlama(ayar), str(video))

    cikti = CIKTI / kod / f"shorts_{sira}.mp4"
    ses_karistir(ayar, video, anlatim, cikti, f"{kod}-s{sira}", sorted([0.02] + kesmeler[1::2] + [g[1] for g in grafikler]),
                 ritim=True, muzik_ek_db=5)
    for gecici in [*klasor.glob("*.png"), *klasor.glob("grafik_*/*.png"), *klasor.glob("c*.mp4"), taban, video]:
        gecici.unlink(missing_ok=True)
    log.info("Shorts hazır: %s (%.1f sn, %d kesme)", cikti, toplam, len(kesmeler))
    return cikti
