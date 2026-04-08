import json
import logging

from discord import Member, Guild, Role

from data_handler import DataHandler

logger = logging.getLogger('ServerRecapBot.bot')

class ConfigManager:

    def __init__(self, data_handler: DataHandler):
        self.data_handler = data_handler
        self.loaded_config = {}

    def load_config(self, guild):
        filepath = self.data_handler.get_config_path_for_guild(guild)
        with open(filepath, 'r') as file:
            self.loaded_config = json.load(file)

    def close_config(self):
        self.loaded_config = {}

    async def save_config(self, guild: Guild):
        filepath = self.data_handler.get_config_path_for_guild(guild.id)
        with open(filepath, 'w') as file:
            json.dump(self.loaded_config, file)

    def has_permission(self, member: Member, guild: Guild) -> bool:
        if member.guild_permissions.administrator:
            return True
        self.load_config(guild)
        for role in member.roles:
            if role in self.loaded_config['allowed_roles']:
                return True
        return False

    def is_dm_export(self, guild: Guild):
        self.load_config(guild)
        return self.loaded_config['dm_export']


    def add_allowed_role(self, guild: Guild, role: Role):
        self.load_config(guild)
        if role in self.loaded_config['allowed_roles']:
            logger.debug(f'Already allowed role {role}')
            return
        self.loaded_config['allowed_roles'].append(role)
        self.save_config(guild)


