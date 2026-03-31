#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse

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
        if dep_name:
            # modinfo often returns just 'name', we need to check for 'name.ko'
            if not dep_name.endswith(".ko"):
                dep_name += ".ko"
            collect_all_dependencies(build_dir, dep_name, visited)

    return visited

def main():
    parser = argparse.ArgumentParser(description="Collect kernel module dependencies.")
    parser.add_argument("build_dir", help="Kernel build output directory")
    parser.add_argument("modules", nargs="*", help="Module names (used only with --non-interactive)")
    parser.add_argument("--non-interactive", action="store_true", help="Get input from params and suppress UI text")

    args = parser.parse_args()

    if not os.path.isdir(args.build_dir):
        print(f"Error: {args.build_dir} is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    input_modules = []

    if args.non_interactive:
        # Get modules from the command line arguments
        input_modules = [m for m in args.modules if m and not m.startswith("#")]
    else:
        # Interactive mode: Get modules from stdin
        print("Enter module names (one per line). End with Ctrl+D (Linux/macOS) or Ctrl+Z (Windows):", file=sys.stderr)
        for line in sys.stdin:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            input_modules.append(line)

        if not args.non_interactive:
            print("\n--- End of input. Processing dependencies... ---\n", file=sys.stderr)

    all_deps = set()
    for mod in input_modules:
        all_deps |= collect_all_dependencies(args.build_dir, mod)

    # Normalize input module names (with .ko suffix) for subtraction
    input_mods_normalized = set(m if m.endswith(".ko") else m + ".ko" for m in input_modules)

    # Remove original modules from dependency set
    result_mods = sorted(all_deps - input_mods_normalized)

    # Header is only printed in interactive mode
    if not args.non_interactive:
        print("\n--- Dependency modules ---\n", file=sys.stderr)

    # Print the resulting module names
    for mod in result_mods:
        print(mod)

if __name__ == "__main__":
    main()
