// Cloudflare Pages Function — "Bu alan adı satılık/kiralık" teklif formu.
// Ücretsiz: Workers free planı (günde 100.000 istek) + KV (günde 1.000 yazma).
// Teklifler KV'de saklanır; GitHub Actions günlük işi bunları okur, yanıt taslağı hazırlar.

const EPOSTA = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function onRequestPost({ request, env }) {
  let veri;
  try {
    const tur = request.headers.get("content-type") || "";
    veri = tur.includes("application/json")
      ? await request.json()
      : Object.fromEntries(await request.formData());
  } catch {
    return yanit(request, 400, "Form okunamadı.");
  }

  // Bot tuzakları: gerçek kullanıcı gizli alanı boş bırakır ve formu sayfa açıldıktan en az 3 sn sonra gönderir.
  if (veri.web_sitesi) return yanit(request, 200, "Teşekkürler.");
  const gecen = Date.now() - Number(veri.t || 0);
  if (!veri.t || gecen < 3000 || gecen > 86400000) return yanit(request, 200, "Teşekkürler.");

  const eposta = String(veri.eposta || "").trim().slice(0, 200);
  const teklif = Number(String(veri.teklif || "").replace(/[^\d]/g, ""));
  if (!EPOSTA.test(eposta) || !teklif) {
    return yanit(request, 400, "Lütfen geçerli bir e-posta ve teklif tutarı girin.");
  }
  if (!env.TEKLIFLER) {
    return yanit(request, 503, "Form geçici olarak kapalı. Lütfen e-posta ile ulaşın.");
  }

  const kayit = {
    alan_adi: new URL(request.url).hostname,
    ad: String(veri.ad || "").trim().slice(0, 100),
    eposta,
    teklif,
    tur: veri.tur === "kiralama" ? "kiralama" : "satis",
    mesaj: String(veri.mesaj || "").trim().slice(0, 1000),
    ulke: request.cf?.country || "",
    tarih: new Date().toISOString(),
  };
  const anahtar = `teklif:${Date.now()}:${crypto.randomUUID().slice(0, 8)}`;
  await env.TEKLIFLER.put(anahtar, JSON.stringify(kayit));
  return yanit(request, 200, "Teklifiniz alındı. En kısa sürede dönüş yapacağız.");
}

function yanit(request, durum, mesaj) {
  if ((request.headers.get("accept") || "").includes("application/json")) {
    return Response.json({ mesaj }, { status: durum });
  }
  const sayfa = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Teklif</title><body style="font-family:system-ui;max-width:560px;margin:15vh auto;padding:16px">
<h1>${durum === 200 ? "Teşekkürler" : "Bir sorun oluştu"}</h1><p>${mesaj}</p><p><a href="/">Ana sayfaya dön</a></p>`;
  return new Response(sayfa, { status: durum, headers: { "content-type": "text/html; charset=utf-8" } });
}
