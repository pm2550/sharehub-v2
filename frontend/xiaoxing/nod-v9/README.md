# v9 — remove overlapping nod silhouettes

The v8 face-only feathered overlay left the original crown, flower and ribbon visible behind the generated pose. The earlier visual review missed this defect.

This fix reuses the existing generated cels. No new drawing/video generation job was submitted. The replacement matte now covers both complete head silhouettes and all hair accessories. During asset preparation the original pixels are removed before the new pose is composited; the feathered boundary lies on the lower hair/neck. The packed cells include the protected original pixels outside that matte.

At runtime the full 400×320 tile is cleared before drawing its replacement, including transparent background. Simply drawing source-over is incorrect: transparent areas would retain the original head. The avatar-nod-active class also hides the poster and old WebGL canvas throughout playback, including standalone previews. Ending or disposing the nod removes that class.

Runtime atlas: static/images/xiaoxing-nod-atlas-v9.webp, 1200×640, 213044 bytes (about 208 KiB). It remains one on-demand image with the same decoded dimensions as v8. The six original generated poses, timeline and pause behavior are retained.

Source poses and generation prompts: ../nod-v8/nod-atlas-generated.png and ../nod-v8/prompts.json. This release changes compositing only. build-assets.cjs records matte construction and premultiplied-alpha composition; nod-complete-tiles.png is the lossless composed master.

Checks: all six decoded atlas cells must have matching output alpha in the full crown/accessory area; pixels that became transparent may not contain the original head. The deepest pose clears 1120 previously opaque old-head pixels in the checked area, with zero residual pixels. Browser playback also asserts exactly one visible character layer and successful restoration after the nod. Comparison and full playback evidence are in the v9 working directory (not published).
