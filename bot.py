
import time
from enum import Enum
import logging

from discord.ext import commands

import discord
from discord import VoiceChannel, Intents, ChannelType


from data_handler import DataHandler

logger = logging.getLogger('ServerRecapBot.bot')


class EventType(Enum):
    JOIN = 'join'
    LEAVE = 'leave'


class SessionType(Enum):
    COMPLETE = 'complete'
    CORRUPTED = 'corrupted'


class RecapBot(commands.Bot):

    def __init__(self, mode: str, data_path: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode: str = mode
        self.currently_tracked_connections: dict = {}
        self.data_handler = DataHandler(data_path)

    # region Overrides

    async def on_ready(self) -> None:
        logger.info(f'Logged in as {self.user.name}')
        logger.info('Checking file structure for all guilds the bot is in, creating missing directories')
        for guild in self.guilds:
            self.data_handler.ensure_guild_files_exist(guild.id, guild.name)
        logger.info('Checked file structure and created missing directories and files, synced guild names to ids')

    async def on_message(self, message) -> None:
        logger.debug(f'Message received from {message.author}: {message.content}')
        # TODO: Build message logging
        # TODO: {timestamp; author; guild; channel_id}
        await self.process_commands(message)

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

    # endregion

    # region Command Methods

    async def send_collected_data(self, ctx) -> None:
        await ctx.send('All data that has been stored will be sent to you via DM!')
        dm_channel = ctx.author.dm_channel
        if dm_channel is None:
            dm_channel = await self.create_dm(ctx.author)
        filepath = self.data_handler.get_zip_for_guild(ctx.guild)
        file: discord.File = discord.File(filepath)
        await dm_channel.send(f'Here is all data stored for the guild {ctx.guild.name}')
        await dm_channel.send(file=file)
        self.data_handler.remove_file(filepath)

    # endregion

    # region Own Methods

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

    # endregion

def get_bot_intents() -> Intents:
    intents = discord.Intents.default()
    intents.voice_states = True
    intents.guilds = True
    intents.members = True
    intents.messages = True
    intents.message_content = True
    return intents

def add_commands(bot: RecapBot):
    @bot.command(name='data')
    # @commands.has_permissions(administrator=True)
    async def data(ctx: commands.Context) -> None:
        if not ctx.author.guild_permissions.administrator:
            await ctx.send('Oops, this function is currently only usable by administrators.')
            return
        await bot.send_collected_data(ctx)

    @bot.command(name='roles')
    async def roles(ctx: commands.Context) -> None:
        logger.debug(ctx.author.roles)
        #await ctx.send(ctx.author.roles)