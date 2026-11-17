"""Conservative sheng board memory guard for the observed 0x8B9D00000 abort."""
from pathlib import Path
import hashlib, sys
source=Path(sys.argv[1])
original=source.read_bytes()
assert hashlib.sha256(original).hexdigest()=='3c275538a2698b742af9d90052e7ee29f4dce0b54521aa6e04679133cad34178', 'Unexpected board memory source'
old='{"DRAM bank 1 low", 0x880000000, 0x3B300000,'
new='{"DRAM bank 1 low", 0x880000000, 0x39D00000,'
text=original.decode()
assert text.count(old)==1
text=text.replace(old,new)
text=text.replace('// Full five-GiB extent reported by the hardware SMEM partition table.', '// Diagnostic guard: this tablet faults at 0x8B9D00000. Exclude another 22 MiB from the low extent.\n  // Full five-GiB extent reported by the hardware SMEM partition table.',1)
source.write_text(text)
print('Guarded low-bank end: 0x8B9D00000; excluded extra 22 MiB. All other extents unchanged.')
print('Source SHA256',hashlib.sha256(source.read_bytes()).hexdigest())

