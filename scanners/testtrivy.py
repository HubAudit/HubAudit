import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanners.trivy import TrivyConfigScanner

scanner = TrivyConfigScanner()

# result = scanner.timed_scan(r"/mnt/c/Users/anonymous/Downloads/Scanner/tests/samples/bad.yaml")
results = scanner.timed_folder_scan(r"/mnt/c/Users/anonymous/Downloads/Scanner/tests/samples/")
# results = scanner.timed_folder_scan(r"/mnt/c/Users/anonymous/Downloads/Scanner/tests/samples/repo")
# print(result.__dict__)

# print("testing -- how many verdicts:", len(results))

if not results:
    print("No findings found.")
else:
    for r in results:
        print(r.__dict__)
