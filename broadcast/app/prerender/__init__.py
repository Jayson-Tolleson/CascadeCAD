"""PostGIS-backed pre-render feature cache for LFTR /gfs.

The cache stores interpreted render features, not raw provider grids and not final
particles.  Frontend renderers keep generating particles from stable feature recipes,
while PostGIS handles spatial lookup, simplified geometry, time windows, and stable IDs.
"""
