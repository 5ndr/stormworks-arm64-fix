#!/usr/bin/env python3
"""
Stormworks: Build and Rescue - Windows on ARM64 Patcher
Bypasses the offscreen autosave thumbnail generation (FUN_1407daef0) that
triggers an unhandled CreateGraphicsPipelineState failure on Qualcomm Adreno D3D12.
"""

import os
import sys
import shutil
import argparse

DEFAULT_PATHS = [
    r"C:\Program Files (x86)\Steam\steamapps\common\Stormworks\stormworks64.exe",
    r"C:\Steam\steamapps\common\Stormworks\stormworks64.exe",
    r"D:\SteamLibrary\steamapps\common\Stormworks\stormworks64.exe",
    r"E:\SteamLibrary\steamapps\common\Stormworks\stormworks64.exe",
]

PATCH_OFFSET = 0x7da2f0
ORIGINAL_BYTE = b"\x48"  # mov [rsp+8], rbx
PATCHED_BYTE = b"\xc3"   # ret

def find_executable(custom_path=None):
    if custom_path:
        if os.path.isfile(custom_path):
            return os.path.abspath(custom_path)
        print(f"[-] Specified path does not exist: {custom_path}")
        return None

    for p in DEFAULT_PATHS:
        if os.path.isfile(p):
            return p
    return None

def verify_file(exe_path):
    if not os.path.isfile(exe_path):
        print(f"[-] Executable not found at {exe_path}")
        return False

    with open(exe_path, "rb") as f:
        f.seek(PATCH_OFFSET)
        b = f.read(1)

    bak_path = exe_path + ".bak"
    has_backup = os.path.isfile(bak_path)

    print(f"[*] Target: {exe_path}")
    print(f"[*] Backup exists: {has_backup}")

    if b == ORIGINAL_BYTE:
        print("[*] Status: UNPATCHED (Original byte 0x48 present at offset 0x7da2f0)")
        return "unpatched"
    elif b == PATCHED_BYTE:
        print("[+] Status: PATCHED (RET 0xc3 present at offset 0x7da2f0)")
        return "patched"
    else:
        print(f"[!] Status: UNKNOWN (Unexpected byte {b.hex()} at offset 0x7da2f0)")
        return "unknown"

def apply_patch(exe_path):
    status = verify_file(exe_path)
    if status == "patched":
        print("[+] File is already patched. Nothing to do!")
        return True

    if status != "unpatched":
        print("[-] Aborting patch due to unexpected file contents at target offset.")
        return False

    bak_path = exe_path + ".bak"
    if not os.path.isfile(bak_path):
        print(f"[*] Creating backup at {bak_path}...")
        shutil.copy2(exe_path, bak_path)

    print("[*] Writing RET (0xc3) instruction to offset 0x7da2f0...")
    with open(exe_path, "r+b") as f:
        f.seek(PATCH_OFFSET)
        f.write(PATCHED_BYTE)

    print("[+] Patch successfully applied! Multi-block vehicles will now spawn from the workbench without crashing.")
    return True

def restore_backup(exe_path):
    bak_path = exe_path + ".bak"
    if not os.path.isfile(bak_path):
        print(f"[-] Backup file not found at {bak_path}. Cannot restore.")
        return False

    print(f"[*] Restoring from backup {bak_path}...")
    shutil.copy2(bak_path, exe_path)
    print("[+] Executable successfully restored to original state.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Stormworks ARM64 Workbench Spawn Fix Patcher")
    parser.add_argument("--path", help="Path to stormworks64.exe", default=None)
    parser.add_argument("--restore", action="store_true", help="Restore original executable from .bak")
    parser.add_argument("--verify", action="store_true", help="Check current patch status")

    args = parser.parse_args()

    exe_path = find_executable(args.path)
    if not exe_path:
        print("[-] Could not automatically locate stormworks64.exe. Please pass --path <path>.")
        sys.exit(1)

    if args.restore:
        success = restore_backup(exe_path)
        sys.exit(0 if success else 1)
    elif args.verify:
        verify_file(exe_path)
        sys.exit(0)
    else:
        success = apply_patch(exe_path)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
