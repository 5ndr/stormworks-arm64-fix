# Stormworks: Build and Rescue — Windows on ARM64 Fix & Reverse Engineering

[![Windows on ARM64](https://img.shields.io/badge/Platform-Windows%20on%20ARM64%20(Snapdragon%20X)-blue.svg)](#)
[![Status](https://img.shields.io/badge/Status-Fully%20Playable-brightgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A complete compatibility fix, patcher, and technical analysis for running ***Stormworks: Build and Rescue*** (`stormworks64.exe`) on native **Windows 11 on ARM64** (Qualcomm Snapdragon X Elite / Plus / Adreno GPUs) under Microsoft Prism x64 emulation.

---

## Table of Contents
1. [The Problem](#the-problem)
2. [Root Cause Analysis](#root-cause-analysis)
   - [Issue 1: Missing OpenGL ICD](#1-missing-opengl-icd-crash-on-launch)
   - [Issue 2: Workbench Multi-Block Spawn Crash](#2-workbench-multi-block-spawn-crash-0xc0000409)
3. [The Fix](#the-fix)
4. [Quick Start (Installation)](#quick-start-installation)
5. [Automated Patcher Usage](#automated-patcher-usage)
6. [Physics Engine Analysis & Roadmap](#physics-engine-analysis--roadmap)
7. [Repository Structure](#repository-structure)
8. [License](#license)

---

## The Problem

When running *Stormworks: Build and Rescue* on ARM64 Windows laptops powered by the Qualcomm Snapdragon X Elite:
1. **Initial Launch Crash**: The game crashes immediately upon launch with the dialog:
   ```
   OpenGL 3.2 is required but your version is 0.0. Are your graphics drivers up to date?
   ```
2. **Workbench Spawn Crash**: After bypassing the OpenGL launch failure via translation layers, spawning a single block from the workbench works, and spawning complex vehicles via mission scripts (`server.spawnVehicle`) works. However, **spawning any vehicle with more than 1 block from the workbench UI immediately crashed the game** with `STATUS_STACK_BUFFER_OVERRUN` / `0xc0000409` (`FAST_FAIL_FATAL_APP_EXIT`).

---

## Root Cause Analysis

### 1. Missing OpenGL ICD (Crash on Launch)
* **Mechanism**: `stormworks64.exe` links directly against `OPENGL32.dll` and enforces a strict version check in [`FUN_1401bd800`](docs/TECHNICAL_ANALYSIS.md#1-opengl--glfw-bootstrap-fun_1401bd800):
  ```c
  glGetIntegerv(GL_MAJOR_VERSION, &major); // 0x821B
  glGetIntegerv(GL_MINOR_VERSION, &minor); // 0x821C
  if (major < 3 || (major == 3 && minor < 2)) {
      MessageBoxA(0, "OpenGL 3.2 is required but your version is ...", 0, 0);
  }
  ```
* **Why ARM64 fails natively**: Qualcomm's Windows on ARM64 Adreno driver package does not provide a desktop OpenGL Installable Client Driver (ICD); it only exposes Direct3D 11/12, Vulkan, and OpenGL ES. The standard Microsoft GDI fallback `OPENGL32.dll` reports version 1.1, failing the check.
* **Resolution**: Deploying prebuilt Mesa Gallium with the D3D12 driver (`GALLIUM_DRIVER=d3d12`) translates all desktop OpenGL 3.3+ calls directly into native Direct3D 12 API calls understood by the Adreno GPU.

---

### 2. Workbench Multi-Block Spawn Crash (`0xc0000409`)
* **Crash Dump Evidence**: Analysis of crash dump `stormworks64.exe.10400.dmp` revealed:
  ```
  Exception Code: 0xc0000409 (FAST_FAIL_FATAL_APP_EXIT)
  Crashing Thread: Main Thread (TID 22340)
  Top Frame: crashhandler64.dll!TerminateProcess
  ```
* **Unwinding the ARM64EC Call Stack**:
  Under Windows 11 on ARM64 Prism emulation, return addresses contain Pointer Authentication Codes (PAC) in the upper 16 bits. Stripping PAC tags (`val & 0x0000ffffffffffff`) revealed the exact execution chain:
  ```
  stormworks64.exe+0x80bf94 (FUN_14080bc50: Workbench Spawn Handler)
    └─► stormworks64.exe+0x7daef0 (FUN_1407daef0: Autosave Thumbnail Generator)
          ├─► FUN_1408e4140 (Octree Voxel Grid Traversal)
          └─► FUN_1407dae30 / FUN_1407db030 (Offscreen FBO Vehicle Render)
                └─► opengl32.dll -> libgallium_wgl.dll (Mesa D3D12)
                      └─► ID3D12Device::CreateGraphicsPipelineState()
                            └─► qcdx12arm64xum.dll (Qualcomm Adreno D3D12 Driver) -> FAILS (E_INVALIDARG / Error HRESULT)
                                  └─► libgallium_wgl.dll calls abort() / TerminateProcess
  ```
* **Why Single Blocks & Mission Spawning Worked**:
  * **Mission Spawning**: Uses `server.spawnVehicle()`, which spawns vehicles directly into the game simulation world without touching the workbench UI or generating preview thumbnails.
  * **Single Block**: A single block does not require octree mesh consolidation or multi-block ambient occlusion / shadow buffers during offscreen thumbnail generation.
  * **Multi-Block Workbench**: When clicking "Spawn", Stormworks creates an autosave:
    1. Writes XML to `data/vehicles/tmp/autosave/`.
    2. Renders an offscreen preview screenshot to `data/vehicles/tmp/autosave.png` via [`FUN_1407daef0`](docs/TECHNICAL_ANALYSIS.md#3-autosave-thumbnail-renderer-fun_1407daef0).
    3. The offscreen pipeline state created for multi-block thumbnail rendering triggers an unsupported pipeline configuration in the Qualcomm Adreno D3D12 driver, returning a failure HRESULT that causes Mesa to abort.

---

## The Fix

1. **Mesa D3D12 Translation**: Provides desktop OpenGL 3.3 to Stormworks via Direct3D 12.
2. **Thumbnail Bypass Binary Patch**:
   * [`FUN_1407daef0`](file:///C:/Program%20Files%20%28x86%29/Steam/steamapps/common/Stormworks/stormworks64.exe) is a `void` function whose sole side-effect is writing `autosave.png` to disk. The game engine does not require this image to spawn the vehicle.
   * Right after `FUN_1407daef0` returns, the workbench handler immediately executes:
     ```c
     FUN_140275d80(param_3 + 0x50, param_2); // Dispatches the actual vehicle spawn
     ```
   * By replacing the first byte of `FUN_1407daef0` at file offset `0x7da2f0` with `0xc3` (`RET`), the offscreen thumbnail rendering is skipped entirely. The vehicle XML is saved, the game dispatches the spawn packet, and vehicles of any size spawn cleanly into the world!

---

## Quick Start (Installation)

### Step 1: Install Mesa D3D12 Drop-in
1. Download prebuilt **Mesa 24.x+ x64** for Windows (with `d3d12` Gallium driver).
2. Copy the following files into your Stormworks directory (`C:\Program Files (x86)\Steam\steamapps\common\Stormworks`):
   * `opengl32.dll`
   * `libgallium_wgl.dll`
   * `dxil.dll`
   * `spirv_to_dxil.dll`
   * `stormworks64.exe.local` (enables DotLocal DLL redirection)
3. Set the environment variable:
   ```powershell
   [Environment]::SetEnvironmentVariable("GALLIUM_DRIVER", "d3d12", "User")
   [Environment]::SetEnvironmentVariable("MESA_LOADER_DRIVER_OVERRIDE", "d3d12", "User")
   ```

### Step 2: Apply the Binary Patch
Run the included python patcher:
```powershell
python scripts/patch_stormworks.py
```
Or specify a custom Steam path:
```powershell
python scripts/patch_stormworks.py --path "D:\SteamLibrary\steamapps\common\Stormworks\stormworks64.exe"
```

The patcher will automatically verify file integrity, create a `.bak` backup, and apply the single-byte `RET` patch.

---

## Automated Patcher Usage

```
usage: patch_stormworks.py [-h] [--path PATH] [--restore] [--verify]

options:
  -h, --help     show this help message and exit
  --path PATH    Path to stormworks64.exe (default: auto-detected)
  --restore      Restore the original unpatched executable from .bak
  --verify       Check if the executable is currently patched or unpatched
```

---

## Physics Engine Analysis & Roadmap

Beyond graphics and spawning, decompilation of the Stormworks physics simulation subsystem (`FUN_140135190` / `calculateSimulationIslands`) identified the root cause of the game's famous physics slowdown with complex creations:

* **Island Consolidation**: Stormworks vehicles use mechanical constraints (rotators, hinges, sliders, pivots) to link sub-grids.
* Bullet Physics groups rigid bodies into "simulation islands" using a Union-Find algorithm. In [`FUN_140135190`](docs/TECHNICAL_ANALYSIS.md#4-bullet-simulation-island-manager-fun_140135190), Stormworks unifies all bodies connected by constraints into the same island.
* Because every sub-grid on a ship or aircraft is merged into a single mega-island, Bullet's `btSequentialImpulseConstraintSolver` is forced to solve them on a single thread.
* **Optimization Opportunities**:
  1. Decoupling non-stiff constraint subgraphs into parallel islands.
  2. Vectorizing sub-grid buoyancy mesh point sampling (`FUN_1407af590`).
  3. Multithreading the constraint impulse solver across Snapdragon X Elite's 12 Oryon CPU cores.

Full disassembly and decompilation notes are available in [docs/TECHNICAL_ANALYSIS.md](docs/TECHNICAL_ANALYSIS.md).

---

## Repository Structure

```
stormworks-arm64-fix/
├── README.md                      # Overview, root cause, and instructions
├── LICENSE                        # MIT License
├── scripts/
│   ├── patch_stormworks.py        # Automated Python patcher with --restore
│   └── launch_with_mesa_d3d12.bat # Standalone launcher batch script
├── tools/
│   ├── parse_dump.py              # Minidump parser with ARM64EC PAC unwinding
│   └── AnalyzeStormworks.java     # Ghidra 12 headless analysis script
└── docs/
    └── TECHNICAL_ANALYSIS.md      # Detailed decompiled C pseudocode & call stacks
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
