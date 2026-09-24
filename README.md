# Building Estimate

Offline Windows desktop foundation for preparing building civil engineering estimates.

## Current scope

The application provides a PySide6 window for creating, saving, and reopening building projects. The `BOQ and measurements` tab supports BOQ item editing, manual development rates, reordering, deletion, and detailed volume, area, length, count, and direct-quantity measurements. It stores SQLite data in the per-user application-data directory, not in the source or installation directory.

Manual rates are labelled `Unverified manual rate`. This step contains no CPWD DSR catalogue or invented CPWD rates. Rate import, estimate revisions, materials abstracts, taxes, contingencies, and report export are deferred.

## BOQ calculation rules

Dimensional inputs use metres. A measurement's quantity is calculated as:

- Volume: repetitions x number x length x breadth x height/depth
- Area: repetitions x number x length x breadth
- Length: repetitions x number x length
- Count: repetitions x number
- Direct quantity: the entered quantity in the BOQ item's unit

All inputs are stored and calculated as `Decimal` text values. Full precision is retained until display; quantities display to 3 decimal places and money to 2 decimal places using `ROUND_HALF_UP`. Amounts use the displayed, rounded BOQ quantity. Additions and deductions are shown separately. Missing measurements, missing rates, and explicit zero rates remain distinct; negative net quantities are flagged and cannot be finalised.

Changing a unit after measurements exist requires explicit confirmation and clears those measurements only after confirmation.

## Using the BOQ editor

Open or create a project, then select the `BOQ and measurements` tab. Create a BOQ item with its work section, text DSR code, description, unit, quantity type, and optional development rate. Select the item to add or edit measurements. Select an item row to reopen its saved measurements. The DSR catalogue and verified CPWD source data are not part of this step.

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
