#!/usr/bin/env python3
"""
Stormworks Minidump Crash Parser for Windows on ARM64
Unwinds thread call stacks and strips ARM64EC Pointer Authentication (PAC) tags
to reconstruct the exact x64 / ARM64 execution frames.
"""

import sys
import struct
import os

def parse_dump(dump_path):
    if not os.path.isfile(dump_path):
        print(f"[-] Dump file not found: {dump_path}")
        return

    with open(dump_path, "rb") as f:
        sig, ver, num_streams, stream_dir_rva = struct.unpack("<4sIII", f.read(16))
        if sig != b"MDMP":
            print("[-] Invalid minidump signature.")
            return

        f.seek(stream_dir_rva)
        streams = [struct.unpack("<III", f.read(12)) for _ in range(num_streams)]

        modules = []
        threads = []
        exception_info = None

        for st_type, size, rva in streams:
            # ModuleListStream = 4
            if st_type == 4:
                f.seek(rva)
                num_mods = struct.unpack("<I", f.read(4))[0]
                for _ in range(num_mods):
                    mod_data = f.read(108)
                    base_addr, mod_size, chk, ts, name_rva = struct.unpack("<QIIII", mod_data[:24])
                    curr = f.tell()
                    f.seek(name_rva)
                    name_len = struct.unpack("<I", f.read(4))[0]
                    name = f.read(name_len).decode("utf-16le", errors="ignore").rstrip("\x00")
                    f.seek(curr)
                    modules.append((base_addr, mod_size, name))

            # ThreadListStream = 3
            elif st_type == 3:
                f.seek(rva)
                num_th = struct.unpack("<I", f.read(4))[0]
                for _ in range(num_th):
                    tid, sus, pri, tid_p, teb, mem_start, mem_size, mem_rva, ctx_size, ctx_rva = struct.unpack("<IIIIQQIIII", f.read(48))
                    threads.append({
                        "tid": tid,
                        "stack_start": mem_start,
                        "stack_size": mem_size,
                        "stack_rva": mem_rva,
                        "ctx_size": ctx_size,
                        "ctx_rva": ctx_rva
                    })

            # ExceptionStream = 6
            elif st_type == 6:
                f.seek(rva)
                thread_id, _, code, flags, record_ptr, addr, num_params = struct.unpack("<IIIIQQI", f.read(36))
                params = [struct.unpack("<Q", f.read(8))[0] for _ in range(15)]
                exception_info = {
                    "thread_id": thread_id,
                    "code": code,
                    "addr": addr,
                    "params": params[:num_params]
                }

    def resolve_module(addr):
        for base, size, name in modules:
            if base <= addr < base + size:
                return f"{os.path.basename(name)}+{hex(addr - base)} (Base: {hex(base)})"
        return None

    print("==================================================")
    print(f" Minidump Analysis: {os.path.basename(dump_path)}")
    print("==================================================")
    if exception_info:
        print(f"Exception Thread: TID {exception_info['thread_id']}")
        print(f"Exception Code:   {hex(exception_info['code'])}")
        print(f"Exception Target: {hex(exception_info['addr'])} -> {resolve_module(exception_info['addr'])}")

    print("\n--- Unwinding Threads (with ARM64EC PAC Stripping) ---")
    with open(dump_path, "rb") as f:
        for idx, th in enumerate(threads):
            is_crash_th = exception_info and th['tid'] == exception_info['thread_id']
            if not is_crash_th:
                continue

            print(f"\n[Thread #{idx} (TID {th['tid']}) *CRASH THREAD*]")
            f.seek(th['stack_rva'])
            sdata = f.read(th['stack_size'])

            for offset in range(0, len(sdata) - 8, 8):
                val = struct.unpack_from("<Q", sdata, offset)[0]
                m = resolve_module(val)
                actual_val = val
                if not m:
                    # Strip 16-bit Pointer Authentication Code (PAC)
                    unpac = val & 0x0000ffffffffffff
                    m = resolve_module(unpac)
                    if m:
                        actual_val = unpac

                if m:
                    stack_addr = th['stack_start'] + offset
                    print(f"  [Stack {hex(stack_addr)}] {hex(actual_val)} -> {m}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parse_dump(sys.argv[1])
    else:
        default_dmp = r"C:\Users\decla\AppData\Local\CrashDumps\stormworks64.exe.10400.dmp"
        if os.path.isfile(default_dmp):
            parse_dump(default_dmp)
        else:
            print("Usage: python parse_dump.py <path_to_dump.dmp>")
