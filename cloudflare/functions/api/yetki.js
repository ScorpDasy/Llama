// Cloudflare Pages Function — tek tıkla yetki dönüş sayfası (Google onaydan sonra buraya yönlendirir).
// Yalnızca sistemin beklediği isteği kabul eder (KV'de "yetki-bekle:<state>" olmalı) ve tek kullanımlık
// kodu 15 dakikalığına KV'ye bırakır. Kod tek başına işe yaramaz: PKCE doğrulayıcısı ve istemci sırrı
// yalnızca GitHub sunucusundadır. Bu sayfa hiçbir anahtar görmez ve saklamaz.

const DURUM = /^[A-Za-z0-9_-]{32,64}$/;

export async function onRequestGet({ request, env }) {
  const u = new URL(request.url);
  const durum = u.searchParams.get("state") || "";
  const kod = u.searchParams.get("code") || "";
  const hata = u.searchParams.get("error") || "";

  if (!DURUM.test(durum)) {
    return sayfa(400, "Geçersiz bağlantı", "Bu sayfayı GitHub'daki onay bağlantısıyla açmalısın.");
  }
  if (!env.TEKLIFLER) {
    return sayfa(503, "Sistem henüz hazır değil", "Cloudflare KV bağlı değil; ana iş akışı bir kez çalışmalı.");
  }
  if (!(await env.TEKLIFLER.get("yetki-bekle:" + durum))) {
    return sayfa(410, "Bağlantının süresi dolmuş",
      "GitHub'daki konuya yeniden <b>onay</b> yaz; yeni bir bağlantı gelecek.");
  }
  if (!hata && (!kod || kod.length > 1024)) {
    return sayfa(400, "Eksik bilgi", "Google kod göndermedi. GitHub'daki konuya yeniden <b>onay</b> yaz.");
  }
  const kayit = hata ? { hata: hata.slice(0, 100) } : { kod };
  await env.TEKLIFLER.put("yetki:" + durum, JSON.stringify(kayit), { expirationTtl: 900 });
  await env.TEKLIFLER.delete("yetki-bekle:" + durum);
  return hata
    ? sayfa(200, "Onay verilmedi", "Sorun değil. İstediğin zaman GitHub'daki konuya yeniden <b>onay</b> yazabilirsin.")
    : sayfa(200, "✅ Onay alındı",
      "Bu sayfayı kapatabilirsin. Sistem birkaç dakika içinde kanalı bağlayıp GitHub'daki konuda haber verecek.");
}

function sayfa(durum, baslik, mesaj) {
  const html = `<!doctype html><html lang="tr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>${baslik}</title>
<body style="font-family:system-ui,sans-serif;max-width:560px;margin:15vh auto;padding:16px;line-height:1.5">
<h1 style="font-size:1.6rem">${baslik}</h1><p>${mesaj}</p></body></html>`;
  return new Response(html, {
    status: durum,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "referrer-policy": "no-referrer",
      "x-robots-tag": "noindex",
      "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'",
    },
  });
}
