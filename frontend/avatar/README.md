# ShareHub animated companion

Build from this directory: `npm ci && npm run build`. Pinned versions and lockfile are included. No CDN is required at runtime. The built browser module is committed under `static/vendor/`.

Model: pixiv/three-vrm v3.5.5 `VRM1_Constraint_Twist_Sample.vrm`; author and license are recorded in `static/models/README.md` and embedded metadata. To rebuild the optimized model, save the file from https://raw.githubusercontent.com/pixiv/three-vrm/v3.5.5/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm here as `sample.vrm`, then run `python3 optimize_model.py` (requires ImageMagick `convert`). The download, intermediate textures and node_modules are build artifacts, not deployment inputs.

Runtime changes include a lavender top tint and a small modeled star hair clip. This character is not a rigged version of the separate generated site illustration.

The browser schedules at most 30 fps desktop / 24 fps mobile during actions, 12 fps idle, adapts to 18 fps on slow rendering, and pauses offscreen, minimized, hidden, or when motion is disabled. Mobile floating characters load on demand; the homepage hero may load when visible and motion is allowed. Reduced-motion / save-data users retain the poster unless they explicitly load the character. A motion-disabled explicit action displays a static pose. WebGL failure retains the poster.
