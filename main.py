import os
import discord
from dotenv import load_dotenv

load_dotenv()

class RecapBot(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user.name}!')

    async def on_message(self, message):
        print(f'Message from {message.author}: {message.content}')

    async def on_voice_state_update(self, member, before, after):
        print(f'Member {member.name} has joined voice channel {after.channel} from {before.channel}')
        print(f'Member: {member}')
        print(f'Before: {before}')
        print(f'After: {after}')


intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True


client = RecapBot(intents=intents)
client.run(os.getenv('BOT_TOKEN'))
