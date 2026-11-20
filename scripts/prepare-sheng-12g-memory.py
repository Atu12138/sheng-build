#!/usr/bin/env python3
"""Accept the measured sheng 12 GiB DDR layout in the pinned UEFI source."""

import argparse
import hashlib
from pathlib import Path


SOURCE_SHA256 = '3c275538a2698b742af9d90052e7ee29f4dce0b54521aa6e04679133cad34178'


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise SystemExit(f'Unexpected memory map source at {old!r}')
    return text.replace(old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--device', type=Path, required=True)
    args = parser.parse_args()
    data = args.source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise SystemExit('Unexpected UEFI source revision')
    source = data.decode()
    source = replace(source, '{"DRAM bank 1 low", 0x880000000, 0x3B300000,',
                     '{"DRAM bank 1 low", 0x880000000, 0x39D00000,')
    source = replace(source, '  // These corrections are qualified against the 8 GiB sheng layout only.\n', '')
    source = replace(source, '''  if (Value == NULL || Length != 4 || Fdt32ToCpu (ReadUnaligned32 (Value)) != 8 ||
      !ShengEnabled''', '''  if (Value == NULL || Length != 4) { return; }
  UINT32 DdrGiB = Fdt32ToCpu (ReadUnaligned32 (Value));
  if (DdrGiB != 8 && DdrGiB != 12) { return; }
  if (!ShengEnabled''')
    source = replace(source, '  BOOLEAN HasHighBank = FALSE;', '''  // The two adjacent high banks were read from the 12 GiB tablet's live ABL FDT.
  // Never add nominal RAM absent from the bank list or reserved by firmware.
  UINT64 HighEnd = DdrGiB == 12 ? 0xb00000000ULL : 0xa00000000ULL;
  UINT64 FirstHighEnd = DdrGiB == 12 ? 0x980000000ULL : HighEnd;
  BOOLEAN HasFirstHighBank = FALSE;
  BOOLEAN HasSecondHighBank = DdrGiB == 8;''')
    source = replace(source, 'End <= 0xa00000000ULL', 'End <= HighEnd', count=2)
    source = replace(source, '''    if (Base == 0x8c0000000ULL && End == 0xa00000000ULL) { HasHighBank = TRUE; }''',
                     '''    if (Base == 0x8c0000000ULL && End == FirstHighEnd) { HasFirstHighBank = TRUE; }
    if (DdrGiB == 12 && Base == FirstHighEnd && End == HighEnd) { HasSecondHighBank = TRUE; }''')
    source = replace(source, '  if (!HasHighBank) { return; }',
                     '  if (!HasFirstHighBank || !HasSecondHighBank) { return; }')
    source = replace(source, '''  if (!ShengCut (Free, &FreeCount, (SHENG_RAM_RANGE){0xd0000000, 0xd0010000}) ||''',
                     '''  // The tablet previously faulted at 0x8b9d00000. Retain the measured gap.
  if (!ShengCut (Free, &FreeCount, (SHENG_RAM_RANGE){0x8b9d00000ULL, 0x8b9f00000ULL}) ||
      !ShengCut (Free, &FreeCount, (SHENG_RAM_RANGE){0xd0000000, 0xd0010000}) ||''')
    # XNU's outside-memory support only adopts banks below its main window.
    # Therefore the 4 GiB extension belongs inside the existing high window.
    window = args.core / 'drivers/DarwinBoot/DarwinBootPkg/Driver/WindowSize.h'
    window_text = replace(window.read_text(), 'size <= 0x200000000ULL', 'size <= 0x280000000ULL')
    generator = args.core / 'scripts/unixnu/devicetree.py'
    generator_text = replace(generator.read_text(), 'size <= 0x200000000', 'size <= 0x280000000')
    generator_text = replace(generator_text, 'to 8 GiB in 2 MiB steps', 'to 10 GiB in 2 MiB steps')
    board = args.device / 'board.toml'
    board_text = replace(board.read_text(), '"owned_memory_size" = "0x180000000"', '"owned_memory_size" = "0x280000000"')
    board_text = replace(board_text, 'The 6 GiB bootstrap window spans the high bank.',
                         'The 10 GiB bootstrap window spans the measured high banks.')
    args.source.write_text(source)
    window.write_text(window_text)
    generator.write_text(generator_text)
    board.write_text(board_text)
    print('Enabled the measured 12 GiB DDR range while retaining the low-bank guard and FDT reservations.')
    print('Updated memory map source SHA-256:', hashlib.sha256(source.encode()).hexdigest())


if __name__ == '__main__':
    main()
