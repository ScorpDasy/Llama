"""Ses tasarımı — ücretsiz, telifsiz, tamamen yerel (numpy + ffmpeg).

* Üretken fon müziği: her video kendi tonunda ve kendi akor dizisiyle yumuşak bir fon alır (telif sorunu yok).
  config/muzik/ klasörüne mp3 koyarsan önce onlar kullanılır.
* Geçiş sesi (whoosh): sahne geçişlerine eşlenir, soldan sağa süzülür.
* Anlatım işleme: uğultu süzgeci, sıkıştırma, netlik ve YouTube'un önerdiği -14 LUFS ses düzeyi.
* Müzik kısma (ducking): konuşma başlayınca müzik kısılır, duraklamalarda yükselir.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000

# Akorlar: kök sese göre yarım ses aralıkları. Ruh hali kanal/niş ayarından seçilir.
RUH_HALLERI = {
    "sakin": {"bpm": 68, "akorlar": [[0, 4, 7, 11], [9, 12, 16, 19], [5, 9, 12, 16], [7, 11, 14, 17]], "nota": 0.0},
    "merakli": {"bpm": 82, "akorlar": [[0, 3, 7, 10], [8, 12, 15, 19], [3, 7, 10, 14], [10, 14, 17, 21]], "nota": 0.6},
    "enerjik": {"bpm": 100, "akorlar": [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]], "nota": 1.0},
    "gizemli": {"bpm": 72, "akorlar": [[0, 3, 7], [1, 5, 8], [0, 3, 7], [-2, 2, 5]], "nota": 0.4},
}


def _frekans(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _wav_yaz(yol: Path, sol: np.ndarray, sag: np.ndarray) -> Path:
    tepe = max(1e-6, float(np.max(np.abs(sol))), float(np.max(np.abs(sag))))
    veri = (np.stack([sol, sag], axis=1) / tepe * 0.8 * 32767).astype(np.int16)
    yol.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(yol), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(veri.tobytes())
    return yol


def fon_muzigi(yol: Path, saniye: float, tohum: int, ruh_hali: str = "merakli") -> Path:
    """Yumuşak pad akorları + bas + (ruh haline göre) hafif arpej. Her tohum farklı ton ve dizi verir."""
    rng = np.random.default_rng(tohum)
    rh = RUH_HALLERI.get(ruh_hali, RUH_HALLERI["merakli"])
    kok = 50 + int(rng.integers(0, 10))
    dizi = list(rh["akorlar"])
    if rng.random() < 0.5:  # aynı ruh halinde bile videodan videoya farklı akış
        dizi = dizi[2:] + dizi[:2]
    vurus = 60.0 / rh["bpm"]
    akor_sn = vurus * 8
    n = int(saniye * SR) + 1
    sol, sag = np.zeros(n, np.float32), np.zeros(n, np.float32)
    seg, kuyruk = int(akor_sn * SR), int(1.5 * SR)
    for i, bas in enumerate(range(0, n, seg)):
        akor = dizi[i % len(dizi)]
        L = min(seg + kuyruk, n - bas)
        t = np.arange(L, dtype=np.float32) / SR
        zarf = np.clip(np.minimum(t / 1.2, (L / SR - t) / 1.5), 0, 1) ** 1.5
        pad_l, pad_r = np.zeros(L, np.float32), np.zeros(L, np.float32)
        for j, aralik in enumerate(akor):
            f = _frekans(kok + aralik)
            faz = rng.random() * 6.28
            ton = np.sin(2 * np.pi * f * t + faz) + 0.3 * np.sin(2 * np.pi * 2 * f * t + faz)
            hafif = np.sin(2 * np.pi * f * 1.004 * t)  # hafif kayık ikinci ses: genişlik
            pan = 0.5 + 0.35 * np.sin(j * 1.7)
            pad_l += (ton * (1 - pan) + hafif * 0.4) * 0.25
            pad_r += (ton * pan + hafif * 0.4) * 0.25
        bas_ses = 0.5 * np.sin(2 * np.pi * _frekans(kok - 12 + akor[0]) * t) * zarf
        sol[bas:bas + L] += pad_l * zarf * 0.55 + bas_ses
        sag[bas:bas + L] += pad_r * zarf * 0.55 + bas_ses
        if rh["nota"]:  # arpej: akor seslerinden yumuşak, sönümlü notalar
            adim = vurus / 2
            for k in range(int(akor_sn / adim)):
                if rng.random() > rh["nota"]:
                    continue
                p0 = bas + int(k * adim * SR)
                ln = min(int(0.9 * SR), n - p0)
                if ln <= 0:
                    break
                tt = np.arange(ln, dtype=np.float32) / SR
                f = _frekans(kok + 12 + akor[int(rng.integers(0, len(akor)))])
                nota = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 5) * np.minimum(1, tt / 0.01) * 0.22
                p = rng.random()
                sol[p0:p0 + ln] += nota * (1 - p)
                sag[p0:p0 + ln] += nota * p
    son = min(n, int(3 * SR))  # sonda 3 sn yumuşak bitiş
    sol[-son:] *= np.linspace(1, 0, son)
    sag[-son:] *= np.linspace(1, 0, son)
    return _wav_yaz(yol, sol, sag)


def whoosh(sure: float = 0.7, tohum: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Gürültüden süpürülen bant: yükselen frekans + soldan sağa geçiş (geçiş efekti sesi)."""
    rng = np.random.default_rng(tohum)
    L = int(sure * SR)
    gurultu = rng.standard_normal(L).astype(np.float32)
    pencere, adim = 2048, 512
    cikti = np.zeros(L + pencere, np.float32)
    hann = np.hanning(pencere).astype(np.float32)
    frek = np.fft.rfftfreq(pencere, 1 / SR)
    for bas in range(0, L - pencere, adim):
        p = bas / max(1, L - pencere)
        merkez = 300 * (12 ** p)  # 300 Hz -> ~3,6 kHz
        maske = np.exp(-((np.log(frek + 1) - np.log(merkez)) ** 2) / 0.5)
        parca = np.fft.irfft(np.fft.rfft(gurultu[bas:bas + pencere] * hann) * maske, pencere)
        cikti[bas:bas + pencere] += parca.astype(np.float32) * hann
    cikti = cikti[:L]
    t = np.linspace(0, 1, L, dtype=np.float32)
    zarf = np.where(t < 0.6, (t / 0.6) ** 2, ((1 - t) / 0.4) ** 1.5)
    cikti = cikti * zarf / (np.max(np.abs(cikti)) + 1e-6)
    return cikti * np.cos(t * np.pi / 2), cikti * np.sin(t * np.pi / 2)


def efekt_izi(yol: Path, saniye: float, anlar: list[float], tohum: int = 0) -> Path:
    """Verilen anlarda (geçiş noktaları) whoosh çalan tek bir ses izi."""
    n = int(saniye * SR) + 1
    sol, sag = np.zeros(n, np.float32), np.zeros(n, np.float32)
    for i, an in enumerate(anlar):
        wl, wr = whoosh(0.6 + 0.2 * ((tohum + i) % 3) / 2, tohum + i)
        p0 = max(0, int((an - len(wl) / SR * 0.6) * SR))  # tepe noktası geçiş anına denk gelsin
        ln = min(len(wl), n - p0)
        if ln > 0:
            sol[p0:p0 + ln] += wl[:ln]
            sag[p0:p0 + ln] += wr[:ln]
    if not anlar:
        sol[0] = sag[0] = 1e-4
    return _wav_yaz(yol, sol, sag)


def karisim_suzgeci(muzik_db: float, efekt_db: float, muzik: bool, efekt: bool) -> str:
    """[0:a] anlatım, [1:a] müzik, [2:a] efekt → [a]. Anlatım işlenir, müzik konuşmada kısılır."""
    parcalar = ["[0:a]highpass=f=70,acompressor=threshold=-20dB:ratio=3:attack=5:release=80:makeup=2,"
                "equalizer=f=3200:t=q:w=1.2:g=2.5,aresample=48000,aformat=channel_layouts=stereo[ses]"]
    karisim, sayi = "[sesa]", 1
    if muzik:
        parcalar += ["[ses]asplit=2[sesa][sesb]",
                     f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={muzik_db}dB[m]",
                     "[m][sesb]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[md]"]
        karisim += "[md]"
        sayi += 1
    else:
        parcalar[0] = parcalar[0].replace("[ses]", "[sesa]")
    if efekt:
        parcalar.append(f"[{2 if muzik else 1}:a]aresample=48000,volume={efekt_db}dB[ef]")
        karisim += "[ef]"
        sayi += 1
    parcalar.append(f"{karisim}amix=inputs={sayi}:duration=first:normalize=0,"
                    "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")
    return ";".join(parcalar)


def ritim_muzigi(yol: Path, saniye: float, tohum: int, bpm: int | None = None) -> tuple[Path, float]:
    """Shorts için vuruşlu, enerjik fon (davul + bas + akor), telifsiz. Bas ve akor her vuruşta "nefes alır"
    (pompalama). Döner: (dosya, vuruş süresi) — kesmeler vuruşa denk getirilebilir."""
    rng = np.random.default_rng(tohum)
    bpm = bpm or int(rng.choice([94, 98, 102, 106]))
    vurus = 60.0 / bpm
    kok = 45 + int(rng.integers(0, 7))
    dizi = [[[0, 3, 7], [8, 12, 15], [3, 7, 10], [10, 14, 17]],
            [[0, 3, 7], [5, 8, 12], [8, 12, 15], [7, 11, 14]],
            [[0, 4, 7], [9, 12, 16], [5, 9, 12], [7, 11, 14]]][int(rng.integers(0, 3))]
    n = int(saniye * SR) + SR
    sol, sag = np.zeros(n, np.float32), np.zeros(n, np.float32)

    def ekle(sinyal, an, pan=0.5, kazanc=1.0):
        p0 = int(an * SR)
        ln = min(len(sinyal), n - p0)
        if ln > 0:
            sol[p0:p0 + ln] += sinyal[:ln] * kazanc * (1 - pan) * 2
            sag[p0:p0 + ln] += sinyal[:ln] * kazanc * pan * 2

    t3 = np.arange(int(0.3 * SR), dtype=np.float32) / SR
    davul = np.sin(2 * np.pi * np.cumsum(45 + 90 * np.exp(-t3 * 30)) / SR) * np.exp(-t3 * 14)
    t2 = np.arange(int(0.2 * SR), dtype=np.float32) / SR
    el = np.diff(rng.standard_normal(len(t2) + 1)).astype(np.float32) * np.exp(-t2 * 28) * 0.35
    t1 = np.arange(int(0.05 * SR), dtype=np.float32) / SR
    zil = np.diff(np.diff(rng.standard_normal(len(t1) + 2))).astype(np.float32) * np.exp(-t1 * 90) * 0.12

    pompa = np.ones(n, np.float32)
    for b in range(int(saniye / vurus) + 1):
        an, konum = b * vurus, b % 4
        if konum in (0, 2) or (konum == 3 and rng.random() < 0.3):
            ekle(davul, an + (vurus / 2 if konum == 3 else 0), kazanc=0.9)
            p0 = int(an * SR)
            ln = min(int(vurus * SR), n - p0)
            if ln > 0:
                pompa[p0:p0 + ln] = np.minimum(pompa[p0:p0 + ln],
                                               1 - 0.75 * np.exp(-np.arange(ln, dtype=np.float32) / SR * 9))
        if konum in (1, 3):
            ekle(el, an, 0.5, 0.8)
        for yarim in (0, 0.5):
            ekle(zil, an + yarim * vurus, 0.35 + 0.3 * rng.random(), 0.6 + 0.6 * rng.random())

    t = np.arange(n, dtype=np.float32) / SR
    olcu = 4 * vurus
    akor_no = (t // olcu).astype(int) % 4
    for j in range(3):
        f = np.array([_frekans(kok + 12 + dizi[k][j]) for k in range(4)], np.float32)[akor_no]
        dalga = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.06
        sol += dalga * pompa * (0.7 if j == 0 else 0.5)
        sag += dalga * pompa * (0.5 if j == 0 else 0.7)
    fb = np.array([_frekans(kok + dizi[k][0]) for k in range(4)], np.float32)[akor_no]
    bas = np.tanh(2.2 * np.sin(2 * np.pi * np.cumsum(fb) / SR)) * 0.22 * pompa
    sol += bas
    sag += bas
    son = int(1.2 * SR)
    kes = int(saniye * SR)
    sol, sag = sol[:kes], sag[:kes]
    sol[-son:] *= np.linspace(1, 0, son)
    sag[-son:] *= np.linspace(1, 0, son)
    return _wav_yaz(yol, sol, sag), vurus
