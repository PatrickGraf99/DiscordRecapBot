import os
import logging
from enum import Enum

import discord

logger = logging.getLogger('ServerRecapBot.data')

class DataHandler:

    def __init__(self, data_path: str):
        self.DATA_PATH: str = data_path
        if not os.path.exists(self.DATA_PATH):
            os.mkdir(self.DATA_PATH)
        self.EVENT_LOG_HEADER: str = ('member_id,member_name,timestamp,guild_id,guild_name,'
                                      'channel_id,channel_name,event_type\n')
        self.SESSION_LOG_HEADER: str = ('member_id,member_name,start_time,duration,guild_id,guild_name,'
                                        'channel_id,channel_name,session_type\n')
        self.SESSION_LOG_FILENAME: str = 'session_log.csv'
        self.EVENT_LOG_FILENAME: str = 'event_log.csv'

    def ensure_guild_files_exist(self, guild_id: str) -> None:
        guild_dir = os.path.join(self.DATA_PATH, guild_id)
        if not os.path.exists(guild_dir):
            os.mkdir(guild_dir)
        event_log_file = os.path.join(guild_dir, 'event_log.csv')
        session_log_file = os.path.join(guild_dir, 'session_log.csv')
        metadata_event_file = os.path.join(guild_dir, 'metadata_events.jsonl')
        metadata_snapshot_file = os.path.join(guild_dir, 'metadata_snapshot.json')
        if not os.path.exists(event_log_file):
            with open(event_log_file, 'w') as file:
                file.write(self.EVENT_LOG_HEADER)
        if not os.path.exists(session_log_file):
            with open(session_log_file, 'w') as file:
                file.write(self.SESSION_LOG_HEADER)
        for filename in [metadata_event_file, metadata_snapshot_file]:
            if not os.path.exists(filename):
                with open(filename, 'w') as file:
                    file.write('')

    def log_event(self, member_id: int, member_name: str, timestamp: float, guild_id: int, guild_name: str,
                  channel_id: int, channel_name: str, event_type: str) -> None:
        event_csv_string: str = (f'{member_id},{member_name},{timestamp},{guild_id},{guild_name},'
                                 f'{channel_id},{channel_name},{event_type}\n')

        event_log_path = os.path.join(self.DATA_PATH, str(guild_id), self.EVENT_LOG_FILENAME)
        with open(event_log_path, 'a') as event_log:
            event_log.write(event_csv_string)

    def log_session(self, member_id: int, member_name: str, start_time: float, duration: float,
                    guild_id: int, guild_name: str, channel_id: int, channel_name: str, session_type: str) -> None:
        session_csv_string: str = (f'{member_id},{member_name},{start_time},{duration},{guild_id},{guild_name},'
                                   f'{channel_id},{channel_name},{session_type}\n')

        session_log_path = os.path.join(self.DATA_PATH, str(guild_id), self.SESSION_LOG_FILENAME)
        with open(session_log_path, 'a') as session_log:
            session_log.write(session_csv_string)

