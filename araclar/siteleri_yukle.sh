#!/usr/bin/env bash
# Üretilen statik siteleri Cloudflare Pages'e yükler (ücretsiz: sınırsız trafik + SSL).
# Gerekli ortam değişkenleri: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
set -euo pipefail
[ -f site/projeler.txt ] || { echo "Site yok, atlanıyor."; exit 0; }
WRANGLER="npx --yes wrangler@4.157.0"
while read -r proje; do
  [ -n "$proje" ] || continue
  echo "▶ $proje"
  (
    cd "site/$proje"
    # İlk seferde proje oluşturulur; varsa hata yok sayılır.
    $WRANGLER pages project create "$proje" --production-branch main >/dev/null 2>&1 || true
    $WRANGLER pages deploy public --project-name "$proje" --branch main --commit-dirty=true
  )
done < site/projeler.txt
# Hepsi başarıyla yüklendiyse özetleri kaydet (değişmeyen siteler bir dahaki sefere atlanır)
cp site/ozetler.json veri/site_ozetleri.json
