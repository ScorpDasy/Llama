# 🔒 Güvenlik

## Sistemin kendi aldığı önlemler (otomatik)

| Önlem | Nerede |
|---|---|
| Gizli anahtarlar yalnızca GitHub Secrets'ta; depoda anahtar kalıbı olursa testler başarısız olur | `tests/` (her PR'da) |
| İş akışında en az yetki: varsayılan salt-okunur, yazma yalnızca gereken işlerde | `.github/workflows/otonom.yml` |
| Gizli anahtarlar yalnızca onları kullanan adımlara verilir (önbellek/kurulum adımları göremez) | aynı dosya |
| Elle girilen değerler (kanal adı, açıklama) kabuğa doğrudan yazılmaz; kanal kodu yalnızca `a-z 0-9 -` | iş akışı + `otonom/ayarlar.py` |
| Paket açığı taraması (pip-audit) her PR'da ve her çarşamba | `test.yml` |
| Kod güvenlik taraması (CodeQL: Python, JavaScript, iş akışları) | `codeql.yml` → Security sekmesi |
| Paket güncellemeleri (Dependabot) | `.github/dependabot.yml` |
| Sitelerde güvenlik başlıkları: CSP, HSTS, çerçeveleme yasağı, izin politikası | `otonom/mikro_site.py` |
| Teklif formu: bot tuzağı + zaman tuzağı + uzunluk sınırları | `cloudflare/functions/api/teklif.js` |
| Herkese açık depoda teklif e-postaları/isimleri maskelenir; tam hali yalnızca özel Cloudflare KV'de | `otonom/m12_gelir.py` |
| Dış kaynaklardan (gündem, RSS) gelen başlıklar temizlenir; komut sokma ve suç/ölüm/kumar/yetişkin konuları elenir | `otonom/m02_nis_analizi.py` |
| Her kanal yalnızca kendi YouTube anahtarıyla yükler; başka kanala yükleme imkânsız | `otonom/m09_youtube_yukleme.py` |
| Tek tıkla yetki: PKCE + tek kullanımlık bağlantı (25 dk); kod sitede saklanmaz, anahtara yalnızca GitHub sunucusu çevirebilir; yanlış/başka kanala bağlı YouTube kanalı seçilirse anahtar kaydedilmez; yalnızca depo sahibinin "onay" yorumu çalıştırır | `otonom/yetki.py`, `yetki.yml`, `functions/api/yetki.js` |
| Yapay zekâ görseli kullanılan videoda YouTube sentetik içerik beyanı otomatik | `otonom/m09_youtube_yukleme.py` |

**Bilinen ve kabul edilen risk:** `diskcache` (yerel model kütüphanesinin alt paketi, PYSEC-2026-2447) yalnızca
önbellek klasörüne yazabilen bir saldırganı etkiler. Sistem bu önbelleği kullanmaz ve GitHub sunucusu her
çalıştırmada sıfırdan kurulur. Düzeltme yayınlanınca Dependabot güncelleyecek.

## Senin yapman gerekenler (bir kez, 10 dakika)

1. **İki adımlı doğrulama** aç: GitHub, Google (YouTube), Cloudflare, Anthropic hesaplarında.
2. **GitHub > Settings > Code security**: *Secret scanning* ve *Push protection*'ı aç (herkese açık depoda ücretsiz).
3. **GitHub > Settings > Branches**: ana dal için *branch protection* (silme ve zorla gönderim yasak).
4. **Cloudflare token**'ı yalnızca README'de yazan izinlerle oluştur (Pages, KV, Zone Read, DNS, Workers AI).
5. Depo herkese açık kalacaksa raporların/metriklerin herkesçe görüleceğini kabul et; istemezsen depoyu özel yap.

## Bir anahtar sızarsa

1. Anahtarı **hemen iptal et** (Google Cloud > Credentials, Cloudflare > API Tokens, Anthropic > API Keys).
2. Yenisini oluştur ve GitHub Secrets'ta güncelle.
3. Anahtar bir dosyaya yazıldıysa dosyadan sil; git geçmişinden temizlemek için GitHub'ın rehberine bak
   ("Removing sensitive data from a repository").
