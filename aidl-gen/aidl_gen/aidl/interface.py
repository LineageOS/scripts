from aidl_gen.aidl.method import AIDLMethod
from pathlib import Path

class AIDLInterface:
    def __init__(self, file: Path):
        self.file = file

        self.methods = []
        self.imports = []
        open_comment = False
        inside_interface = False

        self.content = file.read_text()
        for line in self.content.splitlines():
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Deal with comments, we relay on the .aidl
            # not having comments in the middle of the code
            if open_comment:
                if "*/" in line:
                    open_comment = False
                continue

            if line.startswith("/*"):
                open_comment = True
                continue

            if line.startswith("import"):
                # Save the imports, they will be used in the code
                # to know from where data types comes from
                line = line.removesuffix(';')
                self.imports.append(line.split()[1])
                continue

            if line.startswith("interface"):
                if inside_interface:
                    raise AssertionError("Found interface inside interface")
                inside_interface = True
                continue

            if inside_interface:
                # If we reached end of interface declaration exit
                if line[0] == '}':
                    inside_interface = False
                    continue

                # Skip non functions
                if not '(' in line:
                    continue

                # This should be a method
                self.methods.append(AIDLMethod(line))
                continue
