import os
import time
from enum import Enum

import discord
from discord import VoiceChannel
from dotenv import load_dotenv

load_dotenv()


class EventType(Enum):
    JOIN = 'join'
    LEAVE = 'leave'


class SessionType(Enum):
    COMPLETE = 'complete'
    CORRUPTED = 'corrupted'


class RecapBot(discord.Client):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.currently_tracked_connections: dict = {}
        self.DATA_PATH: str = 'data-dev'
        self.EVENT_LOG_HEADER: str = 'member_id,member_name,timestamp,channel_id,channel_name,event_type\n'
        self.SESSION_LOG_HEADER: str = 'member_id,member_name,start_time,duration,channel_id,channel_name,session_type\n'

    async def on_ready(self) -> None:
        print(f'Logged in as {self.user.name}!')
        if not os.path.exists(self.DATA_PATH):
            print('Creating data directory')
            os.mkdir(self.DATA_PATH)
        else:
            print('Data directory already exists')

        print('Checking file structure for all guilds')
        for guild in self.guilds:
            if not self.guild_files_exist(guild):
                self.create_guild_files(guild)

    async def on_message(self, message) -> None:
        print(f'Message from {message.author}: {message.content}')

    async def on_guild_join(self, guild: discord.Guild) -> None:
        print(f'Bot was added to guild {guild.name} with id {guild.id}')
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
                and os.path.exists(os.path.join(guild_path, 'event_log.csv'))
                and os.path.exists(os.path.join(guild_path, 'session_log.csv')))

    def create_guild_files(self, guild) -> None:
        """
        Creates the file structure to support data from the specified guild
        :param guild: The guild to create files for
        :return:
        """
        print(f'Creating file structure for guild {guild.name} with id {guild.id}')
        guild_path = os.path.join(self.DATA_PATH, str(guild.id))
        if not os.path.exists(guild_path):
            os.mkdir(guild_path)
        if not os.path.exists(os.path.join(guild_path, 'event_log.csv')):
            with open(os.path.join(guild_path, 'event_log.csv'), 'w') as event_log:
                event_log.write(self.EVENT_LOG_HEADER)
        if not os.path.exists(os.path.join(guild_path, 'session_log.csv')):
            with open(os.path.join(guild_path, 'session_log.csv'), 'w') as session_log:
                session_log.write(self.SESSION_LOG_HEADER)

    async def on_voice_state_update(self, member, before, after) -> None:

        timestamp: float = time.time()

        # If channel stays the same it means user has not switched channel obviously
        if before.channel == after.channel:
            return

        channel_after: VoiceChannel = after.channel
        channel_before: VoiceChannel = before.channel

        guild_id: str = str(member.guild.id)

        # If before is None, user has joined a channel
        # --> handle join with member, channel and time
        if before.channel is None:
            self.log_event(member.id, member.name, timestamp, channel_after.id, channel_after.name, EventType.JOIN)
            self.handle_voice_join(member, timestamp, channel_after)
            return

        # If after is None, user has left the VC completely
        # --> handle leave with member and time
        if after.channel is None:
            self.log_event(member.id, member.name, timestamp, channel_before.id, channel_before.name, EventType.LEAVE)
            self.handle_voice_leave(member, timestamp, channel_before)
            return

        # If after and before both are not None
        # --> handle leaving the old channel
        # --> handle joining the new channel
        self.log_event(member.id, member.name, timestamp, channel_before.id, channel_before.name, EventType.LEAVE)
        self.log_event(member.id, member.name, timestamp, channel_after.id, channel_after.name, EventType.JOIN)

        self.handle_voice_leave(member, timestamp, channel_before)
        self.handle_voice_join(member, timestamp, channel_after)

        # print(f'Member {member.name} has joined voice channel {after.channel} from {before.channel}')
        # print(f'Member: {member}')
        # print(f'Before: {before}')
        # print(f'After: {after}')

    def log_event(self, member_id: int, member_name: str, timestamp: float, channel_id: int, channel_name: str,
                  event_type: EventType) -> None:
        event_csv_string: str = f'{member_id},{member_name},{timestamp},{channel_id},{channel_name},{event_type.value}\n'

        with open('data/event_log.csv', 'a') as event_log:
            event_log.write(event_csv_string)

    def handle_voice_join(self, member: discord.Member, timestamp: float, voice_channel: discord.VoiceChannel) -> None:
        """
        Stores the connection of the member in a dictionary. Will write to file when user leaves
        :return:
        """
        # Data that needs to be logged
        member_id: int = member.id
        member_name: str = member.name
        timestamp: float = timestamp
        channel_id: int = voice_channel.id
        channel_name: str = voice_channel.name

        connection: dict = {'member_name': member_name, 'timestamp': timestamp, 'channel_name': channel_name,
                            'channel_id': channel_id}
        self.currently_tracked_connections[member_id] = connection

    def handle_voice_leave(self, member: discord.Member, timestamp: float, voice_channel: discord.VoiceChannel) -> None:
        member_id: int = member.id
        if member_id in self.currently_tracked_connections:
            # Session complete
            tracked_connection: dict = self.currently_tracked_connections.pop(member_id)
            member_name: str = tracked_connection['member_name']
            start_time: float = tracked_connection['timestamp']
            duration: float = timestamp - start_time
            channel_id: int = tracked_connection['channel_id']
            channel_name: str = tracked_connection['channel_name']
            session_type: SessionType = SessionType.COMPLETE
        else:
            # Session corrupted, leave event without join
            member_name: str = member.name
            start_time: float = -1
            duration: float = 0
            channel_id: int = voice_channel.id
            channel_name: str = voice_channel.name
            session_type: SessionType = SessionType.CORRUPTED

        session_csv_string: str = f'{member_id},{member_name},{start_time},{duration},{channel_id},{channel_name},{session_type.value}\n'
        with open(f'data/session_log.csv', 'a') as session_log:
            session_log.write(session_csv_string)


intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True
intents.guilds = True

client = RecapBot(intents=intents)
client.run(os.getenv('DEV_TOKEN'))
