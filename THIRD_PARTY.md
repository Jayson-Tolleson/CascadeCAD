# Third-party components

This project installs and uses open-source dependencies under their respective licenses, including Quart, Hypercorn, CadQuery, OCP/Open CASCADE, Trimesh, NumPy, Three.js, lxml and Pillow. Consult each installed package for its complete license text. No Siemens Parasolid SDK or proprietary CAD runtime is included or required.

## FreeCAD

FCStd export uses the Debian `freecad-python3` command-line runtime. FreeCAD is licensed under LGPL-2.0-or-later. The runtime is installed from Debian and is not bundled in this archive.

## OpenSCAD CSG compatibility

CSG export writes the textual subset accepted by OpenSCAD, using separate top-level `polyhedron()` nodes. It is a tessellated representation, not recovered feature history.

## FFmpeg

The square-recording share tool uses Debian's system `ffmpeg` package to normalize browser recordings to H.264 MP4. FFmpeg is installed from Debian and is not bundled in this archive; its effective license depends on the Debian build configuration and linked codecs.
