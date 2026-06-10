import zipfile
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "dist"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "dist",
}

EXCLUDED_TOP_LEVEL_DATA_DIRS = {
    Path("data/input"),
    Path("data/intermediate"),
    Path("data/output"),
}

EXCLUDED_SUFFIXES = {
    ".pyc",
}

EXCLUDED_NAMES = {
    ".DS_Store",
}


def should_include(path: Path) -> bool:
    rel = path.relative_to(BASE_DIR)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    if any(rel == excluded or excluded in rel.parents for excluded in EXCLUDED_TOP_LEVEL_DATA_DIRS):
        return False
    return True


def main():
    DIST_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = DIST_DIR / f"running_dinner_pipeline_{stamp}.zip"

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(BASE_DIR.rglob("*")):
            if path.is_file() and should_include(path):
                zf.write(path, path.relative_to(BASE_DIR))

        for folder in ["data/input", "data/intermediate", "data/output"]:
            zf.writestr(f"{folder}/.keep", "")

    print(archive_path)


if __name__ == "__main__":
    main()
