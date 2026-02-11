from datetime import datetime
import os
import sys
import time
from enum import Enum
import argparse
import logging

import discord
from discord import VoiceChannel, Intents, ChannelType
from dotenv import load_dotenv

from data_handler import DataHandler

logger = logging.getLogger('ServerRecapBot.bot')

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
        self.data_handler = DataHandler(data_path)


    async def on_ready(self) -> None:
        logger.info(f'Logged in as {self.user.name}')
        logger.info('Checking file structure for all guilds the bot is in, creating missing directories')
        for guild in self.guilds:
            self.data_handler.ensure_guild_files_exist(guild.id)

    async def on_message(self, message) -> None:
        logger.debug(f'Message received from {message.author}: {message.content}')
        # TODO: Build message logging
        # TODO: {timestamp; author; guild; channel_id}

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info(f'Bot has joined guild {guild.name} with id {guild.id}')
        self.data_handler.ensure_guild_files_exist(guild.id)
        self.data_handler.log_guild_bot_join(time.time(), guild.id, guild.name)

    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        logger.debug('A guild has been updated')
        timestamp: float = time.time()
        if before.name != after.name:
            logger.debug(f'Name changed from {before.name} to {after.name}')
            self.data_handler.log_guild_rename(timestamp, before.id, before.name, after.name)


    async def on_guild_channel_create(self, channel) -> None:
        timestamp: float = time.time()
        category_id = channel.category.id if channel.category is not None else None
        logger.debug(f'A channel has been created in guild {channel.guild} with name {channel.name}')
        self.data_handler.log_guild_channel_add(timestamp, channel.guild.id, channel.id, channel.name,
                                                    category_id, channel.type.name)

    async def on_guild_channel_delete(self, channel) -> None:
        timestamp: float = time.time()
        category_id = channel.category.id if channel.category is not None else None
        logger.debug(f'A channel has been deleted in guild {channel.guild} with name {channel.name}')
        self.data_handler.log_guild_channel_remove(timestamp, channel.guild.id, channel.id, channel.name,
                                                category_id, channel.type.name)

    async def on_guild_channel_update(self, before, after) -> None:
        timestamp: float = time.time()
        category_before_id = before.category.id if before.category is not None else None
        category_after_id = after.category.id if after.category is not None else None
        if before.name != after.name:
            logger.debug(f'A channel has changed name in guild {before.guild} from {before.name} to {after.name}')
            self.data_handler.log_guild_channel_rename(timestamp, before.guild.id, before.id, before.name,
                                                    after.name, category_before_id, before.type.name)

        if category_before_id != category_after_id:
            logger.debug(f'Category of {after.name} changed from {category_before_id} to {category_after_id}')
            self.data_handler.log_guild_channel_category_change(timestamp, before.guild.id, before.id, before.name,
                                                                category_before_id, category_after_id, before.type.name)

    async def on_member_join(self, member: discord.Member) -> None:
        logger.info(f'Member {member.name} with id {member.id} joined guild {member.guild.name}')
        timestamp: float = time.time()
        self.data_handler.log_guild_member_join(timestamp, member.guild.id, member.id, member.name)

    async def on_member_remove(self, member: discord.Member) -> None:
        logger.debug(f'Member {member.name} ({member.id}) has been removed from guild {member.guild.name}')
        timestamp: float = time.time()
        self.data_handler.log_guild_member_remove(timestamp, member.guild.id, member.id, member.name)


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
            self.data_handler.log_event(member.id, member.name, timestamp, guild.id, guild.name,
                           channel_after.id, channel_after.name, EventType.JOIN.value)
            self.handle_voice_join(member, timestamp, channel_after)
            return

        # If after is None, user has left the VC completely
        # --> handle leave with member and time
        if after.channel is None:
            self.data_handler.log_event(member.id, member.name, timestamp, guild.id, guild.name,
                           channel_before.id, channel_before.name, EventType.LEAVE.value)
            self.handle_voice_leave(member, timestamp, channel_before)
            return

        # If after and before both are not None
        # --> handle leaving the old channel
        # --> handle joining the new channel
        self.data_handler.log_event(member.id, member.name, timestamp, guild.id, guild.name,
                       channel_before.id, channel_before.name, EventType.LEAVE.value)
        self.data_handler.log_event(member.id, member.name, timestamp, guild.id, guild.name,
                       channel_after.id, channel_after.name, EventType.JOIN.value)

        self.handle_voice_leave(member, timestamp, channel_before)
        self.handle_voice_join(member, timestamp, channel_after)



    def handle_voice_join(self, member: discord.Member, timestamp: float, voice_channel: discord.VoiceChannel) -> None:
        """
        Stores the connection of the member in a dictionary. Will write to file when user leaves
        :return:
        """
        guild = member.guild
        connection: dict = {'member_name': member.name, 'timestamp': timestamp, 'guild_name': guild.name,
                            'channel_name': voice_channel.name, 'channel_id': voice_channel.id}
        self.currently_tracked_connections[(member.id, guild.id)] = connection

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

        self.data_handler.log_session(member_id, member_name, start_time, duration, guild_id, guild_name,
                                    channel_id, channel_name, session_type.value)

        #logger.debug(f'A session has been ended, logging: {session_csv_string}')

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mode', choices=['dev', 'prod'], default=None, type=str)
    args = parser.parse_args()
    mode: str = args.mode
    auto_mode = False
    if mode is None:
        auto_mode = True
        mode = 'dev'

    init_logs(mode)

    if mode == 'dev':
        if auto_mode:
            logger.warning('No mode was specified, defaulting to development')
        logger.info('Starting bot in development mode')

    elif mode == 'prod':
        answer = input('Bot about to run in production, continue? (y/n) ')
        while answer != 'y' and answer != 'n':
            print('Please enter either "y" or "n"')
            answer = input('Bot about to run in production, continue? (y/n) ')
        if answer == 'n':
            logger.info('Exiting bot')
            exit(0)
        elif answer == 'y':
            logger.info('Starting bot in production mode')

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

    file_handler = logging.FileHandler(os.path.join('logs',logfile_name))
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
    intents.messages = True
    return intents

if __name__ == '__main__':
    main()
