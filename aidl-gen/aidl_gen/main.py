from aidl_gen.aidl.interface import AIDLInterface
from aidl_gen.aidl.service import AIDLService
from argparse import ArgumentParser
from pathlib import Path

def main():
	parser = ArgumentParser(prog="aidl_gen")

	parser.add_argument("fqname", type=str,
	                    help="Full qualifier of an AIDL interface (e.g. android.hardware.light.ILights)")
	parser.add_argument("include_dir", type=Path,
	                    help="Folders to include that contains the AIDL interface "
						     "(note: use the folder where Android.bp resides)")
	parser.add_argument("out_dir", type=Path,
	                    help="Folders where the service will be written on")

	args = parser.parse_args()

	service = AIDLService(args.fqname, args.include_dir)
	service.write_to_folder(args.out_dir)
