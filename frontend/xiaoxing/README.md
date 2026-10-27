> **v9 current: nod overlap fixed.** Complete head tiles replace the original silhouette, including transparent pixels; the old poster and rig are hidden during playback. See [root cause and checks](nod-v9/README.md). The v8 visual review missed the overlapping crown/accessories.

> **Historical v8: drawn-frame nod.** The nod is restored using six generated head cels plus the original pose, played forward and back once. The original body and moon remain fixed. See [v8 artwork, prompts and workflow](nod-v8/README.md). This supersedes the video/3D exploration; the v5 dance remains withdrawn.

> **Historical v7 status: nod withdrawn.** The `nod` mesh motion, its public control, and its AI prompt-seed event have been removed following the user visual review. Historical six-action checks below no longer describe the active control set. Five other gestures remain. No new 3D model has been made in this change.

> **Historical v5 status (2026-09-26): dance withdrawn after user visual review.** The hand-authored full-body deformation was not visually acceptable. Public entrypoints are restored to the prior seated illustration. Historical functional tests below are not evidence of animation quality. A real rendered-video pipeline is being evaluated.

# Original-art Xiaoxing animation

The visible character stays the original silver-lavender-haired girl on the sakura moon. The previous unrelated VRM example is no longer referenced by the public loader.

This is a small custom **2D layered mesh rig**, not a full 3D model and not a Cubism/Live2D `.moc3` asset. It retains the original illustration and has four layers: body, sleeve, waving hand and star. A shoulder/elbow/wrist chain articulates the waving arm; the head, hair and star-holding arm have local mesh weights. Eyelids use a separately generated expression patch.

Six actions: a 4.2-second enthusiastic wave (wrist up to 33°, elbow 19°, shoulder 11°), wink, two-beat nod with up to 18 source pixels of vertical movement, closed-eye smile, a 7.4° head tilt followed by a look back, and a star toss with a full turn and a soft catch. The star travels 140 source pixels vertically. These are texture-preserving 2D movements; they do not reconstruct unseen body views. Hair follows the head with damped movement. The moon and the rest of the picture stay still.

Clicks on the waving hand, face, star or body select actions. All actions also have labeled keyboard-accessible buttons. A short greeting starts as soon as the enabled character is ready; brief idle gestures are spaced 20 seconds apart. Repeated clicks blend from the current pose instead of jumping to the starting frame.

## Files and build

Runtime source (no build dependency): `static/js/xiaoxing-2d.js`.
Loader: `static/js/avatar-loader.js`.
Body texture: existing `static/images/sharehub-muse-800.webp` (160,992 bytes).
Additional runtime images: closed-eye patch (4,946 bytes), arm backplate (29,516 bytes), empty-hand backplate (5,132 bytes), star sprite (7,886 bytes). The older hand-only backplate remains on disk for rollback but is no longer requested. The three new WebP files total 42,534 bytes.
The runtime is about 15 KB before HTTP compression and issues four WebGL draws, 6,866 triangles. It caps actions at 30 fps, idle at 24 fps, and lowers to 18 fps on slow rendering. Pixel ratio is capped at 1.75 desktop / 1.5 mobile for detail. Hidden, offscreen, minimized and motion-disabled states stop the frame loop. Collapsed mobile companions do not load the rig. WebGL failure keeps the original illustration.

Generated source PNGs are in `artwork/`. The built-in imagegen prompts and reference roles are in [prompts.json](frontend/xiaoxing/prompts.json); no CLI/API fallback was used. They are production inputs, not images shown as replacement bodies. The blink image contributes only eye-region pixels. New backplates fill the space behind the entire waving arm and the empty palm. The face, body, moon and separated waving arm remain original artwork. The new generation prompts are in [motion-prompts.json](frontend/xiaoxing/motion-prompts.json).

Texture preparation (ImageMagick):

```sh
convert artwork/closed-eyes.png -resize 800x1200 -crop 152x100+383+125 +repage -quality 95 ../../static/images/xiaoxing-blink.webp
convert artwork/arm-and-star-backplate.png -resize 800x1200 -crop 225x340+250+185 +repage -quality 94 ../../static/images/xiaoxing-arm-back.webp
convert artwork/arm-and-star-backplate.png -resize 800x1200 -crop 140x150+660+255 +repage -quality 94 ../../static/images/xiaoxing-star-back.webp
convert artwork/star-sprite.png -trim +repage -resize 192x192 -bordercolor none -border 3 -quality 94 ../../static/images/xiaoxing-star.webp
```

The hand silhouette and local bone weights are in the runtime source. Blink and backplate UV coordinates must be updated together with any crop change. The original illustration must not be replaced by a stylistically different fallback character.

## Video covers in the same release

All 13 pre-existing videos lacked `thumbnail_path`. Static WebP covers were extracted from their local preview clips (336,906 bytes total), without downloading originals or altering video files. The conditional database changes and previous fields are recorded under the working directory backup. Future uploads call `generate_video_thumbnail` separately from the hover-preview encoder, and return that path for persistence. Gallery playback remains opt-in on hover/focus. Detail pages use the cover while waiting for playback. Creator workspace queries include cover and preview fields.

Checks from the previous release: four independently measured actions, natural blink, unchanged original-art identity, no VRM/old-runtime requests, motion/offscreen/minimized pauses, mobile lazy loading, 13 static video posters and no initial MP4 requests. Isolated Python tests cover short/normal/invalid video extraction and the real video-processing upload pipeline with only remote storage mocked.

Full 3D would require reconstructing hidden geometry, materials and a matching rig; extra reference drawings can guide that work but are not themselves a 3D model.

Live local-service verification passed: 13 decodable static posters, zero initial MP4 requests, correct hover preview requests, original-art animated character, zero VRM requests, and background pause; no script errors or failed static resources. The installed headless Chromium lacks H.264 decoding, so actual H.264 playback was not asserted in that browser. The preview encoding/playback handler was retained. Isolated FFmpeg tests and the upload processing pipeline passed.


## Larger-motion release — 2026-09-26 (v4)

Browser checks passed for all six actions, the initial greeting, interruption without an immediate pose jump, four body hotspots, quiet/offscreen/background/minimized pauses, mobile deferred loading, and 320/390/768/1440 px layouts. All 13 video covers still load without an initial MP4 request. No old 3D runtime/model request, missing static resource or uncaught script error was observed. Critical frames were inspected at an enlarged scale and at real desktop/mobile sizes; the thumb weights and exposed old finger edges were corrected during that review.

`sampleMotion` is a deterministic timeline shared by the renderer and offline inspection. The original painting remains visible if WebGL or a required texture is unavailable. Rendering timing in the development browser measures JavaScript command submission only, not GPU time or a physical-phone battery benchmark.

Source artwork: [arm / palm backplate](frontend/xiaoxing/artwork/arm-and-star-backplate.png), [isolated star](frontend/xiaoxing/artwork/star-sprite.png). Runtime assets: `static/images/xiaoxing-arm-back.webp`, `xiaoxing-star-back.webp`, `xiaoxing-star.webp`. Full prompts: [motion-prompts.json](frontend/xiaoxing/motion-prompts.json).

Reduced-motion deferred loading, action clicks during module loading, static manual poses, history-cache resume, WebGL context loss and a failed backplate fetch also passed browser checks. Both failure cases retained the original poster. Release evidence: `UI_XIAOXING_MOTION_RELEASE.json`.

Live v4a verification passed for the automatic greeting, all six actions, smooth interruption, body hotspots, 320/390/768/1440 px layouts, all pause conditions and 13 unchanged video posters. No script errors or failed static assets. Backups are recorded in `UI_XIAOXING_MOTION_RELEASE.json`; the service was not restarted.


## Full-body dance — 2026-09-26 (v5)

The shared hero/floating companion now has a **下来跳舞** button. One explicit click loads a 13.2-second illustrated performance: entrance and landing, alternating steps, overhead reaches, open arms, a finishing dip, and a return to the seated illustration. The button changes to **回到月亮**; clicking it again, another gesture, or Escape starts an early return. Existing seated actions remain available.

The entrance blends the seated pose into a separately illustrated standing rig; it does not reconstruct a physical standing-up action or a 360-degree 3D turn. The face/costume are referenced from the original. Full 3D geometry and unseen-side views are not implied by this release.

Implementation: `static/js/xiaoxing-dance.js` is imported only for an explicit dance request. The matching standing illustration is separated into a torso/hair/skirt layer, two arms and two legs. Shoulder, elbow, wrist, pelvis, knee and ankle joints articulate these layers. Two-bone inverse kinematics controls the feet during pelvis movement. Head/hair/skirt follow the dance; a small procedural floor shadow gives a landing reference. The empty moon stays behind her.

Runtime images, loaded on demand only: `xiaoxing-standing-v5.webp` (200,072 bytes), `xiaoxing-standing-back-v5.webp` (145,270 bytes), `xiaoxing-moon-v5.webp` (67,380 bytes), total 412,722 bytes. The module uses at most 8 draw calls / 8,278 triangles, caps dance rendering at 24 fps desktop / 18 fps mobile, drops to 15 fps when command submission is slow, and caps pixel ratio at 1.5 / 1.35. These are limits, not a physical-phone battery benchmark. The seated renderer stops while the dance is active. GPU textures, buffers, program and temporary WebGL context are released at the end; cropped preparation textures are reused for replay on the current page.

Hidden, offscreen, minimized and motion-disabled states pause the dance clock. Explicit dance selection under reduced-motion settings shows a still dance pose; returning restores the seated artwork without animation. Missing dance resources leave the seated character usable. A canonical 800x1200 seated snapshot preserves proportions if the viewport changes during a performance.

Generated source art and complete built-in-tool prompts: [dance-prompts.json](frontend/xiaoxing/dance-prompts.json), [standing figure](frontend/xiaoxing/artwork/standing.png), [hidden-part backplate](frontend/xiaoxing/artwork/standing-backplate.png), [empty moon](frontend/xiaoxing/artwork/empty-moon.png).

Texture preparation (source-preserving resize / registration / WebP encoding):

```sh
convert artwork/standing.png -quality 91 ../../static/images/xiaoxing-standing-v5.webp
convert artwork/standing-backplate.png -resize 80% -gravity north -background none -extent 1024x1536 -quality 91 ../../static/images/xiaoxing-standing-back-v5.webp
convert artwork/empty-moon.png -resize 800x1200 -quality 88 ../../static/images/xiaoxing-moon-v5.webp
```

The floating companion temporarily expands during a performance and returns to its compact size afterward. Browser validation passed: full automatic sequence, steps and overhead reaches, explicit early return, queued seated gestures, replay without extra asset requests, resize during playback, quiet/background/offscreen/minimized pauses, Escape, 320/390/768/1440 px layouts, reduced-motion still poses, repeated GPU cleanup, context loss, missing-resource retry and history-cache resume. No video/3D model was requested and no uncaught script error was observed.

Live v5 verification passed against the running website: complete automatic dance and return, actual steps/reaches, isolated renderer loops, all pause/resume conditions, explicit return, replay, viewport resize, expanded mobile companion and 320/390/768/1440 px layouts. No script errors, missing assets, video or 3D model downloads. Evidence and rollback manifest: `UI_XIAOXING_DANCE_RELEASE.json`. Existing service remained active and was not restarted.


## Real video generation trial — v6 (not published)

After explicit user authorization, the existing RunPod account generated a Wan 2.2 image-to-video sample from the original illustration for USD 0.30. It contains real coordinated full-body standing and stepping; the later frames crop the boots and the ending does not form a natural loop. The sample is therefore **not installed as the public character**. The v5 handmade dance remains withdrawn.

The original video, browser-review page, isolated native-video candidate and review evidence were kept in a local working directory outside this repository and are not published; `REVIEW_RESULT.json` records the outcome and nine passed candidate playback/lifecycle checks. An 8-second retry was prepared but never submitted; it has been superseded by the user’s v8 drawn-frame direction. No new server, port, model runtime or cloud GPU instance was created.
