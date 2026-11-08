"""Cloudflare otomatik kurulum — elle yapılacak adımları azaltır (ücretsiz REST API).

* KV deposu (TEKLIFLER) yoksa oluşturur; CF_KV_NAMESPACE_ID girmeye gerek kalmaz.
* Her alan adını kendi Pages projesine bağlar ve Cloudflare'de DNS kaydı yoksa ekler.
Gerekli token izinleri: Pages:Edit, Workers KV Storage:Edit, (alan adı bağlamak için) Zone:Read + DNS:Edit.
"""
from __future__ import annotations

import requests

from .ayarlar import Ayarlar, gizli, log

API = "https://api.cloudflare.com/client/v4"
_KV: str | None = None


def hazir() -> bool:
    return bool(gizli("CLOUDFLARE_API_TOKEN") and gizli("CLOUDFLARE_ACCOUNT_ID"))


def _istek(yontem: str, yol: str, **kw) -> dict:
    r = requests.request(yontem, API + yol, timeout=30,
                         headers={"Authorization": f"Bearer {gizli('CLOUDFLARE_API_TOKEN')}"}, **kw)
    try:
        return r.json()
    except ValueError:
        return {"success": False, "errors": [{"message": r.text[:200]}]}


def kv_kimligi() -> str:
    """Ortam değişkeni varsa onu, yoksa 'TEKLIFLER' adlı KV deposunu bulur/oluşturur."""
    global _KV
    if gizli("CF_KV_NAMESPACE_ID"):
        return gizli("CF_KV_NAMESPACE_ID")
    if _KV is not None or not hazir():
        return _KV or ""
    hesap = gizli("CLOUDFLARE_ACCOUNT_ID")
    liste = _istek("GET", f"/accounts/{hesap}/storage/kv/namespaces", params={"per_page": 100})
    for ns in liste.get("result") or []:
        if ns.get("title") == "TEKLIFLER":
            _KV = ns["id"]
            return _KV
    yeni = _istek("POST", f"/accounts/{hesap}/storage/kv/namespaces", json={"title": "TEKLIFLER"})
    if yeni.get("success"):
        _KV = yeni["result"]["id"]
        log.info("Cloudflare KV deposu oluşturuldu: TEKLIFLER")
    else:
        log.warning("KV deposu oluşturulamadı (token'da 'Workers KV Storage: Edit' izni olmalı): %s", yeni.get("errors"))
        _KV = ""
    return _KV


def alan_adlarini_bagla(ayar: Ayarlar) -> list[str]:
    """Her alan adını Pages projesine bağlar. Zaten bağlıysa dokunmaz."""
    from .mikro_site import proje_adi

    if not hazir():
        return []
    hesap, baglanan = gizli("CLOUDFLARE_ACCOUNT_ID"), []
    for a in ayar.alan_adlari:
        alan, proje = a["ad"], proje_adi(a["ad"])
        mevcut = _istek("GET", f"/accounts/{hesap}/pages/projects/{proje}/domains")
        if not mevcut.get("success"):
            continue  # proje henüz yüklenmemiş
        if any(d.get("name") == alan for d in mevcut.get("result") or []):
            continue
        sonuc = _istek("POST", f"/accounts/{hesap}/pages/projects/{proje}/domains", json={"name": alan})
        if not sonuc.get("success"):
            log.warning("%s bağlanamadı: %s", alan, sonuc.get("errors"))
            continue
        baglanan.append(alan)
        _dns_kaydi(alan, f"{proje}.pages.dev")
        log.info("Alan adı bağlandı: %s -> %s.pages.dev", alan, proje)
    return baglanan


def _dns_kaydi(alan: str, hedef: str) -> None:
    """Alan adı Cloudflare'de ise ve kök kaydı yoksa CNAME ekler. Var olan kayda (ör. park) dokunmaz."""
    bolge = _istek("GET", "/zones", params={"name": alan}).get("result") or []
    if not bolge:
        log.warning("%s Cloudflare'de değil: kayıt firmanızda nameserver'ları Cloudflare'e çevirin.", alan)
        return
    zid = bolge[0]["id"]
    kayitlar = _istek("GET", f"/zones/{zid}/dns_records", params={"name": alan}).get("result") or []
    if any(k.get("type") in ("A", "AAAA", "CNAME") for k in kayitlar):
        if not any(k.get("type") == "CNAME" and k.get("content") == hedef for k in kayitlar):
            log.warning("%s için zaten bir DNS kaydı var; siteyi göstermek için onu silip tekrar çalıştırın.", alan)
        return
    _istek("POST", f"/zones/{zid}/dns_records",
           json={"type": "CNAME", "name": alan, "content": hedef, "proxied": True})


def dns_txt_ekle(alan: str, deger: str) -> bool:
    """Alan adının kökün TXT kaydını ekler (Google doğrulaması için). Zaten varsa dokunmaz."""
    if not hazir():
        return False
    bolge = _istek("GET", "/zones", params={"name": alan}).get("result") or []
    if not bolge:
        return False
    zid = bolge[0]["id"]
    mevcut = _istek("GET", f"/zones/{zid}/dns_records", params={"type": "TXT", "name": alan}).get("result") or []
    if any(k.get("content", "").strip('"') == deger for k in mevcut):
        return True
    return bool(_istek("POST", f"/zones/{zid}/dns_records",
                       json={"type": "TXT", "name": alan, "content": deger, "ttl": 300}).get("success"))
