# Otonom Gelir ve İçerik Sistemi

**İstediğin kadar YouTube kanalını** (her biri farklı konu, kaynak, dil ve biçimde) ve alan adlarından
(trustneurohub.com.tr, okyanusbilisimtr.com, turizm alan adları) gelir elde etmeyi **ücretsiz bulut
katmanlarında**, kendi kendine öğrenerek yürüten otomasyon sistemi. Video ve Shorts üretimi, seslendirme,
görsel, küçük resim, yükleme ve yeni kanal kurulumu dahil tüm yapay zekâ işleri otomatiktir.
Hiçbir ücretli hesap gerektirmez.

> 🧭 **Tüm sistem tek sayfada → [Kontrol Merkezi](https://claude.ai/artifact/JmGazg5W8YwsfdmMX7WeLf)**
> (çalıştırma düğmeleri, tüm bağlantılar, test sonuçları, kurulum ilerlemesi)
>
> 🔒 Güvenlik: [SECURITY.md](SECURITY.md) · 🔁 Yeni oturumda devam: [DEVAM.md](DEVAM.md)
>
> 📊 **Canlı durum, eksik kurulum adımları ve son videolar → [DURUM.md](DURUM.md)**
> (her çalıştırmada kendiliğinden güncellenir; telefondan GitHub uygulamasıyla da okunur)

---

## 🚀 3 adımda başla

Hiçbir anahtar eklemeden başlayabilirsin; sistem eksikleri ücretsiz yedeklerle tamamlar.

1. **Beta'yı çalıştır:** GitHub > **Actions > Otonom sistem > Run workflow** → `beta` seç → **Run**.
   Sistem 1 gerçek video + 2 Shorts + site sayfası üretir, YouTube'a **yüklemez**. Bitince
   çalıştırmanın sayfasında en altta **Artifacts**'tan indirip izle.
2. **DURUM.md'yi aç:** neyin kurulu, neyin eksik olduğunu ve her eksiğin nasıl tamamlanacağını gösterir.
   En büyük kalite artışı için önce ücretsiz **Pexels** anahtarını ekle (aşağıda adım B).
3. **Başlat:** aynı yerden `haftalik` çalıştır. Sonrası otomatik: her pazartesi plan ve üretim,
   her gün yükleme ve teklif kontrolü. Bir adım hata verirse GitHub sana e-posta gönderir.
4. **Yeni kanal aç (istediğin kadar):** **Run workflow** → komut `yeni_kanal` → **aciklama** kutusuna kanalı
   bir cümleyle yaz, ör. *"Osmanlı tarihinden az bilinen hikâyeler anlatan, sadece Shorts kanalı"*.
   Sistem kanalı tasarlar ve sonraki çalıştırmadan itibaren kendi paralel işinde üretime başlar.

---

## 💰 Maliyet

| Hizmet | Ne için | Ücret |
|---|---|---|
| GitHub Actions | Zamanlayıcı, yapay zekâ, video üretimi | **0 ₺** (özel depoda ayda 2.000 dk; yerel modelle ~300-600 dk kullanılır) |
| Yerel yapay zekâ: Gemma 4 E2B | Senaryo, plan, satış metinleri | **0 ₺** (GitHub sunucusunda çalışır) |
| Edge TTS (yedek: Piper) | Türkçe seslendirme | **0 ₺** |
| Pexels / Pixabay / Openverse | Telifsiz fotoğraflar | **0 ₺** |
| YouTube Data API | Yükleme ve istatistik | **0 ₺** (günlük ücretsiz kota) |
| Cloudflare Pages, Workers, KV, Email Routing | Siteler, teklif formu, link takibi | **0 ₺** |
| *İsteğe bağlı:* Claude Haiku 5.5 | Daha kaliteli Türkçe metin | ≈ 0,01-0,05 $/ay |

Tek gider alan adlarının yıllık yenileme ücreti. Sistem dakika bütçesini kendisi izler; sınıra yaklaşınca
üretimi azaltır, böylece hesap asla ücretliye dönmez.

---

## ⚙️ Nasıl çalışır?

```
Pazartesi 09:17 ─ HER KANAL KENDİ İŞİNDE, PARALEL:
                    laboratuvar → Öğrenme Mühendisi → konu kaynakları → plan (Thompson) → senaryo →
                    seslendirme → görsel → video + Shorts → küçük resim → YouTube
                  ARDINDAN GENEL İŞ: alan adı metinleri → siteler (tüm kanalların yazıları) → rapor → DURUM.md
Pazartesi 13:37 ─ (Claude toplu işi kullanılıyorsa) senaryoları alır ve üretir
Her gün   07:07 ─ Kanallar: kalan yüklemeler, viral kontrol · Genel: teklifler, link tıklamaları, siteler
```

**🩺 Kendini denetleyen ve onaran sistem (tamamen yerel):**
- **Kalite Denetçisi:** Her video yayından önce muayene edilir ve 100 üzerinden karne alır. Bakılanlar: ses düzeyi
  (YouTube standardı -14 LUFS), ses kırpması, uzun sessizlik, siyah kare, donmuş görüntü, Shorts süresi ve
  görsellerin cümleye uygunluğu.
- **Onarım:** Kusur varsa sistem onarır ve yeniden üretir. Örnekler: klasik harekete geçmek, seslendirmeyi yenilemek,
  Shorts'u hızlandırmak, zayıf görseller için hazırlığa geri dönüp daha fazla aday üretmek, metni kısaltmak.
  Her kusurun birkaç çözüm yolu vardır; hangisinin gerçekten işe yaradığı denenerek öğrenilir.
- **Birbirine öğretme:**
  - Bir kanalda işe yarayan onarım diğer kanallara da geçer.
  - Kanallar biçim deneylerinde (başlık stili, görsel stili, müzik, uzunluk) birbirinin deneyiminden %15 ödünç alır.
  - Kalite Denetçisi'nin sık bulduğu kusurlar Öğrenme Mühendisi'ne ders olur ve kök nedenden çözülür. Örneğin görseller
    sık zayıfsa aday sayısı artırılır, Shorts sık uzunsa anlatım hızlandırılır.
- **Yeni deneyler:** Görsel stili (sinematik / belgesel / canlı renkli) ve müzik ruh hali de izlenmeye göre öğrenilir.
  Kazanan bulunca mühendis havuzdan yeni stiller dener. Sonuçlar DURUM.md'deki "🩺 Kalite Denetçisi" bölümünde görünür.

**🧩 Hazırlık aşaması (videonun parçaları ayrı zamanlarda, acele etmeden):**
- Senaryodan sonra video hemen birleştirilmez. Hazırlık günde 3 kez çalışır, her seferinde 25 dakika ilerler ve
  kaldığı yerden devam eder.
- Her görsel yuvası (sahne / Shorts cümlesi) için 3 aday üretilir: farklı kaynak, kadraj ve tohum.
- Adaylar **yerel CLIP modeliyle** cümleye uygunluk ve netliğe göre puanlanır, en iyisi seçilir.
  Örneğin "akan sıvı" sahnesinde limonata bardağı elenir.
- Shorts metinleri kurala uymuyorsa (ilk cümle uzun, toplam kelime fazla) yerel yapay zekâ düzeltir.
- Seslendirmeler önceden hazırlanıp saklanır. Her şey hazır olunca (en fazla 36 saat sonra) video birleştirilip yüklenir.
- **Yapay zekâ sırası varsayılan olarak "ucretsiz":** Önce yerel model çalışır, gerekirse ücretsiz kotalı servisler devreye girer.
  Claude ya da paralı bir hizmet kullanılmaz (`config/ayarlar.yaml` > `llm.saglayici`).

**🎬 Video kalitesi (montaj v3, hepsi ücretsiz, yerel ve anahtarsız):**
- **2.5D sinematik hareket:** Her fotoğraf yerel bir derinlik modeliyle (Depth-Anything-V2-Small, Apache-2.0, 27 MB)
  üç boyutlu canlanır; kamera hareket ettikçe yakındaki nesneler uzaktakilerden farklı kayar. Uzun sahneler sanal
  kamera kesmeleriyle (geniş → yakın → orta plan) birkaç çekime bölünür.
- **Otomatik bilgi grafikleri:** Metinde sayı geçince ("yüzde altmış", "86 milyar nöron", "3 kat", "1928 yılında")
  söylendiği anda ekranda canlı grafik çıkar: dolan yüzde halkası, sayan rakam, tarih damgası.
- **YouTube'un resmî önerileri senaryoya işlendi:** İlk 2 cümle başlığın sözünü hemen karşılar ve sayılar somut
  verilir. Merak döngüleri kurulur. Başlıklar teknik terim yerine herkesin yaşadığı sorun üzerinden yazılır.
  Shorts sonunda "TAMAMI KANALDA" çağrısı çıkar. Yeni kanal ilk 12 videoda tek konuya odaklanır.
- **Anahtarsız görsel:** Stok anahtarı yoksa önce konuya uygun yapay zekâ görseli (1920 piksel) kullanılır.
- Her sahnede farklı, yumuşak kamera hareketi (yaklaş, uzaklaş, kaydır, köşeye odaklan, süzül); açılışta hızlı "darbe" yakınlaşması.
- Sahneler arası geçişler (kayma, çözülme, daire, bulanık...); bölüm başlarında karartmalı geçiş ve kayan bölüm bandı.
- Söylenen cümle ekranda yumuşakça belirir.
- **Shorts (izleyiciyi tutmak için baştan tasarlandı):**
  - Ekranda selam ya da giriş yok; ilk cümle en fazla 8 kelimelik şaşırtıcı bir iddia ya da sorudur.
  - Toplam süre 25-35 saniyedir. Her cümleye ayrı görsel düşer ve 1,5-3 saniyede bir kesme yapılır.
    `PEXELS_API_KEY` varsa her cümlede **gerçek stok video** oynar (ücretsizdir, atıf gerekmez); yoksa fotoğraf kullanılır.
  - Kesmelerde vuruşlu yakınlaşma, ara sıra beyaz flaş ve whoosh sesi vardır.
  - Altyazı iri, kalın ve BÜYÜK HARF'tir; kelime kelime renklenir ve zıplar. Telefonda arayüzün altında kalmasın diye ekranın ortasındadır.
  - Üstte sürekli duran, renkli bir başlık kutusu vardır.
  - Müzik vuruşludur ve konuşmada kısılır. Son cümle başa bağlanır, izleyici videoyu tekrar izler. Sonda "TAKİP ET" yazar.
- Logo filigranı (`config/marka/logo.png`), ince ilerleme çubuğu, videonun ~%30'unda kayan "ABONE OL" rozeti, logolu kapanış.
- Ses: canlı tonlama (kanca enerjik, sorular hafif yüksek perdeden, kapanış sakin). Her videoya özel, telifsiz
  **üretilmiş fon müziği** konuşma sırasında kısılır. Geçişlerde stereo "whoosh" sesi duyulur. Ses düzeyi
  YouTube standardındadır (-14 LUFS). Hepsi `config/ayarlar.yaml` > `video:` / `ses:` altından açılıp kapanır.

**Tek senaryodan 4 içerik:** 1 uzun video (5-9 dk, bölümlü, altyazılı) + 2 Shorts (büyük altyazılı)
+ alan adının sitesinde SEO uyumlu yazı + başlık/açıklama/etiketler. Uzun videolar Salı/Perşembe/Cumartesi
yayına girer (`gizlilik: "zamanla"` iken; değilse Studio'dan tek tıkla).

**Alan adları:** Her alan adına Cloudflare'de ücretsiz site kurulur; içerik büyüdükçe değeri artar.
Sitede "satılık/kiralık" teklif formu vardır; gelen teklife yanıt taslağı otomatik hazırlanır.
Ortaklık (affiliate) linkleri kendi alan adından kısa link olur (`/git/kurs`), tıklamalar sayılır,
link değişince eski videolar otomatik düzelir.

## 📺 Kanallar: istediğin kadar, her biri farklı

Her kanal `config/kanallar/<kod>.yaml` dosyasıdır. Kanal başına ayrı ayarlanabilenler:

| Ayar | Seçenekler |
|---|---|
| **Konu** | Kanalın nişleri; her nişin hedef kitlesi ve arama tohumları |
| **Konu kaynakları** | `youtube_oneri` (insanların aradıkları), `google_trendler` (Türkiye gündemi), `rss` (haber/blog akışları), `wikipedia_bugun` (tarihte bugün), `elle` (kendi listen) |
| **Biçim** | `uzun_ve_shorts` · `sadece_shorts` · `sadece_uzun` |
| **Dil ve ses** | `tr`, `en`, `de`, `es`, `fr`, `ar`; erkek/kadın Edge sesi (yedek: dile uygun Piper sesi) |
| **Üslup** | Ör. "merak uyandıran hikâye anlatıcısı" — kanallar birbirine benzemez |
| **Görsel sırası** | Stok fotoğraf önce, veya tarih/fantastik konular için yapay zekâ görseli önce |
| **Video sayısı, uzunluk, yayın günleri** | `ayarlar:` altında kanalın genel ayarlardan farkları |
| **Alan adı** | Nişin yazıları hangi sitede yayınlanacak (birden çok kanal aynı siteyi besleyebilir) |

Yeni kanal açmanın iki yolu: **sihirbaz** (Run workflow → `yeni_kanal` → açıklama) veya `ana.yaml`'ı kopyalayıp
düzenlemek. Kanalı durdurmak için dosyada `aktif: false`. Her kanalın öğrenme hafızası (`veri/kanallar/<kod>/`)
ayrıdır: bir kanalda iyi giden başlık stili diğerini etkilemez.

**YouTube bağlantısı kanal başına:** her kanal kendi anahtarıyla yükler (`YT_REFRESH_TOKEN_<KANAL>`,
ör. `YT_REFRESH_TOKEN_TARIH`). Bilgisayarında `python araclar/youtube_token_al.py <kanal_kodu>` çalıştırıp çıkan
anahtarı Secrets'a ekle; iş akışını değiştirmen gerekmez. Anahtarı olmayan kanalın videoları indirilebilir kalır,
başka bir kanala asla yüklenmez. Günlük YouTube kotası kanallar arasında paylaştırılır.

## ✅ Haftalık 15 dakikalık kontrol

1. **DURUM.md**'ye bak: eksik adım veya uyarı varsa orada yazar.
2. YouTube Studio'da yeni videoları izle, sorun yoksa **Yayınla**. Bitiş ekranı: **Bitiş ekranı > Videodan içe aktar**.
3. Senaryolara göz at: küçük yerel model ara sıra hatalı bilgi yazabilir.
4. Yeni teklif varsa `veri/teklif_taslaklari/` içindeki yanıtı kontrol edip gönder.

**YouTube bağlantısı kurmadıysan:** videoları Artifacts'tan indirip elle yükle, sonra linklerini
[config/elle_yuklenenler.yaml](config/elle_yuklenenler.yaml) dosyasına ekle (DURUM.md hangi kodla
ekleyeceğini gösterir). Böylece öğrenme motoru bu videolardan da öğrenir.

---

## 📱 Telefondan yönetim (Hibrit AI ile birlikte)

Termux'a `otonom` komutunu kur: `bash araclar/telefon/kur.sh`. Telefonda Hibrit AI kuruluysa onunla yan yana
çalışır ve Hibrit'in NVIDIA/OpenRouter/Anthropic anahtarlarını buluta aktarmayı önerir.

| Komut | Ne yapar |
|---|---|
| `otonom durum` | Panel özeti (DURUM.md) |
| `otonom video [kanal]` | Hemen yeni video + Shorts üret |
| `otonom gunluk` / `haftalik` / `beta` | İş akışını şimdi çalıştır |
| `otonom yeni-kanal "açıklama"` | Yeni kanal aç (onay konusu kendiliğinden gelir) |
| `otonom onay [kanal\|google]` | Tek tıkla yetki: Google onay sayfası telefonda kendiliğinden açılır |
| `otonom bildirim` / `otonom zamanla` | Bekleyen onaylar telefon bildirimi olur (3 saatte bir kontrol) |
| `otonom anahtar-aktar` | Hibrit AI anahtarlarını bulut sistemine aktar |

---

## 🔑 Kurulum ayrıntıları (hepsi isteğe bağlı, hepsi ücretsiz)

Anahtarları **GitHub > Settings > Secrets and variables > Actions > New repository secret** bölümüne,
tablodaki adla ekle. Anahtarları asla dosyalara yazma.

### A. Yapay zekâ
Hiçbir şey yapmana gerek yok: anahtar yoksa ücretsiz yerel model kullanılır (ilk çalıştırmada bir kez
indirilir). Sistem şu sırayla dener, biri kullanılamazsa (kredi, kota, ağ) sıradakine geçer:

1. **Claude Haiku 5.5** (en kaliteli): https://console.anthropic.com → **Billing**'den 5 $ → **API Keys** → `ANTHROPIC_API_KEY`
2. **Cloudflare Workers AI** (ücretsiz günlük kota, Llama 3.3 70B; logosuz yapay zekâ görseli de üretir):
   Cloudflare token'ına (adım D) *Account – Workers AI – Read* ve *Edit* izinlerini eklemen yeterli.
3. **NVIDIA** (`NVIDIA_API_KEY`, build.nvidia.com) ve **OpenRouter** (`OPENROUTER_API_KEY`, ücretsiz modeller):
   Hibrit AI'da zaten varsa telefondan `otonom anahtar-aktar` ile tek komutta aktarılır.
4. **Evdeki PC (Jormungand)**: PC'yi Cloudflare Tunnel ile dışarı açarsan `JORMUNGAND_URL` + `JORMUNGAND_TOKEN`.
5. **Yerel Gemma 4 E2B** (her zaman var, tamamen ücretsiz).

Görseller için ayrıca anahtarsız **Pollinations** yapay zekâ görseli son yedektir (köşesinde küçük logo olur).

### B. Görseller (önerilir)
- https://www.pexels.com/api → `PEXELS_API_KEY`
- https://pixabay.com/api/docs → `PIXABAY_API_KEY`

Anahtar yoksa anahtarsız Openverse'ten CC0 fotoğraf aranır, o da olmazsa renkli yazı kartı kullanılır.

### ⚡ En kolayı: kurulum sihirbazı
Telefonda (Termux) ya da bilgisayarda bir kez: `pkg install python gh` → `python araclar/kurulum.py`
(telefonda `otonom kurulum`). Sihirbaz eksik anahtarları sırayla sorar ve her biri için doğru sayfayı açar.
Yapıştırdığın anahtarı dener, Cloudflare hesap numarasını kendisi bulur ve hepsini GitHub'a kendisi ekler.
Sonra sistemi başlatıp YouTube onay bağlantısını açar. Eklenmiş olanları atlar; yarıda kalırsa kaldığı yerden sürer.

### C. YouTube ve Google — **tek tıkla yetki** (bir kez 10 dk, sonra yalnızca "İzin ver")
Sistem anahtarları **kendisi alır**. Sen yalnızca telefonuna gelen bağlantıda **İzin ver**'e basarsın.
Google, uygulama (istemci) oluşturmayı otomatik yaptırmadığı için şu adımlar **bir kez** elle yapılır:
1. https://console.cloud.google.com → yeni proje. **OAuth consent screen**: "External" seç, uygulamayı
   **"In production"** yap (⚠️ "Testing" modunda bağlantı 7 günde kopar).
2. **Credentials > Create credentials > OAuth client ID > Web application**. **Authorized redirect URIs**
   kısmına `https://<ilk-alan-adın-tireli>.pages.dev/api/yetki` ekle (ör. `https://trustneurohub-com-tr.pages.dev/api/yetki`;
   adres yanlışsa sistem doğrusunu GitHub konusunda yazar). Çıkan değerleri Secrets'a ekle:
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`. **Credentials > API key** → `YOUTUBE_API_KEY`.
3. *(Önerilir)* Anahtarları sistem GitHub Secrets'a kendisi yazsın: GitHub > Settings > Developer settings >
   **Fine-grained token** → yalnızca bu depo, izin **Secrets: Read and write** → Secrets'a `GH_YONETICI_TOKEN`.
   Bu yoksa anahtarlar senin özel Cloudflare KV kasanda saklanır. Bu yöntem de çalışır.

**Sonrası tamamen otomatik:**
- Sistem her gün anahtarları dener. Eksik ya da bozuk olan kanal için GitHub'da **"🔑 Onay gerekiyor"** konusu açar
  ve telefonuna bildirim gelir. Yeni kanal açınca da aynı konu kendiliğinden açılır.
- Konuya **onay** yaz → 1 dakika içinde bir bağlantı gelir → Google'da **o kanalın YouTube kanalını** seç → **İzin ver**.
- Sistem anahtarı kaydeder. Doğru kanal seçildi mi diye kontrol eder; yanlışsa kaydetmez. Ardından kanalı
  kurar (açıklama, anahtar kelimeler, oynatma listeleri) ve konuyu kapatır.
- **İlk olarak** Actions > **Yetki al** > Run workflow > kanal: `google` çalıştır. Bu Google hesabı onayıyla
  gerekli Google API'leri (YouTube Data, YouTube Analytics, Site Verification, Search Console) **kendiliğinden açılır**
  ve siteler arama motorlarına kaydedilir.
- 💡 Yeni kanal için **yeni Gmail açmana gerek yok**: aynı Google hesabında birden çok YouTube kanalı açılabilir
  (youtube.com/create_channel). Onay ekranında hangi kanalı seçersen sistem ona bağlanır.
- Yedek yöntem (bilgisayarda): `python araclar/youtube_token_al.py <kanal>`.

- Kanalını telefonla doğrula (youtube.com/verify): özel küçük resim için gerekli.
- ⚠️ Google, denetimden geçmemiş API projelerinin yüklediği videoları **gizli** tutar. Bu yüzden sistem
   "gizli" yükler, sen Studio'dan yayınlarsın. Tam otomatik yayın için ücretsiz **YouTube API Audit**
   formunu doldur; onaydan sonra `config/ayarlar.yaml` > `gizlilik: "zamanla"` yap.

### D. Cloudflare (siteler, teklif formu, link takibi)
1. https://dash.cloudflare.com → ücretsiz hesap → **Add a domain** ile alan adlarını ekle, alan adı
   firmanda nameserver'ları Cloudflare'inkilerle değiştir.
2. **My Profile > API Tokens > Create Token > Custom token** izinleri: *Account – Cloudflare Pages – Edit*,
   *Account – Workers KV Storage – Edit*, *Zone – Zone – Read*, *Zone – DNS – Edit* → `CLOUDFLARE_API_TOKEN`.
3. Sağ menüdeki **Account ID** → `CLOUDFLARE_ACCOUNT_ID`.
4. Gerisi otomatik: teklif deposu kurulur, siteler yüklenir, alan adları bağlanır, DNS kaydı eklenir.
   (Eski bir park kaydı varsa Cloudflare > DNS'ten sil.) İsteğe bağlı: **Email Routing** ile
   `teklif@alanadin` → Gmail; **Web Analytics** token'ını `config/ayarlar.yaml` > `cloudflare`'e yaz.

### E. Kendi bilgilerin
`config/kanallar/<kanal>.yaml` (ör. `ana.yaml`): `kanal_id` (Studio > Ayarlar > Kanal > Gelişmiş, "UC..." ile
başlar), nişlerin `alan_adi` ve `ortaklik_linkleri` (`kisa-ad: "https://..."`).
`config/varliklar.yaml`: alan adların (turizm alan adları için örnek satırlardaki `#` işaretini kaldır).
Dosyayı GitHub'da açıp kalem simgesiyle düzenleyebilirsin. Ayar dosyasında yazım hatası yaparsan sistem satır numarasıyla
Türkçe uyarı verir; eksik bıraktığın ayarları varsayılanla tamamlar.

### F. Arama motorları (isteğe bağlı, ücretsiz)
Siteler her güncellemede **IndexNow** ile Bing/Yandex'e kendiliğinden bildirilir (anahtar gerekmez).
Google için: Google Cloud'da aynı projede **Site Verification API** ve **Search Console API**'yi etkinleştir
(APIs & Services > Library), sonra bilgisayarında `python araclar/youtube_token_al.py arama` çalıştır ve çıkan
değeri `GOOGLE_ARAMA_TOKEN` adıyla GitHub Secrets'a ekle. Sistem siteleri doğrular, Search Console'a ekler ve site haritasını gönderir.

### G. Paylaşım (isteğe bağlı, ücretsiz)
Yayına giren her video otomatik duyurulur:
- **Telegram:** @BotFather'dan bot aç → `TELEGRAM_BOT_TOKEN`; botu kanalına yönetici yap → `TELEGRAM_KANAL` (ör. `@kanaladi`).
- **Bluesky:** Ayarlar > Uygulama şifreleri → `BLUESKY_KULLANICI` (ör. `ad.bsky.social`) ve `BLUESKY_SIFRE`.

---

## 🚀 Büyüme araçları (YouTube algoritması için, kendiliğinden)
Günlük çalıştırmada, yayına giren her video için (kota elverdikçe, her adım bir kez):

| Araç | Ne yapar? |
|---|---|
| Oynatma listeleri | Her niş için liste açar, videoyu ekler (izlenme süresi ve oturum uzar) |
| Sahip yorumu | Videoya soru soran ilk yorumu yazar. **Sabitleme API'de yok:** DURUM.md hangi videolarda Studio'dan sabitleyeceğini söyler |
| Yorum yanıtlama | Günde en fazla 10 yeni yoruma kısa, saygılı yanıt; bağlantı/spam/hakaret içerenler yanıtlanmaz |
| İngilizce yerelleştirme | Uzun videolara İngilizce başlık ve açıklama ekler (yabancı aramalarda görünür) |
| Kanal SEO | Ayda bir kanal açıklamasını ve anahtar kelimelerini nişlere göre yeniler |
| İç bağlantılar | Açıklamaya "▶ Şunu da izle" (nişin en çok izlenen videosu); Shorts'a aynı konunun uzun videosu |
| Erken aksiyon | 2-4 günlük video yaşına göre çok zayıfsa başlığı değiştirir + yeni küçük resim yükler; 7 gün sonra kazanan seçilir, kaybederse eski başlık geri gelir |
| Paylaşım | Telegram / Bluesky duyurusu (anahtar varsa) |

Sahip yorumu ve yorum yanıtlama için kanal dosyasında `kanal_id` yazılı olmalı. Eski YouTube anahtarı yorum izni
içermiyorsa `python araclar/youtube_token_al.py <kanal>` ile bir kez yenile. Elle çalıştırmak için komut: `buyume`.

---

## 🔒 Güvenlik
Gizli anahtarlar yalnızca GitHub Secrets'ta durur, depoda asla yer almaz (testler bunu denetler); herkese açık depoda
kişisel veriler maskelenir, dış kaynaklardan gelen metin filtrelenir, sitelere güvenlik başlıkları eklenir.
Ayrıntılar ve açık bildirme: [SECURITY.md](SECURITY.md).

---

## 🧠 Kendi kendine öğrenme

| Katman | Ne yapar? |
|---|---|
| **Thompson örneklemesi** | Niş, başlık stili, video uzunluğu ve yayın saatini başarı dağılımlarından örnek çekerek seçer. Veri azken her şeyi dener, kazanan netleştikçe ona yoğunlaşır, keşfi bırakmaz. |
| **Zaman aşınması** | Eski videoların etkisi 45 günde yarıya iner; izleyici zevki değişirse uyum sağlar. |
| **Yaşa göre düzeltilmiş puan** | Kanalın izlenme-yaş eğrisinden sapmayı ölçer; yeni ve eski videolar adil karşılaştırılır. |
| **Trend momentumu** | Haftadan haftaya yeni çıkan veya yükselen aramaları öne alır. |
| **Çeşitlilik filtresi** | Yayınlanmışa çok benzeyen konuyu eler (artırmak = arttırmak gibi yazım farkları dahil). |
| **A/B başlık testi** | Zayıf videoda alternatif başlığı dener; 7 gün sonra kötüyse eskiye döner. |
| **Viral takip** | 10.000 izlenmeyi geçen videonun devamını öncelikli planlar. |

20 haftalık simülasyonda sistem gizli "en iyi" seçenekleri kendi buldu: en iyi nişin payı %33 → %67,
en iyi başlık stilininki %17 → %50. Öğrenilenler DURUM.md > "Laboratuvar öğrenimi"nde görünür.

### 👷 Öğrenme Mühendisi
Her pazartesi laboratuvardan sonra çalışır ve **sistemin kendisini** geliştirir:

| Görev | Örnek karar |
|---|---|
| Deney evrimi | "1400 kelime %73 olasılıkla en iyi → 1700'ü de dene" · "'nasıl' başlıkları kaybediyor → emekliye ayır, yerine 'hata uyarısı' dene" |
| Uyum hızı | Performans kaydıysa eski verinin etkisini hızlandırır, kararlıysa yavaşlatır |
| Pazar keşfi | En başarılı videoların anahtar kelimelerini yeni arama tohumu yapar |
| Kendini onarma | Metinler yarım kalıyorsa model belleğini, YouTube kotası doluyorsa Shorts sayısını ayarlar |
| Ders çıkarma | En iyi 3 / en zayıf 3 videodan en fazla 5 kural çıkarıp senaryo yazarına ekler |
| Gözcülük | Çözemediği sorunları ve yeni çıkan yerel modelleri GitHub issue yapar; Dependabot paketleri günceller |

Mühendis senin `config/` dosyalarına dokunmaz; öğrendiklerini `veri/ogrenilen_ayarlar.yaml`'a, her kararı
gerekçesiyle `veri/muhendis_gunlugu.md`'ye yazar. Dosyayı silersen fabrika ayarlarına döner; bir ayarı
korumak için `config/ayarlar.yaml > muhendis > kilitli`'ye ekle; yalnızca öneri istersen `otomatik_uygula: false`.

### 🛡️ Sınıra takılınca sistem durmaz

| Sınır / sorun | Sistem ne yapar? |
|---|---|
| Claude kredisi biter, kota veya ağ hatası | Cloudflare Workers AI'a, o da olmazsa yerel modele geçer |
| Stok fotoğraf bulunamaz | Yapay zekâ görseli üretir (Cloudflare → Pollinations); videoda sentetik içerik beyanı otomatik işaretlenir |
| Bir kanalın işi hata verir | Diğer kanallar etkilenmez (her kanal ayrı paralel iş) |
| Toplu yapay zekâ işi 26 saatte bitmez | Senaryoları anlık üretir |
| Yerel model metni kısa / yarım bırakır | Sahneleri tek tek genişletir; yarım kalırsa kısaltıp tekrar dener |
| Edge seslendirme engellenir | İnternetsiz **Piper** Türkçe sesine geçer |
| Görsel anahtarı yok veya sınır doldu | Openverse → yazı kartı |
| YouTube günlük kotası / yükleme sınırı | Kalan videoları ertesi gün kaldığı yerden yükler |
| YouTube bağlantısı bozulur | Üretime devam eder, videoları indirilebilir bırakır, uyarır |
| GitHub dakikası %85'e yaklaşır / %93'e ulaşır | Üretimi azaltır / ay sonuna kadar yalnızca hafif işler |
| Herhangi bir adım hata verir | Diğer adımlar sürer, GitHub e-posta atar, DURUM.md'de görünür |
| Aynı sorun tekrar eder | Mühendis ayarla düzeltir; düzeltemezse issue açar |

---

## 🤖 Yerel model seçimi (test sonuçları, Kasım 2026)

| Model | Bellek (çalışırken) | Hız | Sonuç |
|---|---|---|---|
| **Gemma 4 E2B** | 4,9 GB | 6,8 token/sn | **Seçildi:** akıcı Türkçe, en hızlı, ücretsiz sunucuya (7 GB) sığar |
| Gemma 4 E4B | 8,8 GB | 4,5 token/sn | En akıcı ama ücretsiz sunucuya sığmaz |
| Qwen3.5 4B | ~3 GB | 4,6 token/sn | Belirgin dil bilgisi hataları |

Küçük model uzun metni kısa keser (700 kelime istendi, 177 yazdı); sistem kısa sahneleri tek tek genişletir
(testte 69 → 233 kelime). Testlerde pomodoro süresini yanlış yazdı (doğrusu 25 dakika): senaryolara haftada bir
göz at. Site adresi ve emoji gibi seslendirmeyi bozan şeyler kodla temizlenir. Modeli değiştirmek için
`config/ayarlar.yaml > llm.yerel_*`.

## ⚡ Orijinal plana göre yapılan iyileştirmeler

| Orijinal | Yeni |
|---|---|
| Ücretli yapay zekâ | Ücretsiz yerel model; anahtar varsa Claude, kredi biterse yerel |
| Senaryo, açıklama, makale ayrı ayrı | Tek çağrıda 4 içerik |
| MoviePy | Doğrudan ffmpeg: 5-10 kat hızlı |
| Skor = İzlenme×0,5 + CTR×0,3 + Süre×0,2 | Yüzdelik sıra + yaşa göre düzeltilmiş izlenme (ölçek farkı yok) |
| Sabit 4 haftalık takvim | Her hafta güncel veriyle, Thompson örneklemesiyle plan |
| Google Sheets | Depoda CSV + Markdown raporlar |
| 3 sn boş intro | Doğrudan kanca (isteğe bağlı açılır) |
| Domain parking | Ücretsiz site + teklif formu + yanıt taslağı |
| — | Otomatik bölüm zaman damgaları, altyazı, A/B başlık testi, Öğrenme Mühendisi |

---

## 📁 Dosyalar ve komutlar

| Dosya | Görev |
|---|---|
| `config/ayarlar.yaml` | Genel ayarlar (yapay zekâ, video sayısı, ses, yayın, deneyler, mühendis) |
| `config/kanallar/<kod>.yaml` | Her kanal: nişler, konu kaynakları, dil, ses, biçim, üslup, ortaklık linkleri |
| `config/varliklar.yaml` | Alan adları ve iletişim |
| `config/elle_yuklenenler.yaml` | Elle yüklediğin videoların linkleri |
| `otonom/m01_envanter.py` … `m12_gelir.py` | Master prompttaki 12 modül |
| `otonom/optimizasyon.py`, `muhendis.py` | Öğrenme motoru ve Öğrenme Mühendisi |
| `otonom/kanal_sihirbazi.py` | Tek cümleden yeni kanal |
| `otonom/yerel_llm.py`, `butce.py`, `durum_paneli.py` | Yerel model, sınır bütçesi, DURUM.md |
| `otonom/orkestrator.py`, `mikro_site.py`, `cloudflare_kur.py` | Döngüler, siteler (VideoObject şeması), Cloudflare kurulumu |
| `otonom/buyume.py`, `arama_motoru.py` | YouTube büyüme araçları, arama motoru kaydı |
| `cloudflare/functions/` | Teklif formu ve kısa link fonksiyonları |
| `veri/` | Sistemin hafızası (bkz. [veri/BENIOKU.md](veri/BENIOKU.md)) |
| `MASTER_PROMPT.md` | Sistemin ana talimatı |

Komutlar (Actions'tan veya bilgisayarında `python -m otonom <komut>`):
`beta, haftalik, gunluk, buyume, arama, yeni_kanal, kanallar, muhendis, durum, cloudflare, envanter, nis, plan, uret, alanadi, site, analiz, teklifler, rapor, maliyet`
(kanal komutlarına `--kanal <kod>` eklenirse yalnızca o kanal çalışır)

Bilgisayarında denemek için:
```
pip install -r requirements.txt          # ayrıca ffmpeg kurulu olmalı
pip install -r requirements-yerel.txt    # ücretsiz yerel model (bir kez derlenir)
python -m otonom haftalik --deneme       # hiçbir servise bağlanmadan uçtan uca test
python -m pytest -q                      # testler
```
Gerçek çalıştırma için `.env.example` dosyasını `.env` adıyla kopyalayıp doldur.

---

## ⚠️ Gerçekçi beklentiler

- **YouTube para kazanma şartı:** 1.000 abone + son 12 ayda 4.000 saat izlenme (veya 90 günde
  10 milyon Shorts izlenmesi). Genelde aylar sürer; garantisi yoktur.
- **"Özgün olmayan içerik" politikası:** YouTube toplu üretilmiş, birbirinin tekrarı yapay zekâ videolarını
  para kazanmadan çıkarabilir. Sistem her videoya özgün bir bakış açısı zorunlu kılar; yine de ara sıra kendi
  sesinle yorum veya deneyim eklemen çok faydalıdır.
- **Alan adı satışı:** Çoğu alan adı uzun süre satılmayabilir; fiyat uydurulmaz, "teklife açık" satılır.
- **Sağlık nişi:** Teşhis/tedavi vaadi yasaktır; senaryo talimatları buna göre ayarlıdır.
- **Gizlilik (KVKK):** Depo **herkese açıksa** (şu an öyle; GitHub dakikası bu sayede sınırsız) teklif
  e-postaları, isimler ve mesajlar depoya **maskeli** yazılır (`a***@g***.com`); tam hali yalnızca özel
  Cloudflare deponda (Cloudflare > KV > TEKLIFLER) kalır. Raporlar ve metrikler yine herkese açıktır; bunu
  istemezsen deponu **Settings > General > Change visibility** ile özel yap (aylık 2.000 dakika sınırına
  sistem kendiliğinden uyar).
