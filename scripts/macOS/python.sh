# Shared Python discovery for macOS setup. Source after setting project_dir.
find_macos_python() {
    local candidate
    if [ -n "${PYTHON_BIN:-}" ]; then
        if "$PYTHON_BIN" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
            printf '%s\n' "$PYTHON_BIN"
            return
        fi
        echo "PYTHON_BIN must point to a working Python 3.12+ executable: $PYTHON_BIN" >&2
        return 1
    fi
    for candidate in \
        "$project_dir"/.tools/python/*/bin/python3 \
        python3.14 python3.13 python3.12 python3 \
        /opt/homebrew/bin/python3 /usr/local/bin/python3 \
        /opt/homebrew/opt/python@3.12/bin/python3.12 \
        /usr/local/opt/python@3.12/bin/python3.12 \
        /Library/Frameworks/Python.framework/Versions/3.*/bin/python3; do
        if "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
            # Resolve PATH commands before callers change directories.
            command -v "$candidate"
            return
        fi
    done
    echo "Python 3.12+ was not found. Install it, then rerun setup." >&2
    echo "With Homebrew: brew install python@3.12" >&2
    echo "Or set PYTHON_BIN=/absolute/path/to/python3.12" >&2
    return 1
}
