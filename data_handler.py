import shutil
from datetime import datetime
import enum
import json
import os
import logging

import discord

logger = logging.getLogger('ServerRecapBot.data')

class GuildEvent(enum.Enum):
    CHANNEL_ADD = 'channel_add'
    CHANNEL_REMOVE = 'channel_remove'
    CHANNEL_RENAME = 'channel_rename'
    MEMBER_JOIN = 'member_join'
    MEMBER_REMOVE = 'member_remove'
    GUILD_RENAME = 'guild_rename'
    GUILD_JOIN_BOT = 'guild_join_bot'
    CHANNEL_CATEGORY_CHANGE = 'channel_category_change'

class DataHandler:

    def __init__(self, data_path: str):
        # Init constants
        self.DATA_PATH: str = data_path
        self.EVENT_LOG_HEADER: str = ('member_id,member_name,timestamp,guild_id,guild_name,'
                                      'channel_id,channel_name,event_type\n')
        self.SESSION_LOG_HEADER: str = ('member_id,member_name,start_time,duration,guild_id,guild_name,'
                                        'channel_id,channel_name,session_type\n')
        self.SESSION_LOG_FILENAME: str = 'session_log.csv'
        self.EVENT_LOG_FILENAME: str = 'event_log.csv'
        self.GUILD_EVENTS_FILENAME: str = 'guild_events.jsonl'
        self.CONFIG_FILENAME: str = 'config.json'
        self.GUILD_ID_NAME_MAP: str = 'guild_id_name_map.json'
        self.CONFIG_BASE: dict = {
            'allowed_roles': [],
            'dm_export': True,
            'needs_permissions': True
        }

        # Init vars
        self.json_schema_version: int = 1
        self.initialized_guilds_ids = set()
        self.guild_id_name_map: dict = {}

        # Call init methods
        self.ensure_meta_dirs_and_files_exist()
        self.load_guild_id_name_map()

    def ensure_meta_dirs_and_files_exist(self) -> None:
        os.makedirs(self.DATA_PATH, exist_ok=True)
        path = os.path.join(self.DATA_PATH, self.GUILD_ID_NAME_MAP)
        if not os.path.exists(path):
            with open(path, 'w') as file:
                json.dump({}, file)

    def ensure_guild_files_exist(self, guild_id: int) -> None:
        if guild_id in self.initialized_guilds_ids:
            return
        self.sync_guild_id_name_map()
        guild_dir = os.path.join(self.DATA_PATH, str(guild_id))
        if not os.path.exists(guild_dir):
            os.mkdir(guild_dir)
        event_log_file = os.path.join(guild_dir, self.EVENT_LOG_FILENAME)
        session_log_file = os.path.join(guild_dir, self.SESSION_LOG_FILENAME)
        metadata_event_file = os.path.join(guild_dir, self.GUILD_EVENTS_FILENAME)
        config_file = os.path.join(guild_dir, self.CONFIG_FILENAME)
        if not os.path.exists(event_log_file):
            with open(event_log_file, 'w') as file:
                file.write(self.EVENT_LOG_HEADER)
        if not os.path.exists(session_log_file):
            with open(session_log_file, 'w') as file:
                file.write(self.SESSION_LOG_HEADER)
        if not os.path.exists(metadata_event_file):
            with open(metadata_event_file, 'w') as file:
                file.write('')
        if not os.path.exists(config_file):
            with open(config_file, 'w') as file:
                file.write(json.dumps(self.CONFIG_BASE))
        self.initialized_guilds_ids.add(guild_id)

    # region event logging

    def log_event(self, member_id: int, member_name: str, timestamp: float, guild_id: int, guild_name: str,
                  channel_id: int, channel_name: str, event_type: str) -> None:
        self.ensure_guild_files_exist(guild_id)
        event_csv_string: str = (f'{member_id},{member_name},{timestamp},{guild_id},{guild_name},'
                                 f'{channel_id},{channel_name},{event_type}\n')

        event_log_path = os.path.join(self.DATA_PATH, str(guild_id), self.EVENT_LOG_FILENAME)
        with open(event_log_path, 'a') as event_log:
            event_log.write(event_csv_string)

    def log_session(self, member_id: int, member_name: str, start_time: float, duration: float,
                    guild_id: int, guild_name: str, channel_id: int, channel_name: str, session_type: str) -> None:
        self.ensure_guild_files_exist(guild_id)
        session_csv_string: str = (f'{member_id},{member_name},{start_time},{duration},{guild_id},{guild_name},'
                                   f'{channel_id},{channel_name},{session_type}\n')

        session_log_path = os.path.join(self.DATA_PATH, str(guild_id), self.SESSION_LOG_FILENAME)
        with open(session_log_path, 'a') as session_log:
            session_log.write(session_csv_string)

    def _append_guild_metadata(self, timestamp: float, guild_id: int, guild_event_type: str, payload: dict) -> None:
        logger.debug(f'Guild {guild_id} event type {guild_event_type}')
        self.ensure_guild_files_exist(guild_id)

        json_object = {'schema_version': self.json_schema_version, 'timestamp': timestamp,
                       'guild_event': guild_event_type, 'guild_id': guild_id, 'payload': payload}
        filename: str = os.path.join(self.DATA_PATH, str(guild_id), self.GUILD_EVENTS_FILENAME)
        with open(filename, 'a') as event_file:
            json.dump(json_object, event_file)
            event_file.write('\n')

    def log_guild_channel_add(self, timestamp: float, guild_id: int, channel_id: int,
                              channel_name: str, channel_category_id: int | None, channel_type: str) -> None:
        payload = {
            'channel_id': channel_id,
            'channel_name': channel_name,
            'channel_category_id': channel_category_id,
            'channel_type': channel_type
        }
        self._append_guild_metadata(timestamp, guild_id, GuildEvent.CHANNEL_ADD.value, payload )

    def log_guild_channel_remove(self, timestamp: float, guild_id: int, channel_id: int,
                                 channel_name: str, channel_category_id: int | None, channel_type: str) -> None:
        payload = {
            'channel_id': channel_id,
            'channel_name': channel_name,
            'channel_category_id': channel_category_id,
            'channel_type': channel_type
        }
        self._append_guild_metadata(timestamp, guild_id, GuildEvent.CHANNEL_REMOVE.value, payload)

    def log_guild_channel_rename(self, timestamp: float, guild_id: int, channel_id: int,
                                 channel_name_old: str, channel_name_new: str, channel_category_id: int | None,
                                 channel_type: str) -> None:
        payload = {
            'channel_id': channel_id,
            'channel_name_old': channel_name_old,
            'channel_name_new': channel_name_new,
            'channel_category_id': channel_category_id,
            'channel_type': channel_type
        }
        self._append_guild_metadata(timestamp, guild_id, GuildEvent.CHANNEL_RENAME.value, payload)

    def log_guild_channel_category_change(self, timestamp: float, guild_id: int, channel_id: int, channel_name: str,
                                          channel_category_old: int | None, channel_category_new: int | None,
                                          channel_type: str) -> None:
        payload = {
            'channel_id': channel_id,
            'channel_name': channel_name,
            'channel_category_old': channel_category_old,
            'channel_category_new': channel_category_new,
            'channel_type': channel_type
        }
        self._append_guild_metadata(timestamp, guild_id, GuildEvent.CHANNEL_CATEGORY_CHANGE.value, payload)

    def log_guild_member_join(self, timestamp: float, guild_id: int, member_id: int, member_name: str) -> None:
        payload = {
            'member_id': member_id,
            'member_name': member_name,
        }
        self._append_guild_metadata(timestamp, guild_id, GuildEvent.MEMBER_JOIN.value, payload)

    def log_guild_member_remove(self, timestamp: float, guild_id: int, member_id: int, member_name: str) -> None:
        payload = {
            'member_id': member_id,
            'member_name': member_name,
        }
        self._append_guild_metadata(timestamp, guild_id, GuildEvent.MEMBER_REMOVE.value, payload)

    def log_guild_rename(self, timestamp: float, guild_id: int, guild_name_old: str, guild_name_new: str) -> None:
        payload = {
            'guild_name_old': guild_name_old,
            'guild_name_new': guild_name_new,
        }
        self._append_guild_metadata(timestamp, guild_id, GuildEvent.GUILD_RENAME.value, payload)
        self.sync_guild_id_name_map(guild_id, guild_name_new)

    def log_guild_bot_join(self, timestamp: float, guild_id: int, guild_name: str) -> None:
        payload = {
            'guild_name': guild_name,
        }
        self._append_guild_metadata(timestamp, guild_id, GuildEvent.GUILD_JOIN_BOT.value, payload)
        self.sync_guild_id_name_map(guild_id, guild_name)

    # endregion

    def create_zip_for_guild(self, guild_id: int, guild_name: str) -> str:
        path: str = os.path.join(self.DATA_PATH, str(guild_id))
        guild_name = guild_name.replace(' ', '_')
        timestamp = datetime.now()
        formatted_time = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
        filename: str = f'data_{guild_name}_{formatted_time}'
        target_path = os.path.join(path, filename)
        shutil.make_archive(target_path, 'zip', path)
        return f'{target_path}.zip'

    def get_zip_for_guild(self, guild: discord.Guild) -> str:
        filepath = self.create_zip_for_guild(guild.id, guild.name)
        return filepath

    def get_config_path_for_guild(self, guild_id: int) -> str:
        path: str = os.path.join(self.DATA_PATH, str(guild_id), self.CONFIG_FILENAME)
        return path

    def remove_file(self, path: str) -> None:
        os.remove(path)

    def load_guild_id_name_map(self) -> None:
        path = os.path.join(self.DATA_PATH, self.GUILD_ID_NAME_MAP)
        with open(path, 'r') as file:
            self.guild_id_name_map = json.load(file)

    def sync_guild_id_name_map(self, guild_id: int, guild_name: str) -> None:
        path: str = os.path.join(self.DATA_PATH, self.GUILD_ID_NAME_MAP)
        if str(guild_id) not in self.guild_id_name_map or self.guild_id_name_map[str(guild_id)] != guild_name:
            self.guild_id_name_map[str(guild_id)] = guild_name
            with open(path, 'w') as file:
                json.dump(self.guild_id_name_map, file, indent=4)
