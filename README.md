**pyoncatqt README**
## Installation

Create and activate a virtual environment with [Pixi](https://pixi.sh/).
Prerequisites: Pixi installation e.g. for Linux:

```bash
curl -fsSL https://pixi.sh/install.sh | sh

```

Download the repository. Setup/Update the environment

```bash
pixi install
```

Enter the environment

```bash
pixi shell

```

The pyoncatqt environment is activated and the application is ready to use.


**Development/Deployment**


---

Any change to pyproject.toml, e.g. new dependencies, requires updating the pixi.lock file and including it in the commit.

```bash

pixi.lock

```

**Testing**

---

To run all tests for shiver
```bash

pytest
#or
python -m pytest
#or
pixi run test

```

To run pre-commit manually
```bash

pre-commit run --all-files

```

Or

To set the pre-commit hook before each git commit
```bash

pre-commit install

```

**Project Overview:**
pyoncatqt is a Python package designed to enhance the graphical user interface (GUI) experience for developers using the pyoncat library. pyoncat is a Python package for interacting with the ONCat API.
