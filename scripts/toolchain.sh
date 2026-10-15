# Source from scripts that have already set project_dir. Only adjusts this process.
if ! command -v node >/dev/null 2>&1; then
    for node_dir in "$project_dir"/.tools/node-*/bin; do
        if [ -x "$node_dir/node" ]; then
            export PATH="$node_dir:$PATH"
            break
        fi
    done
fi
