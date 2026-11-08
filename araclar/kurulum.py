#!/usr/bin/env python3
"""Kurulum sihirbazı — eksik anahtarları toplar, doğrular ve GitHub'a KENDİSİ ekler.

Telefonda (Termux) ya da bilgisayarda bir kez çalıştır:
    pkg install python gh        # Termux'ta (bilgisayarda: python ve GitHub CLI kurulu olsun)
    python kurulum.py

Ne yapar:
  1. GitHub'a bağlanır (gh; tarayıcıda bir kez "Authorize").
  2. Hangi anahtarların eksik olduğuna bakar; olanları atlar.
  3. Her eksik için doğru sayfayı açar, ne yapacağını söyler. Sen anahtarı buraya yapıştırırsın;
     sihirbaz geçerli mi diye dener, Cloudflare hesap numarasını kendisi bulur, GitHub Secrets'a kendisi yazar.
  4. Sistemi çalıştırır ve YouTube onay bağlantısını kendisi getirip açar: sen yalnızca "İzin ver"e basarsın.
Anahtarlar yalnızca senin cihazında ve GitHub'ın kilitli Secrets bölümünde kalır; hiçbir yere gönderilmez.
"""
from __future__ import annotations

import getpass
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

DEPO = "Das-Hub-qi/das"
YONLENDIRME = "https://trustneurohub-com-tr.pages.dev/api/yetki"


# ------------------------------------------------------------ yardımcılar

def yaz(metin: str = "") -> None:
    print(metin, flush=True)


def baslik(metin: str) -> None:
    yaz(f"\n\033[1;36m━━ {metin} ━━\033[0m")


def ac(url: str) -> None:
    yaz(f"   🔗 {url}")
    if shutil.which("termux-open-url"):
        subprocess.run(["termux-open-url", url], check=False)
    else:
        try:
            webbrowser.open(url)
        except Exception:
            pass


def panoya(metin: str) -> None:
    for komut in (["termux-clipboard-set"], ["pbcopy"], ["xclip", "-selection", "clipboard"], ["clip"]):
        if shutil.which(komut[0]):
            subprocess.run(komut, input=metin.encode(), check=False)
            yaz("   📋 Panoya kopyalandı (yapıştırabilirsin).")
            return


def sor(soru: str, gizli: bool = False, bos_olur: bool = False) -> str:
    while True:
        deger = (getpass.getpass(f"   ➜ {soru}: ") if gizli else input(f"   ➜ {soru}: ")).strip()
        if deger or bos_olur:
            return deger
        yaz("   Boş bırakılamaz.")


def http(url: str, baslik_: dict | None = None) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=baslik_ or {}), timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, ValueError, TimeoutError):
        return 0, {}


def gh(*args: str, girdi: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], input=girdi, capture_output=True, text=True)


def gizli_ekle(ad: str, deger: str) -> bool:
    r = gh("secret", "set", ad, "-R", DEPO, girdi=deger)
    yaz(f"   {'✅' if r.returncode == 0 else '❌'} {ad} GitHub'a {'eklendi' if r.returncode == 0 else 'eklenemedi: ' + r.stderr.strip()[:200]}")
    return r.returncode == 0


# ------------------------------------------------------------ adımlar

def github_baglan() -> set[str]:
    baslik("1/5 GitHub bağlantısı")
    if not shutil.which("gh"):
        sys.exit("GitHub CLI (gh) yok. Termux: pkg install gh   ·   Bilgisayar: https://cli.github.com")
    if gh("auth", "status").returncode != 0:
        yaz("   Tarayıcı açılacak: GitHub'da kodu onayla ve 'Authorize'a bas.")
        subprocess.run(["gh", "auth", "login", "--web", "--git-protocol", "https", "--scopes", "repo,workflow"])
    var = gh("secret", "list", "-R", DEPO, "--json", "name")
    if var.returncode != 0:
        sys.exit(f"Depoya erişilemedi: {var.stderr.strip()[:300]}")
    mevcut = {s["name"] for s in json.loads(var.stdout or "[]")}
    yaz(f"   ✅ Bağlandı. Mevcut anahtarlar: {', '.join(sorted(mevcut)) or 'yok'}")
    return mevcut


def cloudflare(mevcut: set[str]) -> None:
    baslik("2/5 Cloudflare (siteler, teklif formu, tek tıkla onay sayfası)")
    if {"CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"} <= mevcut:
        yaz("   ✅ Zaten ekli, atlanıyor.")
        return
    izinler = [{"key": "page", "type": "edit"}, {"key": "workers_kv_storage", "type": "edit"},
               {"key": "workers_ai", "type": "edit"}, {"key": "zone", "type": "read"}, {"key": "dns", "type": "edit"}]
    yaz("   Açılan sayfada izinler hazır gelir (gelmezse şunları ekle: Cloudflare Pages: Edit, Workers KV Storage: Edit,\n"
        "   Workers AI: Edit, Zone: Read, DNS: Edit). En alta in → 'Continue to summary' → 'Create Token' → anahtarı kopyala.")
    ac("https://dash.cloudflare.com/profile/api-tokens?name=otonom-sistem&accountId=*&zoneId=all&permissionGroupKeys="
       + urllib.request.quote(json.dumps(izinler, separators=(",", ":"))))
    while True:
        token = sor("Cloudflare anahtarını yapıştır (görünmez)", gizli=True)
        kod, d = http("https://api.cloudflare.com/client/v4/user/tokens/verify", {"Authorization": f"Bearer {token}"})
        if kod == 200 and d.get("success"):
            break
        yaz("   ❌ Anahtar geçersiz görünüyor, tekrar dene.")
    _, hesaplar = http("https://api.cloudflare.com/client/v4/accounts", {"Authorization": f"Bearer {token}"})
    liste = hesaplar.get("result") or []
    if len(liste) == 1:
        hesap = liste[0]["id"]
        yaz(f"   ✅ Hesap bulundu: {liste[0].get('name', '')}")
    elif liste:
        for i, h in enumerate(liste, 1):
            yaz(f"   {i}) {h.get('name')}")
        hesap = liste[int(sor('Hangisi? (numara)')) - 1]["id"]
    else:
        yaz("   Hesap numarası otomatik bulunamadı. Cloudflare ana sayfasında sağ altta 'Account ID' yazar.")
        hesap = sor("Account ID")
    gizli_ekle("CLOUDFLARE_API_TOKEN", token)
    gizli_ekle("CLOUDFLARE_ACCOUNT_ID", hesap)


def google(mevcut: set[str]) -> None:
    baslik("3/5 Google uygulaması (YouTube'a yükleme ve onay için, bir kez)")
    if {"YT_CLIENT_ID", "YT_CLIENT_SECRET"} <= mevcut:
        yaz("   ✅ Zaten ekli, atlanıyor.")
        return
    yaz("   a) Yeni proje oluştur (adı: otonom) → 'Create'.")
    ac("https://console.cloud.google.com/projectcreate")
    input("   Bitince Enter'a bas…")
    yaz("   b) 'Get started' → uygulama adı: Otonom, e-postanı seç → Audience: External → Create.\n"
        "      Sonra 'Audience' sayfasında 'Publish app' (In production) yap.")
    ac("https://console.cloud.google.com/auth/overview")
    input("   Bitince Enter'a bas…")
    yaz("   c) Create client → Application type: Web application → 'Authorized redirect URIs' kısmına şunu ekle:")
    yaz(f"      {YONLENDIRME}")
    panoya(YONLENDIRME)
    ac("https://console.cloud.google.com/auth/clients/create")
    while True:
        istemci = sor("Client ID'yi yapıştır")
        if istemci.endswith(".apps.googleusercontent.com"):
            break
        yaz("   ❌ Client ID '...apps.googleusercontent.com' ile biter, tekrar dene.")
    sir = sor("Client secret'ı yapıştır (görünmez)", gizli=True)
    gizli_ekle("YT_CLIENT_ID", istemci)
    gizli_ekle("YT_CLIENT_SECRET", sir)


def istege_bagli(mevcut: set[str]) -> None:
    baslik("4/5 İsteğe bağlı (Enter = atla)")
    if "PEXELS_API_KEY" not in mevcut:
        yaz("   Pexels: Shorts'ta gerçek stok video (ücretsiz). Hesap aç → 'Your API Key' kopyala.")
        ac("https://www.pexels.com/api/new/")
        anahtar = sor("Pexels anahtarı (atlamak için Enter)", bos_olur=True)
        if anahtar:
            kod, _ = http("https://api.pexels.com/v1/search?query=brain&per_page=1", {"Authorization": anahtar})
            gizli_ekle("PEXELS_API_KEY", anahtar) if kod == 200 else yaz("   ❌ Pexels anahtarı çalışmadı, atlandı.")
    if "YOUTUBE_API_KEY" not in mevcut:
        yaz("   YouTube istatistik anahtarı (rakip/trend analizi): Create credentials → API key → kopyala.")
        ac("https://console.cloud.google.com/apis/credentials")
        anahtar = sor("API key (atlamak için Enter)", bos_olur=True)
        if anahtar:
            gizli_ekle("YOUTUBE_API_KEY", anahtar)


def baslat_ve_onayla() -> None:
    baslik("5/5 Sistemi başlat ve YouTube'u bağla")
    yaz("   Siteler ve onay sayfası yükleniyor (günlük iş başlatıldı, ~10 dk)…")
    gh("workflow", "run", "otonom.yml", "-R", DEPO, "-f", "komut=gunluk")
    for kanal, ad in (("google", "Google hesabı (API'ler + arama motorları)"), ("ana", "YouTube kanalı")):
        if input(f"   {ad} onayını şimdi yapalım mı? (E/h) ").strip().lower() == "h":
            continue
        bas = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        gh("workflow", "run", "yetki.yml", "-R", DEPO, "-f", f"kanal={kanal}")
        yaz("   ⏳ Onay bağlantısı bekleniyor (en fazla 15 dk; site ilk kez yükleniyorsa biraz sürer)…")
        bulundu = False
        for _ in range(90):
            time.sleep(10)
            r = gh("api", f"repos/{DEPO}/issues/comments?since={bas}&per_page=50")
            for yorum in reversed(json.loads(r.stdout or "[]") if r.returncode == 0 else []):
                govde = yorum.get("body") or ""
                m = re.search(r"\((https://accounts\.google\.com/o/oauth2/[^)\s]+)\)", govde)
                if m:
                    yaz("   👉 Google açılıyor: hesabını/kanalını seç ve 'İzin ver'e bas.")
                    ac(m.group(1))
                    bulundu = True
                    break
                if "henüz yüklenmemiş" in govde or "bir kerelik kurulum" in govde:
                    yaz("   ⏳ Onay sayfası henüz hazır değil; 10 dk sonra sihirbazı tekrar çalıştır (eklenenler atlanır).")
                    return
            if bulundu:
                break
        if not bulundu:
            yaz("   Bağlantı gelmedi. GitHub'daki '🔑 Onay gerekiyor' konusuna 'onay' yaz.")
            ac(f"https://github.com/{DEPO}/issues")
        else:
            input("   İzin verdikten sonra Enter'a bas…")
    yaz("\n✅ Kurulum tamam. Sistem artık kendi kendine çalışır; durum: "
        f"https://github.com/{DEPO}/blob/HEAD/DURUM.md")


def main() -> None:
    yaz("\033[1mOtonom sistem — kurulum sihirbazı\033[0m  (eksik olanları sırayla toplar; olanları atlar)")
    mevcut = github_baglan()
    cloudflare(mevcut)
    google(mevcut)
    istege_bagli(mevcut)
    baslat_ve_onayla()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        yaz("\nYarıda kesildi. Tekrar çalıştırınca eklenenler atlanır, kaldığın yerden devam eder.")
