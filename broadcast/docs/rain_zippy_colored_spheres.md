# Rain pill: zippy colored falling spheres

Rain now renders from live GFS atmosphere samples as colored globe-space precipitation:

- precip rate is normalized by `rainIntensity()` and drives color, sphere count, fall speed, shaft width, and footprint;
- cloud top height is derived from low/mid/high/cloud density fields plus storm intensity;
- each falling drop is a small stack of `gmp-polygon-3d` ellipse discs, which reads as a colored sphere on the 3D globe;
- color ramp remains white → blue → green → yellow → orange → red → black;
- rain falls from cloud top to near-ground floor with a faint floor splash and vertical streak line;
- IDs stay stable by sample/drop/ring so updates animate instead of clearing the whole Rain pill.
