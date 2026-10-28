#!/usr/bin/env python3
# TextWorld Adventure - A Complete Text-Based RPG Game
# Author: YSNRFD
# Version: 1.0.0

import os
import sys
import json
import random
import time
import pickle
import math
from enum import Enum
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict
import colorama
from colorama import Fore, Back, Style

# Initialize colorama for cross-platform colored text
colorama.init()

# Game Constants
GAME_VERSION = "1.0.0"
GAME_TITLE = "TextWorld Adventure"
SAVE_FILE = "textworld_save.pkl"
CONFIG_FILE = "textworld_config.json"

# Game Enums
class ItemType(Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"
    QUEST = "quest"
    MISC = "misc"

class SkillType(Enum):
    COMBAT = "combat"
    MAGIC = "magic"
    STEALTH = "stealth"
    SOCIAL = "social"

class DamageType(Enum):
    PHYSICAL = "physical"
    FIRE = "fire"
    ICE = "ice"
    LIGHTNING = "lightning"
    POISON = "poison"

class QuestStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

# Game Data Classes
@dataclass
class Item:
    id: str
    name: str
    description: str
    item_type: ItemType
    value: int
    rarity: str
    stats: Dict[str, int]
    consumable: bool = False
    stackable: bool = False
    max_stack: int = 1
    
    def use(self, player):
        if self.consumable:
            if "heal" in self.stats:
                player.health = min(player.max_health, player.health + self.stats["heal"])
                return f"You used {self.name} and restored {self.stats['heal']} health."
            elif "mana" in self.stats:
                player.mana = min(player.max_mana, player.mana + self.stats["mana"])
                return f"You used {self.name} and restored {self.stats['mana']} mana."
        return f"You can't use {self.name}."

@dataclass
class Skill:
    id: str
    name: str
    description: str
    skill_type: SkillType
    level: int = 1
    experience: int = 0
    max_experience: int = 100
    
    def add_experience(self, amount):
        self.experience += amount
        leveled_up = False
        while self.experience >= self.max_experience:
            self.experience -= self.max_experience
            self.level += 1
            self.max_experience = int(self.max_experience * 1.5)
            leveled_up = True
        return leveled_up

@dataclass
class Quest:
    id: str
    name: str
    description: str
    objectives: List[str]
    rewards: Dict[str, Any]
    status: QuestStatus = QuestStatus.NOT_STARTED
    progress: Dict[str, int] = None
    
    def __post_init__(self):
        if self.progress is None:
            self.progress = {obj: 0 for obj in self.objectives}

@dataclass
class NPC:
    id: str
    name: str
    description: str
    dialogue: Dict[str, List[str]]
    quests: List[str]
    friendly: bool = True
    shop_items: List[Item] = None
    
    def get_dialogue(self, topic="default"):
        return self.dialogue.get(topic, self.dialogue.get("default", ["I have nothing to say."]))

@dataclass
class Location:
    id: str
    name: str
    description: str
    exits: Dict[str, str]
    npcs: List[str]
    items: List[str]
    enemies: List[str]
    visited: bool = False
    
    def get_description(self, game):
        desc = f"{self.name}\n{'='*len(self.name)}\n{self.description}\n\n"
        
        if self.exits:
            desc += "Exits: " + ", ".join(self.exits.keys()) + "\n"
        
        if self.npcs:
            npcs = [game.npcs[npc_id] for npc_id in self.npcs]
            desc += "People here: " + ", ".join([npc.name for npc in npcs]) + "\n"
        
        if self.items:
            items = [game.items[item_id] for item_id in self.items]
            desc += "Items here: " + ", ".join([item.name for item in items]) + "\n"
        
        if self.enemies:
            enemies = [game.enemies[enemy_id] for enemy_id in self.enemies]
            desc += "Enemies here: " + ", ".join([enemy.name for enemy in enemies]) + "\n"
        
        return desc

@dataclass
class Enemy:
    id: str
    name: str
    description: str
    level: int
    health: int
    max_health: int
    attack: int
    defense: int
    experience: int
    gold: int
    loot: List[str]
    abilities: List[str]
    
    def take_damage(self, damage):
        actual_damage = max(1, damage - self.defense)
        self.health -= actual_damage
        return actual_damage
    
    def is_alive(self):
        return self.health > 0

@dataclass
class Player:
    name: str
    level: int = 1
    experience: int = 0
    max_experience: int = 100
    health: int = 100
    max_health: int = 100
    mana: int = 50
    max_mana: int = 50
    attack: int = 10
    defense: int = 5
    gold: int = 50
    inventory: List[Dict[str, Any]] = None
    equipment: Dict[str, str] = None
    skills: Dict[str, Skill] = None
    quests: Dict[str, Quest] = None
    current_location: str = "town_square"
    
    def __post_init__(self):
        if self.inventory is None:
            self.inventory = []
        if self.equipment is None:
            self.equipment = {"weapon": None, "armor": None, "accessory": None}
        if self.skills is None:
            self.skills = {
                "combat": Skill("combat", "Combat", "Your skill in fighting", SkillType.COMBAT),
                "magic": Skill("magic", "Magic", "Your skill in casting spells", SkillType.MAGIC),
                "stealth": Skill("stealth", "Stealth", "Your skill in moving unseen", SkillType.STEALTH),
                "social": Skill("social", "Social", "Your skill in interacting with others", SkillType.SOCIAL)
            }
        if self.quests is None:
            self.quests = {}
    
    def add_experience(self, amount):
        self.experience += amount
        leveled_up = False
        while self.experience >= self.max_experience:
            self.experience -= self.max_experience
            self.level += 1
            self.max_experience = int(self.max_experience * 1.5)
            self.max_health += 10
            self.health = self.max_health
            self.max_mana += 5
            self.mana = self.max_mana
            self.attack += 2
            self.defense += 1
            leveled_up = True
        return leveled_up
    
    def add_item(self, item, quantity=1):
        for inv_item in self.inventory:
            if inv_item["item"].id == item.id and item.stackable:
                inv_item["quantity"] += quantity
                return True
        
        self.inventory.append({"item": item, "quantity": quantity})
        return True
    
    def remove_item(self, item_id, quantity=1):
        for i, inv_item in enumerate(self.inventory):
            if inv_item["item"].id == item_id:
                if inv_item["quantity"] <= quantity:
                    self.inventory.pop(i)
                    return True
                else:
                    inv_item["quantity"] -= quantity
                    return True
        return False
    
    def get_item(self, item_id):
        for inv_item in self.inventory:
            if inv_item["item"].id == item_id:
                return inv_item["item"]
        return None
    
    def equip_item(self, item_id):
        item = self.get_item(item_id)
        if not item:
            return False, "You don't have that item."
        
        if item.item_type == ItemType.WEAPON:
            if self.equipment["weapon"]:
                self.add_item(self.get_item(self.equipment["weapon"]))
            self.equipment["weapon"] = item_id
            self.attack += item.stats.get("attack", 0)
            return True, f"You equipped {item.name}."
        
        elif item.item_type == ItemType.ARMOR:
            if self.equipment["armor"]:
                self.add_item(self.get_item(self.equipment["armor"]))
            self.equipment["armor"] = item_id
            self.defense += item.stats.get("defense", 0)
            return True, f"You equipped {item.name}."
        
        return False, "You can't equip that item."
    
    def get_total_attack(self):
        total = self.attack
        if self.equipment["weapon"]:
            weapon = self.get_item(self.equipment["weapon"])
            if weapon:
                total += weapon.stats.get("attack", 0)
        return total
    
    def get_total_defense(self):
        total = self.defense
        if self.equipment["armor"]:
            armor = self.get_item(self.equipment["armor"])
            if armor:
                total += armor.stats.get("defense", 0)
        return total

# Game Configuration
class GameConfig:
    def __init__(self):
        self.settings = {
            "text_speed": 0.03,
            "auto_save": True,
            "auto_save_interval": 300,  # seconds
            "color_scheme": "default",
            "difficulty": "normal",
            "debug_mode": False
        }
        self.load_config()
    
    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    self.settings.update(json.load(f))
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_setting(self, key, default=None):
        return self.settings.get(key, default)
    
    def set_setting(self, key, value):
        self.settings[key] = value
        self.save_config()

# Plugin System
class PluginManager:
    def __init__(self, game):
        self.game = game
        self.plugins = {}
        self.hooks = {
            "on_command": [],
            "on_move": [],
            "on_combat": [],
            "on_level_up": [],
            "on_quest_complete": [],
            "on_item_pickup": []
        }
    
    def load_plugin(self, plugin_name):
        try:
            # This is a simplified plugin loader
            # In a real implementation, you'd load from files
            if plugin_name == "debug":
                self.plugins[plugin_name] = DebugPlugin(self.game)
            elif plugin_name == "hardcore":
                self.plugins[plugin_name] = HardcorePlugin(self.game)
            return True
        except Exception as e:
            print(f"Error loading plugin {plugin_name}: {e}")
            return False
    
    def register_hook(self, hook_name, callback):
        if hook_name in self.hooks:
            self.hooks[hook_name].append(callback)
    
    def trigger_hook(self, hook_name, *args, **kwargs):
        if hook_name in self.hooks:
            for callback in self.hooks[hook_name]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    print(f"Error in hook {hook_name}: {e}")

# Base Plugin Class
class BasePlugin:
    def __init__(self, game):
        self.game = game
        self.name = "Base Plugin"
        self.version = "1.0.0"
        self.description = "Base plugin class"
        self.enabled = True
    
    def initialize(self):
        pass
    
    def on_command(self, command, args):
        pass
    
    def on_move(self, from_location, to_location):
        pass
    
    def on_combat(self, player, enemy):
        pass
    
    def on_level_up(self, player):
        pass
    
    def on_quest_complete(self, quest):
        pass
    
    def on_item_pickup(self, item):
        pass

# Example Plugins
class DebugPlugin(BasePlugin):
    def __init__(self, game):
        super().__init__(game)
        self.name = "Debug Plugin"
        self.description = "Adds debug commands to the game"
    
    def initialize(self):
        self.game.register_command("debug", self.debug_command)
    
    def debug_command(self, args):
        if len(args) < 1:
            return "Usage: debug <command>"
        
        cmd = args[0].lower()
        if cmd == "teleport":
            if len(args) < 2:
                return "Usage: debug teleport <location_id>"
            location_id = args[1]
            if location_id in self.game.locations:
                self.game.player.current_location = location_id
                return f"Teleported to {self.game.locations[location_id].name}"
            return "Location not found"
        
        elif cmd == "give":
            if len(args) < 2:
                return "Usage: debug give <item_id>"
            item_id = args[1]
            if item_id in self.game.items:
                self.game.player.add_item(self.game.items[item_id])
                return f"Gave {self.game.items[item_id].name}"
            return "Item not found"
        
        elif cmd == "level":
            if len(args) < 2:
                return "Usage: debug level <amount>"
            try:
                amount = int(args[1])
                if self.game.player.add_experience(amount):
                    return f"Gained {amount} experience and leveled up!"
                return f"Gained {amount} experience"
            except ValueError:
                return "Invalid amount"
        
        elif cmd == "heal":
            self.game.player.health = self.game.player.max_health
            self.game.player.mana = self.game.player.max_mana
            return "Fully healed"
        
        return "Unknown debug command"

class HardcorePlugin(BasePlugin):
    def __init__(self, game):
        super().__init__(game)
        self.name = "Hardcore Mode"
        self.description = "Makes the game more challenging"
    
    def initialize(self):
        self.game.register_hook("on_combat", self.on_combat)
        self.game.register_hook("on_level_up", self.on_level_up)
    
    def on_combat(self, player, enemy):
        enemy.attack = int(enemy.attack * 1.5)
        enemy.health = int(enemy.health * 1.5)
        enemy.max_health = enemy.health
    
    def on_level_up(self, player):
        player.max_health = int(player.max_health * 0.8)
        player.health = player.max_health

# Main Game Class
class TextWorldGame:
    def __init__(self):
        self.config = GameConfig()
        self.plugin_manager = PluginManager(self)
        self.player = None
        self.locations = {}
        self.items = {}
        self.npcs = {}
        self.enemies = {}
        self.quests = {}
        self.running = True
        self.commands = {}
        self.combat_active = False
        self.current_enemy = None
        
        self.initialize_game_data()
        self.register_commands()
        self.load_plugins()
    
    def initialize_game_data(self):
        # Initialize Items
        self.items = {
            "sword": Item("sword", "Iron Sword", "A simple iron sword", ItemType.WEAPON, 50, "common", {"attack": 5}),
            "shield": Item("shield", "Wooden Shield", "A basic wooden shield", ItemType.ARMOR, 30, "common", {"defense": 3}),
            "potion": Item("potion", "Health Potion", "A red potion that restores health", ItemType.CONSUMABLE, 10, "common", {"heal": 25}, consumable=True, stackable=True, max_stack=10),
            "mana_potion": Item("mana_potion", "Mana Potion", "A blue potion that restores mana", ItemType.CONSUMABLE, 15, "common", {"mana": 15}, consumable=True, stackable=True, max_stack=10),
            "leather_armor": Item("leather_armor", "Leather Armor", "Basic leather armor", ItemType.ARMOR, 40, "common", {"defense": 5}),
            "magic_scroll": Item("magic_scroll", "Magic Scroll", "A scroll containing a magic spell", ItemType.MISC, 100, "rare", {"magic_power": 10}),
            "gold_coin": Item("gold_coin", "Gold Coin", "A shiny gold coin", ItemType.MISC, 1, "common", {}, stackable=True, max_stack=999),
            "dragon_sword": Item("dragon_sword", "Dragon Sword", "A legendary sword forged from dragon scales", ItemType.WEAPON, 1000, "legendary", {"attack": 20, "fire_damage": 10}),
            "dragon_armor": Item("dragon_armor", "Dragon Armor", "Legendary armor made from dragon scales", ItemType.ARMOR, 1500, "legendary", {"defense": 15, "fire_resistance": 20}),
        }
        
        # Initialize Enemies
        self.enemies = {
            "goblin": Enemy("goblin", "Goblin", "A small green creature with sharp teeth", 1, 30, 30, 8, 2, 20, 10, ["potion"], ["bite"]),
            "orc": Enemy("orc", "Orc", "A large green brute with a club", 3, 60, 60, 15, 5, 50, 25, ["sword", "potion"], ["smash"]),
            "dragon": Enemy("dragon", "Dragon", "A massive fire-breathing dragon", 10, 200, 200, 30, 15, 200, 500, ["dragon_sword", "dragon_armor"], ["fire_breath", "tail_swipe"]),
            "skeleton": Enemy("skeleton", "Skeleton", "An undead warrior with rusty armor", 2, 40, 40, 12, 4, 30, 15, ["gold_coin"], ["bone_throw"]),
            "dark_wizard": Enemy("dark_wizard", "Dark Wizard", "A powerful spellcaster in dark robes", 5, 80, 80, 20, 8, 100, 100, ["magic_scroll", "mana_potion"], ["fireball", "lightning"]),
        }
        
        # Initialize NPCs
        self.npcs = {
            "merchant": NPC("merchant", "Merchant", "A friendly merchant selling various items", {
                "default": ["Welcome to my shop! What can I get for you?", "I have the finest items in town!"],
                "buy": ["What would you like to buy?"],
                "sell": ["What would you like to sell?"],
                "quest": ["I have a quest for you if you're interested."]
            }, ["merchant_quest"], True, [self.items["potion"], self.items["sword"], self.items["shield"]]),
            
            "guard": NPC("guard", "Town Guard", "A brave guard protecting the town", {
                "default": ["Halt! State your business.", "The town is safe under my watch."],
                "dragon": ["A dragon has been spotted in the mountains! Be careful if you go there."],
                "quest": ["We need help dealing with the goblins in the forest."]
            }, ["goblin_quest"], True),
            
            "wizard": NPC("wizard", "Wizard", "A mysterious wizard with powerful magic", {
                "default": ["Greetings, traveler. I sense great potential in you.", "Magic flows through the world like a river."],
                "magic": ["Magic is the art of manipulating reality itself.", "Would you like to learn some spells?"],
                "quest": ["I need someone to retrieve a rare artifact for me."]
            }, ["wizard_quest"], True),
        }
        
        # Initialize Locations
        self.locations = {
            "town_square": Location("town_square", "Town Square", "The central square of the town. People are bustling about.", {
                "north": "town_gate",
                "east": "market",
                "west": "tavern",
                "south": "temple"
            }, ["guard"], [], []),
            
            "town_gate": Location("town_gate", "Town Gate", "The main entrance to the town. A large wooden gate stands open.", {
                "south": "town_square",
                "north": "forest_entrance"
            }, [], [], []),
            
            "market": Location("market", "Market", "A busy market with merchants selling their wares.", {
                "west": "town_square"
            }, ["merchant"], [], []),
            
            "tavern": Location("tavern", "Tavern", "A cozy tavern with a warm fireplace and friendly patrons.", {
                "east": "town_square"
            }, [], ["potion"], []),
            
            "temple": Location("temple", "Temple", "A peaceful temple where people come to pray and heal.", {
                "north": "town_square"
            }, [], [], []),
            
            "forest_entrance": Location("forest_entrance", "Forest Entrance", "The edge of a dark forest. You can hear strange noises from within.", {
                "south": "town_gate",
                "north": "deep_forest",
                "east": "river",
                "west": "cave_entrance"
            }, [], [], ["goblin"]),
            
            "deep_forest": Location("deep_forest", "Deep Forest", "A dense forest with tall trees and little light.", {
                "south": "forest_entrance",
                "north": "mountain_base"
            }, [], [], ["goblin", "skeleton"]),
            
            "river": Location("river", "River", "A wide river flowing from the mountains.", {
                "west": "forest_entrance",
                "east": "bridge"
            }, [], [], []),
            
            "bridge": Location("bridge", "Bridge", "An old stone bridge crossing the river.", {
                "west": "river",
                "east": "abandoned_tower"
            }, [], [], ["orc"]),
            
            "cave_entrance": Location("cave_entrance", "Cave Entrance", "The entrance to a dark cave. You can feel cold air coming from inside.", {
                "east": "forest_entrance",
                "west": "cave_depths"
            }, [], [], ["skeleton"]),
            
            "cave_depths": Location("cave_depths", "Cave Depths", "The deepest part of the cave. It's dark and damp here.", {
                "east": "cave_entrance"
            }, [], ["magic_scroll"], ["dark_wizard"]),
            
            "mountain_base": Location("mountain_base", "Mountain Base", "The base of a tall mountain. A path leads up.", {
                "south": "deep_forest",
                "north": "mountain_path"
            }, [], [], []),
            
            "mountain_path": Location("mountain_path", "Mountain Path", "A narrow path winding up the mountain.", {
                "south": "mountain_base",
                "north": "dragon_lair"
            }, [], [], ["orc"]),
            
            "dragon_lair": Location("dragon_lair", "Dragon Lair", "A massive cave where a dragon lives. You can feel the heat.", {
                "south": "mountain_path"
            }, [], [], ["dragon"]),
            
            "abandoned_tower": Location("abandoned_tower", "Abandoned Tower", "An old tower that was once home to a powerful wizard.", {
                "west": "bridge"
            }, ["wizard"], [], []),
        }
        
        # Initialize Quests
        self.quests = {
            "merchant_quest": Quest("merchant_quest", "Merchant's Request", "The merchant needs you to deliver a package to the wizard.", 
                                   ["Deliver package to wizard"], {"experience": 100, "gold": 50}),
            
            "goblin_quest": Quest("goblin_quest", "Goblin Problem", "The town guard needs help dealing with goblins in the forest.", 
                                 ["Defeat 3 goblins"], {"experience": 150, "gold": 75}),
            
            "wizard_quest": Quest("wizard_quest", "Wizard's Artifact", "The wizard needs you to retrieve a magic scroll from the cave depths.", 
                                 ["Find magic scroll in cave depths"], {"experience": 200, "gold": 100, "item": "mana_potion"}),
            
            "dragon_quest": Quest("dragon_quest", "Dragon Slayer", "A dragon terrorizes the mountains. Someone needs to defeat it.", 
                                 ["Defeat the dragon"], {"experience": 500, "gold": 500, "item": "dragon_sword"}),
        }
    
    def register_commands(self):
        self.commands = {
            "help": self.cmd_help,
            "look": self.cmd_look,
            "go": self.cmd_go,
            "move": self.cmd_go,
            "inventory": self.cmd_inventory,
            "inv": self.cmd_inventory,
            "equip": self.cmd_equip,
            "unequip": self.cmd_unequip,
            "use": self.cmd_use,
            "take": self.cmd_take,
            "get": self.cmd_take,
            "drop": self.cmd_drop,
            "talk": self.cmd_talk,
            "attack": self.cmd_attack,
            "fight": self.cmd_attack,
            "quests": self.cmd_quests,
            "status": self.cmd_status,
            "save": self.cmd_save,
            "load": self.cmd_load,
            "quit": self.cmd_quit,
            "exit": self.cmd_quit,
            "rest": self.cmd_rest,
            "skills": self.cmd_skills,
            "shop": self.cmd_shop,
            "buy": self.cmd_buy,
            "sell": self.cmd_sell,
            "map": self.cmd_map,
            "clear": self.cmd_clear,
            "version": self.cmd_version,
            "config": self.cmd_config,
        }
    
    def load_plugins(self):
        # Load default plugins
        if self.config.get_setting("debug_mode", False):
            self.plugin_manager.load_plugin("debug")
        
        # Initialize all loaded plugins
        for plugin in self.plugin_manager.plugins.values():
            plugin.initialize()
    
    def register_command(self, command, callback):
        self.commands[command] = callback
    
    def register_hook(self, hook_name, callback):
        self.plugin_manager.register_hook(hook_name, callback)
    
    def start(self):
        self.clear_screen()
        self.print_title()
        
        # Check for save file
        if os.path.exists(SAVE_FILE):
            choice = self.get_input("A save file exists. Do you want to load it? (y/n): ").lower()
            if choice == 'y':
                self.load_game()
                self.print_slow("Game loaded successfully!")
                self.game_loop()
                return
        
        # Character creation
        self.print_slow("Welcome to TextWorld Adventure!")
        self.print_slow("Let's create your character...")
        
        name = self.get_input("Enter your character's name: ")
        while not name:
            name = self.get_input("Please enter a valid name: ")
        
        self.player = Player(name)
        self.player.add_item(self.items["potion"], 3)
        self.player.add_item(self.items["gold_coin"], 50)
        
        self.print_slow(f"\nWelcome, {self.player.name}!")
        self.print_slow("Your adventure begins in the Town Square.")
        self.print_slow("Type 'help' for a list of commands.")
        
        self.game_loop()
    
    def game_loop(self):
        last_auto_save = time.time()
        
        while self.running:
            # Auto-save check
            if self.config.get_setting("auto_save", True):
                if time.time() - last_auto_save > self.config.get_setting("auto_save_interval", 300):
                    self.save_game(silent=True)
                    last_auto_save = time.time()
            
            # Get player input
            if self.combat_active:
                prompt = f"{Fore.RED}[COMBAT]{Style.RESET_ALL} What do you do? > "
            else:
                location = self.locations[self.player.current_location]
                prompt = f"{Fore.GREEN}[{location.name}]{Style.RESET_ALL} What do you do? > "
            
            command_input = self.get_input(prompt).strip().lower()
            
            # Parse command
            if not command_input:
                continue
            
            parts = command_input.split()
            command = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            # Trigger command hook
            self.plugin_manager.trigger_hook("on_command", command, args)
            
            # Execute command
            if command in self.commands:
                try:
                    result = self.commands[command](args)
                    if result:
                        self.print_slow(result)
                except Exception as e:
                    self.print_slow(f"Error executing command: {e}")
            else:
                self.print_slow(f"Unknown command: {command}. Type 'help' for available commands.")
    
    def cmd_help(self, args):
        help_text = f"""
{Fore.CYAN}=== TextWorld Adventure Commands ==={Style.RESET_ALL}

{Fore.YELLOW}Movement:{Style.RESET_ALL}
  go/move <direction>  - Move in a direction (north, south, east, west)
  look                 - Look around the current location
  map                  - Show a simple map of the area

{Fore.YELLOW}Inventory:{Style.RESET_ALL}
  inventory/inv        - Show your inventory
  equip <item>         - Equip an item
  unequip <item>       - Unequip an item
  use <item>           - Use an item
  take/get <item>      - Pick up an item
  drop <item>          - Drop an item

{Fore.YELLOW}Combat:{Style.RESET_ALL}
  attack/fight <enemy> - Attack an enemy
  rest                 - Rest to restore health and mana

{Fore.YELLOW}NPCs:{Style.RESET_ALL}
  talk <npc>           - Talk to an NPC
  shop                 - Open shop interface (if available)
  buy <item>           - Buy an item from shop
  sell <item>          - Sell an item to shop

{Fore.YELLOW}Character:{Style.RESET_ALL}
  status               - Show your character status
  skills               - Show your skills
  quests               - Show your active quests

{Fore.YELLOW}System:{Style.RESET_ALL}
  save                 - Save the game
  load                 - Load a saved game
  config <setting> <value> - Change game settings
  clear                - Clear the screen
  version              - Show game version
  quit/exit            - Quit the game
"""
        return help_text
    
    def cmd_look(self, args):
        location = self.locations[self.player.current_location]
        location.visited = True
        return location.get_description(self)
    
    def cmd_go(self, args):
        if not args:
            return "Go where? Specify a direction (north, south, east, west)."
        
        direction = args[0].lower()
        location = self.locations[self.player.current_location]
        
        if direction not in location.exits:
            return f"You can't go {direction} from here."
        
        new_location_id = location.exits[direction]
        new_location = self.locations[new_location_id]
        
        # Trigger move hook
        self.plugin_manager.trigger_hook("on_move", self.player.current_location, new_location_id)
        
        self.player.current_location = new_location_id
        
        # Check for enemies in new location
        if new_location.enemies and random.random() < 0.5:
            enemy_id = random.choice(new_location.enemies)
            enemy = Enemy(**asdict(self.enemies[enemy_id]))
            self.start_combat(enemy)
        
        return new_location.get_description(self)
    
    def cmd_inventory(self, args):
        if not self.player.inventory:
            return "Your inventory is empty."
        
        inv_text = f"{Fore.CYAN}=== Inventory ==={Style.RESET_ALL}\n"
        
        for inv_item in self.player.inventory:
            item = inv_item["item"]
            quantity = inv_item["quantity"]
            if quantity > 1:
                inv_text += f"{item.name} x{quantity} - {item.description}\n"
            else:
                inv_text += f"{item.name} - {item.description}\n"
        
        # Show equipped items
        inv_text += f"\n{Fore.YELLOW}=== Equipped Items ==={Style.RESET_ALL}\n"
        for slot, item_id in self.player.equipment.items():
            if item_id:
                item = self.player.get_item(item_id)
                if item:
                    inv_text += f"{slot.capitalize()}: {item.name}\n"
        
        return inv_text
    
    def cmd_equip(self, args):
        if not args:
            return "Equip what? Specify an item name."
        
        item_name = " ".join(args).lower()
        item = None
        
        for inv_item in self.player.inventory:
            if inv_item["item"].name.lower() == item_name:
                item = inv_item["item"]
                break
        
        if not item:
            return f"You don't have a {item_name}."
        
        success, message = self.player.equip_item(item.id)
        return message
    
    def cmd_unequip(self, args):
        if not args:
            return "Unequip what? Specify 'weapon' or 'armor'."
        
        slot = args[0].lower()
        if slot not in self.player.equipment:
            return "You can only unequip 'weapon' or 'armor'."
        
        if not self.player.equipment[slot]:
            return f"You don't have anything equipped in your {slot} slot."
        
        item_id = self.player.equipment[slot]
        item = self.player.get_item(item_id)
        
        if item:
            self.player.add_item(item)
            if slot == "weapon":
                self.player.attack -= item.stats.get("attack", 0)
            elif slot == "armor":
                self.player.defense -= item.stats.get("defense", 0)
        
        self.player.equipment[slot] = None
        return f"You unequipped {item.name}."
    
    def cmd_use(self, args):
        if not args:
            return "Use what? Specify an item name."
        
        item_name = " ".join(args).lower()
        item = None
        
        for inv_item in self.player.inventory:
            if inv_item["item"].name.lower() == item_name:
                item = inv_item["item"]
                break
        
        if not item:
            return f"You don't have a {item_name}."
        
        if not item.consumable:
            return f"You can't use {item.name}."
        
        result = item.use(self.player)
        
        # Trigger item pickup hook (for use as well)
        self.plugin_manager.trigger_hook("on_item_pickup", item)
        
        if item.consumable:
            self.player.remove_item(item.id)
        
        return result
    
    def cmd_take(self, args):
        if not args:
            return "Take what? Specify an item name."
        
        item_name = " ".join(args).lower()
        location = self.locations[self.player.current_location]
        
        for item_id in location.items[:]:
            item = self.items[item_id]
            if item.name.lower() == item_name:
                self.player.add_item(item)
                location.items.remove(item_id)
                
                # Trigger item pickup hook
                self.plugin_manager.trigger_hook("on_item_pickup", item)
                
                return f"You took {item.name}."
        
        return f"There's no {item_name} here."
    
    def cmd_drop(self, args):
        if not args:
            return "Drop what? Specify an item name."
        
        item_name = " ".join(args).lower()
        location = self.locations[self.player.current_location]
        
        for inv_item in self.player.inventory[:]:
            item = inv_item["item"]
            if item.name.lower() == item_name:
                self.player.remove_item(item.id)
                location.items.append(item.id)
                return f"You dropped {item.name}."
        
        return f"You don't have a {item_name}."
    
    def cmd_talk(self, args):
        if not args:
            return "Talk to whom? Specify an NPC name."
        
        npc_name = " ".join(args).lower()
        location = self.locations[self.player.current_location]
        
        for npc_id in location.npcs:
            npc = self.npcs[npc_id]
            if npc.name.lower() == npc_name:
                dialogue = npc.get_dialogue()
                return f"{npc.name}: {random.choice(dialogue)}"
        
        return f"There's no one named {npc_name} here."
    
    def cmd_attack(self, args):
        if not self.combat_active:
            return "There's nothing to attack here."
        
        if not self.current_enemy:
            self.combat_active = False
            return "The enemy has disappeared."
        
        # Player attacks
        player_damage = self.player.get_total_attack()
        actual_damage = self.current_enemy.take_damage(player_damage)
        
        result = f"You attack {self.current_enemy.name} for {actual_damage} damage!\n"
        
        # Trigger combat hook
        self.plugin_manager.trigger_hook("on_combat", self.player, self.current_enemy)
        
        if not self.current_enemy.is_alive():
            result += f"You defeated {self.current_enemy.name}!\n"
            result += f"You gained {self.current_enemy.experience} experience and {self.current_enemy.gold} gold!\n"
            
            # Level up check
            if self.player.add_experience(self.current_enemy.experience):
                result += f"LEVEL UP! You are now level {self.player.level}!\n"
                # Trigger level up hook
                self.plugin_manager.trigger_hook("on_level_up", self.player)
            
            self.player.gold += self.current_enemy.gold
            
            # Loot
            if self.current_enemy.loot:
                loot_item = random.choice(self.current_enemy.loot)
                if loot_item in self.items:
                    item = self.items[loot_item]
                    self.player.add_item(item)
                    result += f"You found {item.name}!\n"
            
            self.combat_active = False
            self.current_enemy = None
            
            # Update quest progress
            self.update_quest_progress("defeat", self.current_enemy.id if self.current_enemy else "unknown")
            
            return result
        
        # Enemy attacks
        enemy_damage = max(1, self.current_enemy.attack - self.player.get_total_defense())
        self.player.health -= enemy_damage
        result += f"{self.current_enemy.name} attacks you for {enemy_damage} damage!\n"
        
        if self.player.health <= 0:
            result += f"{Fore.RED}You have been defeated! Game Over.{Style.RESET_ALL}\n"
            self.running = False
        
        return result
    
    def cmd_quests(self, args):
        if not self.player.quests:
            return "You don't have any active quests."
        
        quest_text = f"{Fore.CYAN}=== Active Quests ==={Style.RESET_ALL}\n"
        
        for quest_id, quest in self.player.quests.items():
            if quest.status == QuestStatus.IN_PROGRESS:
                quest_text += f"{Fore.YELLOW}{quest.name}{Style.RESET_ALL}\n"
                quest_text += f"  {quest.description}\n"
                quest_text += "  Objectives:\n"
                for obj, progress in quest.progress.items():
                    quest_text += f"    - {obj}: {progress}\n"
                quest_text += "\n"
        
        return quest_text
    
    def cmd_status(self, args):
        status_text = f"""
{Fore.CYAN}=== Character Status ==={Style.RESET_ALL}
Name: {self.player.name}
Level: {self.player.level} ({self.player.experience}/{self.player.max_experience} XP)
Health: {self.player.health}/{self.player.max_health}
Mana: {self.player.mana}/{self.player.max_mana}
Attack: {self.player.get_total_attack()} (Base: {self.player.attack})
Defense: {self.player.get_total_defense()} (Base: {self.player.defense})
Gold: {self.player.gold}
Location: {self.locations[self.player.current_location].name}
"""
        return status_text
    
    def cmd_save(self, args):
        return self.save_game()
    
    def cmd_load(self, args):
        return self.load_game()
    
    def cmd_quit(self, args):
        choice = self.get_input("Are you sure you want to quit? (y/n): ").lower()
        if choice == 'y':
            self.save_game()
            self.running = False
            return "Thanks for playing TextWorld Adventure!"
        return "Continuing game..."
    
    def cmd_rest(self, args):
        if self.combat_active:
            return "You can't rest during combat!"
        
        location = self.locations[self.player.current_location]
        
        # Can only rest in safe locations
        if location.id in ["town_square", "tavern", "temple"]:
            self.player.health = self.player.max_health
            self.player.mana = self.player.max_mana
            return "You rest and recover your health and mana."
        
        # Resting in dangerous locations has a chance of encounter
        if random.random() < 0.3:
            if location.enemies:
                enemy_id = random.choice(location.enemies)
                enemy = Enemy(**asdict(self.enemies[enemy_id]))
                self.start_combat(enemy)
                return "While resting, you were ambushed!"
        
        # Partial rest
        heal_amount = int(self.player.max_health * 0.3)
        mana_amount = int(self.player.max_mana * 0.3)
        self.player.health = min(self.player.max_health, self.player.health + heal_amount)
        self.player.mana = min(self.player.max_mana, self.player.mana + mana_amount)
        return f"You rest and recover {heal_amount} health and {mana_amount} mana."
    
    def cmd_skills(self, args):
        skills_text = f"{Fore.CYAN}=== Skills ==={Style.RESET_ALL}\n"
        
        for skill_id, skill in self.player.skills.items():
            skills_text += f"{Fore.YELLOW}{skill.name}{Style.RESET_ALL} (Level {skill.level})\n"
            skills_text += f"  {skill.description}\n"
            skills_text += f"  Experience: {skill.experience}/{skill.max_experience}\n\n"
        
        return skills_text
    
    def cmd_shop(self, args):
        location = self.locations[self.player.current_location]
        
        # Find merchant in current location
        merchant = None
        for npc_id in location.npcs:
            npc = self.npcs[npc_id]
            if npc.shop_items:
                merchant = npc
                break
        
        if not merchant:
            return "There's no shop here."
        
        shop_text = f"{Fore.CYAN}=== {merchant.name}'s Shop ==={Style.RESET_ALL}\n"
        shop_text += "Items for sale:\n"
        
        for item in merchant.shop_items:
            shop_text += f"  {item.name} - {item.value} gold\n"
        
        shop_text += "\nType 'buy <item>' to purchase or 'sell <item>' to sell."
        return shop_text
    
    def cmd_buy(self, args):
        if not args:
            return "Buy what? Specify an item name."
        
        item_name = " ".join(args).lower()
        location = self.locations[self.player.current_location]
        
        # Find merchant in current location
        merchant = None
        for npc_id in location.npcs:
            npc = self.npcs[npc_id]
            if npc.shop_items:
                merchant = npc
                break
        
        if not merchant:
            return "There's no shop here."
        
        # Find item in shop
        for item in merchant.shop_items:
            if item.name.lower() == item_name:
                if self.player.gold >= item.value:
                    self.player.gold -= item.value
                    self.player.add_item(item)
                    return f"You bought {item.name} for {item.value} gold."
                else:
                    return f"You don't have enough gold to buy {item.name}."
        
        return f"{merchant.name} doesn't have {item_name} for sale."
    
    def cmd_sell(self, args):
        if not args:
            return "Sell what? Specify an item name."
        
        item_name = " ".join(args).lower()
        location = self.locations[self.player.current_location]
        
        # Find merchant in current location
        merchant = None
        for npc_id in location.npcs:
            npc = self.npcs[npc_id]
            if npc.shop_items:
                merchant = npc
                break
        
        if not merchant:
            return "There's no shop here."
        
        # Find item in inventory
        for inv_item in self.player.inventory[:]:
            item = inv_item["item"]
            if item.name.lower() == item_name:
                sell_price = int(item.value * 0.5)  # Sell for half the value
                self.player.gold += sell_price
                self.player.remove_item(item.id)
                return f"You sold {item.name} for {sell_price} gold."
        
        return f"You don't have a {item_name} to sell."
    
    def cmd_map(self, args):
        location = self.locations[self.player.current_location]
        
        # Simple ASCII map
        map_text = f"{Fore.CYAN}=== Map ==={Style.RESET_ALL}\n"
        map_text += "You are here: *\n\n"
        
        # Show connected locations
        for direction, loc_id in location.exits.items():
            loc = self.locations[loc_id]
            map_text += f"{direction.capitalize()}: {loc.name}\n"
        
        return map_text
    
    def cmd_clear(self, args):
        self.clear_screen()
        return ""
    
    def cmd_version(self, args):
        return f"{GAME_TITLE} v{GAME_VERSION}"
    
    def cmd_config(self, args):
        if len(args) < 2:
            return "Usage: config <setting> <value>"
        
        setting = args[0]
        value = args[1]
        
        if setting == "text_speed":
            try:
                self.config.set_setting(setting, float(value))
                return f"Text speed set to {value}"
            except ValueError:
                return "Invalid value for text_speed"
        
        elif setting == "auto_save":
            if value.lower() in ["true", "false"]:
                self.config.set_setting(setting, value.lower() == "true")
                return f"Auto-save set to {value}"
            return "Value must be 'true' or 'false'"
        
        elif setting == "difficulty":
            if value in ["easy", "normal", "hard"]:
                self.config.set_setting(setting, value)
                return f"Difficulty set to {value}"
            return "Difficulty must be 'easy', 'normal', or 'hard'"
        
        elif setting == "debug_mode":
            if value.lower() in ["true", "false"]:
                self.config.set_setting(setting, value.lower() == "true")
                if value.lower() == "true":
                    self.plugin_manager.load_plugin("debug")
                return f"Debug mode set to {value}"
            return "Value must be 'true' or 'false'"
        
        return f"Unknown setting: {setting}"
    
    def start_combat(self, enemy):
        self.combat_active = True
        self.current_enemy = enemy
        self.print_slow(f"{Fore.RED}Combat started with {enemy.name}!{Style.RESET_ALL}")
        self.print_slow(f"{enemy.description}")
        self.print_slow(f"{enemy.name} - HP: {enemy.health}/{enemy.max_health}")
    
    def update_quest_progress(self, action, target):
        for quest_id, quest in self.player.quests.items():
            if quest.status == QuestStatus.IN_PROGRESS:
                for obj in quest.objectives:
                    if action in obj.lower() and target.lower() in obj.lower():
                        quest.progress[obj] += 1
                        
                        # Check if quest is complete
                        if all(progress > 0 for progress in quest.progress.values()):
                            quest.status = QuestStatus.COMPLETED
                            self.complete_quest(quest)
    
    def complete_quest(self, quest):
        self.print_slow(f"{Fore.GREEN}Quest Completed: {quest.name}{Style.RESET_ALL}")
        
        # Give rewards
        if "experience" in quest.rewards:
            self.player.add_experience(quest.rewards["experience"])
            self.print_slow(f"You gained {quest.rewards['experience']} experience!")
        
        if "gold" in quest.rewards:
            self.player.gold += quest.rewards["gold"]
            self.print_slow(f"You gained {quest.rewards['gold']} gold!")
        
        if "item" in quest.rewards:
            item_id = quest.rewards["item"]
            if item_id in self.items:
                self.player.add_item(self.items[item_id])
                self.print_slow(f"You received {self.items[item_id].name}!")
        
        # Trigger quest complete hook
        self.plugin_manager.trigger_hook("on_quest_complete", quest)
    
    def save_game(self, silent=False):
        try:
            save_data = {
                "player": self.player,
                "locations": self.locations,
                "config": self.config.settings
            }
            
            with open(SAVE_FILE, 'wb') as f:
                pickle.dump(save_data, f)
            
            if not silent:
                return "Game saved successfully!"
        except Exception as e:
            return f"Error saving game: {e}"
    
    def load_game(self):
        try:
            with open(SAVE_FILE, 'rb') as f:
                save_data = pickle.load(f)
            
            self.player = save_data["player"]
            self.locations = save_data["locations"]
            self.config.settings = save_data["config"]
            
            return True
        except Exception as e:
            self.print_slow(f"Error loading game: {e}")
            return False
    
    def print_slow(self, text, delay=None):
        if delay is None:
            delay = self.config.get_setting("text_speed", 0.03)
        
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(delay)
        print()
    
    def get_input(self, prompt):
        return input(prompt)
    
    def print_title(self):
        title = f"""
{Fore.CYAN}
 _____ _   _ _   _    _    _   _  ____ _____ ____  
| ____| \ | | | | |  / \  | \ | |/ ___| ____|  _ \ 
|  _| |  \| | |_| | / _ \ |  \| | |   |  _| | | | |
| |___| |\  |  _  |/ ___ \| |\  | |___| |___| |_| |
|_____|_| \_|_| |_/_/   \_\_| \_|\____|_____|____/ 
{Style.RESET_ALL}
{Fore.YELLOW}              A Text-Based RPG Adventure{Style.RESET_ALL}
{Fore.GREEN}                    Version {GAME_VERSION}{Style.RESET_ALL}
"""
        print(title)
        time.sleep(2)
    
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

# Main execution
if __name__ == "__main__":
    game = TextWorldGame()
    game.start()