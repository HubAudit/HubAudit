import os
import sys
import json
import random
import time
import math
import pickle
import importlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any, Union
from abc import ABC, abstractmethod

# Color codes for terminal output
class Colors:
    RESET = '\033[0m'
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'

# Game Enums
class Direction(Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTHEAST = "northeast"
    NORTHWEST = "northwest"
    SOUTHEAST = "southeast"
    SOUTHWEST = "southwest"
    UP = "up"
    DOWN = "down"

class SkillType(Enum):
    COMBAT = "combat"
    MAGIC = "magic"
    STEALTH = "stealth"
    CRAFTING = "crafting"
    SOCIAL = "social"
    SURVIVAL = "survival"

class Weather(Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    STORMY = "stormy"
    SNOWY = "snowy"
    FOGGY = "foggy"

class TimeOfDay(Enum):
    DAWN = "dawn"
    MORNING = "morning"
    NOON = "noon"
    AFTERNOON = "afternoon"
    DUSK = "dusk"
    EVENING = "evening"
    NIGHT = "night"
    MIDNIGHT = "midnight"

# Data Classes
@dataclass
class Position:
    x: int = 0
    y: int = 0
    z: int = 0

@dataclass
class Stats:
    health: int = 100
    max_health: int = 100
    mana: int = 50
    max_mana: int = 50
    stamina: int = 100
    max_stamina: int = 100
    hunger: int = 100
    max_hunger: int = 100
    thirst: int = 100
    max_thirst: int = 100
    experience: int = 0
    level: int = 1
    
    def level_up(self):
        self.level += 1
        self.experience = 0
        self.max_health += 10
        self.health = self.max_health
        self.max_mana += 5
        self.mana = self.max_mana
        self.max_stamina += 5
        self.stamina = self.max_stamina

@dataclass
class Skill:
    name: str
    type: SkillType
    level: int = 1
    experience: int = 0
    max_experience: int = 100
    
    def gain_experience(self, amount: int):
        self.experience += amount
        while self.experience >= self.max_experience:
            self.experience -= self.max_experience
            self.level += 1
            self.max_experience = int(self.max_experience * 1.5)
            return True  # Leveled up
        return False

@dataclass
class Item:
    id: str
    name: str
    description: str
    value: int = 0
    weight: float = 1.0
    consumable: bool = False
    equippable: bool = False
    stackable: bool = True
    max_stack: int = 99
    effects: Dict[str, Any] = field(default_factory=dict)
    
    def use(self, player):
        if self.consumable:
            for stat, value in self.effects.items():
                if hasattr(player.stats, stat):
                    current = getattr(player.stats, stat)
                    max_stat = getattr(player.stats, f"max_{stat}")
                    setattr(player.stats, stat, min(max_stat, current + value))
            return True
        return False

@dataclass
class Weapon(Item):
    damage: int = 10
    damage_type: str = "physical"
    two_handed: bool = False
    range: int = 1
    
    def __post_init__(self):
        self.equippable = True

@dataclass
class Armor(Item):
    defense: int = 5
    armor_type: str = "light"
    slot: str = "chest"
    
    def __post_init__(self):
        self.equippable = True

@dataclass
class Quest:
    id: str
    name: str
    description: str
    objectives: List[str]
    rewards: Dict[str, Any]
    completed: bool = False
    active: bool = False

@dataclass
class NPC:
    id: str
    name: str
    description: str
    dialogue: Dict[str, List[str]]
    location_id: str
    hostile: bool = False
    stats: Stats = field(default_factory=Stats)
    inventory: List[Item] = field(default_factory=list)
    quests: List[Quest] = field(default_factory=list)
    faction: str = "neutral"
    
    def talk(self, topic="greeting"):
        if topic in self.dialogue:
            return random.choice(self.dialogue[topic])
        return "I don't have anything to say about that."

@dataclass
class Location:
    id: str
    name: str
    description: str
    exits: Dict[Direction, str] = field(default_factory=dict)
    items: List[Item] = field(default_factory=list)
    npcs: List[NPC] = field(default_factory=list)
    discovered: bool = False
    indoor: bool = False
    position: Position = field(default_factory=Position)
    
    def add_exit(self, direction: Direction, location_id: str):
        self.exits[direction] = location_id
    
    def add_item(self, item: Item):
        self.items.append(item)
    
    def add_npc(self, npc: NPC):
        self.npcs.append(npc)
    
    def remove_item(self, item: Item):
        if item in self.items:
            self.items.remove(item)
            return True
        return False
    
    def remove_npc(self, npc: NPC):
        if npc in self.npcs:
            self.npcs.remove(npc)
            return True
        return False

# Plugin System
class Plugin(ABC):
    @abstractmethod
    def initialize(self, game):
        pass
    
    @abstractmethod
    def get_commands(self) -> Dict[str, Callable]:
        return {}

# Game Classes
class GameWorld:
    def __init__(self):
        self.locations: Dict[str, Location] = {}
        self.global_time: int = 0  # Game time in minutes
        self.weather: Weather = Weather.CLEAR
        self.time_of_day: TimeOfDay = TimeOfDay.MORNING
        self.day_count: int = 1
        
    def add_location(self, location: Location):
        self.locations[location.id] = location
    
    def get_location(self, location_id: str) -> Optional[Location]:
        return self.locations.get(location_id)
    
    def update_time(self, minutes: int = 1):
        self.global_time += minutes
        # Update day count (each day is 1440 minutes)
        self.day_count = (self.global_time // 1440) + 1
        
        # Update time of day (each period is 3 hours = 180 minutes)
        time_periods = list(TimeOfDay)
        period_index = (self.global_time // 180) % len(time_periods)
        self.time_of_day = time_periods[period_index]
        
        # Randomly change weather
        if random.random() < 0.05:  # 5% chance of weather change
            self.weather = random.choice(list(Weather))
    
    def get_time_description(self) -> str:
        return f"Day {self.day_count}, {self.time_of_day.value.capitalize()}, Weather: {self.weather.value.capitalize()}"

class Player:
    def __init__(self, name: str):
        self.name: str = name
        self.location_id: str = "start"
        self.stats: Stats = Stats()
        self.inventory: Dict[str, Tuple[Item, int]] = {}  # item_id: (item, quantity)
        self.equipped: Dict[str, Item] = {}  # slot: item
        self.skills: Dict[str, Skill] = {
            "combat": Skill("Combat", SkillType.COMBAT),
            "magic": Skill("Magic", SkillType.MAGIC),
            "stealth": Skill("Stealth", SkillType.STEALTH),
            "crafting": Skill("Crafting", SkillType.CRAFTING),
            "social": Skill("Social", SkillType.SOCIAL),
            "survival": Skill("Survival", SkillType.SURVIVAL)
        }
        self.quests: List[Quest] = []
        self.known_locations: List[str] = ["start"]
        self.faction_reputation: Dict[str, int] = {}
        
    def add_item(self, item: Item, quantity: int = 1):
        if item.id in self.inventory:
            current_item, current_quantity = self.inventory[item.id]
            if item.stackable:
                new_quantity = min(current_quantity + quantity, item.max_stack)
                self.inventory[item.id] = (current_item, new_quantity)
                return quantity - (new_quantity - current_quantity)  # Return leftover quantity
            else:
                # For non-stackable items, add multiple entries
                for _ in range(quantity):
                    self.inventory[f"{item.id}_{len(self.inventory)}"] = (item, 1)
                return 0
        else:
            self.inventory[item.id] = (item, quantity)
            return 0
    
    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        if item_id in self.inventory:
            item, current_quantity = self.inventory[item_id]
            if current_quantity <= quantity:
                del self.inventory[item_id]
                return True
            else:
                self.inventory[item_id] = (item, current_quantity - quantity)
                return True
        return False
    
    def has_item(self, item_id: str, quantity: int = 1) -> bool:
        if item_id in self.inventory:
            _, current_quantity = self.inventory[item_id]
            return current_quantity >= quantity
        return False
    
    def equip_item(self, item_id: str) -> bool:
        if item_id in self.inventory:
            item, _ = self.inventory[item_id]
            if item.equippable:
                # Determine slot based on item type
                if isinstance(item, Weapon):
                    slot = "weapon"
                elif isinstance(item, Armor):
                    slot = item.slot
                else:
                    slot = "accessory"
                
                # Unequip current item if any
                if slot in self.equipped:
                    self.add_item(self.equipped[slot])
                
                # Equip new item
                self.equipped[slot] = item
                self.remove_item(item_id)
                return True
        return False
    
    def unequip_item(self, slot: str) -> bool:
        if slot in self.equipped:
            item = self.equipped[slot]
            self.add_item(item)
            del self.equipped[slot]
            return True
        return False
    
    def get_total_defense(self) -> int:
        defense = 0
        for item in self.equipped.values():
            if isinstance(item, Armor):
                defense += item.defense
        return defense
    
    def get_total_damage(self) -> int:
        damage = 5  # Base damage
        if "weapon" in self.equipped:
            weapon = self.equipped["weapon"]
            if isinstance(weapon, Weapon):
                damage = weapon.damage
        return damage
    
    def gain_experience(self, amount: int):
        self.stats.experience += amount
        exp_needed = self.stats.level * 100  # Simple formula
        while self.stats.experience >= exp_needed:
            self.stats.experience -= exp_needed
            self.stats.level_up()
            exp_needed = self.stats.level * 100
            return True  # Leveled up
        return False
    
    def add_quest(self, quest: Quest):
        self.quests.append(quest)
        quest.active = True
    
    def complete_quest(self, quest_id: str) -> bool:
        for quest in self.quests:
            if quest.id == quest_id and quest.active and not quest.completed:
                quest.completed = True
                # Apply rewards
                if "experience" in quest.rewards:
                    self.gain_experience(quest.rewards["experience"])
                if "items" in quest.rewards:
                    for item_id, quantity in quest.rewards["items"].items():
                        # This would need a reference to the game world to get the actual item
                        pass
                if "reputation" in quest.rewards:
                    for faction, amount in quest.rewards["reputation"].items():
                        if faction in self.faction_reputation:
                            self.faction_reputation[faction] += amount
                        else:
                            self.faction_reputation[faction] = amount
                return True
        return False
    
    def update_vitals(self):
        # Decrease hunger and thirst over time
        self.stats.hunger = max(0, self.stats.hunger - 1)
        self.stats.thirst = max(0, self.stats.thirst - 1)
        
        # Apply effects of hunger and thirst
        if self.stats.hunger == 0:
            self.stats.health = max(0, self.stats.health - 2)
        if self.stats.thirst == 0:
            self.stats.health = max(0, self.stats.health - 3)
        
        # Regenerate health, mana, and stamina slowly
        if self.stats.health < self.stats.max_health:
            self.stats.health = min(self.stats.max_health, self.stats.health + 1)
        if self.stats.mana < self.stats.max_mana:
            self.stats.mana = min(self.stats.max_mana, self.stats.mana + 1)
        if self.stats.stamina < self.stats.max_stamina:
            self.stats.stamina = min(self.stats.max_stamina, self.stats.stamina + 2)

class CombatSystem:
    @staticmethod
    def attack(attacker, defender):
        # Calculate damage
        base_damage = attacker.get_total_damage() if hasattr(attacker, 'get_total_damage') else 10
        
        # Add some randomness
        damage = max(1, base_damage + random.randint(-2, 2))
        
        # Apply defense
        defense = defender.get_total_defense() if hasattr(defender, 'get_total_defense') else 0
        damage = max(1, damage - defense // 2)
        
        # Apply damage
        defender.stats.health = max(0, defender.stats.health - damage)
        
        return damage
    
    @staticmethod
    def check_flee(player, npc) -> bool:
        # Base chance to flee is 50%, modified by player's level vs NPC's level
        base_chance = 0.5
        level_diff = player.stats.level - npc.stats.level
        chance = base_chance + (level_diff * 0.1)
        chance = max(0.1, min(0.9, chance))  # Clamp between 10% and 90%
        
        return random.random() < chance

class Game:
    def __init__(self):
        self.world = GameWorld()
        self.player = None
        self.running = True
        self.plugins: Dict[str, Plugin] = {}
        self.commands: Dict[str, Callable] = {}
        self.combat = CombatSystem()
        self.in_combat = False
        self.current_opponent = None
        
        # Initialize core commands
        self.register_command("help", self.cmd_help)
        self.register_command("quit", self.cmd_quit)
        self.register_command("look", self.cmd_look)
        self.register_command("go", self.cmd_go)
        self.register_command("take", self.cmd_take)
        self.register_command("inventory", self.cmd_inventory)
        self.register_command("use", self.cmd_use)
        self.register_command("equip", self.cmd_equip)
        self.register_command("unequip", self.cmd_unequip)
        self.register_command("talk", self.cmd_talk)
        self.register_command("attack", self.cmd_attack)
        self.register_command("flee", self.cmd_flee)
        self.register_command("quests", self.cmd_quests)
        self.register_command("skills", self.cmd_skills)
        self.register_command("time", self.cmd_time)
        self.register_command("save", self.cmd_save)
        self.register_command("load", self.cmd_load)
        self.register_command("wait", self.cmd_wait)
        self.register_command("status", self.cmd_status)
        self.register_command("drop", self.cmd_drop)
        self.register_command("examine", self.cmd_examine)
        self.register_command("map", self.cmd_map)
        self.register_command("rest", self.cmd_rest)
        self.register_command("plugins", self.cmd_plugins)
        
        # Initialize the game world
        self.initialize_world()
    
    def register_command(self, name: str, func: Callable):
        self.commands[name] = func
    
    def load_plugin(self, plugin_path: str):
        try:
            spec = importlib.util.spec_from_file_location("plugin", plugin_path)
            plugin_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(plugin_module)
            
            # Get plugin class (should be named "Plugin")
            if hasattr(plugin_module, "Plugin"):
                plugin_class = getattr(plugin_module, "Plugin")
                plugin = plugin_class()
                plugin.initialize(self)
                
                # Register plugin commands
                plugin_commands = plugin.get_commands()
                for name, func in plugin_commands.items():
                    self.register_command(name, func)
                
                self.plugins[plugin_path] = plugin
                return True
        except Exception as e:
            print(f"{Colors.RED}Error loading plugin: {e}{Colors.RESET}")
        return False
    
    def unload_plugin(self, plugin_path: str):
        if plugin_path in self.plugins:
            plugin = self.plugins[plugin_path]
            plugin_commands = plugin.get_commands()
            
            # Unregister plugin commands
            for name in plugin_commands:
                if name in self.commands:
                    del self.commands[name]
            
            del self.plugins[plugin_path]
            return True
        return False
    
    def initialize_world(self):
        # Create starting location
        start_location = Location(
            id="start",
            name="Starting Village",
            description="A small village surrounded by forests and mountains. There's a path leading north to the forest and east to the mountains.",
            position=Position(0, 0, 0)
        )
        
        # Create forest location
        forest_location = Location(
            id="forest",
            name="Dark Forest",
            description="A dense forest with tall trees and little light. You can hear strange sounds in the distance.",
            position=Position(0, 1, 0)
        )
        
        # Create mountain location
        mountain_location = Location(
            id="mountain",
            name="Mountain Pass",
            description="A narrow path through the mountains. It's cold and windy here.",
            position=Position(1, 0, 0)
        )
        
        # Create cave location
        cave_location = Location(
            id="cave",
            name="Mysterious Cave",
            description="A dark cave with glowing crystals on the walls. You can hear dripping water.",
            position=Position(0, 0, -1),
            indoor=True
        )
        
        # Create village shop
        shop_location = Location(
            id="shop",
            name="Village Shop",
            description="A small shop with various items for sale. The shopkeeper looks friendly.",
            position=Position(-1, 0, 0),
            indoor=True
        )
        
        # Connect locations
        start_location.add_exit(Direction.NORTH, "forest")
        start_location.add_exit(Direction.EAST, "mountain")
        start_location.add_exit(Direction.WEST, "shop")
        
        forest_location.add_exit(Direction.SOUTH, "start")
        forest_location.add_exit(Direction.DOWN, "cave")
        
        mountain_location.add_exit(Direction.WEST, "start")
        
        cave_location.add_exit(Direction.UP, "forest")
        
        shop_location.add_exit(Direction.EAST, "start")
        
        # Add items to locations
        # Starting village items
        start_location.add_item(Item(
            id="apple",
            name="Apple",
            description="A fresh red apple. Looks delicious.",
            value=5,
            consumable=True,
            effects={"hunger": 20}
        ))
        
        start_location.add_item(Item(
            id="bread",
            name="Bread",
            description="A loaf of bread. Still warm.",
            value=10,
            consumable=True,
            effects={"hunger": 40}
        ))
        
        # Forest items
        forest_location.add_item(Weapon(
            id="sword",
            name="Rusty Sword",
            description="An old rusty sword. Better than nothing.",
            value=25,
            damage=15,
            weight=3.0
        ))
        
        forest_location.add_item(Item(
            id="herb",
            name="Healing Herb",
            description="A green herb with medicinal properties.",
            value=15,
            consumable=True,
            effects={"health": 20}
        ))
        
        # Cave items
        cave_location.add_item(Item(
            id="crystal",
            name="Magic Crystal",
            description="A glowing crystal that hums with magical energy.",
            value=100,
            consumable=True,
            effects={"mana": 50}
        ))
        
        # Shop items
        shop_location.add_item(Weapon(
            id="dagger",
            name="Dagger",
            description="A sharp dagger. Good for quick attacks.",
            value=30,
            damage=10,
            weight=1.0
        ))
        
        shop_location.add_item(Armor(
            id="leather_armor",
            name="Leather Armor",
            description="Simple armor made of leather. Provides basic protection.",
            value=50,
            defense=10,
            armor_type="light",
            slot="chest"
        ))
        
        # Add NPCs
        # Village elder
        elder = NPC(
            id="elder",
            name="Village Elder",
            description="An old man with a long white beard and wise eyes.",
            dialogue={
                "greeting": [
                    "Welcome to our humble village, young adventurer.",
                    "Ah, a new face. What brings you to our village?"
                ],
                "quest": [
                    "We have a problem with wolves in the forest. Could you help us?",
                    "The forest to the north has become dangerous. Please investigate."
                ],
                "help": [
                    "You can use 'go [direction]' to move around.",
                    "Try 'talk [npc]' to interact with people."
                ]
            },
            location_id="start"
        )
        
        # Add quest to elder
        wolf_quest = Quest(
            id="wolf_problem",
            name="Wolf Problem",
            description="Deal with the wolves in the forest.",
            objectives=["Kill 5 wolves"],
            rewards={
                "experience": 100,
                "items": {"gold": 50}
            }
        )
        elder.quests.append(wolf_quest)
        
        # Shopkeeper
        shopkeeper = NPC(
            id="shopkeeper",
            name="Shopkeeper",
            description="A friendly-looking person with a big smile.",
            dialogue={
                "greeting": [
                    "Welcome to my shop! Feel free to browse.",
                    "Hello! Looking for something special?"
                ],
                "buy": [
                    "What would you like to buy?",
                    "Everything here is for sale, just name it."
                ],
                "sell": [
                    "What do you want to sell me?",
                    "I'll give you a fair price for your items."
                ]
            },
            location_id="shop"
        )
        
        # Forest wolf
        wolf = NPC(
            id="wolf",
            name="Wolf",
            description="A wild wolf with sharp teeth and hungry eyes.",
            dialogue={},
            location_id="forest",
            hostile=True,
            stats=Stats(health=50, max_health=50)
        )
        
        # Add NPCs to locations
        start_location.add_npc(elder)
        shop_location.add_npc(shopkeeper)
        forest_location.add_npc(wolf)
        
        # Add locations to world
        self.world.add_location(start_location)
        self.world.add_location(forest_location)
        self.world.add_location(mountain_location)
        self.world.add_location(cave_location)
        self.world.add_location(shop_location)
    
    def start(self):
        self.clear_screen()
        self.print_title()
        
        # Character creation
        name = input(f"{Colors.CYAN}Enter your character's name: {Colors.RESET}")
        self.player = Player(name)
        
        # Welcome message
        self.print_wrapped(f"{Colors.GREEN}Welcome, {self.player.name}!{Colors.RESET}")
        self.print_wrapped("You find yourself in a small village. Your adventure begins here.")
        self.print_wrapped("Type 'help' for a list of commands.")
        self.print_separator()
        
        # Main game loop
        while self.running:
            if not self.in_combat:
                # Update game world
                self.world.update_time()
                self.player.update_vitals()
                
                # Check if player is dead
                if self.player.stats.health <= 0:
                    self.game_over()
                    break
                
                # Display location
                self.display_location()
            
            # Get player input
            try:
                command_input = input(f"{Colors.YELLOW}> {Colors.RESET}").strip().lower()
                if not command_input:
                    continue
                
                # Parse command
                parts = command_input.split()
                command = parts[0]
                args = parts[1:] if len(parts) > 1 else []
                
                # Execute command
                if command in self.commands:
                    self.commands[command](args)
                else:
                    print(f"{Colors.RED}Unknown command: {command}{Colors.RESET}")
                    print(f"{Colors.CYAN}Type 'help' for a list of commands.{Colors.RESET}")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                self.running = False
            except EOFError:
                print("\nGoodbye!")
                self.running = False
            except Exception as e:
                print(f"{Colors.RED}Error: {e}{Colors.RESET}")
    
    def game_over(self):
        self.clear_screen()
        print(f"{Colors.RED}========================================{Colors.RESET}")
        print(f"{Colors.RED}            GAME OVER{Colors.RESET}")
        print(f"{Colors.RED}========================================{Colors.RESET}")
        print(f"{Colors.WHITE}You have died.{Colors.RESET}")
        print(f"{Colors.WHITE}Level reached: {self.player.stats.level}{Colors.RESET}")
        print(f"{Colors.WHITE}Experience gained: {self.player.stats.experience}{Colors.RESET}")
        print(f"{Colors.RED}========================================{Colors.RESET}")
        self.running = False
    
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_title(self):
        print(f"{Colors.BRIGHT_CYAN}")
        print("========================================")
        print("       ULTIMATE OPEN WORLD GAME        ")
        print("========================================")
        print(f"{Colors.RESET}")
    
    def print_separator(self):
        print(f"{Colors.BRIGHT_BLACK}----------------------------------------{Colors.RESET}")
    
    def print_wrapped(self, text, width=80):
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= width:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        for line in lines:
            print(line)
    
    def display_location(self):
        location = self.world.get_location(self.player.location_id)
        if not location:
            return
        
        # Mark location as discovered
        if not location.discovered:
            location.discovered = True
            if location.id not in self.player.known_locations:
                self.player.known_locations.append(location.id)
        
        # Display location name
        print(f"{Colors.BRIGHT_GREEN}{location.name}{Colors.RESET}")
        
        # Display location description
        self.print_wrapped(f"{Colors.WHITE}{location.description}{Colors.RESET}")
        
        # Display time and weather
        print(f"{Colors.CYAN}{self.world.get_time_description()}{Colors.RESET}")
        
        # Display exits
        if location.exits:
            exits = ", ".join([d.value for d in location.exits.keys()])
            print(f"{Colors.YELLOW}Exits: {exits}{Colors.RESET}")
        
        # Display items
        if location.items:
            item_names = [f"{item.name} ({quantity})" if item.stackable else item.name 
                         for item, quantity in [(item, 1) for item in location.items]]
            print(f"{Colors.GREEN}Items: {', '.join(item_names)}{Colors.RESET}")
        
        # Display NPCs
        if location.npcs:
            npc_names = [npc.name for npc in location.npcs]
            print(f"{Colors.MAGENTA}People: {', '.join(npc_names)}{Colors.RESET}")
        
        self.print_separator()
    
    # Command implementations
    def cmd_help(self, args):
        print(f"{Colors.CYAN}Available commands:{Colors.RESET}")
        for command in sorted(self.commands.keys()):
            print(f"  {Colors.YELLOW}{command}{Colors.RESET}")
        print(f"\n{Colors.CYAN}For more information on a command, type: help [command]{Colors.RESET}")
    
    def cmd_quit(self, args):
        print(f"{Colors.YELLOW}Are you sure you want to quit? (y/n){Colors.RESET}")
        response = input("> ").strip().lower()
        if response == 'y':
            self.running = False
    
    def cmd_look(self, args):
        self.display_location()
    
    def cmd_go(self, args):
        if not args:
            print(f"{Colors.RED}Go where?{Colors.RESET}")
            return
        
        direction_str = args[0]
        try:
            direction = Direction(direction_str)
        except ValueError:
            print(f"{Colors.RED}Invalid direction: {direction_str}{Colors.RESET}")
            return
        
        location = self.world.get_location(self.player.location_id)
        if not location:
            return
        
        if direction in location.exits:
            # Check for hostile NPCs that might block the way
            for npc in location.npcs:
                if npc.hostile and npc.stats.health > 0:
                    print(f"{Colors.RED}{npc.name} blocks your path!{Colors.RESET}")
                    self.start_combat(npc)
                    return
            
            # Move to the new location
            self.player.location_id = location.exits[direction]
            print(f"{Colors.GREEN}You go {direction.value}.{Colors.RESET}")
            
            # Update time (movement takes time)
            self.world.update_time(5)
            
            # Consume stamina
            self.player.stats.stamina = max(0, self.player.stats.stamina - 5)
            
            # Check for random encounters
            if random.random() < 0.1:  # 10% chance of random encounter
                self.random_encounter()
        else:
            print(f"{Colors.RED}You can't go {direction.value} from here.{Colors.RESET}")
    
    def cmd_take(self, args):
        if not args:
            print(f"{Colors.RED}Take what?{Colors.RESET}")
            return
        
        item_name = ' '.join(args)
        location = self.world.get_location(self.player.location_id)
        if not location:
            return
        
        # Find the item
        for item in location.items:
            if item.name.lower() == item_name.lower():
                # Add to player inventory
                leftover = self.player.add_item(item)
                if leftover == 0:
                    location.remove_item(item)
                    print(f"{Colors.GREEN}You take the {item.name}.{Colors.RESET}")
                else:
                    print(f"{Colors.YELLOW}You can only carry {item.max_stack} {item.name}s.{Colors.RESET}")
                return
        
        print(f"{Colors.RED}There is no {item_name} here.{Colors.RESET}")
    
    def cmd_inventory(self, args):
        if not self.player.inventory:
            print(f"{Colors.YELLOW}Your inventory is empty.{Colors.RESET}")
            return
        
        print(f"{Colors.CYAN}Inventory:{Colors.RESET}")
        for item_id, (item, quantity) in self.player.inventory.items():
            if item.stackable:
                print(f"  {Colors.GREEN}{item.name} x{quantity}{Colors.RESET} - {item.description}")
            else:
                print(f"  {Colors.GREEN}{item.name}{Colors.RESET} - {item.description}")
        
        # Show equipped items
        if self.player.equipped:
            print(f"\n{Colors.CYAN}Equipped:{Colors.RESET}")
            for slot, item in self.player.equipped.items():
                print(f"  {Colors.YELLOW}{slot}: {item.name}{Colors.RESET}")
    
    def cmd_use(self, args):
        if not args:
            print(f"{Colors.RED}Use what?{Colors.RESET}")
            return
        
        item_name = ' '.join(args)
        
        # Find the item in inventory
        for item_id, (item, quantity) in self.player.inventory.items():
            if item.name.lower() == item_name.lower():
                if item.use(self.player):
                    if item.consumable:
                        if quantity > 1:
                            self.player.inventory[item_id] = (item, quantity - 1)
                        else:
                            self.player.remove_item(item_id)
                    print(f"{Colors.GREEN}You use the {item.name}.{Colors.RESET}")
                else:
                    print(f"{Colors.RED}You can't use the {item.name}.{Colors.RESET}")
                return
        
        print(f"{Colors.RED}You don't have a {item_name}.{Colors.RESET}")
    
    def cmd_equip(self, args):
        if not args:
            print(f"{Colors.RED}Equip what?{Colors.RESET}")
            return
        
        item_name = ' '.join(args)
        
        # Find the item in inventory
        for item_id, (item, quantity) in self.player.inventory.items():
            if item.name.lower() == item_name.lower():
                if self.player.equip_item(item_id):
                    print(f"{Colors.GREEN}You equip the {item.name}.{Colors.RESET}")
                else:
                    print(f"{Colors.RED}You can't equip the {item.name}.{Colors.RESET}")
                return
        
        print(f"{Colors.RED}You don't have a {item_name}.{Colors.RESET}")
    
    def cmd_unequip(self, args):
        if not args:
            print(f"{Colors.RED}Unequip what?{Colors.RESET}")
            return
        
        slot = args[0].lower()
        
        if self.player.unequip_item(slot):
            print(f"{Colors.GREEN}You unequip your {slot}.{Colors.RESET}")
        else:
            print(f"{Colors.RED}You don't have anything equipped in that slot.{Colors.RESET}")
    
    def cmd_talk(self, args):
        if not args:
            print(f"{Colors.RED}Talk to whom?{Colors.RESET}")
            return
        
        npc_name = ' '.join(args)
        location = self.world.get_location(self.player.location_id)
        if not location:
            return
        
        # Find the NPC
        for npc in location.npcs:
            if npc.name.lower() == npc_name.lower():
                # Get dialogue topic
                topic = "greeting"
                if len(args) > 1:
                    topic = ' '.join(args[1:])
                
                # Get dialogue
                dialogue = npc.talk(topic)
                print(f"{Colors.MAGENTA}{npc.name}: {dialogue}{Colors.RESET}")
                
                # Check for quests
                if topic == "quest" and npc.quests:
                    for quest in npc.quests:
                        if not quest.completed and not any(q.id == quest.id for q in self.player.quests):
                            self.player.add_quest(quest)
                            print(f"{Colors.GREEN}New quest: {quest.name}{Colors.RESET}")
                            print(f"{Colors.WHITE}{quest.description}{Colors.RESET}")
                
                return
        
        print(f"{Colors.RED}There is no one named {npc_name} here.{Colors.RESET}")
    
    def cmd_attack(self, args):
        if not args:
            print(f"{Colors.RED}Attack whom?{Colors.RESET}")
            return
        
        npc_name = ' '.join(args)
        location = self.world.get_location(self.player.location_id)
        if not location:
            return
        
        # Find the NPC
        for npc in location.npcs:
            if npc.name.lower() == npc_name.lower():
                if not npc.hostile:
                    print(f"{Colors.RED}You can't attack {npc.name}.{Colors.RESET}")
                    return
                
                self.start_combat(npc)
                return
        
        print(f"{Colors.RED}There is no one named {npc_name} here.{Colors.RESET}")
    
    def cmd_flee(self, args):
        if not self.in_combat:
            print(f"{Colors.RED}You're not in combat.{Colors.RESET}")
            return
        
        if self.combat.check_flee(self.player, self.current_opponent):
            print(f"{Colors.GREEN}You successfully flee from combat.{Colors.RESET}")
            self.end_combat()
            
            # Move to a random adjacent location
            location = self.world.get_location(self.player.location_id)
            if location and location.exits:
                directions = list(location.exits.keys())
                random_direction = random.choice(directions)
                self.player.location_id = location.exits[random_direction]
                print(f"{Colors.GREEN}You run away to the {random_direction.value}.{Colors.RESET}")
        else:
            print(f"{Colors.RED}You fail to flee!{Colors.RESET}")
            # Enemy gets a free attack
            damage = self.combat.attack(self.current_opponent, self.player)
            print(f"{Colors.RED}{self.current_opponent.name} attacks you for {damage} damage!{Colors.RESET}")
            
            if self.player.stats.health <= 0:
                self.game_over()
    
    def cmd_quests(self, args):
        if not self.player.quests:
            print(f"{Colors.YELLOW}You don't have any active quests.{Colors.RESET}")
            return
        
        print(f"{Colors.CYAN}Active Quests:{Colors.RESET}")
        for quest in self.player.quests:
            if quest.active and not quest.completed:
                print(f"  {Colors.YELLOW}{quest.name}{Colors.RESET}")
                print(f"    {quest.description}")
                print(f"    Objectives: {', '.join(quest.objectives)}")
        
        print(f"\n{Colors.CYAN}Completed Quests:{Colors.RESET}")
        for quest in self.player.quests:
            if quest.completed:
                print(f"  {Colors.GREEN}{quest.name}{Colors.RESET}")
    
    def cmd_skills(self, args):
        print(f"{Colors.CYAN}Skills:{Colors.RESET}")
        for skill_name, skill in self.player.skills.items():
            print(f"  {Colors.YELLOW}{skill.name}: Level {skill.level} ({skill.experience}/{skill.max_experience} XP){Colors.RESET}")
    
    def cmd_time(self, args):
        print(f"{Colors.CYAN}{self.world.get_time_description()}{Colors.RESET}")
    
    def cmd_save(self, args):
        save_name = args[0] if args else "save1"
        save_data = {
            "player": self.player,
            "world": self.world,
            "in_combat": self.in_combat,
            "current_opponent": self.current_opponent
        }
        
        try:
            with open(f"{save_name}.sav", "wb") as f:
                pickle.dump(save_data, f)
            print(f"{Colors.GREEN}Game saved as {save_name}.{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Failed to save game: {e}{Colors.RESET}")
    
    def cmd_load(self, args):
        save_name = args[0] if args else "save1"
        
        try:
            with open(f"{save_name}.sav", "rb") as f:
                save_data = pickle.load(f)
            
            self.player = save_data["player"]
            self.world = save_data["world"]
            self.in_combat = save_data["in_combat"]
            self.current_opponent = save_data["current_opponent"]
            
            print(f"{Colors.GREEN}Game loaded from {save_name}.{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Failed to load game: {e}{Colors.RESET}")
    
    def cmd_wait(self, args):
        minutes = 30  # Default wait time
        if args:
            try:
                minutes = int(args[0])
            except ValueError:
                print(f"{Colors.RED}Invalid time: {args[0]}{Colors.RESET}")
                return
        
        print(f"{Colors.YELLOW}You wait for {minutes} minutes...{Colors.RESET}")
        self.world.update_time(minutes)
        self.player.update_vitals()
        
        # Random events while waiting
        if random.random() < 0.2:  # 20% chance of something happening
            self.random_event()
    
    def cmd_status(self, args):
        print(f"{Colors.CYAN}Character Status:{Colors.RESET}")
        print(f"  Name: {self.player.name}")
        print(f"  Level: {self.player.stats.level}")
        print(f"  Experience: {self.player.stats.experience}")
        print(f"  Health: {self.player.stats.health}/{self.player.stats.max_health}")
        print(f"  Mana: {self.player.stats.mana}/{self.player.stats.max_mana}")
        print(f"  Stamina: {self.player.stats.stamina}/{self.player.stats.max_stamina}")
        print(f"  Hunger: {self.player.stats.hunger}/{self.player.stats.max_hunger}")
        print(f"  Thirst: {self.player.stats.thirst}/{self.player.stats.max_thirst}")
        print(f"  Defense: {self.player.get_total_defense()}")
        print(f"  Damage: {self.player.get_total_damage()}")
    
    def cmd_drop(self, args):
        if not args:
            print(f"{Colors.RED}Drop what?{Colors.RESET}")
            return
        
        item_name = ' '.join(args)
        location = self.world.get_location(self.player.location_id)
        if not location:
            return
        
        # Find the item in inventory
        for item_id, (item, quantity) in self.player.inventory.items():
            if item.name.lower() == item_name.lower():
                # Remove from player inventory
                if self.player.remove_item(item_id):
                    # Add to location
                    location.add_item(item)
                    print(f"{Colors.GREEN}You drop the {item.name}.{Colors.RESET}")
                return
        
        print(f"{Colors.RED}You don't have a {item_name}.{Colors.RESET}")
    
    def cmd_examine(self, args):
        if not args:
            print(f"{Colors.RED}Examine what?{Colors.RESET}")
            return
        
        target_name = ' '.join(args)
        location = self.world.get_location(self.player.location_id)
        if not location:
            return
        
        # Check items
        for item in location.items:
            if item.name.lower() == target_name.lower():
                print(f"{Colors.GREEN}{item.name}: {item.description}{Colors.RESET}")
                if isinstance(item, Weapon):
                    print(f"  Damage: {item.damage}, Type: {item.damage_type}")
                elif isinstance(item, Armor):
                    print(f"  Defense: {item.defense}, Type: {item.armor_type}, Slot: {item.slot}")
                return
        
        # Check NPCs
        for npc in location.npcs:
            if npc.name.lower() == target_name.lower():
                print(f"{Colors.MAGENTA}{npc.name}: {npc.description}{Colors.RESET}")
                if npc.hostile:
                    print(f"  {Colors.RED}Hostile{Colors.RESET}")
                print(f"  Health: {npc.stats.health}/{npc.stats.max_health}")
                return
        
        print(f"{Colors.RED}There is no {target_name} here.{Colors.RESET}")
    
    def cmd_map(self, args):
        print(f"{Colors.CYAN}Map of Known Locations:{Colors.RESET}")
        
        # Get all known locations
        known_locations = [self.world.get_location(loc_id) for loc_id in self.player.known_locations]
        if not known_locations:
            print(f"{Colors.YELLOW}You haven't discovered any locations yet.{Colors.RESET}")
            return
        
        # Find min and max coordinates
        min_x = min(loc.position.x for loc in known_locations)
        max_x = max(loc.position.x for loc in known_locations)
        min_y = min(loc.position.y for loc in known_locations)
        max_y = max(loc.position.y for loc in known_locations)
        
        # Create map grid
        grid_width = max_x - min_x + 1
        grid_height = max_y - min_y + 1
        grid = [[' ' for _ in range(grid_width)] for _ in range(grid_height)]
        
        # Place locations on grid
        for loc in known_locations:
            x = loc.position.x - min_x
            y = loc.position.y - min_y
            
            if loc.id == self.player.location_id:
                grid[y][x] = 'X'  # Player's current location
            else:
                grid[y][x] = 'O'  # Other known locations
        
        # Print map
        print(f"{Colors.BRIGHT_BLACK}+{'-' * grid_width}+{Colors.RESET}")
        for row in grid:
            print(f"{Colors.BRIGHT_BLACK}|{Colors.RESET}", end="")
            for cell in row:
                if cell == 'X':
                    print(f"{Colors.GREEN}{cell}{Colors.RESET}", end="")
                elif cell == 'O':
                    print(f"{Colors.YELLOW}{cell}{Colors.RESET}", end="")
                else:
                    print(cell, end="")
            print(f"{Colors.BRIGHT_BLACK}|{Colors.RESET}")
        print(f"{Colors.BRIGHT_BLACK}+{'-' * grid_width}+{Colors.RESET}")
        print(f"{Colors.GREEN}X = Your location{Colors.RESET}")
        print(f"{Colors.YELLOW}O = Known location{Colors.RESET}")
    
    def cmd_rest(self, args):
        if self.in_combat:
            print(f"{Colors.RED}You can't rest during combat!{Colors.RESET}")
            return
        
        location = self.world.get_location(self.player.location_id)
        if location and not location.indoor:
            print(f"{Colors.YELLOW}Resting outdoors is not safe. You might be attacked.{Colors.RESET}")
            response = input("Continue anyway? (y/n) ").strip().lower()
            if response != 'y':
                return
        
        print(f"{Colors.YELLOW}You rest for a while...{Colors.RESET}")
        
        # Restore health, mana, and stamina
        self.player.stats.health = self.player.stats.max_health
        self.player.stats.mana = self.player.stats.max_mana
        self.player.stats.stamina = self.player.stats.max_stamina
        
        # Advance time
        self.world.update_time(60)  # Rest for 1 hour
        
        # Random event chance
        if random.random() < 0.3:  # 30% chance of something happening
            self.random_event()
    
    def cmd_plugins(self, args):
        if not args:
            print(f"{Colors.CYAN}Loaded plugins:{Colors.RESET}")
            for plugin_path in self.plugins:
                print(f"  {plugin_path}")
            return
        
        command = args[0].lower()
        
        if command == "load" and len(args) > 1:
            plugin_path = args[1]
            if self.load_plugin(plugin_path):
                print(f"{Colors.GREEN}Plugin loaded: {plugin_path}{Colors.RESET}")
            else:
                print(f"{Colors.RED}Failed to load plugin: {plugin_path}{Colors.RESET}")
        elif command == "unload" and len(args) > 1:
            plugin_path = args[1]
            if self.unload_plugin(plugin_path):
                print(f"{Colors.GREEN}Plugin unloaded: {plugin_path}{Colors.RESET}")
            else:
                print(f"{Colors.RED}Failed to unload plugin: {plugin_path}{Colors.RESET}")
        else:
            print(f"{Colors.RED}Usage: plugins [load|unload] [path]{Colors.RESET}")
    
    # Combat methods
    def start_combat(self, opponent):
        self.in_combat = True
        self.current_opponent = opponent
        
        print(f"{Colors.RED}Combat started with {opponent.name}!{Colors.RESET}")
        
        # Combat loop
        while self.in_combat:
            # Display combat status
            print(f"{Colors.RED}{opponent.name}: {opponent.stats.health}/{opponent.stats.max_health} HP{Colors.RESET}")
            print(f"{Colors.GREEN}You: {self.player.stats.health}/{self.player.stats.max_health} HP{Colors.RESET}")
            
            # Get player action
            try:
                action = input(f"{Colors.YELLOW}What do you do? (attack/flee/use/item): {Colors.RESET}").strip().lower()
                
                if action == "attack":
                    # Player attacks
                    damage = self.combat.attack(self.player, opponent)
                    print(f"{Colors.GREEN}You attack {opponent.name} for {damage} damage!{Colors.RESET}")
                    
                    # Check if opponent is defeated
                    if opponent.stats.health <= 0:
                        print(f"{Colors.GREEN}You defeated {opponent.name}!{Colors.RESET}")
                        
                        # Gain experience
                        exp_gained = opponent.stats.level * 20
                        leveled_up = self.player.gain_experience(exp_gained)
                        print(f"{Colors.GREEN}You gained {exp_gained} experience!{Colors.RESET}")
                        if leveled_up:
                            print(f"{Colors.BRIGHT_GREEN}You leveled up! You are now level {self.player.stats.level}.{Colors.RESET}")
                        
                        # Loot opponent
                        if opponent.inventory:
                            for item in opponent.inventory:
                                self.player.add_item(item)
                                print(f"{Colors.GREEN}You looted: {item.name}{Colors.RESET}")
                        
                        self.end_combat()
                        continue
                    
                    # Opponent attacks
                    damage = self.combat.attack(opponent, self.player)
                    print(f"{Colors.RED}{opponent.name} attacks you for {damage} damage!{Colors.RESET}")
                    
                    # Check if player is defeated
                    if self.player.stats.health <= 0:
                        self.game_over()
                        break
                
                elif action == "flee":
                    if self.combat.check_flee(self.player, opponent):
                        print(f"{Colors.GREEN}You successfully flee from combat.{Colors.RESET}")
                        self.end_combat()
                        
                        # Move to a random adjacent location
                        location = self.world.get_location(self.player.location_id)
                        if location and location.exits:
                            directions = list(location.exits.keys())
                            random_direction = random.choice(directions)
                            self.player.location_id = location.exits[random_direction]
                            print(f"{Colors.GREEN}You run away to the {random_direction.value}.{Colors.RESET}")
                    else:
                        print(f"{Colors.RED}You fail to flee!{Colors.RESET}")
                        # Opponent gets a free attack
                        damage = self.combat.attack(opponent, self.player)
                        print(f"{Colors.RED}{opponent.name} attacks you for {damage} damage!{Colors.RESET}")
                        
                        if self.player.stats.health <= 0:
                            self.game_over()
                            break
                
                elif action == "use":
                    item_name = input(f"{Colors.YELLOW}Use what item? {Colors.RESET}").strip().lower()
                    
                    # Find the item in inventory
                    for item_id, (item, quantity) in self.player.inventory.items():
                        if item.name.lower() == item_name.lower():
                            if item.use(self.player):
                                if item.consumable:
                                    if quantity > 1:
                                        self.player.inventory[item_id] = (item, quantity - 1)
                                    else:
                                        self.player.remove_item(item_id)
                                print(f"{Colors.GREEN}You use the {item.name}.{Colors.RESET}")
                            else:
                                print(f"{Colors.RED}You can't use the {item.name}.{Colors.RESET}")
                            break
                    else:
                        print(f"{Colors.RED}You don't have a {item_name}.{Colors.RESET}")
                    
                    # Opponent attacks
                    damage = self.combat.attack(opponent, self.player)
                    print(f"{Colors.RED}{opponent.name} attacks you for {damage} damage!{Colors.RESET}")
                    
                    if self.player.stats.health <= 0:
                        self.game_over()
                        break
                
                elif action == "item":
                    # Use an item (same as "use")
                    item_name = input(f"{Colors.YELLOW}Use what item? {Colors.RESET}").strip().lower()
                    
                    # Find the item in inventory
                    for item_id, (item, quantity) in self.player.inventory.items():
                        if item.name.lower() == item_name.lower():
                            if item.use(self.player):
                                if item.consumable:
                                    if quantity > 1:
                                        self.player.inventory[item_id] = (item, quantity - 1)
                                    else:
                                        self.player.remove_item(item_id)
                                print(f"{Colors.GREEN}You use the {item.name}.{Colors.RESET}")
                            else:
                                print(f"{Colors.RED}You can't use the {item.name}.{Colors.RESET}")
                            break
                    else:
                        print(f"{Colors.RED}You don't have a {item_name}.{Colors.RESET}")
                    
                    # Opponent attacks
                    damage = self.combat.attack(opponent, self.player)
                    print(f"{Colors.RED}{opponent.name} attacks you for {damage} damage!{Colors.RESET}")
                    
                    if self.player.stats.health <= 0:
                        self.game_over()
                        break
                
                else:
                    print(f"{Colors.RED}Invalid action!{Colors.RESET}")
                    # Opponent gets a free attack
                    damage = self.combat.attack(opponent, self.player)
                    print(f"{Colors.RED}{opponent.name} attacks you for {damage} damage!{Colors.RESET}")
                    
                    if self.player.stats.health <= 0:
                        self.game_over()
                        break
            
            except KeyboardInterrupt:
                print("\nGoodbye!")
                self.running = False
                break
            except EOFError:
                print("\nGoodbye!")
                self.running = False
                break
            except Exception as e:
                print(f"{Colors.RED}Error: {e}{Colors.RESET}")
    
    def end_combat(self):
        self.in_combat = False
        self.current_opponent = None
    
    def random_encounter(self):
        encounters = [
            {
                "message": "You encounter a wandering merchant.",
                "type": "npc",
                "npc": NPC(
                    id="merchant",
                    name="Wandering Merchant",
                    description="A traveling merchant with a cart full of goods.",
                    dialogue={
                        "greeting": [
                            "Hello, traveler! Care to buy something?",
                            "Greetings! I have many fine wares for sale."
                        ]
                    },
                    location_id=self.player.location_id
                )
            },
            {
                "message": "You find a treasure chest!",
                "type": "item",
                "items": [
                    Item(
                        id="gold",
                        name="Gold",
                        description="Shiny gold coins.",
                        value=50,
                        stackable=True
                    )
                ]
            },
            {
                "message": "You are ambushed by bandits!",
                "type": "combat",
                "npc": NPC(
                    id="bandit",
                    name="Bandit",
                    description="A dangerous-looking bandit with a weapon.",
                    dialogue={},
                    location_id=self.player.location_id,
                    hostile=True,
                    stats=Stats(health=40, max_health=40)
                )
            },
            {
                "message": "You discover a hidden path!",
                "type": "location",
                "location": Location(
                    id="hidden_path",
                    name="Hidden Path",
                    description="A secret path that few know about.",
                    position=Position(0, 0, 0)
                )
            }
        ]
        
        encounter = random.choice(encounters)
        print(f"{Colors.YELLOW}{encounter['message']}{Colors.RESET}")
        
        if encounter["type"] == "npc":
            location = self.world.get_location(self.player.location_id)
            if location:
                location.add_npc(encounter["npc"])
        
        elif encounter["type"] == "item":
            location = self.world.get_location(self.player.location_id)
            if location:
                for item in encounter["items"]:
                    location.add_item(item)
        
        elif encounter["type"] == "combat":
            self.start_combat(encounter["npc"])
        
        elif encounter["type"] == "location":
            self.world.add_location(encounter["location"])
            self.player.known_locations.append(encounter["location"].id)
    
    def random_event(self):
        events = [
            {
                "message": "It starts to rain.",
                "effect": lambda: setattr(self.world, "weather", Weather.RAINY)
            },
            {
                "message": "The clouds part and the sun shines through.",
                "effect": lambda: setattr(self.world, "weather", Weather.CLEAR)
            },
            {
                "message": "You feel a bit hungry.",
                "effect": lambda: setattr(self.player.stats, "hunger", max(0, self.player.stats.hunger - 10))
            },
            {
                "message": "You feel a bit thirsty.",
                "effect": lambda: setattr(self.player.stats, "thirst", max(0, self.player.stats.thirst - 10))
            },
            {
                "message": "You feel refreshed.",
                "effect": lambda: setattr(self.player.stats, "stamina", min(self.player.stats.max_stamina, self.player.stats.stamina + 20))
            },
            {
                "message": "You find a coin on the ground.",
                "effect": lambda: self.player.add_item(Item(
                    id="gold",
                    name="Gold",
                    description="A single gold coin.",
                    value=1,
                    stackable=True
                ))
            }
        ]
        
        event = random.choice(events)
        print(f"{Colors.YELLOW}{event['message']}{Colors.RESET}")
        event["effect"]()

# Main function
def main():
    game = Game()
    game.start()

if __name__ == "__main__":
    main()