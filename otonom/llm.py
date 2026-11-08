"""Yapay zekâ katmanı — iki sağlayıcı, en düşük maliyet için ayarlı.

  * "yerel"  : ücretsiz yerel model (yerel_llm.py) — API anahtarı ve ücret yok.
  * "claude" : Claude API (daha kaliteli Türkçe, ayda birkaç kuruş).
  * "otomatik" (varsayılan): ANTHROPIC_API_KEY varsa Claude, yoksa yerel model.

Claude için maliyet düşürme yöntemleri:
Maliyet düşürme yöntemleri:
  1. En ucuz model (Claude Haiku 5.5) varsayılan.
  2. Toplu işlem (Message Batches API): tüm tokenlarda %50 indirim.
     GitHub Actions'ta beklerken dakika harcamamak için iki aşamalı çalışır:
     istek gönderilir, kimliği kaydedilir, sonuç bir sonraki çalıştırmada alınır.
  3. Ortak sistem talimatı önbelleğe alınır (prompt caching).
  4. Yapılandırılmış JSON çıktı: bozuk çıktı yüzünden tekrar deneme maliyeti yok.
  5. Tek çağrıda senaryo + başlık + açıklama + Shorts + blog yazısı üretilir.
Her çağrının maliyeti veri/maliyet.csv dosyasına yazılır.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .ayarlar import ISLETME, Ayarlar, csv_ekle, gizli, isletme_dosyalari, log

# 1M token başına $ (girdi, çıktı) — Anthropic fiyat listesi
FIYATLAR = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
MALIYET_DOSYASI = ISLETME / "maliyet.csv"


class LLMHatasi(RuntimeError):
    pass


def _var_mi(ad: str) -> bool:
    if ad == "claude":
        return bool(gizli("ANTHROPIC_API_KEY") or gizli("ANTHROPIC_AUTH_TOKEN"))
    if ad == "cloudflare":
        return bool(gizli("CLOUDFLARE_API_TOKEN") and gizli("CLOUDFLARE_ACCOUNT_ID"))
    if ad in UYUMLU:
        return bool(gizli(UYUMLU[ad][1]))
    if ad == "pc":
        return bool(gizli("JORMUNGAND_URL") and gizli("JORMUNGAND_TOKEN"))
    return True


# OpenAI uyumlu ücretsiz sağlayıcılar (Hibrit AI ile aynı anahtarlar): adres, gizli adı, model ayarı
UYUMLU = {
    "nvidia": ("https://integrate.api.nvidia.com/v1/chat/completions", "NVIDIA_API_KEY", "nvidia_modeli"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "openrouter_modeli"),
}


def saglayici_zinciri(ayar: Ayarlar) -> list[str]:
    """Denenecek yapay zekâ sağlayıcıları, sırayla. Biri kullanılamazsa (kredi, kota, ağ) sıradaki denenir.
    ucretsiz  : (VARSAYILAN) önce YEREL model, gerekirse ücretsiz kotalı servisler; Claude/paralı hizmet ASLA.
    otomatik  : Claude (anahtar varsa) -> Cloudflare Workers AI -> NVIDIA -> OpenRouter -> PC (Jormungand)
                -> yerel model. Anahtarı olmayan atlanır; hepsi ücretsiz kotalıdır (Claude hariç).
    claude    : Claude -> diğerleri     cloudflare: Cloudflare -> diğerleri     yerel: yalnızca yerel"""
    secim = ayar["llm"].get("saglayici", "otomatik")
    ucretsiz = ["cloudflare", "nvidia", "openrouter", "pc", "yerel"]
    sira = {"ucretsiz": ["yerel", "cloudflare", "nvidia", "openrouter", "pc"],
            "otomatik": ["claude", *ucretsiz], "claude": ["claude", *ucretsiz],
            "cloudflare": ucretsiz, "yerel": ["yerel"]}.get(secim, ["yerel"])
    if not ayar["llm"].get("cloudflare_metin_modeli"):
        sira = [x for x in sira if x != "cloudflare"]
    zincir = [x for x in sira if _var_mi(x)]
    return zincir or ["yerel"]


def saglayici(ayar: Ayarlar) -> str:
    """Bu çalıştırmada ilk denenecek sağlayıcı."""
    return saglayici_zinciri(ayar)[0]


def toplu_mu(ayar: Ayarlar) -> bool:
    """Toplu işlem yalnızca Claude'da anlamlı (yerel model zaten ücretsiz ve anlık)."""
    return bool(ayar["llm"]["toplu_islem"]) and not ayar.deneme and saglayici(ayar) == "claude"


def _istemci():
    import anthropic

    if not (gizli("ANTHROPIC_API_KEY") or gizli("ANTHROPIC_AUTH_TOKEN")):
        raise LLMHatasi(
            "ANTHROPIC_API_KEY tanımlı değil. GitHub > Settings > Secrets'a ekleyin "
            "veya test için --deneme kullanın."
        )
    anahtar = gizli("ANTHROPIC_API_KEY")  # GitHub'da toplu gizlilerden (TUM_GIZLILER) de okunur
    return anthropic.Anthropic(api_key=anahtar, max_retries=4) if anahtar else anthropic.Anthropic(max_retries=4)


def _parametreler(model: str, sistem: str, istem: str, sema: dict, efor: str, max_tokens: int) -> dict:
    return {
        "model": model,
        "max_tokens": max_tokens,
        # Sabit sistem talimatı en başta ve önbellek işaretli: tekrar eden isteklerde ucuzlar.
        "system": [{"type": "text", "text": sistem, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": istem}],
        "output_config": {"effort": efor, "format": {"type": "json_schema", "schema": sema}},
    }


def _maliyet(model: str, usage: Any, toplu: bool) -> float:
    girdi, cikti = FIYATLAR.get(model, FIYATLAR["claude-haiku-5-5"])
    okunan = getattr(usage, "cache_read_input_tokens", 0) or 0
    yazilan = getattr(usage, "cache_creation_input_tokens", 0) or 0
    dolar = (
        usage.input_tokens * girdi
        + okunan * girdi * 0.1
        + yazilan * girdi * 1.25
        + usage.output_tokens * cikti
    ) / 1_000_000
    return dolar * (0.5 if toplu else 1.0)


def _kaydet(gorev: str, model: str, usage: Any, toplu: bool) -> None:
    csv_ekle(
        MALIYET_DOSYASI,
        [{
            "gorev": gorev,
            "model": model,
            "toplu": int(toplu),
            "girdi_token": usage.input_tokens,
            "cikti_token": usage.output_tokens,
            "onbellek_okunan": getattr(usage, "cache_read_input_tokens", 0) or 0,
            "dolar": f"{_maliyet(model, usage, toplu):.6f}",
        }],
        ["gorev", "model", "toplu", "girdi_token", "cikti_token", "onbellek_okunan", "dolar"],
    )


def _mesajdan_json(mesaj: Any, gorev: str) -> dict:
    if mesaj.stop_reason == "refusal":
        raise LLMHatasi(f"[{gorev}] model isteği reddetti; konu değiştirilmeli.")
    if mesaj.stop_reason == "max_tokens":
        raise LLMHatasi(f"[{gorev}] çıktı yarıda kesildi (max_tokens); hedef kelime sayısını düşürün.")
    metin = next((b.text for b in mesaj.content if b.type == "text"), "")
    try:
        return json.loads(metin)
    except json.JSONDecodeError as e:
        raise LLMHatasi(f"[{gorev}] geçersiz JSON: {e}") from e


def yerel_kullanilabilir() -> bool:
    import importlib.util

    return importlib.util.find_spec("llama_cpp") is not None


def _yerel_json(ayar: Ayarlar, gorev: str, sistem: str, istem: str, sema: dict, max_tokens: int) -> dict:
    """Yerel model; çıktı yarım kalırsa metinleri kısaltma talimatıyla bir kez daha dener."""
    from . import yerel_llm

    for deneme in range(2):
        ek = "" if deneme == 0 else "\n\nÖNEMLİ: Önceki deneme sığmadı. Tüm metinleri yaklaşık yarı uzunlukta yaz."
        metin, neden, kullanim = yerel_llm.json_uret(ayar, sistem, istem + ek, sema, max_tokens)
        csv_ekle(MALIYET_DOSYASI, [{
            "gorev": gorev, "model": "yerel:" + ayar["llm"]["yerel_dosya"], "toplu": 0,
            "girdi_token": kullanim.get("prompt_tokens", 0), "cikti_token": kullanim.get("completion_tokens", 0),
            "onbellek_okunan": 0, "dolar": "0"}],
            ["gorev", "model", "toplu", "girdi_token", "cikti_token", "onbellek_okunan", "dolar"])
        if neden != "length":
            try:
                return json.loads(metin)
            except json.JSONDecodeError:
                pass
        log.warning("[%s] yerel model çıktısı yarım kaldı, kısaltılarak tekrar deneniyor.", gorev)
    raise LLMHatasi(f"[{gorev}] yerel model iki denemede de tamamlayamadı; llm.yerel_baglam değerini artırın.")


def _claude_json(ayar: Ayarlar, gorev: str, sistem: str, istem: str, sema: dict, efor: str | None,
                 max_tokens: int) -> dict:
    import anthropic

    model = ayar["llm"]["model"]
    try:
        mesaj = _istemci().messages.create(
            **_parametreler(model, sistem, istem, sema, efor or ayar["llm"]["kisa_is_efor"], max_tokens)
        )
    except anthropic.AuthenticationError as e:
        raise LLMHatasi("API anahtarı geçersiz (ANTHROPIC_API_KEY).") from e
    except anthropic.APIStatusError as e:
        raise LLMHatasi(f"[{gorev}] API hatası {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMHatasi(f"[{gorev}] ağ hatası: {e}") from e
    _kaydet(gorev, model, mesaj.usage, toplu=False)
    return _mesajdan_json(mesaj, gorev)


def _cloudflare_json(ayar: Ayarlar, gorev: str, sistem: str, istem: str, sema: dict, max_tokens: int) -> dict:
    """Cloudflare Workers AI (hesabın ücretsiz günlük kotası). JSON şeması 'json_schema' kipiyle istenir."""
    import requests

    model = ayar["llm"]["cloudflare_metin_modeli"]
    url = f"https://api.cloudflare.com/client/v4/accounts/{gizli('CLOUDFLARE_ACCOUNT_ID')}/ai/run/{model}"
    try:
        r = requests.post(url, timeout=300, headers={"Authorization": f"Bearer {gizli('CLOUDFLARE_API_TOKEN')}"},
                          json={"messages": [{"role": "system", "content": sistem}, {"role": "user", "content": istem}],
                                "max_tokens": min(max_tokens, 8000),
                                "response_format": {"type": "json_schema", "json_schema": sema}})
        veri = r.json()
    except (requests.RequestException, ValueError) as e:
        raise LLMHatasi(f"[{gorev}] Cloudflare Workers AI erişilemedi: {e}") from e
    if not veri.get("success"):
        raise LLMHatasi(f"[{gorev}] Cloudflare Workers AI hatası (kota dolmuş olabilir): {veri.get('errors')}")
    cevap = (veri.get("result") or {}).get("response")
    csv_ekle(MALIYET_DOSYASI, [{"gorev": gorev, "model": "cloudflare:" + model, "toplu": 0,
                                "girdi_token": (veri.get("result") or {}).get("usage", {}).get("prompt_tokens", 0),
                                "cikti_token": (veri.get("result") or {}).get("usage", {}).get("completion_tokens", 0),
                                "onbellek_okunan": 0, "dolar": "0"}],
             ["gorev", "model", "toplu", "girdi_token", "cikti_token", "onbellek_okunan", "dolar"])
    if isinstance(cevap, dict):
        return cevap
    try:
        return json.loads(cevap or "")
    except (json.JSONDecodeError, TypeError) as e:
        raise LLMHatasi(f"[{gorev}] Cloudflare geçersiz JSON döndürdü: {e}") from e


def _json_ayikla(metin: str) -> dict:
    metin = (metin or "").strip()
    if metin.startswith("```"):
        metin = metin.split("\n", 1)[-1].rsplit("```", 1)[0]
    bas, son = metin.find("{"), metin.rfind("}")
    return json.loads(metin[bas:son + 1] if bas >= 0 else metin)


def _uyumlu_json(ayar: Ayarlar, ad: str, gorev: str, sistem: str, istem: str, sema: dict, max_tokens: int) -> dict:
    """NVIDIA / OpenRouter (OpenAI uyumlu, ücretsiz kotalı) ya da evdeki PC (Jormungand, tünelle)."""
    import requests

    talimat = (sistem + "\n\nYalnızca şu JSON şemasına uyan geçerli bir JSON nesnesi döndür, başka hiçbir şey yazma:\n"
               + json.dumps(sema.get("schema", sema), ensure_ascii=False))
    try:
        if ad == "pc":
            r = requests.post(gizli("JORMUNGAND_URL").rstrip("/") + "/chat", timeout=300,
                              headers={"X-Jor-Token": gizli("JORMUNGAND_TOKEN")},
                              json={"prompt": talimat + "\n\n" + istem})
            metin, model = r.json().get("response", ""), "pc:jormungand"
        else:
            url, anahtar, model_ayari = UYUMLU[ad]
            model = ayar["llm"][model_ayari]
            r = requests.post(url, timeout=300, headers={"Authorization": f"Bearer {gizli(anahtar)}"},
                              json={"model": model, "max_tokens": min(max_tokens, 8000), "temperature": 0.6,
                                    "messages": [{"role": "system", "content": talimat},
                                                 {"role": "user", "content": istem}],
                                    "response_format": {"type": "json_object"}})
            veri = r.json()
            if not r.ok or "choices" not in veri:
                raise LLMHatasi(f"[{gorev}] {ad} hatası (kota dolmuş olabilir): {str(veri)[:200]}")
            metin, model = veri["choices"][0]["message"]["content"], f"{ad}:{model}"
        sonuc = _json_ayikla(metin)
    except LLMHatasi:
        raise
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
        raise LLMHatasi(f"[{gorev}] {ad} kullanılamadı: {e}") from e
    csv_ekle(MALIYET_DOSYASI, [{"gorev": gorev, "model": model, "toplu": 0, "girdi_token": 0, "cikti_token": 0,
                                "onbellek_okunan": 0, "dolar": "0"}],
             ["gorev", "model", "toplu", "girdi_token", "cikti_token", "onbellek_okunan", "dolar"])
    return sonuc


def json_uret(
    ayar: Ayarlar,
    gorev: str,
    sistem: str,
    istem: str,
    sema: dict,
    sahte: Callable[[], dict],
    efor: str | None = None,
    max_tokens: int = 16000,
) -> dict:
    """Tek, anlık istek. Deneme modunda `sahte()` çıktısını döner.

    Yedek zinciri: bir sağlayıcı kullanılamazsa (kredi bitti, günlük kota, ağ, geçersiz anahtar) iş durmaz,
    sıradaki denenir; en sonda her zaman ücretsiz yerel model vardır. Geçişler DURUM.md'de görünür.
    """
    if ayar.deneme:
        return sahte()
    from .ayarlar import uyari_ekle

    zincir = saglayici_zinciri(ayar)
    if "yerel" not in zincir and yerel_kullanilabilir():
        zincir = zincir + ["yerel"]
    son_hata: LLMHatasi | None = None
    for i, ad in enumerate(zincir):
        try:
            if ad == "claude":
                return _claude_json(ayar, gorev, sistem, istem, sema, efor, max_tokens)
            if ad == "cloudflare":
                return _cloudflare_json(ayar, gorev, sistem, istem, sema, max_tokens)
            if ad in UYUMLU or ad == "pc":
                return _uyumlu_json(ayar, ad, gorev, sistem, istem, sema, max_tokens)
            return _yerel_json(ayar, gorev, sistem, istem, sema, max_tokens)
        except LLMHatasi as e:
            son_hata = e
            if "reddetti" in str(e) or i == len(zincir) - 1:
                raise
            uyari_ekle("yapay zekâ", f"{ad} kullanılamadı ({str(e)[:160]}); {zincir[i + 1]} ile devam edildi.")
    raise son_hata or LLMHatasi(f"[{gorev}] hiçbir yapay zekâ sağlayıcısı kullanılamadı")


# ------------------------------------------------------------- toplu işlem

def toplu_gonder(ayar: Ayarlar, istekler: list[dict]) -> str:  # yalnızca Claude
    """istekler: [{"id", "sistem", "istem", "sema", "efor", "max_tokens"}] -> batch kimliği"""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    model = ayar["llm"]["model"]
    batch = _istemci().messages.batches.create(
        requests=[
            Request(
                custom_id=i["id"],
                params=MessageCreateParamsNonStreaming(
                    **_parametreler(model, i["sistem"], i["istem"], i["sema"], i["efor"], i.get("max_tokens", 16000))
                ),
            )
            for i in istekler
        ]
    )
    log.info("Toplu istek gönderildi: %s (%d iş)", batch.id, len(istekler))
    return batch.id


def toplu_sonuc(ayar: Ayarlar, batch_id: str) -> dict[str, dict | str] | None:
    """Bitmediyse None. Bittiyse {custom_id: json | 'HATA: ...'}"""
    istemci = _istemci()
    batch = istemci.messages.batches.retrieve(batch_id)
    if batch.processing_status != "ended":
        log.info("Toplu iş %s henüz bitmedi (%s).", batch_id, batch.processing_status)
        return None
    model = ayar["llm"]["model"]
    sonuc: dict[str, dict | str] = {}
    for r in istemci.messages.batches.results(batch_id):
        if r.result.type == "succeeded":
            msg = r.result.message
            _kaydet(r.custom_id, model, msg.usage, toplu=True)
            try:
                sonuc[r.custom_id] = _mesajdan_json(msg, r.custom_id)
            except LLMHatasi as e:
                sonuc[r.custom_id] = f"HATA: {e}"
        else:
            sonuc[r.custom_id] = f"HATA: {r.result.type}"
    return sonuc


def toplam_maliyet() -> float:
    from .ayarlar import csv_oku

    return sum(float(s["dolar"]) for d in isletme_dosyalari("maliyet.csv") for s in csv_oku(d))
