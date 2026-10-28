import os
from .template import ScannerTemplate, ScanVerdict, SCOPE_EVERY_FILE, SCOPE_FILE_EXTENSION, SCOPE_PROJECT_FOLDER

# Import all our scanner 
from .opengrep    import OpengrepScanner
from .bandit      import BanditScanner
from .trivy       import TrivyConfigScanner
from .pysentry    import PySentryScanner
from .pip_audit   import PipAuditScanner
from .modelaudit  import ModelAuditScanner


def get_all_scanners():
    vt_key = os.environ.get("VT_API_KEY", "")
    scanner_is_disabled = {
        scanner.strip().lower()
        for scanner in os.environ.get("DISABLE_SCANNERS", "").split(",")
        if scanner.strip()
    }
    
    all_scanners = [
        OpengrepScanner(),
        BanditScanner(),
        TrivyConfigScanner(),  
        PySentryScanner(),
        PipAuditScanner(),
        ModelAuditScanner(),
    
    ]
    
    if scanner_is_disabled:
        all_scanners = [s for s in all_scanners if s.name not in scanner_is_disabled]
        # print(f"  Disabled scanners........: {', '.join(sorted(scanner_is_disabled))}")

    return all_scanners

def verify_scanners(scanner_list):
    available_scanners = []
    print("\nChecking scanners...")
    for scanner in scanner_list:
        try:
            is_healthy, status_msg = scanner.health_check()
            if is_healthy:
                print(f"  [OK] {scanner.name}")
                available_scanners.append(scanner)
            else:
                print(f"  [--] {scanner.name} (failed: {status_msg})")
        except Exception as e:
            print(f"  [!!] {scanner.name} (crashed checking health)")
            
    return available_scanners

def get_file_scanners(scanner_list, file_path):
    applicable_scanners = []
    
    for scanner in scanner_list:
        if scanner.scope in (SCOPE_EVERY_FILE, SCOPE_FILE_EXTENSION):
            if scanner.scanner_applies_to_format(file_path):
                applicable_scanners.append(scanner)
                
    return applicable_scanners


def get_folder_scanners(scanner_list):
    return [
        scanner for scanner in scanner_list 
        if scanner.scope == SCOPE_PROJECT_FOLDER 
        # and scanner.name not in ("virustotal", "presidio")
    ]


def build_registry(vt_api_key: str = "", vt_no_upload: bool = False, **kwargs):
    if vt_api_key:
        os.environ.setdefault("VT_API_KEY", vt_api_key)
    return get_all_scanners()

get_project_scanners = get_folder_scanners


def get_vt_scanner(scanner_list):
    for scanner in scanner_list:
        if scanner.name == "virustotal":
            return scanner
    return None
