# BananaWorldEditor
Universal map editor for 3D games.

- **Terrain editor** — visual grid editing for outdoor maps
- **House editor** — walls, roofs, furniture, interiors
- **Headless CLI** (`bwe_cli.py`) — same model layer as the GUI, for
  scripts and AI harnesses

AI can generate more and more game content, but level design stays a
human's responsibility. In a masterpiece — as opposed to neuroslop — the
level designer is the main person, and they need at least visualization
and convenient instruments.

Future plans: see [ROADMAP.md](ROADMAP.md).

# Status
Both editors (terrain and house) are implemented, plus the headless CLI
driving the same model layer.

Warning: Project is not finished. Interfaces and file format can be changed in the future.

# Map example
![House editor](doc/houseExample.jpg)
![House map rendered in Unity](doc/houseExampleUnity.png)

## Installation

The editor is installed and run with [uv](https://docs.astral.sh/uv/) —
uv replaces pip, and `requirements.txt` no longer exists: dependencies are
declared in `pyproject.toml` and pinned in `uv.lock`.

To install and use **BananaWorldEditor**, follow these steps:

1. Install uv with the official installer:

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2. Clone the repository:

    ```bash
    git clone https://github.com/vitperov/BananaWorldEditor.git
    cd BananaWorldEditor
    ```

3. Create the environment and install the dependencies:

    ```bash
    uv sync
    ```

4. Run from the editor root — the editor:

    ```bash
    uv run BananaWorldEditor.py
    ```

    and the headless CLI:

    ```bash
    uv run bwe_cli.py <command>
    ```

The CLI can also be run from a different working directory (map-file
arguments still resolve against your current directory) — point uv at the
project and give the path to the script:

```bash
uv run --project <path-to-BananaWorldEditor> <path-to-BananaWorldEditor>/bwe_cli.py <command>
```

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2022-2026 Vitaly Perov.


