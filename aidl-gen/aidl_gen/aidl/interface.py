from aidl_gen.aidl.method import AIDLMethod
from pathlib import Path

class AIDLInterface:
    def __init__(self, fqname: str, includes: list[Path]):
        self.fqname = fqname
        self.includes = includes

        self.interface_file = self.get_aidl_file(self.fqname)

        self.methods = []
        self.imports = {}
        self.is_interface = False
        self.is_parcelable = False

        open_comment = False
        inside_structure = False

        self.content = self.interface_file.read_text()
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
                # and what data type it is
                import_name = line.split()[1].removesuffix(';')
                self.imports[import_name.rsplit('.', 1)[1]] = AIDLInterface(import_name, includes)
                continue

            if line.startswith("interface") or line.startswith("parcelable"):
                if inside_structure:
                    raise AssertionError("Found nested declarations")
                inside_structure = True
                if line.startswith("interface"):
                    self.is_interface = True
                elif line.startswith("parcelable"):
                    self.is_parcelable = True
                continue

            if inside_structure:
                # If we reached end of interface declaration exit
                if line[0] == '}':
                    inside_structure = False
                    continue

                if self.is_interface:
                    # Skip non functions
                    if not '(' in line:
                        continue

                    # This should be a method
                    self.methods.append(AIDLMethod(line, self.imports))
                    continue

    def get_aidl_file(self, fqname: str):
        for dir in self.includes:
            file = dir / Path(fqname.replace('.', '/') + '.aidl')
            if not file.is_file():
                continue
            return file

        raise FileNotFoundError(f"Interface {fqname} not found")
