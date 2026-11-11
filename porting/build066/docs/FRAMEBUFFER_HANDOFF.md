# Framebuffer-Handoff: erstes Bild ohne den proprietären VD-Treiber

**Problem (Build 065):** Der Nike-L-Display-Controller ist proprietär; es gibt
keinen offenen Modeset-Treiber. **Lösungsidee fürs erste Bild:** nicht den
Controller programmieren, sondern einen **vom Bootloader bereits initialisierten
Framebuffer übernehmen**.

## Upstream `simpledrm` statt eigenem Treiber

Linux 6.6 hat `CONFIG_DRM_SIMPLEDRM`: ein generischer DRM/KMS-Treiber, der einen
**bestehenden** Framebuffer übernimmt (kein Modeset, kein Panel-Init). Quelle des
Framebuffers:
- DT-Node `simple-framebuffer` (`compatible = "simple-framebuffer"` mit
  `reg`/`width`/`height`/`stride`/`format`), oder
- `sysfb`/`SYSFB_SIMPLEFB` (Hand-off über `screen_info`).

→ **Für das erste Bild ist KEIN eigener Display-Treiber nötig** — vorausgesetzt,
der Bootloader lässt das Panel an und einen gültigen Framebuffer stehen (beim
Stock-Boot sehr wahrscheinlich, da ein Boot-Logo erscheint).

## Vorgehen

1. Am laufenden Stock-System die **echten Framebuffer-Parameter** ermitteln:
   Basis-Adresse, Breite/Höhe, Stride, Pixelformat (`/proc/iomem`, VD-FB-Info,
   oder Bootloader-Hand-off). Platzhalter in `dts/sdp-nikel-simplefb-handoff.dts`.
2. `simple-framebuffer`-Node mit diesen Werten füllen, `status="okay"`.
3. `CONFIG_DRM_SIMPLEDRM=y` (Fragment `configs/nikel-simpledrm.config`).
4. Android: `drm_hwcomposer` + `gbm_gralloc` können auf simpledrm aufsetzen
   (eingeschränkt, kein Hardware-Overlay/Scaling — reicht für UI/Boot).

## Grenzen

- **Statisch:** feste Auflösung/Format, kein Moduswechsel, keine Hardware-Planes,
  kein VSync vom Controller. Reicht für UI/Boot, nicht für Video-Overlay.
- Hängt davon ab, dass der Bootloader den Framebuffer hinterlässt — **am Gerät zu
  verifizieren**.
- Das Build-063-`sdp-drm`-Skelett bleibt für den späteren **vollen** KMS-Treiber
  (Reverse Engineering des VD-IP) die Hülle. simpledrm ist der schnelle Zwischen-
  schritt zum ersten Bild.
