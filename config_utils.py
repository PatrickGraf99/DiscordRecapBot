import json
import logging

from discord import Member, Guild, Role

from data_handler import DataHandler

logger = logging.getLogger('ServerRecapBot.bot')

class ConfigManager:

    def __init__(self, data_handler: DataHandler):
        self.data_handler = data_handler
        self.loaded_configs = {}

    def load_config(self, guild: Guild):
        filepath = self.data_handler.get_config_path_for_guild(guild.id)
        with open(filepath, 'r') as file:
            self.loaded_configs[guild.id] = json.load(file)

    def _is_config_cached(self, guild: Guild) -> bool:
        return guild.id in self.loaded_configs

    def _load_config_if_not_cached(self, guild: Guild) -> None:
        if not self._is_config_cached(guild):
            self.load_config(guild)

    def _save_config(self, guild: Guild):
        filepath = self.data_handler.get_config_path_for_guild(guild.id)
        with open(filepath, 'w') as file:
            json.dump(self.loaded_configs[guild.id], file, indent=4)

    def has_permission(self, member: Member, guild: Guild) -> bool:
        # Always return True for administrators
        if member.guild_permissions.administrator:
            return True
        # Check if a config is cached already and load if not
        self._load_config_if_not_cached(guild)
        conf = self.loaded_configs[guild.id]
        # For each role the member has, check if it is in allowed roles and return True if it is
        for role in member.roles:
            if role.id in conf['allowed_roles']:
                return True
        return False

    def is_dm_export(self, guild: Guild):
        self._load_config_if_not_cached(guild)
        conf = self.loaded_configs[guild.id]
        return conf['dm_export']


    def add_allowed_role(self, guild: Guild, role: Role):
        self._load_config_if_not_cached(guild)
        conf = self.loaded_configs[guild.id]
        if role.id in conf['allowed_roles']:
            logger.debug(f'Already allowed role {role}')
            return False
        conf['allowed_roles'].append(role.id)
        self._save_config(guild)
        return True

    def remove_allowed_role(self, guild: Guild, role: Role):
        self._load_config_if_not_cached(guild)
        conf = self.loaded_configs[guild.id]
        if role.id not in conf['allowed_roles']:
            logger.debug(f'Role {role} is not in allowed roles, can\'t remove')
            return False
        conf['allowed_roles'].remove(role.id)
        self._save_config(guild)
        return True

    def get_allowed_roles_list(self, guild: Guild) -> list[Role]:
        self._load_config_if_not_cached(guild)
        conf = self.loaded_configs[guild.id]
        all_rolls = guild.roles
        allowed_roles = []
        for role in all_rolls:
            if role.id in conf['allowed_roles']:
                allowed_roles.append(role)
        return allowed_roles


