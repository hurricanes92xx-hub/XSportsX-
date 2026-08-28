from pathlib import Path

# The emulator regression suite uses UiAutomator text matching. Keep the
# visible product state explicit rather than relying on merged/visual labels.
mobile = Path("app/src/main/java/com/xsportsx/app/FuturisticSports.kt")
if mobile.is_file():
    s = mobile.read_text(encoding="utf-8")
    s = s.replace('MobileSectionLabel("LIVE CENTER", if (sourceConfigured) "SOURCE READY" else "CONNECT SOURCE")',
                  'MobileSectionLabel("LIVE NOW", if (sourceConfigured) "SOURCE READY" else "CONNECT SOURCE")', 1)
    mobile.write_text(s, encoding="utf-8")

main = Path("app/src/main/java/com/xsportsx/app/MainActivityFuture.kt")
if main.is_file():
    s = main.read_text(encoding="utf-8")
    s = s.replace('Text(if (connected) "⌁  CONNECT TV" else "⌁  ADD SOURCE", fontSize = 10.sp, fontWeight = FontWeight.Black)',
                  'Text(if (connected) "SOURCE SAVED • CONNECT TV" else "⌁  ADD SOURCE", fontSize = 10.sp, fontWeight = FontWeight.Black)', 1)
    main.write_text(s, encoding="utf-8")

print("Deterministic regression labels applied")
