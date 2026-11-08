import os
import tempfile

# Testler gerçek veri ve ayar klasörüne asla yazmasın: içe aktarmadan ÖNCE ayarlanmalı.
os.environ.setdefault("OTONOM_CALISMA", tempfile.mkdtemp(prefix="otonom-test-"))
if not os.environ.get("OTONOM_CONFIG"):
    import shutil
    from pathlib import Path

    _kopya = Path(os.environ["OTONOM_CALISMA"]) / "config"
    if not _kopya.exists():
        shutil.copytree(Path(__file__).resolve().parent.parent / "config", _kopya)
    os.environ["OTONOM_CONFIG"] = str(_kopya)
for anahtar in ("ANTHROPIC_API_KEY", "YOUTUBE_API_KEY", "YT_REFRESH_TOKEN", "PEXELS_API_KEY",
                "PIXABAY_API_KEY", "CLOUDFLARE_API_TOKEN", "CF_KV_NAMESPACE_ID"):
    os.environ.pop(anahtar, None)
