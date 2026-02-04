from datetime import datetime
import os
import sys
import time
from enum import Enum
import argparse
import logging
from fileinput import filename

import discord
from discord import VoiceChannel, Intents
from dotenv import load_dotenv

logger = logging.getLogger('ServerRecapBot')

class EventType(Enum):
    JOIN = 'join'
    LEAVE = 'leave'


class SessionType(Enum):
    COMPLETE = 'complete'
    CORRUPTED = 'corrupted'


class RecapBot(discord.Client):

    def __init__(self, mode: str, data_path: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode: str = mode
        self.currently_tracked_connections: dict = {}
        self.DATA_PATH: str = data_path
        self.EVENT_LOG_HEADER: str = ('member_id,member_name,timestamp,guild_id,guild_name,'
                                      'channel_id,channel_name,event_type\n')
        self.SESSION_LOG_HEADER: str = ('member_id,member_name,start_time,duration,guild_id,guild_name,'
                                        'channel_id,channel_name,session_type\n')
        self.SESSION_LOG_FILENAME: str = 'session_log.csv'
        self.EVENT_LOG_FILENAME: str = 'event_log.csv'

    async def on_ready(self) -> None:
        logger.info(f'Logged in as {self.user.name}')
        if not os.path.exists(self.DATA_PATH):
            logger.info(f'No data directory found, creating data directory with path {self.DATA_PATH}')
            os.mkdir(self.DATA_PATH)
        else:
            logger.info(f'Data directory found at {self.DATA_PATH}')

        logger.info('Checking file structure for all guilds the bot is in, creating missing directories')
        for guild in self.guilds:
            if not self.guild_files_exist(guild):
                self.create_guild_files(guild)

    async def on_message(self, message) -> None:
        logger.debug(f'Message received from {message.author}: {message.content}')

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info(f'Bot has joined guild {guild.name} with id {guild.id}')
        if not self.guild_files_exist(guild):
            self.create_guild_files(guild)

    def guild_files_exist(self, guild) -> bool:
        """
        Checks if the file structure needed for a guild is present in the data directory
        :param guild: The guild to check
        :return: True if the file exists, False otherwise
        """
        guild_path = os.path.join(self.DATA_PATH, str(guild.id))
        return (os.path.exists(guild_path)
                and os.path.exists(os.path.join(guild_path, self.EVENT_LOG_FILENAME))
                and os.path.exists(os.path.join(guild_path, self.SESSION_LOG_FILENAME)))

    def create_guild_files(self, guild) -> None:
        """
        Creates the file structure to support data from the specified guild
        :param guild: The guild to create files for
        :return:
        """
        logger.info(f'Creating file structure for guild {guild.name} with id {guild.id}')
        guild_path = os.path.join(self.DATA_PATH, str(guild.id))
        if not os.path.exists(guild_path):
            os.mkdir(guild_path)
        if not os.path.exists(os.path.join(guild_path, self.EVENT_LOG_FILENAME)):
            with open(os.path.join(guild_path, self.EVENT_LOG_FILENAME), 'w') as event_log:
                event_log.write(self.EVENT_LOG_HEADER)
        if not os.path.exists(os.path.join(guild_path, self.SESSION_LOG_FILENAME)):
            with open(os.path.join(guild_path, self.SESSION_LOG_FILENAME), 'w') as session_log:
                session_log.write(self.SESSION_LOG_HEADER)

    async def on_voice_state_update(self, member, before, after) -> None:

        logger.debug('Received a voice state update')
        logger.debug(f'Voice state update by Member {str(member.name)}({str(member.id)}) '
                     f'in guild {member.guild.name}({str(member.guild.id)})')
        logger.debug(f'Old state: {before}')
        logger.debug(f'New state: {after}')

        timestamp: float = time.time()

        # If channel stays the same it means user has not switched channel obviously
        if before.channel == after.channel:
            return

        guild = member.guild

        channel_after: VoiceChannel = after.channel
        channel_before: VoiceChannel = before.channel


        # If before is None, user has joined a channel
        # --> handle join with member, channel and time
        if before.channel is None:
            self.log_event(member.id, member.name, timestamp, guild.id, guild.name,
                           channel_after.id, channel_after.name, EventType.JOIN)
            self.handle_voice_join(member, timestamp, channel_after)
            return

        # If after is None, user has left the VC completely
        # --> handle leave with member and time
        if after.channel is None:
            self.log_event(member.id, member.name, timestamp, guild.id, guild.name,
                           channel_before.id, channel_before.name, EventType.LEAVE)
            self.handle_voice_leave(member, timestamp, channel_before)
            return

        # If after and before both are not None
        # --> handle leaving the old channel
        # --> handle joining the new channel
        self.log_event(member.id, member.name, timestamp, guild.id, guild.name,
                       channel_before.id, channel_before.name, EventType.LEAVE)
        self.log_event(member.id, member.name, timestamp, guild.id, guild.name,
                       channel_after.id, channel_after.name, EventType.JOIN)

        self.handle_voice_leave(member, timestamp, channel_before)
        self.handle_voice_join(member, timestamp, channel_after)

        # print(f'Member {member.name} has joined voice channel {after.channel} from {before.channel}')
        # print(f'Member: {member}')
        # print(f'Before: {before}')
        # print(f'After: {after}')

    def log_event(self, member_id: int, member_name: str, timestamp: float, guild_id: int, guild_name: str,
                  channel_id: int, channel_name: str, event_type: EventType) -> None:
        event_csv_string: str = (f'{member_id},{member_name},{timestamp},{guild_id},{guild_name},'
                                 f'{channel_id},{channel_name},{event_type.value}\n')

        event_log_path = os.path.join(self.DATA_PATH, str(guild_id), self.EVENT_LOG_FILENAME)
        with open(event_log_path, 'a') as event_log:
            event_log.write(event_csv_string)

        logger.debug(f'An event has been triggered, logging: {event_csv_string}')


    def handle_voice_join(self, member: discord.Member, timestamp: float, voice_channel: discord.VoiceChannel) -> None:
        """
        Stores the connection of the member in a dictionary. Will write to file when user leaves
        :return:
        """
        guild = member.guild

        # Data that needs to be logged
        member_id: int = member.id
        member_name: str = member.name
        timestamp: float = timestamp
        guild_id: int = guild.id
        guild_name: str = guild.name
        channel_id: int = voice_channel.id
        channel_name: str = voice_channel.name

        connection: dict = {'member_name': member_name, 'timestamp': timestamp, 'guild_name': guild_name,
                            'channel_name': channel_name, 'channel_id': channel_id}
        self.currently_tracked_connections[(member_id, guild_id)] = connection

    def handle_voice_leave(self, member: discord.Member, timestamp: float, voice_channel: discord.VoiceChannel) -> None:
        member_id: int = member.id
        guild = member.guild
        guild_id: int = guild.id
        if (member_id, guild_id) in self.currently_tracked_connections:
            # Session complete
            tracked_connection: dict = self.currently_tracked_connections.pop((member_id, guild_id))
            member_name: str = tracked_connection['member_name']
            start_time: float = tracked_connection['timestamp']
            duration: float = timestamp - start_time
            guild_name: str = tracked_connection['guild_name']
            channel_id: int = tracked_connection['channel_id']
            channel_name: str = tracked_connection['channel_name']
            session_type: SessionType = SessionType.COMPLETE
        else:
            # Session corrupted, leave event without join
            member_name: str = member.name
            start_time: float = -1
            duration: float = 0
            guild_name: str = guild.name
            channel_id: int = voice_channel.id
            channel_name: str = voice_channel.name
            session_type: SessionType = SessionType.CORRUPTED

        session_csv_string: str = (f'{member_id},{member_name},{start_time},{duration},{guild_id},{guild_name},'
                                   f'{channel_id},{channel_name},{session_type.value}\n')
        session_log_path: str = os.path.join(self.DATA_PATH, str(guild_id), self.SESSION_LOG_FILENAME)
        with open(session_log_path, 'a') as session_log:
            session_log.write(session_csv_string)

        logger.debug(f'A session has been ended, logging: {session_csv_string}')

def main() -> None:

    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mode', choices=['dev', 'prod'], default=None, type=str)
    args = parser.parse_args()
    mode: str = args.mode

    if mode == 'prod':
        init_logs(mode)
        answer = input('Bot about to run in production, continue? (y/n) ')
        while answer != 'y' and answer != 'n':
            print('Please enter either "y" or "n"')
            answer = input('Bot about to run in production, continue? (y/n) ')
        if answer == 'n':
            logger.info('Exiting bot')
            exit(0)
        elif answer == 'y':
            logger.info('Starting bot in production mode')
    elif mode == 'dev':
        init_logs(mode)
        logger.info('Starting bot in development mode')
    else:
        mode = 'dev'
        init_logs(mode)
        logger.warning('No mode or wrong mode was specified, defaulting to development')

    load_dotenv()

    intents = get_bot_intents()

    token = os.getenv('DEV_TOKEN') if mode == 'dev' else os.getenv('PROD_TOKEN')
    data_path = 'data-dev' if mode == 'dev' else 'data-prod'

    client = RecapBot(intents=intents, mode=mode, data_path=data_path)
    client.run(token)

def init_logs(mode: str) -> None:
    if not os.path.exists('logs'):
        os.mkdir('logs')

    timestamp_str: str = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d_%H-%M-%S")
    logfile_name: str = f'logs-dev-{timestamp_str}.log' if mode == 'dev' else f'logs-prod-{timestamp_str}.log'
    level = logging.DEBUG if mode == 'dev' else logging.INFO

    file_handler = logging.FileHandler(logfile_name)
    file_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s',
                                                   datefmt='%Y-%m-%d %H:%M:%S'))
    file_handler.setLevel(level)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s',
                                                  datefmt='%Y-%m-%d %H:%M:%S'))
    stdout_handler.setLevel(level)

    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(stdout_handler)

def get_bot_intents() -> Intents:
    intents = discord.Intents.default()
    intents.voice_states = True
    intents.guilds = True
    intents.members = True
    return intents

if __name__ == '__main__':
    main()
