# 📊 Sistem Durumu

_Son çalıştırma: 2026-11-09 15:49 · komut: `gunluk` · ✅ Sorunsuz_

## ⚡ Hızlı erişim

- 🧭 **Kontrol Merkezi** (tüm sistem tek sayfada): [aç](https://claude.ai/artifact/JmGazg5W8YwsfdmMX7WeLf)
- ▶️ **Çalıştır** (beta / haftalık / günlük): [Actions > Otonom sistem > Run workflow](https://github.com/ScorpDasy/Llama/actions/workflows/otonom.yml)
- 📥 **Bu çalıştırmanın videoları ve günlüğü**: [aç](https://github.com/ScorpDasy/Llama/actions/runs/42619627357) (en altta Artifacts)
- 🔑 **Anahtarlar**: [Settings > Secrets](https://github.com/ScorpDasy/Llama/settings/secrets/actions)
- ➕ **Yeni kanal aç**: [Run workflow](https://github.com/ScorpDasy/Llama/actions/workflows/otonom.yml) → komut `yeni_kanal` + açıklama · kanal dosyaları: [config/kanallar](config/kanallar)
- 🛠️ **Mühendisin açtığı iş kayıtları**: [Issues](https://github.com/ScorpDasy/Llama/issues)
- ⚙️ **Ayarlar**: [ayarlar.yaml](config/ayarlar.yaml) · [varliklar.yaml](config/varliklar.yaml) (dosyayı açıp kalem simgesine dokunun)
- 📈 **Raporlar**: [veri/raporlar](veri/raporlar) · 👷 [Mühendis günlüğü](veri/muhendis_gunlugu.md) · 🗓️ [İçerik takvimi](veri/icerik_takvimi.md)
- 💰 **Teklifler**: [yanıt taslakları](veri/teklif_taslaklari) · 🏷️ [satış metinleri](veri/alan_adlari)
- 🌐 **Siteler**: [trustneurohub.com.tr](https://trustneurohub.com.tr) · [okyanusbilisimtr.com](https://okyanusbilisimtr.com)
- 🎬 **YouTube Studio**: [studio.youtube.com](https://studio.youtube.com)
- ☁️ **Cloudflare**: [dash.cloudflare.com](https://dash.cloudflare.com) · 📖 [Kurulum rehberi](README.md)

## Kurulum kontrol listesi
6 madde tamamlanabilir — sistem bunlar olmadan da çalışır.

| | Parça | Durum | Ne yapmalı? |
|---|---|---|---|
| ✅ | Yapay zekâ | Ücretsiz yerel model (gemma-4-E2B-it) | İsteğe bağlı: daha kaliteli metin için `ANTHROPIC_API_KEY` (README adım 1) |
| ✅ | Seslendirme | Edge TTS (yedek: çevrimdışı Piper) | — |
| ⚠️ | Görseller | Yalnızca anahtarsız Openverse + yazı kartı | Ücretsiz `PEXELS_API_KEY` ekleyin: görsel kalitesi artar (README adım 2) |
| ❌ | YouTube uygulaması (tüm kanallar için ortak) | Yok — videolar Actions > Artifacts'tan indirilebilir | `YT_CLIENT_ID`, `YT_CLIENT_SECRET` (README adım C); her kanalın anahtarı aşağıdaki tabloda |
| ⚠️ | YouTube istatistik / rekabet | Kapalı (niş analizi yalnızca arama önerileriyle) | `YOUTUBE_API_KEY` (README adım C.2) |
| ❌ | Siteler + teklif formu (Cloudflare) | Kurulmadı | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` (README adım D) |
| ⚠️ | Depo görünürlüğü | Herkese açık: GitHub dakikası sınırsız; teklif e-postaları depoya maskeli yazılır (tam hali Cloudflare KV'de) | İstersen Settings > General > Change visibility ile özel yap (dakika sınırı 2.000 olur) |
| ⚠️ | Arka plan müziği | 0 parça | YouTube Ses Kitaplığı'ndan mp3 → `config/muzik/` |

## Ücretsiz sınırlar
- GitHub dakikası (bu ay): **135** / sınırsız · mod: **normal**
- YouTube API kotası (bugün, tüm kanallar): **0** / 10000
- Yapay zekâ harcaması (toplam): **0.000 $**
- Sınır dolarsa sistem durmaz: üretimi azaltır, yüklemeyi ertesi güne bırakır veya yedek servise geçer.

## Kanallar
Yeni kanal: Actions > Run workflow > komut `yeni_kanal`, açıklama kutusuna kanalı bir cümleyle anlat.

| Kanal | Biçim · dil | YouTube | Bekleyen · yüklendi · elle | Son video |
|---|---|---|---|---|
| **Beyin, Bilişim ve Seyahat** (`ana`) | uzun_ve_shorts · tr | ❌ `YT_REFRESH_TOKEN_ANA` | 0 · 0 · 0 | — |

Kanal ayarlarında tamamlanabilecekler:
- `ana`: kanal_id boş (abone linki için) · 'Turizm ve Seyahat' nişinin alan adı yok · ortaklık linki yok (ek gelir) → [config/kanallar/ana.yaml](config/kanallar/ana.yaml)

## Gelir (bu ay)
- Alan adı teklifleri: **0**
- Ortaklık link tıklamaları: **0**
- Ayrıntılı raporlar: `veri/raporlar/`

## Laboratuvar ve Öğrenme Mühendisi
Her seçeneğin 'en iyi' olma olasılığı (Thompson örneklemesi); veri arttıkça netleşir. Kanalın öğrendiklerini sıfırlamak için `veri/kanallar/<kanal>/ogrenilen_ayarlar.yaml` dosyasını sil.
- **Beyin, Bilişim ve Seyahat**
  - Henüz yeterli veri yok (videolar yayınlanıp 7 gün geçince öğrenme başlar).

## 🚀 Büyüme
- Paylaşım: **kapalı (isteğe bağlı: TELEGRAM_BOT_TOKEN + TELEGRAM_KANAL, BLUESKY_KULLANICI + BLUESKY_SIFRE)**
- **ana** · oynatma listesi: 0 · bugün yanıtlanan yorum: 0/10 · kanal SEO: henüz yok
  - ⚠️ `config/kanallar/ana.yaml` içine `kanal_id` yazılmadı: sahip yorumu ve yorum yanıtlama kapalı.

## Otomatik takvim (Türkiye saati)
- Pazartesi 09:17 — her kanal kendi işinde paralel: öğrenme, plan, senaryo, video ve Shorts
- Her gün 07:07 — kalan yüklemeler, viral kontrol; ardından teklifler ve siteler
- Elle çalıştırmak için: GitHub > Actions > Otonom sistem > Run workflow
