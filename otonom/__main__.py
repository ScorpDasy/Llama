"""Komut satırı: python -m otonom <komut> [--kanal KOD | --genel] [--deneme]

Kanal komutları (her kanal için ayrı çalışır; --kanal verilmezse tüm kanallar sırayla, sonra genel adımlar):
  haftalik   Laboratuvar, Öğrenme Mühendisi, niş/kaynak analizi, plan, senaryo, video+Shorts
  gunluk     Kalan üretim/yükleme, viral kontrol (+ genel: teklifler, tıklamalar, siteler)
  beta       Kanal başına 1 örnek video + Shorts (YouTube'a yüklemez, 'beta/' klasörü)
  nis, plan, uret, analiz, muhendis   Tek tek modüller
Genel komutlar:
  yeni_kanal --aciklama "..."   Bir cümlelik açıklamadan yeni kanal oluşturur (config/kanallar/)
  kanallar   Etkin kanalların listesi (JSON)      envanter, alanadi, site, teklifler, rapor, maliyet
  durum      DURUM.md panelini günceller           cloudflare  Alan adlarını sitelere bağlar
--kanal KOD: yalnızca o kanalın adımları (GitHub'da her kanal ayrı paralel işte böyle çalışır)
--genel    : yalnızca genel adımlar (tüm kanallar bittikten sonra)
--deneme   : dış servis çağırmadan, geçici klasörde sahte veriyle uçtan uca test
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time

KANAL_KOMUTLARI = {"hazirlik", "haftalik", "gunluk", "beta", "nis", "plan", "uret", "analiz", "muhendis", "buyume"}
GENEL_KOMUTLAR = {"envanter", "alanadi", "site", "teklifler", "rapor", "maliyet", "cloudflare", "durum",
                  "yeni_kanal", "kanallar", "arama", "yetki"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="otonom", description="Otonom gelir ve içerik sistemi")
    p.add_argument("komut", choices=sorted(KANAL_KOMUTLARI | GENEL_KOMUTLAR))
    p.add_argument("--kanal", help="yalnızca bu kanalın adımları")
    p.add_argument("--genel", action="store_true", help="yalnızca genel adımlar")
    p.add_argument("--aciklama", default="", help="yeni_kanal için kanalın bir cümlelik tarifi")
    p.add_argument("--deneme", action="store_true", help="dış servis yok, geçici klasör, sahte veri")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    if a.komut == "beta" and not a.deneme and not os.environ.get("OTONOM_CALISMA"):
        from pathlib import Path
        os.environ["OTONOM_CALISMA"] = str(Path(__file__).resolve().parent.parent / "beta")
    if a.deneme and not os.environ.get("OTONOM_CALISMA"):
        os.environ["OTONOM_CALISMA"] = tempfile.mkdtemp(prefix="otonom-deneme-")
        print(f"Deneme klasörü: {os.environ['OTONOM_CALISMA']}")
    if a.deneme and not os.environ.get("OTONOM_CONFIG"):  # deneme gerçek ayarlara asla yazmaz (ör. yeni kanal)
        import shutil
        from pathlib import Path
        kopya = Path(os.environ["OTONOM_CALISMA"]) / "config"
        if not kopya.exists():
            shutil.copytree(Path(__file__).resolve().parent.parent / "config", kopya)
        os.environ["OTONOM_CONFIG"] = str(kopya)
    if a.kanal:
        os.environ["OTONOM_KANAL"] = a.kanal
    else:
        os.environ.pop("OTONOM_KANAL", None)

    k = a.komut
    if k == "kanallar":  # iş akışı bunu yalnızca PyYAML kurulu hafif ortamda çağırır
        from .ayarlar import kanal_listesi
        print(json.dumps(kanal_listesi()))
        return 0

    # Klasör yolları ortam değişkenlerine göre belirlendiği için içe aktarma burada yapılır.
    from . import butce, durum_paneli, llm, m01_envanter, m10_alan_adi, m12_gelir, mikro_site, orkestrator
    from .ayarlar import kanal_listesi, ozet_yaz, yukle

    # ---- Kanal süreci: yalnızca bir kanalın adımları ----
    if k in KANAL_KOMUTLARI and a.kanal:
        baslangic = time.time()
        ayar = yukle(deneme=a.deneme, kanal=a.kanal)
        if k in ("haftalik", "gunluk", "beta"):
            ayar.mod = butce.uyarla(ayar)
        hatalar = orkestrator.KANAL_ISLERI[k](ayar)
        butce.kaydet(ayar, k, time.time() - baslangic)
        return 1 if hatalar else 0

    # ---- Ana süreç: (gerekirse) her kanal ayrı süreçte, sonra genel adımlar ----
    hatalar: list[str] = []
    if k in KANAL_KOMUTLARI and not a.genel:
        for kod in kanal_listesi():
            print(f"\n===== Kanal: {kod} =====", flush=True)
            komut = [sys.executable, "-m", "otonom", k, "--kanal", kod] + (["--deneme"] if a.deneme else [])
            sonuc = subprocess.run(komut, env={**os.environ, "OTONOM_KANAL": kod})
            if sonuc.returncode:
                hatalar.append(f"Kanal '{kod}' adımlarından en az biri hata verdi (günlüğe bakın).")

    baslangic = time.time()
    ayar = yukle(deneme=a.deneme)
    if k in orkestrator.GENEL_ISLER:
        ayar.mod = butce.uyarla(ayar)
        hatalar += orkestrator.GENEL_ISLER[k](ayar)
    elif k == "envanter":
        m01_envanter.calistir(ayar)
    elif k == "alanadi":
        m10_alan_adi.calistir(ayar, zorla=True)
    elif k == "site":
        mikro_site.olustur(ayar)
    elif k == "teklifler":
        m12_gelir.teklifleri_isle(ayar)
        m12_gelir.tiklamalari_topla(ayar)
    elif k == "rapor":
        ozet_yaz(m12_gelir.aylik_rapor(ayar))
    elif k == "cloudflare":
        from . import cloudflare_kur
        cloudflare_kur.kv_kimligi()
        cloudflare_kur.alan_adlarini_bagla(ayar)
    elif k == "arama":
        from . import arama_motoru
        arama_motoru.calistir(ayar)
    elif k == "yetki":
        from . import yetki
        yetki.calistir(ayar)
    elif k == "maliyet":
        print(f"Toplam yapay zekâ maliyeti: {llm.toplam_maliyet():.4f} $")
    elif k == "yeni_kanal":
        from . import kanal_sihirbazi
        try:
            yeni = kanal_sihirbazi.olustur(ayar, a.aciklama)
            if not a.deneme:  # yeni kanalın YouTube onayı için GitHub'da konu aç (sahip "onay" yazar)
                from . import yetki
                yetki.onay_konusu(str(yeni), "youtube", "yeni kanal oluşturuldu")
        except (ValueError, llm.LLMHatasi) as e:
            hatalar.append(f"Yeni kanal oluşturulamadı: {e}")
    if k not in ("cloudflare", "arama", "yetki"):  # ana çalıştırmanın ardından gelen yardımcı adım: panel ve bütçe ana işe aittir
        butce.kaydet(ayar, f"{k}-genel" if k in KANAL_KOMUTLARI else k, time.time() - baslangic)
        durum_paneli.yaz(ayar, k, hatalar)
    return 1 if hatalar else 0


if __name__ == "__main__":
    sys.exit(main())
