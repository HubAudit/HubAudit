import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanners.bandit import BanditScanner

scanner = BanditScanner()
# results = scanner.scan(r"/mnt/c/Users/anonymous/Downloads/Scanner/tests/samples/bad.py")
results = scanner.timed_folder_scan(r"/mnt/c/Users/anonymous/Downloads/Scanner/tests/samples/")

if not results:
    print("No findings found.")
else:
    for r in results:
        print(r.__dict__)
