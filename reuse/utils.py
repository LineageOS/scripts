import sys
from subprocess import Popen, PIPE


def run_subprocess(cmd, silent=False):
    p = Popen(cmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    comm = p.communicate()
    exit_code = p.returncode
    if exit_code != 0 and not silent:
        print(
            "There was an error running the subprocess.\n"
            "cmd: %s\n"
            "exit code: %d\n"
            "stdout: %s\n"
            "stderr: %s" % (cmd, exit_code, comm[0], comm[1]),
            file=sys.stderr,
        )
    return comm, exit_code


def check_run(cmd):
    p = Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    ret = p.wait()
    if ret != 0:
        joined = " ".join(cmd)
        print(f"Failed to run cmd: {joined}", file=sys.stderr)
        sys.exit(ret)


def check_dependencies():
    # Check for Java version of crowdin
    cmd = ["which", "pipx"]
    msg, code = run_subprocess(cmd, silent=True)
    if code != 0:
        print("You have not installed pipx.", file=sys.stderr)
        return False
    return True
