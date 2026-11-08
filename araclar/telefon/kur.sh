#!/data/data/com.termux/files/usr/bin/bash
# Telefona (Termux) "otonom" komutunu kurar. Hibrit AI kuruluysa onunla yan yana çalışır.
#   bash kur.sh
set -e
pkg install -y curl python termux-api >/dev/null 2>&1 || true
KAYNAK="$(dirname "$0")/otonom"
if [ ! -f "$KAYNAK" ]; then  # tek dosya olarak indirildiyse betiği depodan al
  DEPO="${DEPO:-Das-Hub-qi/das}"
  DAL="${DAL:-$(curl -fsS "https://api.github.com/repos/$DEPO" | python -c 'import json,sys; print(json.load(sys.stdin)["default_branch"])')}"
  curl -fsSL "https://raw.githubusercontent.com/$DEPO/$DAL/araclar/telefon/otonom" -o "$TMPDIR/otonom"
  KAYNAK="$TMPDIR/otonom"
fi
install -m 755 "$KAYNAK" "$PREFIX/bin/otonom"
echo "✅ 'otonom' komutu kuruldu."
otonom kur
otonom zamanla || true
[ -f "${HIBRIT_DIZIN:-$HOME/hibrit}/anahtarlar.sh" ] && { echo "Hibrit AI bulundu: anahtarları buluta aktarayım mı? (e/h)"; read -r c; [ "$c" = e ] && otonom anahtar-aktar; }
otonom yardim
