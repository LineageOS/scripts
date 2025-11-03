#!/usr/bin/env python3
import os
import sys
import subprocess

def find_module_path(build_dir, module_name):
    """Search for a .ko file under build_dir matching module_name."""
    for root, _, files in os.walk(build_dir):
        if module_name in files:
            return os.path.join(root, module_name)
    return None

def get_module_dependencies(mod_path):
    """Return a list of dependencies for the given module using modinfo."""
    try:
        result = subprocess.run(
            ["/usr/sbin/modinfo", "-F", "depends", mod_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        deps = result.stdout.strip()
        if not deps:
            return []
        return [dep.strip() for dep in deps.split(",") if dep.strip()]
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"Warning: failed to get dependencies for {mod_path}: {e}\n")
        return []

def collect_all_dependencies(build_dir, module_name, visited=None):
    """Recursively collect all dependencies for the given module."""
    if visited is None:
        visited = set()

    module_name = module_name.strip()
    if not module_name:
        return visited

    if not module_name.endswith(".ko"):
        module_name += ".ko"

    if module_name in visited:
        return visited

    mod_path = find_module_path(build_dir, module_name)
    if not mod_path:
        sys.stderr.write(f"Warning: module {module_name} not found in {build_dir}\n")
        return visited

    visited.add(module_name)

    for dep in get_module_dependencies(mod_path):
        dep_name = dep.strip()
        if dep_name and not dep_name.endswith(".ko"):
            dep_name += ".ko"
        collect_all_dependencies(build_dir, dep_name, visited)

    return visited


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <kernel_build_output_dir>", file=sys.stderr)
        sys.exit(1)

    build_dir = sys.argv[1]
    if not os.path.isdir(build_dir):
        print(f"Error: {build_dir} is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    modules = []
    print("Enter module names (one per line). End with Ctrl+D (Linux/macOS) or Ctrl+Z (Windows):", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        modules.append(line)

    print("\n--- End of input. Processing dependencies... ---\n", file=sys.stderr)

    all_deps = set()
    for mod in modules:
        all_deps |= collect_all_dependencies(build_dir, mod)

    # Normalize input module names (with .ko suffix)
    input_mods = set(m if m.endswith(".ko") else m + ".ko" for m in modules)

    # Remove original modules from dependency set
    result_mods = sorted(all_deps - input_mods)

    print("\n--- Dependency modules ---\n", file=sys.stderr)
    for mod in result_mods:
        print(mod)


if __name__ == "__main__":
    main()
