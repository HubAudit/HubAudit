
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanners.opengrep import OpengrepScanner

start = time.time()
scanner = OpengrepScanner()
results = scanner.timed_folder_scan(r"/mnt/c/Users/anonymous/Downloads/Scanner/tests/samples/")
# result = scanner.scan(r"/mnt/c/Users/anonymous/Downloads/Scanner/tests/samples/bad.py")
end = time.time()

# print(result)

if not results:
    print("No findings found.")
    print(f"Scan completed in {end - start} seconds.")
else:
    for r in results:
        print(r.__dict__)
    print(f"Scan completed in {end - start} seconds.")
