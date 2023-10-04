#!/usr/bin/env python3
"""
Script to install pip packages in editable mode when they happen to be on a read only filesystem.
Currently it isn't possible, see a related issue: https://github.com/pypa/pip/issues/3930

Useful in Docker containers, when you don't want them to pollute your repo with extra files
"""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
from itertools import chain
import sys
import site
from subprocess import check_call
from typing import List


def should_ignore(path: str, names: List[str]) -> List[str]:
    return [
        '.tox', '.mypy_cache', '.pytest_cache', '__pycache__',
        'node_modules',
    ]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('path', type=Path)
    args, rest = p.parse_known_args()
    path = args.path

    with TemporaryDirectory() as td:
        tgt = Path(td) / path.name
        shutil.copytree(path, tgt, symlinks=True, ignore=should_ignore)
        check_call(['pip3', 'install', '-e', tgt, *rest])

    # hmm, getusersitepackages isn't working under pyenv
    if '--user' in sys.argv:
        sp = Path(site.getusersitepackages())
    else:
        [sp] = map(Path, site.getsitepackages())
    print("SITE:", sp, file=sys.stderr)
    print(f"replacing {tgt} with {path}", file=sys.stderr)
    patched = []

    # TODO not sure if need to remove old egg-links after switching to pyproject toml?
    for f in chain(sp.glob('*.egg-link'), [sp / 'easy-install.pth'], sp.glob('__editable__.*.pth')):
        if not f.exists():
            continue
        ft = f.read_text()
        if str(tgt) in ft:
            f.write_text(ft.replace(str(tgt), str(path)))
            patched.append(f)
    # todo assert no other tmp occurences in site packages dir?
    if len(patched) == 0:
        raise RuntimeError('Nothing was patched.. suspicious')


if __name__ == '__main__':
    main()
