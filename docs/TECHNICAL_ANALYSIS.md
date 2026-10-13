# Technical Reverse Engineering Analysis: Stormworks on Windows on ARM64

This document provides complete technical notes, decompiled pseudocode, call stack traces, and architectural breakdown of *Stormworks: Build and Rescue* (`stormworks64.exe`) analyzed using Ghidra 12.1.3 and custom minidump parsing tools on Windows 11 on ARM64 (Qualcomm Snapdragon X Elite).

---

## 1. OpenGL / GLFW Bootstrap (`FUN_1401bd800`)

### Decompiled Signature
```c
undefined8 FUN_1401bd800(undefined8 *param_1, undefined4 param_2, undefined4 param_3, undefined4 param_4, undefined1 param_5);
```

### Analysis & Mechanism
`stormworks64.exe` creates its GLFW window through `FUN_1401bd4a0`. Immediately after initializing GLFW, it queries the OpenGL context version:

```c
glGetIntegerv(GL_MAJOR_VERSION, &local_164); // 0x821b
glGetIntegerv(GL_MINOR_VERSION, local_160);  // 0x821c

if ((2 < local_164) && ((local_164 != 3 || (1 < local_160[0])))) {
    // Context is OpenGL 3.2+
    glEnable(GL_CULL_FACE);      // 0x0b44
    glCullFace(GL_BACK);         // 0x0405
    glEnable(GL_BLEND);          // 0x0be2
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    glEnable(GL_DEPTH_TEST);     // 0x0b71
    glDepthFunc(GL_LEQUAL);      // 0x0201
    return 0; // Success
}

// Version Check Failed:
MessageBoxA(0, "OpenGL 3.2 is required but your version is ...", 0, 0);
return 1;
```

On native Windows on ARM64, Qualcomm's Adreno driver does not implement desktop OpenGL ICD. The system falls back to Microsoft GDI OpenGL 1.1 (`local_164 = 1, local_160 = 1`), throwing the failure dialog.

### The Mesa Solution
Placing Mesa's Gallium D3D12 implementation (`opengl32.dll` + `libgallium_wgl.dll` + `dxil.dll`) into the game directory with `stormworks64.exe.local` redirects OpenGL 3.3 calls to Direct3D 12, satisfying the version check and allowing the main viewport and game world to initialize.

---

## 2. Workbench Spawn Handler (`FUN_14080bc50`)

### Decompiled Code (Offset `0x14080bc50`, Call site at `0x14080bf94`):
```c
// Autosave vehicle XML
FUN_14099d3b0(local_58, "data/vehicles/tmp/autosave/", (local_50 & 0xffffffff) + 1);
FUN_1404c12f0(uVar3, param_2, &local_58, lVar7 + 0xbb670);

// Autosave vehicle thumbnail PNG
FUN_14099d3b0(local_58, "data/vehicles/tmp/autosave.png", (local_50 & 0xffffffff) + 1);
FUN_1407daef0(param_1, param_2, param_1 + 0x13c8, &local_58, plVar14, 0xff101010);

if (local_58 != 0) {
    FUN_1409b2d50();
    local_50 = 0;
}

LAB_14080bfac:
// Spawn vehicle in server/world simulation
FUN_140275d80(param_3 + 0x50, param_2);
return;
```

---

## 3. Autosave Thumbnail Renderer (`FUN_1407daef0`)

### Decompiled Code (Target of Binary Patch at RVA `0x7daef0`, File Offset `0x7da2f0`):
```c
void FUN_1407daef0(longlong param_1, longlong param_2, undefined8 param_3, undefined8 param_4,
                  undefined8 param_5, undefined4 param_6)
{
  // Sets up offscreen rendering context
  FUN_1408990b0(plVar1);
  FUN_1401b1cb0(*(undefined8 *)(param_1 + 0x10), param_2 + 8);
  FUN_1401b2220(*(undefined8 *)(param_1 + 0x10), param_2 + 8);

  // Renders the vehicle model offscreen
  FUN_1407dae30(param_1, param_2, param_3, local_48, param_6);

  // Compresses offscreen buffer into PNG and writes to disk via _wfopen_s()
  FUN_1401ef2a0(param_2 + 8, local_48, param_4);

  // Restores default framebuffer
  glBindFramebuffer(GL_FRAMEBUFFER, 0); // 0x8d40
  glViewport(0, 0, *(int *)(param_2 + 0x8f0), *(int *)(param_2 + 0x8f4));
  return;
}
```

### The Patch
Because `FUN_1407daef0` returns `void` and its only permanent effect is writing `data/vehicles/tmp/autosave.png`, patching the first instruction with `0xc3` (`RET`):
1. Immediately returns to `FUN_14080bc50`.
2. Leaves caller registers intact.
3. Frees the temporary path string.
4. Calls `FUN_140275d80`, cleanly spawning the vehicle into the world.

---

## 4. Octree Voxel Grid Traversal (`FUN_1408e4140`)

When a vehicle has >1 block, the offscreen renderer subdivides the bounding volume into an 8-child octree:

```c
void FUN_1408e4140(undefined8 param_1, longlong *param_2, int *param_3, int *param_4,
                   longlong *param_5, int *param_6, int param_7)
{
  if (param_7 == 1) {
    // Leaf node: append voxel block to vertex / batch buffer
    uVar7 = *(uint *)(param_2 + 2);
    uVar3 = *(uint *)(param_2 + 1);
    if (uVar7 == uVar3) {
      FUN_1408de0b0(param_2); // Realloc via _aligned_malloc
    }
    // ...
  }
  else {
    // Subdivide 2x2x2 child cells (param_7 / 2)
    do {
      do {
        do {
          FUN_1408e4140(param_1, param_2, param_3, param_4, puVar1 + uVar3, &local_60, param_7 / 2);
        } while (--z != 0);
      } while (--y != 0);
    } while (--x < 2);
  }
}
```

---

## 5. Bullet Simulation Island Manager (`FUN_140135190`)

### Decompiled Code:
```c
void FUN_140135190(longlong param_1)
{
  FUN_140163440("calculateSimulationIslands");

  // Step 1: Initialize Union-Find structures
  (**(code **)(**(longlong **)(param_1 + 0x198) + 8))
            (*(longlong **)(param_1 + 0x198), param_1, *(undefined8 *)(param_1 + 0x28));

  // Step 2: Merge bodies linked by collision manifolds
  if (0 < *(int *)(param_1 + 0x244)) {
    do {
      lVar2 = *(longlong *)(uVar7 + *(longlong *)(param_1 + 0x250));
      lVar3 = *(longlong *)(lVar2 + 0x5d0); // body0
      lVar2 = *(longlong *)(lVar2 + 0x5d8); // body1
      if (lVar3 && lVar2) {
        FUN_1400f4c60(*(longlong *)(param_1 + 0x198) + 8, // btUnionFind::unite
                      *(int *)(lVar3 + 0x1a4), *(int *)(lVar2 + 0x1a4));
      }
    } while (...);
  }

  // Step 3: Merge bodies linked by mechanical constraints (rotators, sliders, hinges)
  iVar1 = *(int *)(param_1 + 0x1a4);
  if (0 < (longlong)iVar1) {
    do {
      lVar2 = *(longlong *)(*(longlong *)(param_1 + 0x1b0) + uVar6 * 8);
      if (*(char *)(lVar2 + 0x20) != '\0') {
        lVar3 = *(longlong *)(lVar2 + 0x28); // constraint rigidBodyA
        lVar2 = *(longlong *)(lVar2 + 0x30); // constraint rigidBodyB
        if (lVar3 && lVar2) {
          FUN_1400f4c60(*(longlong *)(param_1 + 0x198) + 8, // btUnionFind::unite
                        *(int *)(lVar3 + 0x1a4), *(int *)(lVar2 + 0x1a4));
        }
      }
    } while (...);
  }

  // Step 4: Dispatch islands to sequential solver
  (**(code **)(**(longlong **)(param_1 + 0x198) + 0x10))(*(longlong **)(param_1 + 0x198), param_1);
  FUN_140163360();
}
```

### Bottleneck Explanation
* In Stormworks, sub-grids (e.g. turrets, cranes, rotor hubs, landing gear) use constraints to attach to the main hull.
* Step 3 unites every constrained rigid body into the same simulation island.
* Consequently, a vehicle with dozens of sub-grids becomes a single monolithic simulation island.
* Bullet solves each island on a single CPU core using `btSequentialImpulseConstraintSolver`, causing severe physics tick rate drops (Physics FPS < 60) regardless of available CPU cores.

---

## 6. Debug Modes State Machine (`FUN_1407af590`)

Stormworks contains built-in debug render modes toggled via key `F2` (`param_6 == 0x31`):
```c
// Toggle mode counter: 0 -> 1 -> 2 -> 3 -> 0
uVar3 = (uint)(*(int *)(param_1 + 0x3b50) == 0);
*(uint *)(param_1 + 0x3b50) = uVar3;

if (mode == 1) {
    pcVar7 = "<1>(F2) <0>Debug Vehicle Physics";
} else if (mode == 2) {
    pcVar7 = "<1>(F2) <0>Debug Buoyancy Mesh";
} else if (mode == 3) {
    pcVar7 = "<1>(F2) <0>Debug Buoyancy Volume";
}
```
This is useful for verifying sub-grid buoyancy mesh sampling in real-time.
