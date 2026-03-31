# EnvDeps

An 'environment-aware' Python project dependency scanner and analyzer.


`envdeps` can:
- Intelligently scan your python project and get all the dependencies you *actually* used.
- Automatically create or update a dependency file format with version specifiers based on your installed packages versions.
- Finely-control how the scanned dependencies merge with entries in your existing dependency file(s).
- Scan both python files and '.ipynb' notebooks.

Envdeps does *not* need to be installed in each project environment. With `envdeps` available on `$PATH`, run in any of your local project directories.


## Quickstart

If scanning a project with an isolated environment (i.e. venv), make sure the project's venv is activated in shell when running `envdeps`.

Scan your python project, export to a requirements.txt file.

```{sh}
envdeps export --target='src/coolpkg' --root='.' --specifier='>=' requirements.txt
```
Created 'requirements.txt' file:
```{requirements}
requests>=2.32.
polars>=1.33.1
pydantic>=2.11.5
```

View used project dependencies and other info in a table

```{sh}
envdeps show --target='src/coolpkg' --root='.' --format=table --verbose
```
```{sh}
        Scanned Packages in 'coolpkg'         
┏━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Package  ┃ Version ┃ Used in               ┃
┡━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ requests │ 2.32.3  │ ['main.py', ... +5]   │
│ pydantic │ 2.11.5  │ ['data.py', ... +4]   │
│ polars   │ 1.33.1  │ ['parser.py', ... +2] │
└──────────┴─────────┴───────────────────────┘
              Env: '.venv'              
```

## Installation

One benefit of envdeps is that it does not require installation into each environment you wish to use.

It is recommended to install with `pipx` so that `envdeps` is globally available, even when different python environments are active.

```{sh}
# Install globally with 'pipx'
pipx install git+https://github.com/dominicmancini/envdeps.git
```

## Commands and Options

Base Arguments:

The following arguments apply to all `envdeps` commands.

- `-t/--target`: Target directory within project containing python source files to scan (recursively). (Fallbacks to CWD.)
- `-r/--root`: Root directory of the project to scan (defaults to CWD)
- `-e/--env-prefix`: The Environment prefix for the python environment. Tries to resolve by multiple methods:
    * In order: Values of `$VIRTUAL_ENV`, `$CONDA_PREFIX`, `$PYENV_VIRTUAL_ENV`. Fallback to the value of `sys.prefix`
- `-i/--ignore`: Comma-separated list of directory names to ignore (by default merges with list of common ignored directories)
- `--ipynb`: Whether to scan python notebooks ('.ipynb' files) in addition to '.py' files?



### `show`

To quickly print out a summary of your projects used dependencies.

Options:
- `-f/--format`: One of `text,json,table`. Useful for piping into other tools.
- `--verbose`: Show which files & imports triggered each dependency.

#### `show` example:

```{sh}
envdeps show --target=envdeps --format=table
```
Output:

```{sh}
             Scanned Packages in 'envdeps'             
┏━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Package   ┃ Version ┃ Used in                       ┃
┡━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ packaging │ 26.0    │ ['envdeps/parse.py', ... +4]  │
│ Pygments  │ 2.19.2  │ ['envdeps/output.py']         │
│ rich      │ 14.3.3  │ ['envdeps/output.py', ... +2] │
│ loguru    │ 0.7.3   │ ['envdeps/parse.py', ... +5]  │
│ tomlkit   │ 0.14.0  │ ['envdeps/utils.py', ... +1]  │
└───────────┴─────────┴───────────────────────────────┘
                  Env: '.venv'                  
```

### `export`

Scan used project dependencies and export to either a 'requirements.txt' or 'pyproject.toml' file.

Required Arguments:
- `path`: Path to desired output file. Relative paths are interpreted relative to `--root`.

Options to control formatting:
- `-f/--format`: One of `pyproject,requirements`. If not specified, will be determined from `path` extension.
- `-s/--specifier`: The version specifier operator to use (e.g. '>=', '=='). If blank, no version specifier is used. [See: PyPa Requirement Specifiers](https://pip.pypa.io/en/stable/reference/requirement-specifiers/#requirement-specifiers)
If the file `path` exists with existing entries, there are several options to control merge behavior (or overwrite if desired)

- `--merge/--no-merge`: Whether to merge with existing dependency entries specified in `path` (Default `True`). If `--no-merge`, scanned dependencies will overwrite existing entries.

Merge Options:
- `--remove-unknown`: Whether to remove unknown entries from existing dependencies, this may include specifiers such as those using pip args & local paths (i.e., `-e ~/some_local_package`) and other non-standard formats (Default **False**)
- `--remove-unused`: Whether to remove existing dependency entries that were not found from scanning used project dependencies. (Default **False**)
- `--update-existing`: When a scanned dependency already has an entry in existing dependencies, replace the entry to use the given `--specifier` and scanned version?

#### `export` example


**'pyproject.toml' Before Scan:**
```{toml}
[project]
name = "foo"
version = "0.1.0"
description = "Foo bar"
dependencies = [
	"typer",
	"rich",
	"pandas",
	"numpy"
]


```
Running Command:
`envdeps export --target src/foo --merge --update-existing --specifier '>=' --remove-unused --remove-unknown pyproject.toml`

**'pyproject.toml' After Scanning**:
``
```{toml}
[project]
name = "foo"
version = "0.1.0"
description = "Foo bar"
dependencies = [
    "pandas>=2.3.0",
    "humanize>=4.12.3",
    "duckdb>=1.4.0",
    "polars>=1.33.1",
    "typing_extensions>=4.15.0",
    "typer-slim>=0.20.1",
    "platformdirs>=4.3.8",
    "rich>=14.2.0",
    "PyPika>=0.48.9"
]
```
- Updated to include dependencies actually imported in project.
- Because of `--remove-unused`, it removed unused dependencies (e.g. `numpy`)
- `--update-existing` updated existing entries with the version specifier



## Planned features:

- [x] Implement scanning of `.ipynb` python notebooks
- [ ] Extend to other dependency formats (i.e. lock files, etc.)



