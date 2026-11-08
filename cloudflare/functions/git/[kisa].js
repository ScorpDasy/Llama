// Cloudflare Pages Function — ortaklık (affiliate) kısa linkleri: /git/<kisa_ad>
// Faydası: link değişince YouTube açıklamalarını tek tek düzenlemek gerekmez;
// config/varliklar.yaml güncellenir, site yeniden yüklenir, tüm eski videolar düzelir.
// Tıklamalar KV'de günlük sayılır (ücretsiz kota aşılırsa sayım atlanır, yönlendirme çalışır).

const LINKLER = __LINKLER__;

export async function onRequestGet({ params, env, waitUntil }) {
  const kisa = String(params.kisa || "").toLowerCase();
  const hedef = LINKLER[kisa];
  if (!hedef) return Response.redirect(new URL("/", "https://" + "__ALAN_ADI__").toString(), 302);

  if (env.TEKLIFLER) {
    const gun = new Date().toISOString().slice(0, 10);
    const anahtar = `tik:${gun}:${kisa}`;
    waitUntil(
      env.TEKLIFLER.get(anahtar)
        .then((v) => env.TEKLIFLER.put(anahtar, String(Number(v || 0) + 1)))
        .catch(() => {})
    );
  }
  return Response.redirect(hedef, 302);
}
