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
    p.add_argument('--no-editable', action='store_false', dest='editable')  # meh
    p.add_argument('path', type=Path)
    args, rest = p.parse_known_args()
    path = args.path

    user_install_requested = '--user' in sys.argv

    split = path.name.split('[')  # handle optional deps
    name = split[0]
    opts = ''
    if len(split) == 2:
        opts = '[' + split[1]
    path = path.parent / name
    assert path.exists()  # just in case

    with TemporaryDirectory() as td:
        tgt = Path(td) / path.name
        shutil.copytree(path, tgt, symlinks=True, ignore=should_ignore)
        meditable = ['--editable'] if args.editable else []
        check_call([sys.executable, '-m', 'pip', 'install', *rest, *meditable, str(tgt) + opts])
        # TODO need to infer the site from pip?

    if not args.editable:
        # no need to patch anything
        return

    # actual site might differ from requested site
    # since pip falls back onto user site e.g. if we're not installing as root
    from pip._internal.commands import install as pip_install
    installed_into_user_site = pip_install.decide_user_install(
        use_user_site=True if user_install_requested else None,
    )

    # hmm, getusersitepackages isn't working under pyenv
    if installed_into_user_site:
        sp = Path(site.getusersitepackages())
    else:
        [sp] = map(Path, site.getsitepackages())
    print("SITE:", sp, file=sys.stderr)
    print(f"replacing {tgt} with {path}", file=sys.stderr)
    patched = []

    # TODO not sure if need to remove old egg-links after switching to pyproject toml?
    for f in chain(
            sp.glob('*.egg-link'),
            [sp / 'easy-install.pth'],
            sp.glob('__editable__.*.pth'),
            sp.glob('*.dist-info/direct_url.json'),  # this is only used in pip freeze?
    ):
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
