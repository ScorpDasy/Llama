"""YouTube yetki anahtarı (refresh token) alma — KENDİ BİLGİSAYARINIZDA BİR KEZ çalıştırın.

NOT: Artık buna gerek yok! "Tek tıkla yetki" (README) ile GitHub'daki konuya "onay" yazman yeterli;
sistem anahtarı kendisi alır ve kaydeder. Bu betik yalnızca yedek yöntemdir.

Ön hazırlık (README'deki adımlar):
  1. Google Cloud Console'da proje açın, "YouTube Data API v3" ve "YouTube Analytics API"yi etkinleştirin.
  2. OAuth izin ekranı: Kullanıcı türü "Harici", yayın durumunu "Üretimde" (In production) yapın.
     ("Test" modunda bırakırsanız anahtar 7 günde geçersiz olur!)
  3. Kimlik bilgisi oluşturun: OAuth istemci kimliği -> "Masaüstü uygulaması".
     JSON dosyasını indirip bu klasöre client_secret.json adıyla koyun.

Çalıştırma (her kanal için bir kez; kanal kodu config/kanallar/<kod>.yaml dosyasının adıdır):
  pip install google-auth-oauthlib
  python araclar/youtube_token_al.py ana
  python araclar/youtube_token_al.py tarih      # başka bir kanal için
Tarayıcı açılır; Google hesabınla giriş yap ve İZİN VERİLECEK KANALI SEÇ (birden çok kanalın varsa
"kanal seç" ekranında doğru kanalı seçmek önemli). Ekrana çıkan değerleri GitHub > Settings >
Secrets and variables > Actions'a ekle. YT_CLIENT_ID ve YT_CLIENT_SECRET tüm kanallar için ortaktır.
"""
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

IZINLER = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",          # altyazı, yorum, oynatma listesi, kanal SEO
    "https://www.googleapis.com/auth/yt-analytics.readonly",       # izlenme süresi
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",  # reklam geliri
]

kanal = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].endswith(".json") else "ana"
if kanal == "arama":  # Google Search Console otomatik kaydı için ayrı anahtar (GOOGLE_ARAMA_TOKEN)
    IZINLER = ["https://www.googleapis.com/auth/siteverification", "https://www.googleapis.com/auth/webmasters"]
dosya = Path(next((a for a in sys.argv[1:] if a.endswith(".json")), "client_secret.json"))
if not dosya.exists():
    sys.exit(f"{dosya} bulunamadı. Google Cloud'dan indirdiğiniz JSON dosyasının yolunu verin.")

akis = InstalledAppFlow.from_client_secrets_file(str(dosya), IZINLER)
kimlik = akis.run_local_server(port=0, prompt="consent", access_type="offline")
icerik = json.loads(dosya.read_text())
istemci = icerik.get("installed") or icerik.get("web")
print("\nAşağıdaki değerleri GitHub Secrets'a ekleyin (ilk ikisi tüm kanallar için bir kez yeterli):\n")
print(f"YT_CLIENT_ID      = {istemci['client_id']}")
print(f"YT_CLIENT_SECRET  = {istemci['client_secret']}")
print(f"{'GOOGLE_ARAMA_TOKEN' if kanal == 'arama' else 'YT_REFRESH_TOKEN_' + kanal.upper().replace('-', '_')}  = {kimlik.refresh_token}")
print(f"\n(Bu anahtar yalnızca '{kanal}' kanalının videolarını yükler.)")
print("\nBu değerleri kimseyle paylaşmayın. client_secret.json dosyasını depoya eklemeyin.")
