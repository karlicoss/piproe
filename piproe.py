#!/usr/bin/env python3
"""
Script to install pip packages in editable mode when they happen to be on a read only filesystem.
Currently it isn't possible, see a related issue: https://github.com/pypa/pip/issues/3930

Useful in Docker containers, when you don't want them to pollute your repo with extra files
"""

import argparse
import shutil
import site
import sys
from itertools import chain
from pathlib import Path
from subprocess import check_call
from tempfile import TemporaryDirectory


def should_ignore(path: str, names: list[str]) -> list[str]:  # noqa: ARG001
    return [
        '.tox',
        '.mypy_cache',
        '.pytest_cache',
        '__pycache__',
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
    assert path.exists(), path  # just in case

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

    for f in chain(
        sp.glob('*.egg-link'),
        [sp / 'easy-install.pth'],
        sp.glob('__editable__.*.pth'),
        sp.glob('*.dist-info/direct_url.json'),  # this is only used in pip freeze?
    ):
        if not f.exists():  # todo why wouldn't it exist??
            continue
        ft = f.read_text()
        if str(tgt) not in ft:
            continue
        f.write_text(ft.replace(str(tgt), str(path)))
        patched.append(f)

    # seems like editable packages installed with setuptools end up with a .py generated finder?
    # see here for more info
    # https://github.com/pypa/setuptools/blob/9cc2f5c05c333cd4cecd2c0d9e7c5e208f2a3148/setuptools/command/editable_wheel.py#L824-L826
    for f in sp.glob('__editable__*_finder.py'):
        ft = f.read_text()
        if f"'{tgt}" not in ft:
            continue
        # replace occurences starting with a single quote, just for safety
        f.write_text(ft.replace(f"'{tgt!s}", f"'{path!s}"))
        patched.append(f)

    # todo assert no other tmp occurences in site packages dir?
    if len(patched) == 0:
        raise RuntimeError('Nothing was patched.. suspicious')


if __name__ == '__main__':
    main()

