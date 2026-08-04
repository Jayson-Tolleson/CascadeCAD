# CascadeCAD 1.0 Production TODO

The following items are intentionally deferred because they require deeper CAD-kernel, authentication-provider, or browser-rendering validation beyond this source-tree refactor pass.

## Rendering

- True GPU occlusion-query culling after profiling representative production assemblies.
- Full GPU instancing for repeated component meshes once duplicate source identity is exposed consistently by the import pipeline.
- Progressive network chunk streaming for GLB/XBF previews; current implementation performs budget-aware lazy visibility after load.

## CAD Interaction

- Full 18-view draggable orientation cube with animated camera transitions.
- Complete professional CAD navigation profile with bookmark persistence.
- Advanced intelligent OSNAP modes for face/intersection/construction geometry after topology-picking APIs are finalized.

## Collaboration/Auth

- Production Google OIDC registration and secret management.
- GitHub and Microsoft provider implementations.
- Organization/team ownership policies.

## Import/Export

- Parasolid adapter interface and licensed-kernel integration.
- Expanded IGES/OBJ/STL round-trip conformance fixtures.

## Plugin Platform

- Plugin manifest format, sandboxing rules, and lifecycle hooks.
