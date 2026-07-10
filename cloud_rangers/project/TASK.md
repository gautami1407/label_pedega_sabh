# Barcode Scanning Debug Task

## Issues Identified:

1. **Wrong CDN Path for ZXing** (`scanner.html` line 427):
   - Current: `@zxing/library@0.20.0/umd/index.min.js`
   - Correct: `@zxing/library@0.20.0/dist/umd/index.min.js`
   - ROOT CAUSE: Script fails to load → ZXing undefined → scanner silently fails

2. **No Debug Logs** anywhere in the barcode pipeline

3. **ZXing API compatibility** issues with decodeFromVideoElement

4. **Product-eval-engine.js** sends POST with body but backend doesn't parse it

5. **No fallback** if ZXing fails to load

## Fix Strategy:
- Replace ZXing with html5-qrcode (more reliable, simpler API)
- Add comprehensive debug logging
- Fix backend endpoint
- Test end-to-end