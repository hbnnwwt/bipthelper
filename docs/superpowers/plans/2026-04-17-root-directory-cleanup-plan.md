# Root Directory Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize root directory from ~30 mixed items into clean structure with vendor/, config/, docs/ subdirectories. Scripts (setup.bat, build.bat, dev.bat, run.bat) and test_implementation.sh remain at root — their internal paths already use `%~dp0vendor\` which resolves correctly from root.

**Architecture:** Move third-party binaries out of root. Python code requires no changes.

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
| Move | `cookies.txt` | `config/cookies.txt` |
| Move | `pagination-selector.txt` | `config/pagination-selector.txt` |
| Move | `.impeccable.md` | `docs/.impeccable.md` |
| Move | `FINAL_SUMMARY.md` | `docs/FINAL_SUMMARY.md` |
| Move | `IMPLEMENTATION_SUMMARY.md` | `docs/IMPLEMENTATION_SUMMARY.md` |

**Scripts kept at root:** `setup.bat`, `build.bat`, `dev.bat`, `run.bat`, `test_implementation.sh`
- These already use `%~dp0vendor\` which resolves to `E:\code\bipthelper\vendor\` from root
- No path changes needed in batch files

---

### Task 1: Move vendor files

- [ ] **Step 1: Create vendor directory structure**

```bash
mkdir -p vendor/runtime
```

- [ ] **Step 2: Move Python runtime**

```bash
mv python_portable vendor/python
```

- [ ] **Step 3: Move search engine binaries**

```bash
mv meilisearch.exe vendor/meilisearch.exe
mv qdrant.exe vendor/qdrant.exe
```

- [ ] **Step 4: Move VC++ runtime DLLs**

```bash
mv vcruntime140.dll vendor/runtime/vcruntime140.dll
mv vcruntime140_1.dll vendor/runtime/vcruntime140_1.dll
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "refactor: move vendor files to vendor/ subdirectory"
```

---

### Task 2: Move config and doc files

- [ ] **Step 1: Move config files**

```bash
mv cookies.txt config/cookies.txt
mv pagination-selector.txt config/pagination-selector.txt
```

- [ ] **Step 2: Move documentation files**

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

### Task 3: Verify final structure

- [ ] **Step 1: Verify root directory is clean**

Run: `ls -la`
Expected: Only `backend/`, `frontend/`, `vendor/`, `config/`, `data/`, `docs/`, `.gitignore`, `README.md`, plus the batch scripts at root

- [ ] **Step 2: Verify vendor structure**

Run: `ls -la vendor/`
Expected: `python/`, `meilisearch.exe`, `qdrant.exe`, `runtime/`

- [ ] **Step 3: Verify scripts still work**

Run setup: `cmd //c setup.bat` (paths resolve from root correctly)
Run build: `cmd //c build.bat`
Run dev: `cmd //c dev.bat`

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: complete root directory cleanup"
```

---

## Spec Coverage Check

- [x] Move vendor files to vendor/ — Task 1
- [x] Move config files to config/ — Task 2
- [x] Move docs to docs/ — Task 2
- [x] Scripts kept at root (no path changes needed) — verified
- [x] Smoke test — Task 3
