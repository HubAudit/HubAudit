import sys
from dotenv import load_dotenv

load_dotenv() 

from scanners import build_registry, verify_scanners

registry = build_registry()
available = verify_scanners(registry)
if len(available) == 0:
    print("No scanners available. Run ./install.sh to install dependencies.")
    sys.exit(1)
