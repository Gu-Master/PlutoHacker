#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
JOBS="${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)}"

sanitize_runtime_environment() {
    local launched_from_snap=0

    if [[ -n "${SNAP:-}" ]] \
        || [[ "${GTK_PATH:-}" == /snap/* ]] \
        || [[ "${GTK_EXE_PREFIX:-}" == /snap/* ]]; then
        launched_from_snap=1
    fi

    if [[ "$launched_from_snap" -eq 0 ]]; then
        return
    fi

    unset GIO_MODULE_DIR
    unset GTK_PATH
    unset GTK_MODULES
    unset GTK3_MODULES
    unset GTK_EXE_PREFIX
    unset GTK_IM_MODULE_FILE

    unset SNAP
    unset SNAP_ARCH
    unset SNAP_COMMON
    unset SNAP_CONTEXT
    unset SNAP_COOKIE
    unset SNAP_DATA
    unset SNAP_EUID
    unset SNAP_INSTANCE_NAME
    unset SNAP_LAUNCHER_ARCH_TRIPLET
    unset SNAP_LIBRARY_PATH
    unset SNAP_NAME
    unset SNAP_REAL_HOME
    unset SNAP_REVISION
    unset SNAP_UID
    unset SNAP_USER_COMMON
    unset SNAP_USER_DATA
    unset SNAP_VERSION

    if [[ -n "${XDG_DATA_DIRS_VSCODE_SNAP_ORIG:-}" ]]; then
        export XDG_DATA_DIRS="$XDG_DATA_DIRS_VSCODE_SNAP_ORIG"
    fi
}

sanitize_runtime_environment

cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

usage() {
    cat <<'EOF'
Usage:
  ./run_plutosdr.sh [--check] [--rebuild] [--skip-build] [app args...]

Options:
  --check       Verify dependencies/extensions and exit without launching.
  --rebuild     Force rebuilding Cython and PlutoSDR native extensions.
  --skip-build  Do not build missing extensions automatically.

Environment:
  PYTHON=/path/to/python3  Use a custom Python interpreter.
  JOBS=4                  Override parallel build jobs.
EOF
}

CHECK_ONLY=0
FORCE_REBUILD=0
SKIP_BUILD=0
APP_ARGS=()

while (($#)); do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --check)
            CHECK_ONLY=1
            shift
            ;;
        --rebuild)
            FORCE_REBUILD=1
            shift
            ;;
        --skip-build)
            SKIP_BUILD=1
            shift
            ;;
        *)
            APP_ARGS+=("$1")
            shift
            ;;
    esac
done

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python interpreter not found: $PYTHON_BIN" >&2
    exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys

if sys.version_info < (3, 9):
    raise SystemExit("Python 3.9 or newer is required.")

required = {
    "PyQt6": "PyQt6",
    "numpy": "numpy<3.0",
    "psutil": "psutil",
    "Cython": "cython",
    "setuptools": "setuptools",
}
missing = []
for module, package in required.items():
    try:
        __import__(module)
    except ImportError:
        missing.append(package)

if missing:
    print("Missing Python packages: " + ", ".join(missing), file=sys.stderr)
    print(
        "Install them, for example: "
        + sys.executable
        + " -m pip install "
        + " ".join(missing),
        file=sys.stderr,
    )
    raise SystemExit(1)
PY

needs_build() {
    "$PYTHON_BIN" - <<'PY'
modules = (
    "urh.cythonext.signal_functions",
    "urh.cythonext.path_creator",
    "urh.cythonext.util",
    "urh.dev.native.lib.plutosdr",
)

missing = []
for module in modules:
    try:
        __import__(module)
    except Exception as exc:
        missing.append(f"{module}: {exc}")

if missing:
    print("Missing or unusable compiled extensions:")
    print("\n".join("  " + item for item in missing))
    raise SystemExit(1)
PY
}

if [[ "$FORCE_REBUILD" -eq 1 ]] || ! needs_build; then
    if [[ "$SKIP_BUILD" -eq 1 ]]; then
        echo "Compiled extensions are missing and --skip-build was set." >&2
        exit 1
    fi

    echo "Building Cython and PlutoSDR native extensions..."
    if ! "$PYTHON_BIN" setup.py build_ext --inplace -j"$JOBS" --with-plutosdr; then
        cat >&2 <<'EOF'
Build failed.

For PlutoSDR native support on Debian/Ubuntu install libiio development files,
then run this script again:
  sudo apt install libiio-dev
EOF
        exit 1
    fi

    needs_build
fi

if [[ "$CHECK_ONLY" -eq 1 ]]; then
    echo "Launch check passed. PlutoSDR Protocol Tool is ready."
    exit 0
fi

exec "$PYTHON_BIN" -m urh.main "${APP_ARGS[@]}"
