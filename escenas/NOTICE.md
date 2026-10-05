# Recursos de terceros en `escenas/`

| Recurso | Archivos | Licencia | Origen |
|---|---|---|---|
| Space Grotesk (Florian Karsten) | `fonts/space-grotesk-latin-700-normal.woff2` | SIL Open Font License 1.1 — [`fonts/OFL-SpaceGrotesk.txt`](fonts/OFL-SpaceGrotesk.txt) | https://github.com/floriankarsten/space-grotesk (archivo de [Fontsource](https://fontsource.org/fonts/space-grotesk)) |
| Plus Jakarta Sans (Tokotype) | `fonts/plus-jakarta-sans-latin-600-normal.woff2`, `fonts/plus-jakarta-sans-latin-700-normal.woff2` | SIL Open Font License 1.1 — [`fonts/OFL-PlusJakartaSans.txt`](fonts/OFL-PlusJakartaSans.txt) | https://github.com/tokotype/PlusJakartaSans (archivo de [Fontsource](https://fontsource.org/fonts/plus-jakarta-sans)) |
| GSAP 3.14.2 (GreenSock) | `vendor/gsap.min.js` | GSAP Standard "no charge" License — [`vendor/GSAP-LICENSE.txt`](vendor/GSAP-LICENSE.txt), https://gsap.com/standard-license | https://www.npmjs.com/package/gsap (vía https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js) |

Las fuentes y GSAP se redistribuyen sin modificar. Las imágenes de `productos/` son fotos de producto de la propia
tienda (sitio de DropAudio CCS). Los textos de licencia no hace falta copiarlos a la carpeta temporal de render; viajan
con la app porque `escenas/` completo entra en `datas` del instalador.
