# DEVAM — yeni bir Claude oturumu için devir dosyası

> Yeni oturumda yalnızca şunu yaz: **"DEVAM.md dosyasını oku ve 'Sıradaki işler'i sırayla yap. Türkçe konuş."**
> Bu dosya önceki uzun oturumun özetidir; yeni oturum küçük bağlamla, az kullanım hakkı harcayarak devam eder.

## Kullanıcı ve kurallar
- Kullanıcı **yalnızca Türkçe** konuşur, İngilizce bilmez. Cevaplar kısa, sade, Türkçe.
- Her şey **en ucuz / ücretsiz** olmalı. Değişiklikler `ccr-4374ffb0-5crvc3` dalına işlenip gönderilir
  (depoda tek dal var; PR açılamıyor). Commit sonuna atıf satırları eklenir.
- Sistem **Claude'a bağlı değildir**: GitHub Actions'ta ücretsiz, kendiliğinden çalışır. Claude yalnızca geliştirme için.

## Sistem (Das-Hub-qi/das, herkese açık depo → GitHub dakikası sınırsız)
- Python paketi `otonom/` (13 modül + optimizasyon, Öğrenme Mühendisi, kanal sihirbazı, arama motorları).
- **Çok kanal:** `config/kanallar/<kod>.yaml` (nişler, konu kaynakları, dil, ses, biçim, üslup); veri `veri/kanallar/<kod>/`.
  GitHub'da her kanal ayrı paralel iş (matrix) + genel iş. Yeni kanal: Run workflow → `yeni_kanal` + açıklama.
- **Yapay zekâ zinciri:** Claude (anahtar varsa) → Cloudflare Workers AI → yerel Gemma 4 E2B (llama.cpp, ücretsiz).
- **Ses:** Edge TTS → Piper (çevrimdışı). **Görsel:** Pexels → Pixabay → Openverse → yapay zekâ (Cloudflare/Pollinations) → kart.
- **Öğrenme:** HİYERARŞİK (konuya göre) Thompson: her niş kendi başlık stili/uzunluk/saat/kaynak kazananını öğrenir, az verili niş kanal genelinden %30 ödünç alır (`optimizasyon.nis_posterior`). Yaşa göre puan, A/B başlık, viral takip, Öğrenme Mühendisi.
- **Güvenlik:** SECURITY.md. **Arama motorları:** `otonom/arama_motoru.py` (IndexNow + Google Search Console).
- **Panel:** `DURUM.md` (her çalıştırmada) ve Kontrol Merkezi: https://claude.ai/artifact/JmGazg5W8YwsfdmMX7WeLf
- Testler: `python -m pytest -q` (29 test), deneme: `python -m otonom haftalik --deneme`.

## Son gerçek deneme (5 Kasım 2026)
- Anahtarsız, yalnızca yerel modelle beta: 8,4 dk video + 2 Shorts üretildi; senaryo 290 → 859 kelime genişletildi.
- Openverse sık 500 hatası veriyor → devre kesici eklendi. Pillow 13.0.0'a yükseltildi (39 açık kapandı).

## Tamamlananlar (5 Kasım 2026, 2. oturum)
- `otonom/buyume.py`: oynatma listeleri, soru içeren sahip yorumu (sabitleme hatırlatması DURUM'da), günlük yorum yanıtlama
  (≤10, bağlantı/spam filtresi, LLM şeması {"uygun","yanit"}), İngilizce yerelleştirme, aylık kanal SEO, iç bağlantı
  (yükleme öncesi açıklamaya), erken aksiyon (2-4 gün, zayıfsa başlık + yeni küçük resim → m11 A/B dosyasına "test"),
  Telegram/Bluesky duyurusu. Yayın sonrası adımlar `veri/kanallar/<k>/buyume.json` ile takip edilir.
- Bağlantılar: `kanal_gunluk` → "Büyüme" adımı; `_uzun_uret/_shorts_uret` → iç bağlantı; yeni komut `buyume`
  (workflow seçeneklerine de eklendi); DURUM.md'de "🚀 Büyüme" bölümü (tüm kanallar).
- `mikro_site.py`: yazı sayfalarına VideoObject JSON-LD + og:image. README: F (arama motorları), G (paylaşım),
  Büyüme araçları ve Güvenlik bölümleri. `.env.example`'a yeni anahtarlar. Testler: 29.

## Tamamlananlar (5 Kasım 2026, 3. oturum)
- **Tek tıkla yetki** (`otonom/yetki.py`, `.github/workflows/yetki.yml`, `cloudflare/functions/api/yetki.js`):
  günlük anahtar denetimi → GitHub'da "🔑 Onay gerekiyor" konusu → sahip "onay" yazar → PKCE'li Google bağlantısı →
  dönüş sayfası kodu KV'ye bırakır → iş anahtara çevirir, kanalı doğrular (youtube_kanali.json), GitHub Secrets'a
  (GH_YONETICI_TOKEN) ya da KV kasasına (`kasa:` öneki; `ayarlar.gizli()` önce kasaya bakar) yazar, `buyume` ile kanalı kurar.
  `google` onayı: Search Console anahtarı + Google API'lerini açar (service.management). Yeni kanalda konu kendiliğinden açılır.
- **Montaj v2** (`m07_montaj.py`, `ses_tasarimi.py`, `gorsel.py`): ease-in-out kamera hareketleri, xfade geçişleri
  (≤10 sahnelik gruplar, bölüm başında karartma), yakılmış altyazı, bölüm bandı, logo filigranı (`config/marka/logo.png`),
  ilerleme çubuğu, abone rozeti, logolu kapanış; üretken fon müziği + whoosh + sidechain + -14 LUFS; tonlama (m05).
  Hız: 1080p'de 8 dk video ≈ 6 dk (4 çekirdek).
- **Telefon** (`araclar/telefon/otonom`, `kur.sh`): durum, video, yeni-kanal, onay (Google sayfasını açar), bildirim,
  zamanla, anahtar-aktar (Hibrit AI `~/hibrit/anahtarlar.sh` → GitHub Secrets, gh ile).
- **Yapay zekâ zinciri**: Claude → Cloudflare → NVIDIA → OpenRouter → PC (Jormungand, JORMUNGAND_URL/TOKEN) → yerel.
- Kullanıcının Hibrit AI dosyaları (Termux ajanı, PC daemonu, Jormungand) depoya EKLENMEDİ; yalnızca bağlantı noktaları yazıldı.
  Kişisel belgeler (risk raporu) ve içinde token olan betikler asla depoya konmaz (depo herkese açık).
- **Shorts v3** (kullanıcı "videolar zayıf" dedi): kısa parçalı senaryo (m04 şeması `kanca_yazi`, `parcalar`),
  parça başına seslendirme, her cümleye görsel/Pexels stok video (`m06.video_bul`), 1,5-3 sn kesme, BÜYÜK HARF
  zıplayan altyazı (Montserrat Black, indirilir), üst başlık kutusu, vuruşlu müzik (`ses_tasarimi.ritim_muzigi`).
  Örnek: "Beynin gece temizliği" (23 sn) kullanıcıya gönderildi. Kendi puanım 7,5/10; 10 için Pexels anahtarı (gerçek video)
  ve gerekirse daha doğal ses gerekli.
- **Montaj v3** (kullanıcı: "daha gelişmiş, izleyici odaklı, dışa bağımlı olmasın"): `derinlik.py` (2.5D paralaks,
  yerel Depth-Anything-V2-Small ONNX + OpenCV, yarım çözünürlük harita; sanal kamera kesmeleri), `grafik.py`
  (sayı bulucu + canlı yüzde/sayaç/yıl grafikleri), `m07.sahne_klibi` ve Shorts'a bağlandı (hata olursa zoompan'e döner).
  YouTube resmî kaynaklarından kurallar m04 SISTEM'e (paketleme, ilk 2 cümle, merak döngüsü); `m03.baslangic_odagi`
  (ilk 12 uzun videoda tek niş); anahtarsız görsel sırası yapay zekâ önce; Shorts sonu "TAMAMI KANALDA".
- **Hazırlık aşaması** (`hazirlik.py`, `secici.py`): kuyruktaki içerik için senaryo denetimi (Shorts kuralları,
  yerel LLM düzeltme), önbellekli seslendirme (m05 yan .json), yuva başına 3 görsel adayı → yerel CLIP
  (Xenova/clip-vit-base-patch32 ONNX) + netlik puanı → en iyisi hedef yola + `.hazir.json` (m06.gorsel_bul önce
  buna bakar). Süre sınırlı, kaldığı yerden devam; `uretime_hazir` (hazır ya da 36 saat). Yeni komut/cron `hazirlik`
  (günde 3 kez). Test: 2 tur (150 sn'de kesildi, 2. turda bitti), ortalama seçilen puan 74.
- **LLM varsayılanı "ucretsiz"**: yerel → Cloudflare → NVIDIA → OpenRouter → PC; Claude yalnızca açıkça seçilirse.
- **Kalite Denetçisi + onarım + birbirine öğretme** (`denetci.py`): ffmpeg tek geçiş ölçüm (LUFS, tepe, sessizlik,
  siyah, donuk, süre) + hazırlık görsel puanı → karne (`kalite.csv`). `denetle_ve_onar` orkestratörde uzun/Shorts
  üretimini sarar; onarım yolu Thompson ile seçilir, deneyim `onarim.json` (kanal klasörü, tüm kanallardan okunur);
  ertelenen onarımlar `hazirlik.yeniden_hazirla` (ek aday / katı metin) + `Ertele`. Kanallar arası deney ödüncü
  (`optimizasyon.kanallar_arasi`, %15). Yeni deneyler gorsel_stili, muzik. `muhendis.kalite_dersleri`.
  Gerçek örnek videolar 100/100 geçti.
- Testler: 42.

## Durum (5 Kasım 2026, kapanış)
- Uçtan uca gerçek test (gerçek ses + hazırlık + 2.5D + geçişler + grafikler + denetim): 35 sn uzun video,
  hazırlık 83 sn, montaj 45 sn, karne 100/100. Kapanış kartında logo/başlık çakışması düzeltildi.
- pip-audit temiz (yeni paketler: opencv-python-headless, tokenizers, numpy, pynacl). 42 test.
- Kontrol Merkezi güncellendi (sürüm 3): https://claude.ai/artifact/JmGazg5W8YwsfdmMX7WeLf

## Sıradaki işler
1. GitHub'daki ilk gerçek çalıştırmadan sonra (Actions > Otonom sistem > beta) günlüğe bak: yerel model, derinlik ve
   CLIP modeli indirmeleri, hazırlık süresi, Kalite Denetçisi karnesi. DURUM.md "🩺 Kalite Denetçisi" ve "🔑 Yetkiler".
2. Kullanıcının bir kez yapması gerekenler (README "Tek tıkla yetki"): Google'da Web istemcisi + yönlendirme adresi,
   Cloudflare anahtarı; isteğe bağlı GH_YONETICI_TOKEN, PEXELS_API_KEY.
3. Fikirler: YouTube kanal filigranı/banner'ı logodan (watermarks.set, channelBanners); en iyi yorumlardan yeni konu;
   uzun videoda açılışta "sonraki sahnelerden hızlı önizleme" (cold open); Kaggle GPU ile yerel görsel üretimi.

## Kullanım hakkını korumak için
- Her yeni büyük işe **yeni oturumla** başla (bu dosyayı okut). Uzun oturum bağlamı her mesajda yeniden işlenir ve hakkı hızla tüketir.
- Gerekmedikçe uzun test/derleme çıktısı isteme; "kısa özetle" de.
