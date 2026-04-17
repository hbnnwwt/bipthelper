# Root Directory Cleanup Design

## Goal

Reduce root directory clutter by reorganizing third-party vendor files and scripts into structured subdirectories.

## Current State

Root contains ~30 items mixing source code, vendor binaries, scripts, and documentation:
- `python_portable/` - portable Python runtime
- `meilisearch.exe`, `qdrant.exe` - search engine binaries
- `vcruntime140.dll`, `vcruntime140_1.dll` - VC++ runtime DLLs
- `build.bat`, `dev.bat`, `run.bat`, `setup.bat`, `test_implementation.sh` - scripts
- `cookies.txt`, `pagination-selector.txt` - config files
- `.impeccable.md`, `FINAL_SUMMARY.md`, `IMPLEMENTATION_SUMMARY.md` - docs

## Target Structure

```
bipthelper/
├── backend/              # Source code (unchanged)
├── frontend/             # Frontend source (unchanged)
├── vendor/               # Third-party runtimes
│   ├── python/           # python_portable moved here
│   ├── meilisearch.exe   # moved from root
│   ├── qdrant.exe        # moved from root
│   └── runtime/          # vcruntime DLLs moved here
├── scripts/              # All scripts
│   ├── setup.bat
│   ├── build.bat
│   ├── dev.bat
│   ├── run.bat
│   └── test_implementation.sh
├── config/               # Configuration files
│   ├── cookies.txt       # moved from root
│   ├── pagination-selector.txt  # moved from root
│   └── qdrant.yaml       # (already here)
├── data/                  # Data directory (unchanged)
├── docs/                  # Documentation
│   ├── .impeccable.md    # moved from root
│   ├── FINAL_SUMMARY.md  # moved from root
│   └── IMPLEMENTATION_SUMMARY.md  # moved from root
├── .gitignore
└── README.md
```

## Changes Required

### Batch Scripts (4 files need path updates)

All scripts reference `python_portable`, `meilisearch.exe`, `qdrant.exe` using `%~dp0` (script directory) relative paths. These need updating:

| Script | Changes |
|--------|---------|
| `setup.bat` | `python_portable` → `vendor\python`, copy DLLs to `vendor\runtime`, download meilisearch/qdrant to `vendor` |
| `build.bat` | Node.js logic unchanged, `cd frontend` unchanged |
| `run.bat` | `python_portable` → `vendor\python`, meilisearch/qdrant paths updated |
| `dev.bat` | Similar path updates |

### Config Files (2 files)

- `cookies.txt` → `config/cookies.txt`
- `pagination-selector.txt` → `config/pagination-selector.txt`

### Documentation Files (3 files)

- `.impeccable.md` → `docs/.impeccable.md`
- `FINAL_SUMMARY.md` → `docs/FINAL_SUMMARY.md`
- `IMPLEMENTATION_SUMMARY.md` → `docs/IMPLEMENTATION_SUMMARY.md`

### Python Code

No changes required. Python code uses `import qdrant_client` / `import meilisearch` (pip packages), not hardcoded paths.

### Git State

The current git status shows many deleted `data.ms/` and `data/htmls/` files already tracked. The cleanup will add those deletions as part of the commit naturally.

## Implementation Order

1. Move vendor files (python_portable, meilisearch.exe, qdrant.exe, DLLs)
2. Move config files
3. Move documentation files
4. Update batch script paths
5. Update `.gitignore` if needed
6. Commit
