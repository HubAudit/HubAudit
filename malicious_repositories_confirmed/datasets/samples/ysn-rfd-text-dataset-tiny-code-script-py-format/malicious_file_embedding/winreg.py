# winreg.py - dummy winreg module for PoC testing of PersistenceManager.add_registry() in full_MFE.py

class HKEY_CURRENT_USER:
    pass

class HKEY_LOCAL_MACHINE:
    pass

class KEY_READ:
    pass

class KEY_WRITE:
    pass

class REG_SZ:
    pass

class REG_DWORD:
    pass

def OpenKey(key, subkey, reserved=0, access=KEY_READ):
    return None

def QueryValueEx(key, value_name):
    return ("", 0)

def SetValueEx(key, value_name, reserved, type, value):
    pass

def CloseKey(key):
    pass

def CreateKey(key, subkey):
    return None

def DeleteKey(key, subkey):
    pass

def EnumKey(key, index):
    return ""

def EnumValue(key, index):
    return ("", "", 0)