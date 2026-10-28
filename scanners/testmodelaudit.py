import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanners.modelaudit import ModelAuditScanner

scanner = ModelAuditScanner()
results = [scanner.timed_scan(r"/mnt/c/Users/anonymous/Downloads/Scanner/tests/abyrne55nuextract-1.5-tiny-mealie-ingredient-parser/nuextract-1.5-tiny-finetuned-q8_0.gguf")]
# results = scanner.timed_folder_scan(r"/mnt/c/Users/anonymous/Downloads/Scanner/tests/nvidia")

if not results:
    print("No findings found.")
else:
    for r in results:
        print(r.__dict__)
