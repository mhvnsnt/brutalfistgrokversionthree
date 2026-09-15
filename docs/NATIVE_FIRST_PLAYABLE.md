# Native-first playable gate

The authoritative game runtime is Schwarzerblitz native, not the old 2D React prototype.

The upstream engine is a Windows/DirectX 9/Win32 application and uses DirectX .x skeletal character models. It is not a browser engine.

Brutal Fist therefore has two explicit targets:

1. Native playable: Schwarzerblitz engine + converted Bannon resources.
2. PWA preview: a browser client for rapid inspection/testing, never presented as the native engine itself.

## First playable milestone

One Bannon real-GLB character must:

- load as a native .x skeletal resource
- retain Bannon identity/bio
- enter a Schwarzerblitz character slot
- load at least idle + locomotion + one attack from real Bannon animation data
- use native collision/move logic
- render through the Schwarzerblitz renderer
- pass resource validation

Only after this works should the roster conversion expand.

This prevents the project from declaring success based on a web mockup that does not exercise the actual fighting engine.
