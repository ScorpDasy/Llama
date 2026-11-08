# veri/ — sistemin hafızası

GitHub Actions her çalıştırmada bu klasörü günceller ve depoya kaydeder. Elle düzenlemen gerekmez.

Her kanalın kendi klasörü vardır: `veri/kanallar/<kanal>/`. Aşağıdaki "Üretim", "Laboratuvar" ve
"Öğrenme Mühendisi" dosyaları kanal klasörünün içindedir; "Gelir" dosyaları ve DURUM.md tüm kanallar için
ortaktır. Kota, uyarı, maliyet ve süre kayıtları kanal işlerinde kanal klasörüne, genel işte `veri/`'ye yazılır
(paralel çalışan kanallar birbirinin dosyasına dokunmaz).

| Dosya / klasör | İçerik |
|---|---|
| **Üretim** | |
| `envanter.md` / `.json` | Alan adı ve kanal durum tablosu (Modül 1) |
| `nis_analizi.json`, `oneri_gecmisi.json` | Fırsat puanlı konu adayları ve trend karşılaştırması için geçen haftanın aramaları (Modül 2) |
| `plan/`, `icerik_takvimi.md` | Haftalık planlar ve her videonun deneyi (Modül 3) |
| `videolar/<kod>/icerik.json` | Senaryo, Shorts metinleri, makale, başlıklar (Modül 4) |
| `durum.json` | Bekleyen toplu iş ve üretim/yükleme kuyruğu |
| `yayinlananlar.csv` | YouTube'a yüklenen her video (elle yüklenenler dahil) |
| `kota.json` | Günlük YouTube API kota kullanımı |
| **Laboratuvar ve öğrenme** | |
| `metrikler.csv` | Haftalık performans anlık görüntüsü (Modül 11) |
| `optimizasyon.json` | Thompson gözlemleri ve her seçeneğin "en iyi" olma olasılığı |
| `ab_testleri.csv` | Başlık A/B testleri ve sonuçları |
| `oncelikli_konular.json`, `viral_takip.json` | Viral videoların planlanacak devamları |
| `raporlar/` | Laboratuvar ve aylık gelir raporları |
| **Öğrenme Mühendisi** | |
| `ogrenilen_ayarlar.yaml` | Mühendisin öğrendiği ayarlar (config'in üzerine uygulanır; silersen sıfırlanır) |
| `ogrenilen_dersler.json` | Senaryo yazarına verilen veriye dayalı kurallar |
| `muhendis_gunlugu.md`, `muhendis_son.json` | Her kararın gerekçesi (en yeni üstte) |
| **Gelir** | |
| `alan_adlari/<alan>/` | Pitch, TR/EN ilan, e-posta ve teklif yanıt şablonları (Modül 10) |
| `teklifler.csv`, `teklif_taslaklari/` | Gelen alan adı teklifleri ve yanıt taslakları |
| `tiklamalar.csv` | Ortaklık kısa linklerinin günlük tıklamaları |
| **İşletme** | |
| `uyarilar.json` | Yedeğe geçişler ve sınır uyarıları (DURUM.md'de gösterilir) |
| `calismalar.csv` | Her çalıştırmanın süresi (GitHub dakika bütçesi) |
| `maliyet.csv` | Her yapay zekâ çağrısının token ve dolar maliyeti (yerel model: 0 $) |
| `site_ozetleri.json` | Son yüklenen sitelerin özeti (değişmeyen site tekrar yüklenmez) |
