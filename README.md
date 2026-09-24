# Building Estimate

Offline Windows desktop foundation for preparing building civil engineering estimates.

## Scope of this step

The application currently provides a PySide6 window for creating, saving, and reopening project metadata. It stores SQLite data in the per-user application-data directory, not in the source or installation directory. Detailed measurements, rate schedules, estimate revisions, and a separate materials abstract are intentionally deferred.

The rate and data rules for future work are recorded in [docs/PROJECT_INSTRUCTIONS.md](docs/PROJECT_INSTRUCTIONS.md).

## Development setup

From the repository root on Windows or Linux:

```text
python -m venv .venv
```

Windows PowerShell:

```text
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python -m estimate_app.main
```

Codespaces/Linux:

```text
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m estimate_app.main
```

On an Ubuntu 24.04 Codespace, install the Qt runtime libraries before running
the headless checks:

```text
sudo apt-get update
sudo apt-get install -y libgl1 libxkbcommon0 libegl1
```

These packages provide `libGL.so.1`, `libxkbcommon.so.0`, and `libEGL.so.1`.
The smoke test uses `QT_QPA_PLATFORM=offscreen`, so it is a Linux headless
check and is not Windows GUI validation.

For a real offline Windows installation, install the pinned/approved dependencies on a connected build machine, package the application with the team's chosen Windows packaging process, and test the produced executable on a clean Windows machine. The application database belongs under `%LOCALAPPDATA%\\BuildingEstimate\\estimate.sqlite3` (falling back to `%APPDATA%` when needed).

## Checks

Run the automated persistence checks with:

```text
python -m pytest -q
```

Run the full Linux headless check with:

```text
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

In Codespaces, a desktop display is required for the PySide6 window. Use a Codespaces GUI/desktop extension or X11/Wayland forwarding, then run `python -m estimate_app.main`; verify that the window opens, a project saves, and selecting it reopens its fields. These checks validate the Linux development environment and application flow only. They do not replace testing the packaged application on actual offline Windows, including its user-data path, display behavior, and packaging dependencies.
