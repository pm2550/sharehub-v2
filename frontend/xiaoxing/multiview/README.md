# Xiaoxing multi-view reconstruction workflow

Status: workflow verified against upstream examples; no new view set, reconstruction, texture generation or rig has been produced. No cloud job was submitted. The earlier Seedance retry remains superseded.

## Input contract

The canonical identity is the original silver-lavender-haired Xiaoxing illustration (`static/images/sharehub-muse-800.webp`). Prepare matching front, left and back character views in one neutral standing A-pose. Keep the head/eye proportions, hair volume, flower/star accessories, cream cardigan, lavender floral dress and white boots fixed across views. Use consistent framing and scale, neutral lighting and isolated foreground. The crescent moon and held star are separate props; the seated/crossed-leg composition must not be treated as a rig-ready body reference. The backside is a designed extrapolation, not recovered evidence.

Do not use independent dance poses, video frames with changing shape, or a casually generated turnaround sheet as if camera/body consistency had already been validated.

## Reconstruction

Use `tencent/Hunyuan3D-2mv`, subfolder `hunyuan3d-dit-v2-mv`, with the explicit `front`, `left`, `back` image dictionary. The upstream shape example uses 50 steps, octree resolution 380 and exports a GLB mesh. Its textured-shape example paints from the front reference. The separate multi-view texture example accepts a list of three views with `hunyuan3d-paint-v2-0-turbo`; these are different upstream paths and must not be conflated.

Official examples:
- https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/examples/shape_gen_multiview.py
- https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/examples/textured_shape_gen_multiview.py
- https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/examples/fast_texture_gen_multiview.py

For generating jointly consistent intermediate views, evaluate Zero123++/InstantMesh rather than assuming independently generated illustrations correspond to the same 3D surface. InstantMesh is an alternative reconstruction pipeline, not a drop-in view generator with Hunyuan's exact camera contract:
- https://github.com/SUDO-AI-3D/zero123plus
- https://github.com/TencentARC/InstantMesh

## Character and browser acceptance

Inspect the textured mesh interactively in the browser alongside the original image: face, hair silhouette, front/side/back proportions, clothing pattern placement and missing geometry. Only after this visual gate should the mesh be repaired/retopologized, eyes/mouth prepared for expressions, clothing and hair separated where necessary, and bones/weights added. A reconstructed static mesh is not automatically a usable animated character.

Then retarget licensed motion and check feet, balance, knee/elbow deformation and dress intersections. Export a browser-ready GLB/VRM. Judge actual browser rendering and performance, not an offline beauty render.

The current ARM server has no CUDA GPU, so the upstream GPU reconstruction stage is not locally verified. Blender installation/plugin compatibility is also not yet verified. Provisioning new GPU resources or submitting paid inference requires a concrete costed task and user authorization; the past USD 0.30 video authorization does not carry over.
