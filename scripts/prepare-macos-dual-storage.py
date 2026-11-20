#!/usr/bin/env python3
"""Configure the pinned sheng build to store macOS on its own GPT partition."""

import argparse
from pathlib import Path
import subprocess
import tomllib


DEVICE_REV = 'c8f92b208068eeaa4cd2b0f592671f04ee70076e'
UFS_REV = '9d527ae1a8d36a7ff210f9f4c9b429549c34c991'
OS = 'macos-27.3-26C5035r'
PARTITION = 'unixnu'
PARTITION_GIB = 64
DATA_GIB = 40
LOG_RESERVE = 1024**3
GIB = 1024**3


def replace(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f'Unexpected pinned source at {old!r}')
    return text.replace(old, new, 1)


def verify_revision(path, expected):
    actual = subprocess.check_output(['git', '-C', path, 'rev-parse', 'HEAD'], text=True).strip()
    if actual != expected:
        raise SystemExit(f'{path}: expected {expected}, found {actual}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('device', type=Path)
    parser.add_argument('--root-image', type=Path, help='check the expanded root image fits with Data and logs')
    args = parser.parse_args()
    device = args.device.resolve()
    ufs = device / 'drivers/ShengUfs'
    verify_revision(device, DEVICE_REV)
    verify_revision(ufs, UFS_REV)
    if args.root_image:
        minimum_slack = 4 * 1024**2
        slack = (PARTITION_GIB - DATA_GIB) * GIB - LOG_RESERVE - args.root_image.stat().st_size
        if slack < minimum_slack:
            raise SystemExit('The root image and persistent Data do not fit inside the macOS partition')
        print(f'Unused space after root, Data and log allocations: {slack / GIB:.2f} GiB.')

    board = device / 'board.toml'
    board_text = replace(board.read_text(), '"data_gib" = 210', f'"data_gib" = {DATA_GIB}')
    assert tomllib.loads(board_text)['os_overrides'][OS]['payload']['runtime']['data_gib'] == DATA_GIB
    header = ufs / 'RootLayout.h'
    patched = header.read_text()
    for old, new in (
        ('static const char wanted[] = "userdata";', f'static const char wanted[] = "{PARTITION}";'),
        ('partition named "userdata"', f'partition named "{PARTITION}"'),
        ('"duplicate userdata partition"', f'"duplicate {PARTITION} partition"'),
        ('"no userdata partition"', f'"no {PARTITION} partition"'),
        ('"userdata first block read"', f'"{PARTITION} first block read"'),
    ):
        patched = replace(patched, old, new)

    # The existing store and diagnostic log use the geometry returned by this parser.
    # Leave the nominal partition field names and factory-partition readers unchanged.
    driver = ufs / 'NativeUfs.cpp'
    driver_text = driver.read_text()
    for message in ('UFS LUN 0 userdata window, read-only',
                    'no valid root manifest in userdata', 'userdata first=%llx last=%llx\\n',
                    'userdata first=%llx last=%llx manifest status'):
        driver_text = replace(driver_text, message, message.replace('userdata', PARTITION))

    header.write_text(patched)
    driver.write_text(driver_text)
    board.write_text(board_text)
    print(f'Root, Data and log are confined to {PARTITION}. Partition: {PARTITION_GIB} GiB. Data: {DATA_GIB} GiB.')


if __name__ == '__main__':
    main()
