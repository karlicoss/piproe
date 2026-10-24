# piproe

Install Python packages in editable mode from a read-only directory (e.g. a code checkout bind-mounted read-only into a Docker container), without writing anything into it.

## You may not need this

`piproe` predates a much simpler workaround, which covers the setuptools case with plain `pip`/`uv`.

The only thing an editable install writes into the source tree is setuptools' `<name>.egg-info` directory, created by its `egg_info` command during the build.
Since setuptools 65.4 (September 2022, [pypa/distutils#177](https://github.com/pypa/distutils/pull/177)), an extra distutils config file can be passed via the `DIST_EXTRA_CONFIG` environment variable.
That config can point `egg_info` at a writable directory instead:

```bash
egg_base=$(mktemp -d)
printf '[egg_info]\negg_base = %s\n' "$egg_base" > "$egg_base/egg_base.cfg"
DIST_EXTRA_CONFIG="$egg_base/egg_base.cfg" uv pip install --editable /path/to/readonly/package
rm -r "$egg_base"
```

`pip install --editable` works the same way.

- The egg-info is only needed during the build.
  With PEP 660 editable installs (setuptools >= 64), the installed package gets its own `.dist-info` in site-packages, so the directory can be removed right after.
- Build isolation installs the latest setuptools anyway, unless the project pins an older one in `build-system.requires`.
- Other build backends (hatchling, uv_build, flit, pdm-backend) don't write into the source tree, so plain `pip install --editable` already works for them.
- The variable is only read by setuptools, so it's safe to set for a whole install command, including dependencies built from sdists.
- It doesn't help if the build writes anything else into the source tree, e.g. setuptools C extensions (built in place for editable installs) or a `setuptools_scm` version file.

## How it works

1. Copies the package into a temporary directory (skipping caches like `.tox`, `.mypy_cache`, `__pycache__` and `node_modules`).
2. Runs `pip install --editable` on the copy.
3. Replaces the temporary path with the original one in the files generated in site-packages:
   `*.egg-link`, `easy-install.pth`, `__editable__.*.pth`, `__editable___*_finder.py` and `*.dist-info/direct_url.json`.

## Usage

Run it with the Python of the target environment, which needs `pip` installed (`piproe` calls `python -m pip` and uses pip internals to find the site-packages directory):

```bash
python3 piproe.py /path/to/package --no-deps
```

- Extras go after the path, e.g. `/path/to/package[extra1,extra2]`.
- Any arguments other than the path and `--no-editable` are passed to `pip install`.
- `--no-editable` does a regular install from the copy, so nothing needs patching.

See [pypa/pip#3930](https://github.com/pypa/pip/issues/3930) for the underlying pip issue.
