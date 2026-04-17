# Root Directory Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize root directory from ~30 mixed items into clean structure with vendor/, scripts/, config/, docs/ subdirectories.

**Architecture:** Move third-party binaries and scripts out of root. Update batch script paths to reflect new locations. Python code requires no changes.

**Tech Stack:** Windows batch scripts, file system operations.

---

## File Map

| Operation | Source | Destination |
|-----------|--------|-------------|
| Move | `python_portable/` | `vendor/python/` |
| Move | `meilisearch.exe` | `vendor/meilisearch.exe` |
| Move | `qdrant.exe` | `vendor/qdrant.exe` |
| Move | `vcruntime140.dll` | `vendor/runtime/vcruntime140.dll` |
| Move | `vcruntime140_1.dll` | `vendor/runtime/vcruntime140_1.dll` |
| Move | `setup.bat` | `scripts/setup.bat` |
| Move | `build.bat` | `scripts/build.bat` |
| Move | `dev.bat` | `scripts/dev.bat` |
| Move | `run.bat` | `scripts/run.bat` |
| Move | `test_implementation.sh` | `scripts/test_implementation.sh` |
| Move | `cookies.txt` | `config/cookies.txt` |
| Move | `pagination-selector.txt` | `config/pagination-selector.txt` |
| Move | `.impeccable.md` | `docs/.impeccable.md` |
| Move | `FINAL_SUMMARY.md` | `docs/FINAL_SUMMARY.md` |
| Move | `IMPLEMENTATION_SUMMARY.md` | `docs/IMPLEMENTATION_SUMMARY.md` |

**Scripts to modify (in new location):**
- `scripts/setup.bat` - 5 path changes
- `scripts/run.bat` - 4 path changes
- `scripts/dev.bat` - 6 path changes
- `scripts/build.bat` - no changes needed

---

## Task 1: Move vendor files

- [ ] **Step 1: Create vendor directory structure**

Run:
```bash
mkdir -p vendor/runtime
```

- [ ] **Step 2: Move Python runtime**

Run:
```bash
mv python_portable vendor/python
```

- [ ] **Step 3: Move search engine binaries**

Run:
```bash
mv meilisearch.exe vendor/meilisearch.exe
mv qdrant.exe vendor/qdrant.exe
```

- [ ] **Step 4: Move VC++ runtime DLLs**

Run:
```bash
mv vcruntime140.dll vendor/runtime/vcruntime140.dll
mv vcruntime140_1.dll vendor/runtime/vcruntime140_1.dll
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: move vendor files to vendor/ subdirectory"
```

---

## Task 2: Move config and doc files

- [ ] **Step 1: Move config files**

Run:
```bash
mv cookies.txt config/cookies.txt
mv pagination-selector.txt config/pagination-selector.txt
```

- [ ] **Step 2: Move documentation files**

Run:
```bash
mv .impeccable.md docs/.impeccable.md
mv FINAL_SUMMARY.md docs/FINAL_SUMMARY.md
mv IMPLEMENTATION_SUMMARY.md docs/IMPLEMENTATION_SUMMARY.md
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor: move config and doc files to subdirectories"
```

---

## Task 3: Move script files

- [ ] **Step 1: Move all scripts to scripts/**

Run:
```bash
mv setup.bat scripts/setup.bat
mv build.bat scripts/build.bat
mv dev.bat scripts/dev.bat
mv run.bat scripts/run.bat
mv test_implementation.sh scripts/test_implementation.sh
```

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "refactor: move scripts to scripts/ subdirectory"
```

---

## Task 4: Update setup.bat paths

**Files:**
- Modify: `scripts/setup.bat`

The following lines need changes (using `replace_all` for each distinct string):

| Line | Old | New |
|------|-----|-----|
| 11 | `set "PYTHON_DIR=%PROJECT_DIR%python_portable"` | `set "PYTHON_DIR=%PROJECT_DIR%vendor\python"` |
| 98 | `copy /Y "%PYTHON_DIR%\vcruntime140.dll" "%PROJECT_DIR%vcruntime140.dll"` | `copy /Y "%PYTHON_DIR%\vcruntime140.dll" "%PROJECT_DIR%vendor\runtime\vcruntime140.dll"` |
| 103 | `copy /Y "%PYTHON_DIR%\vcruntime140_1.dll" "%PROJECT_DIR%vcruntime140_1.dll"` | `copy /Y "%PYTHON_DIR%\vcruntime140_1.dll" "%PROJECT_DIR%vendor\runtime\vcruntime140_1.dll"` |
| 108 | meilisearch download target `%PROJECT_DIR%meilisearch.exe` | `%PROJECT_DIR%vendor\meilisearch.exe` |
| 126 | qdrant download target `%PROJECT_DIR%qdrant.zip` and extract to `%PROJECT_DIR%` | `%PROJECT_DIR%vendor\qdrant.zip` and extract to `%PROJECT_DIR%vendor\` |

Note: The meilisearch/qdrant download lines use inline `if exist` checks. The exact strings to find/replace are the `OutFile` paths and `DestinationPath` in the powershell commands.

- [ ] **Step 1: Update PYTHON_DIR path**

Edit `scripts/setup.bat` line 11:
- Old: `set "PYTHON_DIR=%PROJECT_DIR%python_portable"`
- New: `set "PYTHON_DIR=%PROJECT_DIR%vendor\python"`

- [ ] **Step 2: Update DLL copy destination paths**

Edit `scripts/setup.bat` lines 98 and 103 - change copy destination from `%PROJECT_DIR%` to `%PROJECT_DIR%vendor\runtime\`

- [ ] **Step 3: Update meilisearch download path**

Edit line 118 - change `OutFile` from `%PROJECT_DIR%meilisearch.exe` to `%PROJECT_DIR%vendor\meilisearch.exe`

- [ ] **Step 4: Update qdrant download and extract paths**

Edit line 126 - change `OutFile` to `%PROJECT_DIR%vendor\qdrant.zip` and `DestinationPath` to `%PROJECT_DIR%vendor\`

- [ ] **Step 5: Test setup.bat runs correctly**

Run: `cmd //c scripts\setup.bat`
Expected: Script executes without path errors (may fail at dependency install if network issues, but paths should resolve)

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(setup): update paths for vendor/ layout"
```

---

## Task 5: Update run.bat paths

**Files:**
- Modify: `scripts/run.bat`

| Line | Old | New |
|------|-----|-----|
| 14 | `%~dp0python_portable\python.exe` | `%~dp0vendor\python\python.exe` |
| 48-50 | `set "PYTHONHOME=%~dp0python_portable"` | `set "PYTHONHOME=%~dp0vendor\python"` |
| 54 | `%~dp0meilisearch.exe` | `%~dp0vendor\meilisearch.exe` |
| 61 | `%~dp0qdrant.exe` | `%~dp0vendor\qdrant.exe` |

- [ ] **Step 1: Update python_portable path checks**

Edit lines 14-15: change `python_portable` to `vendor\python`

- [ ] **Step 2: Update PYTHONHOME and PYTHONPATH**

Edit lines 48-50: change `python_portable` to `vendor\python`

- [ ] **Step 3: Update meilisearch path**

Edit line 54: change `%~dp0meilisearch.exe` to `%~dp0vendor\meilisearch.exe`

- [ ] **Step 4: Update qdrant path**

Edit line 61: change `%~dp0qdrant.exe` to `%~dp0vendor\qdrant.exe`

- [ ] **Step 5: Test run.bat syntax**

Run: `cmd //c scripts\run.bat` (it will show errors if paths wrong before trying to start services)

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(run): update paths for vendor/ layout"
```

---

## Task 6: Update dev.bat paths

**Files:**
- Modify: `scripts/dev.bat`

| Line | Old | New |
|------|-----|-----|
| 14 | `%~dp0python_portable\python.exe` | `%~dp0vendor\python\python.exe` |
| 47-49 | `set "PYTHONHOME=%~dp0python_portable"` | `set "PYTHONHOME=%~dp0vendor\python"` |
| 53 | `%~dp0meilisearch.exe` | `%~dp0vendor\meilisearch.exe` |
| 60 | `%~dp0qdrant.exe` | `%~dp0vendor\qdrant.exe` |
| 67 | error message text | updated message pointing to `vendor/` |

- [ ] **Step 1: Update python_portable path check**

Edit line 14-15: change `python_portable` to `vendor\python`

- [ ] **Step 2: Update PYTHONHOME and PYTHONPATH**

Edit lines 47-49: change `python_portable` to `vendor\python`

- [ ] **Step 3: Update meilisearch path**

Edit line 53: change `%~dp0meilisearch.exe` to `%~dp0vendor\meilisearch.exe`

- [ ] **Step 4: Update qdrant path**

Edit line 60: change `%~dp0qdrant.exe` to `%~dp0vendor\qdrant.exe`

- [ ] **Step 5: Update error message**

Edit line 67: change "Place meilisearch.exe in the current directory" to "Place meilisearch.exe in the vendor directory"

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix(dev): update paths for vendor/ layout"
```

---

## Task 7: Verify final structure and test

- [ ] **Step 1: Verify root directory is clean**

Run: `ls -la`
Expected: Only `backend/`, `frontend/`, `vendor/`, `scripts/`, `config/`, `data/`, `docs/`, `.gitignore`, `README.md`

- [ ] **Step 2: Verify vendor structure**

Run: `ls -la vendor/`
Expected: `python/`, `meilisearch.exe`, `qdrant.exe`, `runtime/`

- [ ] **Step 3: Verify scripts structure**

Run: `ls -la scripts/`
Expected: `setup.bat`, `build.bat`, `dev.bat`, `run.bat`, `test_implementation.sh`

- [ ] **Step 4: Full smoke test (setup -> build -> run)**

Run setup: `cmd //c scripts\setup.bat`
Run build: `cmd //c scripts\build.bat`
Run run: `cmd //c scripts\run.bat`

Verify all three complete without path-related errors.

- [ ] **Step 5: Final commit**

```bash
git add -A && git commit -m "refactor: complete root directory cleanup - vendor/scripts/config/docs reorganization"
```

---

## Spec Coverage Check

- [x] Move vendor files to vendor/ — Task 1
- [x] Move config files to config/ — Task 2
- [x] Move docs to docs/ — Task 2
- [x] Move scripts to scripts/ — Task 3
- [x] Update setup.bat paths — Task 4
- [x] Update run.bat paths — Task 5
- [x] Update dev.bat paths — Task 6
- [x] build.bat needs no changes (frontend path unchanged) — verified
- [x] .gitignore — no changes needed (existing entries cover new structure)
- [x] Python code unchanged — verified (no hardcoded vendor paths)
- [x] Smoke test — Task 7
