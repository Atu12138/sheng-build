"""Add a read-only, pre-handoff stop to the pinned DarwinBoot diagnostic build."""
from pathlib import Path
import hashlib, sys
source = Path(sys.argv[1])
expected = '1d19ca1091962bd48b4154e3aae3d0ad80699f6c892a5a407dd3de0d62907fd9'
original = source.read_bytes()
if hashlib.sha256(original).hexdigest() != expected:
    raise SystemExit('DarwinBoot source differs from reviewed pin; refusing patch')
needle = '    Status = gBS->ExitBootServices (mImage, Key);'
block = r'''    // Diagnostic-only image: display map metadata, then stop before ExitBootServices.
    // No address in the suspect range is read or written by this diagnostic.
    {
      UINTN DiagnosticOffset;
      UINTN DiagnosticMatches = 0;
      CONST UINT64 DiagnosticTarget = 0x8B9D00000ULL;
      DEBUG ((DEBUG_ERROR, "\fSHENG MEMORY MAP DIAGNOSTIC - NO KERNEL START\n\n"));
      DEBUG ((DEBUG_ERROR, "target 0x%lx  EL %lu\n", DiagnosticTarget, DarwinCurrentEl () >> 2));
      DEBUG ((DEBUG_ERROR, "window 0x%lx + 0x%lx  head 0x%lx\n", Address, WindowSize, HeadSize));
      DEBUG ((DEBUG_ERROR, "usable 0x%lx  excluded %lu\n", Args->MemorySizeActual, (UINT64)ExcludedCount));
      for (DiagnosticOffset = 0; DiagnosticOffset + sizeof (EFI_MEMORY_DESCRIPTOR) <= MapSize; DiagnosticOffset += Stride) {
        CONST EFI_MEMORY_DESCRIPTOR *Descriptor = (CONST EFI_MEMORY_DESCRIPTOR *)((CONST UINT8 *)Map + DiagnosticOffset);
        UINT64 DescriptorEnd = Descriptor->PhysicalStart + EFI_PAGES_TO_SIZE (Descriptor->NumberOfPages);
        if ((Descriptor->PhysicalStart <= DiagnosticTarget + SIZE_1MB) &&
            (DescriptorEnd > DiagnosticTarget - SIZE_1MB)) {
          DEBUG ((DEBUG_ERROR, "map type %u  attr 0x%lx\n", Descriptor->Type, Descriptor->Attribute));
          DEBUG ((DEBUG_ERROR, "    0x%lx -- 0x%lx\n", Descriptor->PhysicalStart, DescriptorEnd));
          DiagnosticMatches++;
        }
      }
      DEBUG ((DEBUG_ERROR, "nearby map records %lu\n", (UINT64)DiagnosticMatches));
      if (Excluded != NULL) {
        for (Index = 0; Index < ExcludedCount; Index++) {
          UINT64 RangeBase = DarwinRangeBase (Excluded, Index);
          UINT64 RangeEnd = RangeBase + DarwinRangeSize (Excluded, Index);
          if ((RangeBase <= DiagnosticTarget + SIZE_1MB) && (RangeEnd > DiagnosticTarget - SIZE_1MB)) {
            DEBUG ((DEBUG_ERROR, "excluded 0x%lx -- 0x%lx\n", RangeBase, RangeEnd));
          }
        }
      }
      DEBUG ((DEBUG_ERROR, "\nDIAGNOSTIC STOP - photograph this screen.\nHold Power, then Power + Volume Down for Fastboot.\n"));
      CpuDeadLoop ();
      return EFI_ABORTED;
    }
'''
text = original.decode()
assert text.count(needle) == 1
source.write_text(text.replace(needle, block + needle))
print('Applied pre-handoff memory map diagnostic:', source)
print('Modified source SHA256:', hashlib.sha256(source.read_bytes()).hexdigest())

