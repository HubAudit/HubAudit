"""
مدیریت بارگیری و اعمال پلاگین‌ها
"""

import os
import importlib
import sys
from base_plugin import BasePlugin

class PluginManager:
    """مدیریت بارگیری و اعمال پلاگین‌ها"""
    
    def __init__(self, plugins_dir="plugins"):
        """ساخت یک نمونه جدید از مدیر پلاگین‌ها"""
        self.plugins_dir = plugins_dir
        self.plugins = []
        self.loaded_modules = []
        self.active_plugins = []
    
    def load_plugins(self):
        """بارگیری تمام پلاگین‌ها از پوشه مربوطه"""
        # اضافه کردن پوشه پلاگین‌ها به سیستم
        plugins_path = os.path.join(os.path.dirname(__file__), self.plugins_dir)
        sys.path.insert(0, plugins_path)
        
        print(f"جستجوی پلاگین‌ها در: {plugins_path}")
        
        # لیست تمام فایل‌های پایتون در پوشه پلاگین‌ها
        for filename in os.listdir(plugins_path):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]  # حذف .py
                
                try:
                    # بارگیری ماژول
                    print(f"بارگیری ماژول: {module_name}")
                    module = importlib.import_module(module_name)
                    self.loaded_modules.append(module)
                    
                    # یافتن کلاس‌های پلاگین
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr != BasePlugin:
                            plugin = attr()
                            self.plugins.append(plugin)
                            print(f"پیدا شد: {plugin.name} v{plugin.version}")
                except Exception as e:
                    print(f"خطا در بارگیری پلاگین {module_name}: {str(e)}")
        
        # مرتب‌سازی پلاگین‌ها بر اساس نام
        self.plugins.sort(key=lambda p: p.name)
        print(f"{len(self.plugins)} پلاگین بارگیری شد.")
    
    def activate_plugins(self, game):
        """فعال‌سازی پلاگین‌ها و اعمال آنها به بازی"""
        for plugin in self.plugins:
            if plugin not in self.active_plugins:
                plugin.apply(game)
                self.active_plugins.append(plugin)
                print(f"فعال‌سازی پلاگین: {plugin.name}")
    
    def deactivate_plugins(self, game):
        """غیرفعال‌سازی پلاگین‌ها و حذف اثرات آنها از بازی"""
        for plugin in self.active_plugins:
            plugin.remove(game)
        self.active_plugins = []
        print("تمام پلاگین‌ها غیرفعال شدند.")
    
    def list_plugins(self):
        """لیست تمام پلاگین‌های بارگیری شده"""
        print("\nلیست پلاگین‌های بارگیری شده:")
        for i, plugin in enumerate(self.plugins, 1):
            status = "فعال" if plugin in self.active_plugins else "غیرفعال"
            print(f"{i}. {plugin.name} v{plugin.version} - {status}")
            print(f"   {plugin.description}")
    
    def toggle_plugin(self, game, plugin_index):
        """فعال یا غیرفعال کردن یک پلاگین خاص"""
        if 0 <= plugin_index < len(self.plugins):
            plugin = self.plugins[plugin_index]
            
            if plugin in self.active_plugins:
                plugin.remove(game)
                self.active_plugins.remove(plugin)
                print(f"پلاگین '{plugin.name}' غیرفعال شد.")
            else:
                plugin.apply(game)
                self.active_plugins.append(plugin)
                print(f"پلاگین '{plugin.name}' فعال شد.")
        else:
            print("شماره پلاگین نامعتبر است.")
    
    def get_plugin_info(self, plugin_index):
        """دریافت اطلاعات یک پلاگین خاص"""
        if 0 <= plugin_index < len(self.plugins):
            plugin = self.plugins[plugin_index]
            info = {
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "status": "active" if plugin in self.active_plugins else "inactive"
            }
            return info
        return None
    
    def save_plugin_configuration(self, filename="plugins_config.json"):
        """ذخیره پیکربندی پلاگین‌ها"""
        import json
        
        config = {
            "active_plugins": [plugin.name for plugin in self.active_plugins]
        }
        
        with open(filename, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"پیکربندی پلاگین‌ها در '{filename}' ذخیره شد.")
    
    def load_plugin_configuration(self, filename="plugins_config.json"):
        """بارگیری پیکربندی پلاگین‌ها"""
        import json
        import os
        
        if not os.path.exists(filename):
            print(f"فایل پیکربندی '{filename}' یافت نشد.")
            return
        
        try:
            with open(filename, 'r') as f:
                config = json.load(f)
            
            # غیرفعال‌سازی تمام پلاگین‌ها
            self.deactivate_plugins(None)
            
            # فعال‌سازی پلاگین‌های ذخیره شده
            for plugin_name in config.get("active_plugins", []):
                for plugin in self.plugins:
                    if plugin.name == plugin_name:
                        plugin.apply(None)  # این فقط برای بررسی سازگاری است
                        self.active_plugins.append(plugin)
                        break
            
            print(f"پیکربندی پلاگین‌ها از '{filename}' بارگیری شد.")
        except Exception as e:
            print(f"خطا در بارگیری پیکربندی پلاگین‌ها: {str(e)}")