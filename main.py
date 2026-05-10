import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import deque
import logging
import json
import random
import asyncio
import re
import io
import time
from aiohttp import web
import importlib
from games import Deck, Hand, BlackjackView, Games

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '.env')
print(f'Loading .env from: {env_path}')
print(f'File exists: {os.path.exists(env_path)}')

load_dotenv(dotenv_path=env_path, override=True)

TOKEN = os.getenv('DISCORD_TOKEN')

# Log channels for different event types
MESSAGE_LOG_CHANNEL_ID = int(os.getenv('MESSAGE_LOG_CHANNEL_ID', 0))
MEMBER_LOG_CHANNEL_ID = int(os.getenv('MEMBER_LOG_CHANNEL_ID', 0))
CHANNEL_LOG_CHANNEL_ID = int(os.getenv('CHANNEL_LOG_CHANNEL_ID', 0))
ROLE_LOG_CHANNEL_ID = int(os.getenv('ROLE_LOG_CHANNEL_ID', 0))
EMOJI_LOG_CHANNEL_ID = int(os.getenv('EMOJI_LOG_CHANNEL_ID', 0))
COMMAND_LOG_CHANNEL_ID = int(os.getenv('COMMAND_LOG_CHANNEL_ID', 0))

# Ticket channel configuration
TICKET_CATEGORY_ID = int(os.getenv('TICKET_CATEGORY_ID', 0))
TICKET_STAFF_ROLE_ID = int(os.getenv('TICKET_STAFF_ROLE_ID', 0))

# Counting bot configuration
COUNTING_CHANNEL_ID = int(os.getenv('COUNTING_CHANNEL_ID', 0))
COUNTING_DATA_FILE = 'counting_data.json'
REACTION_ROLE_FILE = 'reaction_roles.json'
ECONOMY_DIR = 'economy'
WORK_COOLDOWN_SECONDS = 30
WORK_REWARD_MIN = 25
WORK_REWARD_MAX = 75
STAFF_ALERT_CHANNEL_ID = int(os.getenv('STAFF_ALERT_CHANNEL_ID', 0))
GUILD_ID = int(os.getenv('GUILD_ID', 0))
AUTO_ROLE_IDS = [int(role_id) for role_id in os.getenv('AUTO_ROLE_IDS', '').split(',') if role_id.strip().isdigit()]
VERIFICATION_API_HOST = os.getenv('VERIFICATION_API_HOST', '0.0.0.0')
VERIFICATION_API_PORT = int(os.getenv('VERIFICATION_API_PORT', 8080))
VERIFICATION_API_SECRET = os.getenv('VERIFICATION_API_SECRET', '')
LUCKPERMS_ROLE_MAPPING = json.loads(os.getenv('LUCKPERMS_ROLE_MAPPING', '{}'))
CROSSCHAT_CHANNEL_ID = int(os.getenv('CROSSCHAT_CHANNEL_ID', 0))

# Leveling bot configuration
LEVELING_DATA_FILE = 'leveling_data.json'
MODERATION_DATA_FILE = 'moderation_data.json'
XP_PER_MESSAGE = 5  # XP gained per message
XP_PER_REACTION = 2  # XP gained per reaction
XP_COOLDOWN_SECONDS = 60  # Cooldown between XP gains per user
LEVEL_ROLES = {
    5: int(os.getenv('LEVEL_5_ROLE_ID', 0)),
    10: int(os.getenv('LEVEL_10_ROLE_ID', 0)),
    15: int(os.getenv('LEVEL_15_ROLE_ID', 0)),
    20: int(os.getenv('LEVEL_20_ROLE_ID', 0)),
    25: int(os.getenv('LEVEL_25_ROLE_ID', 0)),
    30: int(os.getenv('LEVEL_30_ROLE_ID', 0)),
    35: int(os.getenv('LEVEL_35_ROLE_ID', 0)),
    40: int(os.getenv('LEVEL_40_ROLE_ID', 0)),
    45: int(os.getenv('LEVEL_45_ROLE_ID', 0)),
    50: int(os.getenv('LEVEL_50_ROLE_ID', 0)),
}

STATUS_MESSAGES = [
    "living life",
    "clem is cute",
    "arcaneisland.minehut.gg",
    "watching over Arcane Islands",
    "IM AN AI",
    "ELLO",
    "lol",
    "xD",
    "who needs sleep?"
]

# Moderation settings
MAX_MESSAGE_LENGTH = 300
MAX_WORDS_PER_MESSAGE = 100
SPAM_WINDOW_SECONDS = 10
SPAM_MAX_MESSAGES = 5
SPAM_TIMEOUT_MINUTES = 10
LARGE_MESSAGE_ALERT_ONLY = True

# Anti-nuke settings
ANTI_NUKE_WINDOW_SECONDS = 30
ANTI_NUKE_CHANNEL_THRESHOLD = 3
ANTI_NUKE_BAN_ON_DETECTION = True

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.guild_messages = True
intents.dm_messages = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Enforce guild-only use for all prefix commands
def guild_only_check(ctx):
    if ctx.guild is None:
        raise commands.NoPrivateMessage("This command can only be used in servers.")
    return True

bot.add_check(guild_only_check)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("❌ This command can only be used in servers.")
        return
    raise error


@bot.event
async def on_command(ctx):
    """Log prefix command usage."""
    if not ctx.guild or ctx.author.bot:
        return

    embed = discord.Embed(
        title="⌨️ Command Used",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="User", value=f"{ctx.author} ({ctx.author.id})", inline=False)
    embed.add_field(name="Command", value=ctx.message.content[:1024], inline=False)
    embed.add_field(name="Channel", value=f"{ctx.channel.mention}", inline=False)
    embed.set_footer(text=f"Guild: {ctx.guild.name} | {get_timestamp()}")
    await send_log(embed, 'command')


@bot.event
async def on_member_join(member: discord.Member):
    """Send welcome message when member joins"""
    if not member.guild:
        return
    
    if get_guild_setting(member.guild.id, 'enable_welcome', False):
        welcome_ch_id = get_guild_setting(member.guild.id, 'welcome_channel')
        welcome_msg = get_guild_setting(member.guild.id, 'welcome_message', f"Welcome {member.mention}!")
        
        if welcome_ch_id:
            try:
                channel = bot.get_channel(welcome_ch_id)
                if channel:
                    # Replace placeholders
                    msg = welcome_msg.replace('{user}', member.mention).replace('{server}', member.guild.name)
                    embed = discord.Embed(
                        title="👋 Welcome!",
                        description=msg,
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send welcome message: {e}")


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """Handle self-roles via reactions"""
    if payload.user_id == bot.user.id:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    
    if not get_guild_setting(guild.id, 'enable_self_roles', False):
        return
    
    roles_dict = get_guild_setting(guild.id, 'self_role_roles', {})
    emoji_str = str(payload.emoji)
    
    if emoji_str in roles_dict:
        try:
            member = await guild.fetch_member(payload.user_id)
            role = guild.get_role(int(roles_dict[emoji_str]))
            if role:
                await member.add_roles(role, reason="Self-role")
        except Exception as e:
            logger.error(f"Failed to add self-role: {e}")


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    """Handle self-role removal via reactions"""
    if payload.user_id == bot.user.id:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    
    if not get_guild_setting(guild.id, 'enable_self_roles', False):
        return
    
    roles_dict = get_guild_setting(guild.id, 'self_role_roles', {})
    emoji_str = str(payload.emoji)
    
    if emoji_str in roles_dict:
        try:
            member = await guild.fetch_member(payload.user_id)
            role = guild.get_role(int(roles_dict[emoji_str]))
            if role:
                await member.remove_roles(role, reason="Self-role removed")
        except Exception as e:
            logger.error(f"Failed to remove self-role: {e}")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.application_command:
        return
    if interaction.user.bot or not interaction.guild:
        return

    # Check if command logging is enabled for this guild
    command_log_channel_id = get_guild_setting(interaction.guild.id, 'command_log_channel_id')
    if not command_log_channel_id:
        return

    command_name = None
    if getattr(interaction, 'command', None):
        command_name = interaction.command.name
    elif interaction.data:
        command_name = interaction.data.get('name')

    if not command_name:
        return

    embed = discord.Embed(
        title="⌨️ Slash Command Used",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="User", value=f"{interaction.user} ({interaction.user.id})", inline=False)
    embed.add_field(name="Command", value=f"{command_name}", inline=False)
    embed.add_field(name="Channel", value=f"{interaction.channel.mention if interaction.channel else 'Unknown'}", inline=False)
    embed.set_footer(text=f"Guild: {interaction.guild.name} | {get_timestamp()}")
    await send_log(embed, command_log_channel_id)

# Global logging toggle
logging_enabled = True
suppressed_message_delete_ids = set()

def get_timestamp():
    """Get current timestamp formatted"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def update_status_loop():
    """Rotate the bot's custom status every 5 seconds."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        for status_message in STATUS_MESSAGES:
            try:
                await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=status_message))
            except Exception as e:
                logger.error(f"Failed to change status: {e}")
            await asyncio.sleep(5)

SEND_DEDUP_CACHE = {}
SEND_DEDUP_MAX_SECONDS = 2

def _cleanup_send_cache():
    now = time.time()
    for key, timestamp in list(SEND_DEDUP_CACHE.items()):
        if now - timestamp > SEND_DEDUP_MAX_SECONDS:
            del SEND_DEDUP_CACHE[key]


def should_send_once(channel_id, message_key):
    _cleanup_send_cache()
    key = (channel_id, message_key)
    if key in SEND_DEDUP_CACHE:
        return False
    SEND_DEDUP_CACHE[key] = time.time()
    return True


async def safe_channel_send(channel, content=None, embed=None, **kwargs):
    message_key = content or ''
    if embed is not None:
        if hasattr(embed, 'title') and embed.title:
            message_key += f"|{embed.title}"
        if hasattr(embed, 'description') and embed.description:
            message_key += f"|{embed.description}"
    if not should_send_once(channel.id, message_key):
        return None
    return await channel.send(content=content, embed=embed, **kwargs)


async def send_log(embed, channel_id):
    """Send log embed to specified log channel"""
    if not logging_enabled:
        return
    try:
        if isinstance(channel_id, str):
            channel_id = get_log_channel_id(channel_id)

        if isinstance(channel_id, str) and channel_id.isdigit():
            channel_id = int(channel_id)

        if not channel_id:
            return

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception as e:
                logger.error(f"Failed to fetch log channel {channel_id}: {e}")
                return

        if channel:
            await channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Failed to send log: {e}")

reaction_roles = {}
moderation_data = {}

def normalize_emoji(emoji_input):
    """Normalize emoji for use as a mapping key."""
    if isinstance(emoji_input, discord.PartialEmoji):
        return f"{emoji_input.id}:{emoji_input.name}" if emoji_input.id else emoji_input.name
    if isinstance(emoji_input, str):
        try:
            emoji_obj = discord.PartialEmoji.from_str(emoji_input)
            if emoji_obj.id:
                return f"{emoji_obj.id}:{emoji_obj.name}"
            return emoji_obj.name
        except Exception:
            return emoji_input
    return str(emoji_input)


def load_reaction_roles():
    global reaction_roles
    try:
        with open(REACTION_ROLE_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            reaction_roles = {
                str(message_id): {
                    normalize_emoji(emoji): int(role_id)
                    for emoji, role_id in emoji_map.items()
                }
                for message_id, emoji_map in raw_data.items()
            }
    except (FileNotFoundError, json.JSONDecodeError):
        reaction_roles = {}


def save_reaction_roles():
    try:
        with open(REACTION_ROLE_FILE, 'w', encoding='utf-8') as f:
            json.dump(reaction_roles, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save reaction roles: {e}")


DEFAULT_MODERATION_RECORD = {
    'warns': 0,
    'timeouts': 0,
    'mutes': 0,
    'bans': 0,
    'kicks': 0,
    'current_timeout_expires': None,
    'current_mute_expires': None,
    'current_ban_expires': None
}


def ensure_moderation_record(user_id):
    user_id = str(user_id)
    if user_id not in moderation_data:
        moderation_data[user_id] = DEFAULT_MODERATION_RECORD.copy()
    else:
        record = moderation_data[user_id]
        for key, default_value in DEFAULT_MODERATION_RECORD.items():
            record.setdefault(key, default_value)
        moderation_data[user_id] = record
    return moderation_data[user_id]


def clear_moderation_field(user_id, field_name):
    user_id = str(user_id)
    record = moderation_data.get(user_id)
    if not record:
        return
    record[field_name] = None
    save_moderation_data()


def format_future_duration(timestamp_str):
    if not timestamp_str:
        return 'None'
    try:
        expire_time = datetime.fromisoformat(timestamp_str)
    except Exception:
        return timestamp_str

    now = datetime.utcnow()
    if expire_time <= now:
        return f"Expired ({expire_time.strftime('%Y-%m-%d %H:%M:%S UTC')})"

    remaining = expire_time - now
    parts = []
    if remaining.days:
        parts.append(f"{remaining.days}d")
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    seconds = remaining.seconds % 60
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        parts.append(f"{seconds}s")

    return f"{expire_time.strftime('%Y-%m-%d %H:%M:%S UTC')} ({' '.join(parts)} remaining)"


def load_moderation_data():
    global moderation_data
    try:
        with open(MODERATION_DATA_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        moderation_data = {
            str(user_id): {
                **DEFAULT_MODERATION_RECORD,
                **(record or {})
            }
            for user_id, record in (raw_data or {}).items()
        }
    except (FileNotFoundError, json.JSONDecodeError):
        moderation_data = {}


def save_moderation_data():
    try:
        with open(MODERATION_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(moderation_data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save moderation data: {e}")


load_reaction_roles()
load_moderation_data()

MINECRAFT_LINK_FILE = 'minecraft_links.json'
MINECRAFT_VERIFICATION_FILE = 'minecraft_verifications.json'
minecraft_links = {}
pending_minecraft_links = {}

KUDOS_FILE = 'kudos.json'
kudos_data = {}


def load_kudos():
    global kudos_data
    try:
        with open(KUDOS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        kudos_data = {str(k): v for k, v in (data or {}).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        kudos_data = {}


def save_kudos():
    try:
        with open(KUDOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(kudos_data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save kudos data: {e}")


def give_kudos(giver_id, receiver_id, reason=None):
    """Give kudos to a user"""
    receiver_id = str(receiver_id)
    if receiver_id not in kudos_data:
        kudos_data[receiver_id] = {'count': 0, 'from': {}}
    
    kudos_data[receiver_id]['count'] += 1
    giver_id_str = str(giver_id)
    if giver_id_str not in kudos_data[receiver_id]['from']:
        kudos_data[receiver_id]['from'][giver_id_str] = {'count': 0, 'reasons': []}
    
    kudos_data[receiver_id]['from'][giver_id_str]['count'] += 1
    if reason:
        kudos_data[receiver_id]['from'][giver_id_str]['reasons'].append(reason)
    
    save_kudos()


def get_kudos(user_id):
    """Get total kudos for a user"""
    user_data = kudos_data.get(str(user_id), {})
    return user_data.get('count', 0)


def get_kudos_details(user_id):
    """Get detailed kudos information for a user"""
    return kudos_data.get(str(user_id), {'count': 0, 'from': {}})


def get_kudos_leaderboard(limit=10):
    """Get top users by kudos count"""
    sorted_users = sorted(
        [(uid, data['count']) for uid, data in kudos_data.items()],
        key=lambda x: x[1],
        reverse=True
    )
    return sorted_users[:limit]


def remove_kudos(user_id, amount=1):
    """Remove kudos from a user (admin only)"""
    user_id = str(user_id)
    if user_id in kudos_data:
        kudos_data[user_id]['count'] = max(0, kudos_data[user_id]['count'] - amount)
        save_kudos()
        return True
    return False


def award_kudos(user_id, amount=1):
    """Award kudos to a user (admin only)"""
    user_id = str(user_id)
    if user_id not in kudos_data:
        kudos_data[user_id] = {'count': 0, 'from': {}}
    
    kudos_data[user_id]['count'] += amount
    save_kudos()


def load_minecraft_links():
    global minecraft_links
    try:
        with open(MINECRAFT_LINK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        minecraft_links = {str(k): str(v) for k, v in (data or {}).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        minecraft_links = {}


def save_minecraft_links():
    try:
        with open(MINECRAFT_LINK_FILE, 'w', encoding='utf-8') as f:
            json.dump(minecraft_links, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save Minecraft links: {e}")


def load_minecraft_verifications():
    global pending_minecraft_links
    try:
        with open(MINECRAFT_VERIFICATION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        pending_minecraft_links = {str(k): v for k, v in (data or {}).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        pending_minecraft_links = {}


def save_minecraft_verifications():
    try:
        with open(MINECRAFT_VERIFICATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(pending_minecraft_links, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save Minecraft verification requests: {e}")


WELCOME_CHANNEL_FILE = 'welcome_channels.json'
welcome_channel_settings = {}

SERVER_SETTINGS_FILE = 'server_settings.json'
server_settings = {}

WARNINGS_FILE = 'warnings.json'
warnings_data = {}

SUGGESTIONS_FILE = 'suggestions.json'
suggestions_data = {}

LOG_CHANNEL_FILE = 'log_channels.json'
log_channel_settings = {}


def load_warnings():
    global warnings_data
    try:
        with open(WARNINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        warnings_data = {str(k): v for k, v in (data or {}).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        warnings_data = {}


def save_warnings():
    try:
        with open(WARNINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(warnings_data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save warnings: {e}")


def load_suggestions():
    global suggestions_data
    try:
        with open(SUGGESTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        suggestions_data = {str(k): v for k, v in (data or {}).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        suggestions_data = {}


def save_suggestions():
    try:
        with open(SUGGESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(suggestions_data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save suggestions: {e}")


def add_warning(user_id, guild_id, reason, moderator_id):
    """Add a warning to a user"""
    user_key = f"{guild_id}_{user_id}"
    if user_key not in warnings_data:
        warnings_data[user_key] = []
    
    warnings_data[user_key].append({
        'reason': reason,
        'moderator_id': str(moderator_id),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })
    save_warnings()


def get_warnings(user_id, guild_id):
    """Get all warnings for a user in a guild"""
    user_key = f"{guild_id}_{user_id}"
    return warnings_data.get(user_key, [])


def clear_warnings(user_id, guild_id):
    """Clear all warnings for a user"""
    user_key = f"{guild_id}_{user_id}"
    if user_key in warnings_data:
        warnings_data.pop(user_key, None)
        save_warnings()
        return True
    return False


def add_suggestion(guild_id, author_id, content):
    """Add a suggestion"""
    if str(guild_id) not in suggestions_data:
        suggestions_data[str(guild_id)] = []
    
    suggestions_data[str(guild_id)].append({
        'id': len(suggestions_data.get(str(guild_id), [])) + 1,
        'author_id': str(author_id),
        'content': content,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'upvotes': [],
        'downvotes': [],
        'status': 'pending'
    })
    save_suggestions()


def get_suggestions(guild_id, status='pending'):
    """Get suggestions by status"""
    guild_suggestions = suggestions_data.get(str(guild_id), [])
    return [s for s in guild_suggestions if s.get('status') == status]


LOG_CHANNEL_TYPES = {
    'message': 'MESSAGE_LOG_CHANNEL_ID',
    'member': 'MEMBER_LOG_CHANNEL_ID',
    'channel': 'CHANNEL_LOG_CHANNEL_ID',
    'role': 'ROLE_LOG_CHANNEL_ID',
    'moderation': 'STAFF_ALERT_CHANNEL_ID',
    'emoji': 'EMOJI_LOG_CHANNEL_ID',
    'command': 'COMMAND_LOG_CHANNEL_ID'
}

LOG_TYPE_ALIASES = {
    'message': 'message',
    'messages': 'message',
    'messagelog': 'message',
    'member': 'member',
    'members': 'member',
    'memberlog': 'member',
    'joinleavelog': 'member',
    'joinleave': 'member',
    'channel': 'channel',
    'channels': 'channel',
    'channellog': 'channel',
    'server': 'channel',
    'serverlog': 'channel',
    'role': 'role',
    'roles': 'role',
    'rolelog': 'role',
    'moderation': 'moderation',
    'moderationlog': 'moderation',
    'staff': 'moderation',
    'staffalert': 'moderation',
    'alerts': 'moderation',
    'emoji': 'emoji',
    'emojis': 'emoji',
    'emojilog': 'emoji',
    'emoji_log': 'emoji',
    'emoji log': 'emoji',
    'reaction': 'emoji',
    'reactions': 'emoji',
    'reactionlog': 'emoji',
    'reaction log': 'emoji',
    'command': 'command',
    'commands': 'command',
    'commandlog': 'command',
    'command_log': 'command',
    'command log': 'command',
    'cmd': 'command',
    'cmdlog': 'command',
    'cmd_log': 'command',
    'cmd log': 'command',
    'all': 'all',
    'setup': 'all',
    'setupall': 'all',
    'setuplog': 'all',
    'alllogs': 'all'
}

def normalize_log_type(log_type):
    if not isinstance(log_type, str):
        return None

    canonical = re.sub(r'[^a-z0-9]', '', log_type.lower())
    return LOG_TYPE_ALIASES.get(canonical)

def load_welcome_channels():
    global welcome_channel_settings
    try:
        with open(WELCOME_CHANNEL_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        welcome_channel_settings = {str(k): int(v) for k, v in (data or {}).items()}
    except (FileNotFoundError, json.JSONDecodeError):
        welcome_channel_settings = {}


def save_welcome_channels():
    try:
        with open(WELCOME_CHANNEL_FILE, 'w', encoding='utf-8') as f:
            json.dump(welcome_channel_settings, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save welcome channel settings: {e}")


def load_server_settings():
    global server_settings
    try:
        with open(SERVER_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        server_settings = {str(k): v for k, v in (raw_data or {}).items()}
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        server_settings = {}


def save_server_settings():
    try:
        with open(SERVER_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(server_settings, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save server settings: {e}")


load_server_settings()

def get_server_setting(guild_id, key, default=None):
    return server_settings.get(str(guild_id), {}).get(key, default)


def set_server_setting(guild_id, key, value):
    server_settings.setdefault(str(guild_id), {})[key] = value
    save_server_settings()


# Message Logging by Server
import os
MESSAGE_LOGS_FOLDER = 'message_logs'

def ensure_message_logs_folder():
    """Create message_logs folder if it doesn't exist"""
    if not os.path.exists(MESSAGE_LOGS_FOLDER):
        os.makedirs(MESSAGE_LOGS_FOLDER)


def get_server_message_log_file(guild_id):
    """Get the JSON file path for a server's message logs"""
    ensure_message_logs_folder()
    return os.path.join(MESSAGE_LOGS_FOLDER, f'{guild_id}.json')


def load_server_messages(guild_id):
    """Load all messages for a server"""
    filepath = get_server_message_log_file(guild_id)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f) or []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_server_messages(guild_id, messages):
    """Save messages for a server"""
    filepath = get_server_message_log_file(guild_id)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save server messages for {guild_id}: {e}")


def log_message(guild_id, message):
    """Log a message to the server's message log"""
    if not message.guild:
        return
    
    # Print to terminal
    print(f"[{message.guild.name}] {message.author}: {message.content}")
    
    messages = load_server_messages(guild_id)
    
    log_entry = {
        'author': str(message.author),
        'author_id': message.author.id,
        'content': message.content,
        'channel': message.channel.name,
        'channel_id': message.channel.id,
        'timestamp': message.created_at.isoformat() + 'Z',
        'message_id': message.id,
        'reply_to': message.reference.message_id if message.reference else None,
        'attachments': [att.url for att in message.attachments]
    }
    
    messages.append(log_entry)
    save_server_messages(guild_id, messages)



def load_log_channels():
    global log_channel_settings
    try:
        with open(LOG_CHANNEL_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log_channel_settings = {str(k): int(v) for k, v in (data or {}).items()}
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        log_channel_settings = {}


def save_log_channels():
    try:
        with open(LOG_CHANNEL_FILE, 'w', encoding='utf-8') as f:
            json.dump(log_channel_settings, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save log channel settings: {e}")


def get_log_channel_id(log_type):
    if isinstance(log_type, int):
        return log_type
    if isinstance(log_type, str) and log_type.isdigit():
        return int(log_type)

    if not isinstance(log_type, str):
        return 0

    log_type = log_type.lower()
    if log_type not in LOG_CHANNEL_TYPES:
        return 0

    stored_channel = log_channel_settings.get(log_type)
    if stored_channel:
        return stored_channel

    env_name = LOG_CHANNEL_TYPES[log_type]
    return globals().get(env_name, 0) or 0


load_welcome_channels()
load_log_channels()
load_warnings()
load_suggestions()


# Guild Settings Helpers
def set_guild_setting(guild_id, key, value):
    """Set a guild-wide setting"""
    guild_id = str(guild_id)
    if guild_id not in server_settings:
        server_settings[guild_id] = {}
    server_settings[guild_id][key] = value
    save_server_settings()


def get_guild_setting(guild_id, key, default=None):
    """Get a guild-wide setting"""
    guild_id = str(guild_id)
    return server_settings.get(guild_id, {}).get(key, default)


# Supported settings: 
# prefix, welcome_channel, welcome_message, self_role_channel, self_role_message, 
# suggestions_channel, enable_warnings, enable_suggestions, enable_welcome, enable_self_roles


STICKY_MESSAGE_FILE = 'sticky_messages.json'
sticky_messages = {}


def load_sticky_messages():
    global sticky_messages
    try:
        with open(STICKY_MESSAGE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        sticky_messages = {
            str(channel_id): {
                'message_id': int(values['message_id']),
                'content': values['content']
            }
            for channel_id, values in (data or {}).items()
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        sticky_messages = {}


def save_sticky_messages():
    try:
        with open(STICKY_MESSAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(sticky_messages, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save sticky messages: {e}")


load_sticky_messages()


def generate_verification_code(length=6):
    return ''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(length))


def cleanup_expired_verifications():
    now_ts = datetime.utcnow().timestamp()
    expired_ids = [user_id for user_id, data in pending_minecraft_links.items() if data.get('expires_at', 0) < now_ts]
    for user_id in expired_ids:
        pending_minecraft_links.pop(user_id, None)
    if expired_ids:
        save_minecraft_verifications()


def create_minecraft_verification(user_id, minecraft_username, expires_hours=1):
    cleanup_expired_verifications()
    code = generate_verification_code()
    pending_minecraft_links[str(user_id)] = {
        'minecraft_username': minecraft_username,
        'code': code,
        'requested_at': datetime.utcnow().isoformat() + 'Z',
        'expires_at': (datetime.utcnow() + timedelta(hours=expires_hours)).timestamp()
    }
    save_minecraft_verifications()
    return code


def get_pending_minecraft_verification(user_id):
    cleanup_expired_verifications()
    return pending_minecraft_links.get(str(user_id))


def remove_pending_minecraft_verification(user_id):
    if str(user_id) in pending_minecraft_links:
        pending_minecraft_links.pop(str(user_id), None)
        save_minecraft_verifications()
        return True
    return False


def set_minecraft_link(user_id, username):
    minecraft_links[str(user_id)] = username
    save_minecraft_links()


def remove_minecraft_link(user_id):
    if str(user_id) in minecraft_links:
        minecraft_links.pop(str(user_id), None)
        save_minecraft_links()
        return True
    return False


def get_minecraft_link(user_id):
    return minecraft_links.get(str(user_id))

load_minecraft_links()
load_minecraft_verifications()
load_kudos()

crosschat_messages = []


async def handle_verify_minecraft(request):
    if not VERIFICATION_API_SECRET:
        return web.json_response({'success': False, 'error': 'Verification API not configured'}, status=503)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({'success': False, 'error': 'Invalid JSON'}, status=400)

    secret = request.headers.get('X-Api-Secret') or data.get('secret')
    if secret != VERIFICATION_API_SECRET:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)

    discord_id = str(data.get('discord_id') or data.get('user_id') or '')
    minecraft_username = str(data.get('minecraft_username') or data.get('minecraft') or '').strip()
    code = str(data.get('code') or data.get('verification_code') or '').strip()
    player_name = str(data.get('player_name') or data.get('minecraft_player') or '')

    if not discord_id or not minecraft_username or not code:
        return web.json_response({'success': False, 'error': 'discord_id, minecraft_username, and code are required'}, status=400)

    pending = get_pending_minecraft_verification(discord_id)
    if not pending:
        return web.json_response({'success': False, 'error': 'No pending verification for that Discord ID'}, status=404)

    if pending.get('minecraft_username', '').lower() != minecraft_username.lower():
        return web.json_response({'success': False, 'error': 'Minecraft username does not match pending request'}, status=400)

    if pending.get('code') != code:
        return web.json_response({'success': False, 'error': 'Verification code does not match'}, status=400)

    set_minecraft_link(discord_id, pending['minecraft_username'])
    remove_pending_minecraft_verification(discord_id)

    # Assign roles based on LuckPerms groups
    groups_str = data.get('groups', '')
    if groups_str and LUCKPERMS_ROLE_MAPPING:
        groups = [g.strip() for g in groups_str.split(',') if g.strip()]
        await assign_luckperms_roles(discord_id, groups)

    response_data = {
        'success': True,
        'discord_id': discord_id,
        'minecraft_username': pending['minecraft_username'],
        'player_name': player_name or None
    }
    return web.json_response(response_data)


async def handle_send_message(request):
    if not VERIFICATION_API_SECRET:
        return web.json_response({'success': False, 'error': 'API not configured'}, status=503)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({'success': False, 'error': 'Invalid JSON'}, status=400)

    secret = request.headers.get('X-Api-Secret') or data.get('secret')
    if secret != VERIFICATION_API_SECRET:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)

    channel_type = data.get('channel', 'minecraft')
    message = data.get('message', '').strip()
    username = data.get('username', 'Unknown')

    if not message:
        return web.json_response({'success': False, 'error': 'Message is required'}, status=400)

    try:
        if channel_type == 'minecraft':
            channel_id = CROSSCHAT_CHANNEL_ID
        else:
            channel_id = int(channel_type) if channel_type.isdigit() else CROSSCHAT_CHANNEL_ID

        channel = bot.get_channel(channel_id)
        if not channel:
            return web.json_response({'success': False, 'error': 'Channel not found'}, status=404)

        embed = discord.Embed(
            description=message,
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_author(name=username, icon_url=None)
        embed.set_footer(text="Minecraft Chat")

        await channel.send(embed=embed)
        return web.json_response({'success': True})
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def handle_get_crosschat_messages(request):
    if not VERIFICATION_API_SECRET:
        return web.json_response({'success': False, 'error': 'API not configured'}, status=503)

    secret = request.headers.get('X-Api-Secret') or request.query.get('secret')
    if secret != VERIFICATION_API_SECRET:
        return web.json_response({'success': False, 'error': 'Unauthorized'}, status=401)

    messages = crosschat_messages.copy()
    crosschat_messages.clear()
    return web.json_response({'success': True, 'messages': messages})


async def assign_luckperms_roles(discord_id, groups):
    """Assign Discord roles based on LuckPerms groups."""
    try:
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            logger.error(f"Guild {GUILD_ID} not found for role assignment")
            return

        member = guild.get_member(int(discord_id))
        if not member:
            try:
                member = await guild.fetch_member(int(discord_id))
            except Exception as e:
                logger.error(f"Could not find member {discord_id}: {e}")
                return

        roles_to_add = []
        for group in groups:
            role_id = LUCKPERMS_ROLE_MAPPING.get(group.lower())
            if role_id:
                role = guild.get_role(int(role_id))
                if role and role not in member.roles:
                    roles_to_add.append(role)

        if roles_to_add:
            await member.add_roles(*roles_to_add, reason='LuckPerms group sync')
            logger.info(f"Assigned roles { [r.name for r in roles_to_add] } to {member.display_name} from groups {groups}")
    except Exception as e:
        logger.error(f"Failed to assign LuckPerms roles: {e}")


async def start_verification_server():
    if not VERIFICATION_API_SECRET:
        logger.warning('VERIFICATION_API_SECRET is not set; Minecraft verification HTTP API will not start.')
        return

    app = web.Application()
    app.add_routes([
        web.post('/verify_minecraft', handle_verify_minecraft),
        web.post('/send_message', handle_send_message),
        web.get('/get_crosschat_messages', handle_get_crosschat_messages)
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, VERIFICATION_API_HOST, VERIFICATION_API_PORT)
    await site.start()
    logger.info(f'Verification API listening on http://{VERIFICATION_API_HOST}:{VERIFICATION_API_PORT}/verify_minecraft')


SWEAR_WORDS = {
    'damn', 'hell', 'shit', 'fuck', 'bitch', 'ass', 'bastard', 'cunt'
}
SLUR_WORDS = {
    'nigga', 'nigger', 'spic', 'n1gga', 'n1gger', 'faggot', 'fag', 'n*gger', 'n*gga', 'f*ggot', 'f*g'
}

def contains_bad_word(content, bad_words):
    normalized = re.sub(r'[^a-z0-9\s]', ' ', content.lower())
    for word in bad_words:
        if re.search(rf'\b{re.escape(word)}\b', normalized):
            return True
    return False

async def alert_staff(title, message, author, channel, details):
    alert_channel_id = get_log_channel_id('moderation') or get_log_channel_id('message')
    embed = discord.Embed(
        title=title,
        description=message,
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    author_text = f'{author} ({getattr(author, "id", "unknown")})' if author else 'Unknown'
    channel_text = f'{channel.mention} ({channel.id})' if channel else 'Unknown'
    embed.add_field(name='User', value=author_text, inline=False)
    embed.add_field(name='Channel', value=channel_text, inline=False)
    embed.add_field(name='Details', value=details or 'No extra details', inline=False)
    embed.set_footer(text='Staff alert')

    try:
        alert_channel = bot.get_channel(alert_channel_id)
        if alert_channel:
            await alert_channel.send(embed=embed)
    except Exception as e:
        logger.error(f'Failed to alert staff: {e}')


def parse_duration(duration_str):
    """Parse a duration string like 10s, 10m, 1h, or 1d into seconds."""
    match = re.match(r'^(\d+)([smhd])$', duration_str.strip().lower())
    if not match:
        return None
    value, unit = match.groups()
    value = int(value)
    if unit == 's':
        return value
    if unit == 'm':
        return value * 60
    if unit == 'h':
        return value * 3600
    if unit == 'd':
        return value * 86400
    return None

USER_MESSAGE_HISTORY = {}
CHANNEL_DELETE_HISTORY = {}
PENDING_UNMUTES = {}
PENDING_UNBANS = {}
PENDING_TIMEOUTS = {}


async def get_or_create_mute_role(guild):
    mute_role = discord.utils.get(guild.roles, name="Muted")
    if mute_role:
        return mute_role

    permissions = discord.Permissions(send_messages=False, speak=False, add_reactions=False)
    try:
        mute_role = await guild.create_role(
            name="Muted",
            permissions=permissions,
            reason="Role created for mute moderation"
        )
    except Exception as e:
        logger.error(f"Failed to create mute role: {e}")
        return None

    for channel in guild.channels:
        try:
            if isinstance(channel, discord.TextChannel):
                await channel.set_permissions(mute_role, send_messages=False, add_reactions=False)
            elif isinstance(channel, discord.VoiceChannel):
                await channel.set_permissions(mute_role, connect=False, speak=False)
        except Exception:
            continue

    return mute_role


async def schedule_unmute(guild, user, role, duration_seconds):
    key = (guild.id, user.id, role.id)
    if key in PENDING_UNMUTES:
        PENDING_UNMUTES[key].cancel()

    async def unmute_task():
        try:
            await asyncio.sleep(duration_seconds)
            if role in user.roles:
                await user.remove_roles(role, reason="Temporary mute expired")
                alert_channel = guild.system_channel or (guild.text_channels[0] if guild.text_channels else None)
                await alert_staff(
                    title='🔈 Unmute Completed',
                    message=f'{user} was automatically unmuted.',
                    author=user,
                    channel=alert_channel,
                    details=f'Mute duration expired after {duration_seconds} seconds.'
                )
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"Failed to auto-unmute {user}: {e}")
        finally:
            clear_moderation_field(user.id, 'current_mute_expires')
            PENDING_UNMUTES.pop(key, None)

    task = asyncio.create_task(unmute_task())
    PENDING_UNMUTES[key] = task


async def schedule_unban(guild, user_id, duration_seconds):
    key = (guild.id, user_id)
    if key in PENDING_UNBANS:
        PENDING_UNBANS[key].cancel()

    async def unban_task():
        try:
            await asyncio.sleep(duration_seconds)
            await guild.unban(discord.Object(id=user_id), reason="Temporary ban expired")
            alert_channel = guild.system_channel or (guild.text_channels[0] if guild.text_channels else None)
            await alert_staff(
                title='🔓 Temporary Ban Lifted',
                message=f'User <@{user_id}> was automatically unbanned.',
                author=bot.user,
                channel=alert_channel,
                details=f'Ban expired after {duration_seconds} seconds.'
            )
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"Failed to auto-unban {user_id}: {e}")
        finally:
            clear_moderation_field(user_id, 'current_ban_expires')
            PENDING_UNBANS.pop(key, None)

    task = asyncio.create_task(unban_task())
    PENDING_UNBANS[key] = task


async def schedule_timeout_clear(guild, user_id, duration_seconds):
    key = (guild.id, user_id)
    if key in PENDING_TIMEOUTS:
        PENDING_TIMEOUTS[key].cancel()

    async def timeout_task():
        try:
            await asyncio.sleep(duration_seconds)
            clear_moderation_field(user_id, 'current_timeout_expires')
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"Failed to clear timeout state for {user_id}: {e}")
        finally:
            PENDING_TIMEOUTS.pop(key, None)

    task = asyncio.create_task(timeout_task())
    PENDING_TIMEOUTS[key] = task


async def set_channel_lockdown(channel, lock=True):
    if lock:
        await channel.set_permissions(channel.guild.default_role, send_messages=False, add_reactions=False)
    else:
        await channel.set_permissions(channel.guild.default_role, send_messages=None, add_reactions=None)


async def set_server_lockdown(guild, lock=True):
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            try:
                if lock:
                    await channel.set_permissions(guild.default_role, send_messages=False, add_reactions=False)
                else:
                    await channel.set_permissions(guild.default_role, send_messages=None, add_reactions=None)
            except Exception:
                continue


def record_user_message(user_id):
    now = datetime.utcnow().timestamp()
    history = USER_MESSAGE_HISTORY.setdefault(user_id, deque())
    history.append(now)
    while history and now - history[0] > SPAM_WINDOW_SECONDS:
        history.popleft()
    return len(history)


def is_spamming(user_id):
    return record_user_message(user_id) > SPAM_MAX_MESSAGES


def record_channel_deletion(guild_id, user_id):
    now = datetime.utcnow().timestamp()
    guild_history = CHANNEL_DELETE_HISTORY.setdefault(guild_id, {})
    history = guild_history.setdefault(user_id, deque())
    history.append(now)
    while history and now - history[0] > ANTI_NUKE_WINDOW_SECONDS:
        history.popleft()
    return len(history)


async def find_channel_delete_actor(guild, channel):
    try:
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.channel_delete):
            target = getattr(entry.target, 'id', None)
            if target == channel.id:
                # Only use recent entries to avoid stale matches
                if (datetime.utcnow() - entry.created_at).total_seconds() < 120:
                    return entry.user
    except Exception as e:
        logger.error(f"Failed to fetch audit logs for channel deletion: {e}")
    return None


async def handle_nuke_detected(channel, actor, delete_count):
    guild = channel.guild
    if not guild:
        return

    action_taken = False
    action_reason = 'Anti-nuke protection: rapid channel deletion'

    try:
        if actor and actor.id == guild.owner_id:
            await alert_staff(
                title='⚠️ Potential Nuke Activity Detected',
                message=f'Owner {actor} deleted {delete_count} channels rapidly. Manual review required.',
                author=actor,
                channel=channel,
                details=f'Owner-initiated channel deletions: {delete_count} in {ANTI_NUKE_WINDOW_SECONDS} seconds.'
            )
            return

        if ANTI_NUKE_BAN_ON_DETECTION and actor:
            await guild.ban(actor, reason=action_reason, delete_message_days=0)
            action_taken = True
            action_name = 'banned'
        elif actor:
            await guild.kick(actor, reason=action_reason)
            action_taken = True
            action_name = 'kicked'
        else:
            action_name = 'flagged'

        if action_taken:
            await alert_staff(
                title='🚨 Anti-nuke Action Taken',
                message=f'{actor} was {action_name} after deleting {delete_count} channels rapidly.',
                author=actor,
                channel=channel,
                details=f'Auto action: {action_reason}'
            )
        else:
            await alert_staff(
                title='🚨 Anti-nuke Alert',
                message=f'A user deleted {delete_count} channels rapidly but no automatic action could be taken.',
                author=actor or bot.user,
                channel=channel,
                details=f'Channel deletion detected in {guild.name}. Actor: {actor}'
            )
    except Exception as e:
        logger.error(f"Failed to take anti-nuke action: {e}")
        await alert_staff(
            title='⚠️ Anti-nuke Failure',
            message=f'Failed to take countermeasures against rapid channel deletion by {actor}.',
            author=actor or bot.user,
            channel=channel,
            details=str(e)
        )


def find_ticket_category(guild):
    """Find a ticket category by ID or common names"""
    if TICKET_CATEGORY_ID:
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if isinstance(category, discord.CategoryChannel):
            return category
    for category in guild.categories:
        if category.name.lower() in ("tickets", "support", "help", "ticket"):
            return category
    return None


def sanitize_ticket_name(name):
    """Convert a name to a safe channel name"""
    safe = "".join(ch if ch.isalnum() or ch == '-' else '-' for ch in name.lower())
    return safe.strip('-') or 'ticket'


def extract_user_id_from_mention(value):
    """Extract a Discord user ID from mention text like <@123> or <@!123>."""
    if not isinstance(value, str):
        return None
    match = re.search(r'<@!?(?P<id>\d+)>', value)
    return int(match.group('id')) if match else None


def extract_user_id_from_mention(value):
    """Extract a Discord user ID from mention text like <@123> or <@!123>."""
    if not isinstance(value, str):
        return None
    match = re.search(r'<@!?(?P<id>\d+)>', value)
    return int(match.group('id')) if match else None


def is_ticket_staff(member):
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.manage_channels:
        return True
    staff_role_id = get_server_setting(member.guild.id, 'staff_role_id') or TICKET_STAFF_ROLE_ID
    if staff_role_id:
        role = member.guild.get_role(int(staff_role_id)) if isinstance(staff_role_id, (str, int)) else None
        if role and role in member.roles:
            return True
    return False


async def send_ticket_transcript(channel, closed_by, owner_id):
    transcript_channel_id = get_server_setting(channel.guild.id, 'ticket_transcript_channel_id')
    if not transcript_channel_id:
        return None

    transcript_channel = channel.guild.get_channel(int(transcript_channel_id))
    if not transcript_channel:
        return None

    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = f"{msg.author} ({msg.author.id})"
        content = msg.content or ""
        attachments = ""
        if msg.attachments:
            attachments = "\n" + "\n".join(att.url for att in msg.attachments)
        messages.append(f"[{timestamp}] {author}: {content}{attachments}")

    transcript_text = "\n".join(messages) or "No messages."
    bio = io.BytesIO(transcript_text.encode('utf-8'))
    bio.seek(0)
    filename = f"{channel.name}-transcript.txt"

    embed = discord.Embed(
        title="📜 Ticket Transcript",
        description=f"Transcript for {channel.name}",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Ticket Owner", value=f"<@{owner_id}>", inline=True)
    embed.add_field(name="Closed By", value=f"{closed_by} ({closed_by.id})", inline=True)
    embed.add_field(name="Channel", value=channel.name, inline=True)

    try:
        await transcript_channel.send(embed=embed, file=discord.File(bio, filename=filename))
        return transcript_channel
    except Exception as e:
        logger.error(f"Failed to send ticket transcript: {e}")
        return None


async def close_ticket_channel(channel, closed_by, owner_id, original_message=None):
    ticket_owner = channel.guild.get_member(owner_id)
    overwrite = discord.PermissionOverwrite(view_channel=False, send_messages=False, read_messages=False, read_message_history=False)
    try:
        await channel.set_permissions(ticket_owner or discord.Object(id=owner_id), overwrite=overwrite)
    except Exception as e:
        logger.error(f"Failed to remove ticket owner access: {e}")

    transcript_channel = await send_ticket_transcript(channel, closed_by, owner_id)
    transcript_text = (
        f"Transcript sent to {transcript_channel.mention}." if transcript_channel
        else "No transcript channel configured or channel not found."
    )

    embed = discord.Embed(
        title="🔒 Ticket Closed",
        description=f"Ticket closed by {closed_by.mention}.\n{transcript_text}",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Ticket Owner", value=f"<@{owner_id}>", inline=True)
    if transcript_channel:
        embed.add_field(name="Transcript Channel", value=transcript_channel.mention, inline=True)

    view = TicketClosedView(owner_id)
    try:
        if original_message:
            await original_message.edit(embed=embed, view=view)
        else:
            await channel.send(embed=embed, view=view)
    except Exception as e:
        logger.error(f"Failed to send closed ticket embed: {e}")

    return transcript_channel


async def create_ticket_channel(source, reason=None):
    guild = source.guild
    user = getattr(source, 'author', None) or getattr(source, 'user', None)
    if not guild or not user:
        raise RuntimeError("Ticket source must have guild and user")

    category = find_ticket_category(guild)
    base_name = sanitize_ticket_name(f"ticket-{user.name}")
    channel_name = base_name
    suffix = 1
    while discord.utils.get(guild.channels, name=channel_name):
        suffix += 1
        channel_name = f"{base_name}-{suffix}"

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
    }
    staff_role_id = get_server_setting(guild.id, 'staff_role_id') or TICKET_STAFF_ROLE_ID
    if staff_role_id:
        staff_role = guild.get_role(int(staff_role_id)) if isinstance(staff_role_id, str) or isinstance(staff_role_id, int) else None
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)

    channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category)
    embed = discord.Embed(
        title="🎟️ Ticket Created",
        description=f"{user.mention}, your ticket is ready!\n\nReason: {reason or 'No reason provided.'}",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Ticket Owner", value=user.mention, inline=True)
    embed.add_field(name="Status", value="Open — waiting for staff to claim", inline=True)
    embed.set_footer(text=f"Created at {get_timestamp()}")
    await channel.send(embed=embed, view=TicketControlView(owner_id=user.id))
    return channel


def build_ticket_panel_embed():
    embed = discord.Embed(
        title="General support",
        description="Open ticket for general support",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    return embed


def build_ticket_panel_view():
    return TicketPanelView()


class TicketControlView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.claimed_by_id = None

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_ticket_staff(interaction.user):
            await interaction.response.send_message("❌ Only staff members can claim tickets.", ephemeral=True)
            return

        if self.claimed_by_id:
            if self.claimed_by_id == interaction.user.id:
                await interaction.response.send_message("✅ You already claimed this ticket.", ephemeral=True)
            else:
                claimed_member = interaction.guild.get_member(self.claimed_by_id)
                claimed_name = claimed_member.mention if claimed_member else f"<@{self.claimed_by_id}>"
                await interaction.response.send_message(f"❌ This ticket is already claimed by {claimed_name}.", ephemeral=True)
            return

        self.claimed_by_id = interaction.user.id
        embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else discord.Embed()
        if embed.fields and len(embed.fields) > 1:
            embed.set_field_at(1, name="Status", value=f"Claimed by {interaction.user.mention}", inline=True)
        else:
            embed.add_field(name="Status", value=f"Claimed by {interaction.user.mention}", inline=True)
        await interaction.message.edit(embed=embed, view=self)
        await interaction.channel.send(f"✅ {interaction.user.mention} has claimed this ticket.")
        await interaction.response.send_message("✅ Ticket claimed.", ephemeral=True)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_ticket_staff(interaction.user):
            await interaction.response.send_message("❌ Only staff members can close tickets.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await close_ticket_channel(interaction.channel, interaction.user, self.owner_id, original_message=interaction.message)
        await interaction.followup.send("✅ Ticket closed. Transcript has been sent if configured.", ephemeral=True)


class TicketClosedView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=None)
        self.owner_id = owner_id

    @discord.ui.button(label="Reopen Ticket", style=discord.ButtonStyle.success, custom_id="ticket_reopen")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_ticket_staff(interaction.user):
            await interaction.response.send_message("❌ Only staff members can reopen tickets.", ephemeral=True)
            return

        owner_member = interaction.guild.get_member(self.owner_id)
        if owner_member:
            overwrite = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True, read_message_history=True)
            await interaction.channel.set_permissions(owner_member, overwrite=overwrite)

        embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description=f"Ticket reopened by {interaction.user.mention}.",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Ticket Owner", value=f"<@{self.owner_id}>", inline=True)
        await interaction.message.edit(embed=embed, view=TicketControlView(owner_id=self.owner_id))
        await interaction.response.send_message("✅ Ticket reopened.", ephemeral=True)

    @discord.ui.button(label="Delete Ticket", style=discord.ButtonStyle.secondary, custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_ticket_staff(interaction.user):
            await interaction.response.send_message("❌ Only staff members can delete tickets.", ephemeral=True)
            return

        await interaction.response.send_message("🗑️ Deleting ticket channel...", ephemeral=True)
        try:
            await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")
        except Exception as e:
            logger.error(f"Failed to delete ticket channel: {e}")
            await interaction.followup.send("❌ Failed to delete the ticket channel. Check my permissions.", ephemeral=True)


class CountingBot:
    def __init__(self):
        self.user_data = {}  # user_id -> {'score': int, 'saves': int, 'streak': int, 'incorrect': int, 'total_correct': int, 'total_attempts': int, 'saves_used': int, 'saves_given': int}
        self.channel_counts = {}  # channel_id -> current_count
        self.channel_last_user = {}  # channel_id -> last_user_id who counted
        self.counting_log_file = 'counting_log.txt'
        self.load_data()
    
    def load_data(self):
        """Load user and counting data from file"""
        try:
            with open(COUNTING_DATA_FILE, 'r') as f:
                data = json.load(f)

            if isinstance(data, dict) and 'user_data' in data:
                self.user_data = data.get('user_data', {})
                self.channel_counts = {int(k): v for k, v in data.get('channel_counts', {}).items()}
                self.channel_last_user = {int(k): v for k, v in data.get('channel_last_user', {}).items()}
            else:
                self.user_data = data
                self.channel_counts = {}
                self.channel_last_user = {}
        except FileNotFoundError:
            self.user_data = {}
            self.channel_counts = {}
            self.channel_last_user = {}
        except json.JSONDecodeError:
            self.user_data = {}
            self.channel_counts = {}
            self.channel_last_user = {}
    
    def reload_data(self):
        """Reload user and counting data from file"""
        self.load_data()
        return f"✅ Counting data reloaded successfully! Loaded {len(self.user_data)} user records."
    
    def save_data(self):
        """Save user and counting data to file"""
        data = {
            'user_data': self.user_data,
            'channel_counts': {str(k): v for k, v in self.channel_counts.items()},
            'channel_last_user': {str(k): v for k, v in self.channel_last_user.items()}
        }
        with open(COUNTING_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def log_counting_event(self, event_type, channel_id, user_id, message, details=""):
        """Log counting events to file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_name = "Unknown"
        try:
            user = bot.get_user(user_id)
            user_name = user.display_name if user and hasattr(user, 'display_name') else str(user_id)
        except:
            user_name = str(user_id)
        
        channel_name = "Unknown"
        try:
            channel = bot.get_channel(channel_id)
            channel_name = channel.name if channel else str(channel_id)
        except:
            channel_name = str(channel_id)
        
        log_entry = f"[{timestamp}] {event_type.upper()}: {user_name} ({user_id}) in #{channel_name} - {message} {details}\n"
        
        with open(self.counting_log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    
    def get_user_data(self, user_id):
        """Get or create user data"""
        if str(user_id) not in self.user_data:
            self.user_data[str(user_id)] = {
                'score': 0,
                'saves': 0,
                'streak': 0,
                'incorrect': 0,
                'total_correct': 0,
                'total_attempts': 0,
                'saves_used': 0,
                'saves_given': 0
            }
        else:
            user_data = self.user_data[str(user_id)]
            if 'total_correct' not in user_data:
                user_data['total_correct'] = 0
            if 'total_attempts' not in user_data:
                user_data['total_attempts'] = 0
            if 'saves_used' not in user_data:
                user_data['saves_used'] = 0
            if 'saves_given' not in user_data:
                user_data['saves_given'] = 0
        return self.user_data[str(user_id)]
    
    def evaluate_math_expression(self, expression):
        """Safely evaluate a math expression"""
        expression = expression.strip()
        if not re.match(r'^[0-9+\-*/().\s]+$', expression):
            return None

        try:
            # Basic security: don't allow too long expressions or dangerous patterns
            if len(expression) > 50:
                return None

            # Use eval with restricted globals
            result = eval(expression, {"__builtins__": {}})

            # Ensure result is an integer
            if isinstance(result, (int, float)) and result == int(result):
                return int(result)
            return None
        except:
            return None

    def is_counting_message(self, message_content):
        """Return True only for messages that should count."""
        if not isinstance(message_content, str):
            return False

        content = message_content.strip()
        if not content or content.startswith('!'):
            return False

        if re.match(r'^[0-9+\-*/().\s]+$', content):
            try:
                int(content)
                return True
            except ValueError:
                return self.evaluate_math_expression(content) is not None

        return False

    def process_counting_message(self, channel_id, user_id, message_content):
        """Process a counting message and return result"""
        # Try to parse the message as a number or math expression
        try:
            # First try direct number
            user_number = int(message_content.strip())
        except ValueError:
            # Try math expression
            user_number = self.evaluate_math_expression(message_content)
            if user_number is None:
                # Not a counting message, ignore it
                return None, None
        
        # Check if this user just counted (two numbers in a row)
        if self.channel_last_user.get(channel_id) == user_id:
            # Same user counted twice in a row - reset to 0
            old_count = self.channel_counts.get(channel_id, 0)
            self.channel_counts[channel_id] = 0
            self.channel_last_user[channel_id] = None  # Clear last user so anyone can start
            
            user_data = self.get_user_data(user_id)
            user_data['incorrect'] += 1
            user_data['total_attempts'] += 1
            
            if user_data['saves'] > 0:
                user_data['saves'] -= 1
                user_data['saves_used'] += 1
                user_data['streak'] = 0
                self.save_data()
                
                self.log_counting_event("double_count_reset", channel_id, user_id, message_content, f"Count reset from {old_count} to 0, used save. Saves left: {user_data['saves']}")
                
                return False, f"❌ You counted twice in a row! Count reset to 0. You used a save! Saves remaining: {user_data['saves']}"
            else:
                old_score = user_data['score']
                user_data['score'] = 0
                user_data['streak'] = 0
                self.save_data()
                
                self.log_counting_event("double_count_reset", channel_id, user_id, message_content, f"Count reset from {old_count} to 0, score reset from {old_score} to 0")
                
                return False, f"❌ You counted twice in a row! Count reset to 0. No saves remaining! Your score: {user_data['score']}"

        # Get current count for this channel
        current_count = self.channel_counts.get(channel_id, 0)
        next_number = current_count + 1
        
        user_data = self.get_user_data(user_id)
        
        # Check if it's the correct next number
        if user_number == next_number:
            # Correct!
            self.channel_counts[channel_id] = next_number
            self.channel_last_user[channel_id] = user_id
            user_data['score'] += 1
            user_data['streak'] += 1
            user_data['total_correct'] += 1
            user_data['total_attempts'] += 1
            self.save_data()
            
            self.log_counting_event("correct", channel_id, user_id, message_content, f"Count: {next_number}, Score: {user_data['score']}, Total correct: {user_data['total_correct']}")
            
            return True, f"✅ **{next_number}**! Good job! Your score: {user_data['score']}, Streak: {user_data['streak']}"
        else:
            # Wrong answer - increment incorrect count
            self.channel_last_user[channel_id] = user_id
            user_data['incorrect'] += 1
            user_data['total_attempts'] += 1
            
            if user_data['saves'] > 0:
                # Use a save
                user_data['saves'] -= 1
                user_data['saves_used'] += 1
                user_data['streak'] = 0
                self.save_data()
                
                self.log_counting_event("save_used", channel_id, user_id, message_content, f"Expected: {next_number}, Saves left: {user_data['saves']}")
                
                return False, f"❌ Wrong! Expected **{next_number}**, you said **{user_number}**. You used a save! Saves remaining: {user_data['saves']}"
            else:
                # No saves, reset
                old_score = user_data['score']
                user_data['score'] = 0
                user_data['streak'] = 0
                self.channel_counts[channel_id] = 0  # Reset channel count
                self.save_data()
                
                self.log_counting_event("reset", channel_id, user_id, message_content, f"Expected: {next_number}, Score reset from {old_score} to 0")
                
                return False, f"❌ Wrong! Expected **{next_number}**, you said **{user_number}**. No saves remaining! Count reset to 0. Your score: {user_data['score']}"
    
    def give_save(self, user_id, amount=1):
        """Give saves to a user"""
        user_data = self.get_user_data(user_id)
        user_data['saves'] += amount
        user_data['saves_given'] += amount
        self.save_data()
        self.log_counting_event("save_given", 0, user_id, f"+{amount} saves", f"Total saves: {user_data['saves']}")
        return user_data['saves']
    
    def reset_channel_count(self, channel_id):
        """Reset counting for a channel"""
        old_count = self.channel_counts.get(channel_id, 0)
        self.channel_counts[channel_id] = 0
        self.log_counting_event("channel_reset", channel_id, 0, f"Reset from {old_count} to 0", "")
        return old_count
    
    def set_channel_count(self, channel_id, new_count):
        """Set counting for a channel to a specific number"""
        old_count = self.channel_counts.get(channel_id, 0)
        self.channel_counts[channel_id] = new_count
        self.log_counting_event("channel_set", channel_id, 0, f"Set from {old_count} to {new_count}", "")
        return old_count, new_count
    
    def get_leaderboard(self, limit=10):
        """Get the leaderboard"""
        sorted_users = sorted(self.user_data.items(), key=lambda x: x[1]['score'], reverse=True)
        return sorted_users[:limit]

# Initialize counting bot
counting_bot = CountingBot()


class LevelingBot:
    def __init__(self):
        self.user_data = {}  # {guild_id}_{user_id} -> {'xp': int, 'level': int, 'last_xp_time': timestamp}
        self.xp_cooldowns = {}  # {guild_id}_{user_id} -> last_xp_timestamp
        self.load_data()
    
    def load_data(self):
        """Load leveling data from file"""
        try:
            with open(LEVELING_DATA_FILE, 'r') as f:
                self.user_data = json.load(f)
        except FileNotFoundError:
            self.user_data = {}
        except json.JSONDecodeError:
            self.user_data = {}
    
    def save_data(self):
        """Save leveling data to file"""
        with open(LEVELING_DATA_FILE, 'w') as f:
            json.dump(self.user_data, f, indent=2)
    
    def reload_data(self):
        """Reload leveling data from file"""
        self.load_data()
        return f"✅ Leveling data reloaded successfully! Loaded {len(self.user_data)} user records."
    
    def _make_key(self, guild_id, user_id):
        """Create a guild-scoped user key"""
        return f"{guild_id}_{user_id}"
    
    def get_user_data(self, guild_id, user_id):
        """Get or create user data for a guild"""
        key = self._make_key(guild_id, user_id)
        if key not in self.user_data:
            self.user_data[key] = {'xp': 0, 'level': 1, 'last_xp_time': 0}
        return self.user_data[key]
    
    def calculate_level(self, xp):
        """Calculate level from XP using a formula"""
        # Level = floor(sqrt(xp / 100)) + 1
        # This means: Level 1 = 0-99 XP, Level 2 = 100-399 XP, Level 3 = 400-899 XP, etc.
        import math
        return math.floor(math.sqrt(xp / 100)) + 1
    
    def calculate_xp_for_level(self, level):
        """Calculate minimum XP required for a level"""
        return (level - 1) ** 2 * 100
    
    def add_xp(self, guild_id, user_id, amount):
        """Add XP to a user and check for level up"""
        user_data = self.get_user_data(guild_id, user_id)
        old_level = user_data['level']
        
        user_data['xp'] += amount
        new_level = self.calculate_level(user_data['xp'])
        user_data['level'] = new_level
        
        self.save_data()
        
        # Return level up info
        if new_level > old_level:
            return True, new_level, old_level
        return False, new_level, old_level
    
    def set_xp(self, guild_id, user_id, amount):
        """Set a user's XP to a specific amount"""
        user_data = self.get_user_data(guild_id, user_id)
        old_level = user_data['level']
        
        user_data['xp'] = max(0, amount)  # Ensure XP doesn't go negative
        new_level = self.calculate_level(user_data['xp'])
        user_data['level'] = new_level
        
        self.save_data()
        return new_level, old_level
    
    def can_gain_xp(self, guild_id, user_id):
        """Check if user can gain XP (cooldown check)"""
        key = self._make_key(guild_id, user_id)
        current_time = datetime.now().timestamp()
        
        if key in self.xp_cooldowns:
            last_xp_time = self.xp_cooldowns[key]
            if current_time - last_xp_time < XP_COOLDOWN_SECONDS:
                return False
        
        self.xp_cooldowns[key] = current_time
        return True
    
    def get_leaderboard(self, guild_id, limit=10):
        """Get the leveling leaderboard for a guild"""
        prefix = f"{guild_id}_"
        guild_data = {k: v for k, v in self.user_data.items() if k.startswith(prefix)}
        sorted_users = sorted(guild_data.items(), key=lambda x: (x[1]['level'], x[1]['xp']), reverse=True)
        return sorted_users[:limit]
    
    def format_level_info(self, user_data):
        """Format level information for display"""
        xp = user_data['xp']
        level = user_data['level']
        xp_for_current = self.calculate_xp_for_level(level)
        xp_for_next = self.calculate_xp_for_level(level + 1)
        xp_needed = xp_for_next - xp
        
        return {
            'level': level,
            'xp': xp,
            'xp_needed': xp_needed,
            'progress': xp - xp_for_current,
            'progress_total': xp_for_next - xp_for_current
        }
    
    async def assign_level_role(self, message_or_user, level):
        """Assign role based on level reached"""
        if not message_or_user.guild:
            return
            
        member = message_or_user.author if hasattr(message_or_user, 'author') else message_or_user
        
        # Get guild-specific level roles or fall back to global LEVEL_ROLES
        level_roles = get_guild_setting(message_or_user.guild.id, 'level_roles', LEVEL_ROLES)
        
        # Remove old level roles
        roles_to_remove = []
        for role_level, role_id in level_roles.items():
            if role_id and int(role_level) < level:
                role = message_or_user.guild.get_role(int(role_id) if isinstance(role_id, str) else role_id)
                if role and role in member.roles:
                    roles_to_remove.append(role)
        
        # Add new level role
        new_role_id = level_roles.get(level) or level_roles.get(str(level))
        if new_role_id:
            new_role = message_or_user.guild.get_role(int(new_role_id) if isinstance(new_role_id, str) else new_role_id)
            if new_role:
                try:
                    # Remove old roles first
                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove)
                    
                    # Add new role
                    await member.add_role(new_role)
                    
                    # Log the role assignment
                    embed = discord.Embed(
                        title="🎖️ Level Role Assigned",
                        description=f"{member.mention} reached level {level} and was given the {new_role.name} role!",
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    await send_log(embed, 'role')
                    
                except Exception as e:
                    logger.error(f"Failed to assign level role: {e}")


# Initialize leveling bot
leveling_bot = LevelingBot()

def format_currency(amount):
    return f"${amount:,}"

class EconomyManager:
    def __init__(self):
        self.data = {}
        os.makedirs(ECONOMY_DIR, exist_ok=True)

    def _make_filename(self, guild_id, user_id):
        """Create a guild-scoped filename"""
        return f"{guild_id}_{user_id}.json"

    def get_user_file(self, guild_id, user_id):
        return os.path.join(ECONOMY_DIR, self._make_filename(guild_id, user_id))

    def load_user(self, guild_id, user_id):
        uid = f"{guild_id}_{user_id}"
        file_path = self.get_user_file(guild_id, user_id)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {
            'wallet': 0,
            'bank': 0,
            'last_work': 0,
            'total_lost': 0,
            'total_stolen': 0,
            'blackjack_count': 0,
            'roulette_count': 0,
            'higher_lower_count': 0,
            'crime_count': 0,
            'rob_success': 0,
            'rob_failure': 0,
            'rob_attempts': 0,
            'robbed_count': 0,
            'money_added': 0,
            'money_removed': 0
        }

    def save_user(self, guild_id, user_id, data):
        uid = f"{guild_id}_{user_id}"
        file_path = self.get_user_file(guild_id, user_id)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save economy data for {guild_id}_{user_id}: {e}")

    def get_user(self, guild_id, user_id):
        uid = f"{guild_id}_{user_id}"
        if uid not in self.data:
            self.data[uid] = self.load_user(guild_id, user_id)
        return self.data[uid]

    def get_user_data(self, guild_id, user_id):
        return self.get_user(guild_id, user_id)

    def save_data(self):
        for uid, data in self.data.items():
            # Parse guild_id and user_id from uid
            parts = uid.rsplit('_', 1)
            if len(parts) == 2:
                guild_id, user_id = parts
                self.save_user(guild_id, user_id, data)

    def get_wallet(self, guild_id, user_id):
        return self.get_user(guild_id, user_id)['wallet']

    def get_bank(self, guild_id, user_id):
        return self.get_user(guild_id, user_id)['bank']

    def add_wallet(self, guild_id, user_id, amount):
        user = self.get_user(guild_id, user_id)
        user['wallet'] += amount
        self.save_data()

    def remove_wallet(self, guild_id, user_id, amount):
        user = self.get_user(guild_id, user_id)
        user['wallet'] = max(0, user['wallet'] - amount)
        self.save_data()

    def add_bank(self, guild_id, user_id, amount):
        user = self.get_user(guild_id, user_id)
        user['bank'] += amount
        self.save_data()

    def remove_bank(self, guild_id, user_id, amount):
        user = self.get_user(guild_id, user_id)
        user['bank'] = max(0, user['bank'] - amount)
        self.save_data()

    def can_work(self, guild_id, user_id):
        user = self.get_user(guild_id, user_id)
        return int(datetime.utcnow().timestamp()) - int(user.get('last_work', 0)) >= WORK_COOLDOWN_SECONDS

    def record_work(self, guild_id, user_id):
        amount = random.randint(WORK_REWARD_MIN, WORK_REWARD_MAX)
        user = self.get_user(guild_id, user_id)
        user['wallet'] += amount
        user['last_work'] = int(datetime.utcnow().timestamp())
        self.save_data()
        return amount

    def add_stat(self, guild_id, user_id, key, amount=1):
        user = self.get_user(guild_id, user_id)
        user[key] = user.get(key, 0) + amount
        self.save_data()

    def total_assets(self, guild_id, user_id):
        user = self.get_user(guild_id, user_id)
        return user['wallet'] + user['bank']

    def leaderboard(self, guild_id, limit=10):
        # Load all user files for this guild
        entries = []
        prefix = f"{guild_id}_"
        for filename in os.listdir(ECONOMY_DIR):
            if filename.endswith('.json') and filename.startswith(prefix):
                # Extract user_id from filename like "guild_id_user_id.json"
                parts = filename[:-5].rsplit('_', 1)  # remove .json and split
                if len(parts) == 2:
                    gid, user_id = parts
                    data = self.load_user(gid, user_id)
                    total = data.get('wallet', 0) + data.get('bank', 0)
                    entries.append((user_id, data, total))
        entries.sort(key=lambda x: x[2], reverse=True)
        return entries[:limit]


economy = EconomyManager()


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.danger, custom_id="open_ticket_button")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("Tickets can only be opened inside a server.", ephemeral=True)
            return

        try:
            channel = await create_ticket_channel(interaction, reason="General support")
            await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to create ticket from button: {e}")
            await interaction.response.send_message("❌ Could not create a ticket. Please contact staff.", ephemeral=True)


class GiveawayView(discord.ui.View):
    def __init__(self, prize, winners, required_role, end_time):
        super().__init__(timeout=None)
        self.prize = prize
        self.winners = winners
        self.required_role = required_role
        self.end_time = end_time
        self.participants = set()
        self.message = None

    @discord.ui.button(label="Join Giveaway", style=discord.ButtonStyle.primary, custom_id="giveaway_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.required_role and isinstance(interaction.user, discord.Member):
            if self.required_role not in interaction.user.roles:
                await interaction.response.send_message(
                    f"❌ You need the {self.required_role.mention} role to join this giveaway.",
                    ephemeral=True
                )
                return

        if interaction.user.id in self.participants:
            await interaction.response.send_message("You have already joined this giveaway.", ephemeral=True)
            return

        self.participants.add(interaction.user.id)
        await interaction.response.send_message("✅ You have joined the giveaway!", ephemeral=True)

    async def end_giveaway(self):
        if not self.message:
            return

        self.disable_all_items()
        winners = []
        if self.participants:
            winner_count = min(self.winners, len(self.participants))
            winners = random.sample(list(self.participants), winner_count)
            winner_mentions = []
            for user_id in winners:
                try:
                    user = await bot.fetch_user(user_id)
                    winner_mentions.append(user.mention)
                except Exception:
                    winner_mentions.append(f"<@{user_id}>")
            winners_text = '\n'.join(winner_mentions)
        else:
            winners_text = 'No valid participants.'

        embed = self.message.embeds[0]
        embed.title = '🎉 Giveaway Ended'
        embed.color = discord.Color.dark_gold()
        embed.add_field(name='Winners', value=winners_text, inline=False)
        embed.add_field(name='Status', value='Ended', inline=False)
        embed.set_footer(text=f'Ended at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

        await self.message.edit(embed=embed, view=self)

        if winners:
            await alert_staff(
                title='🎉 Giveaway Ended',
                message=f'Giveaway for {self.prize} has ended. Winners: {winners_text}',
                author=self.message.interaction.user if self.message.interaction else bot.user,
                channel=self.message.channel,
                details=f'Giveaway ended with {len(self.participants)} participants.'
            )
        else:
            await alert_staff(
                title='⚠️ Giveaway Ended',
                message=f'Giveaway for {self.prize} ended with no participants.',
                author=self.message.interaction.user if self.message.interaction else bot.user,
                channel=self.message.channel,
                details=f'No participants joined.'
            )




def schedule_giveaway_end(view):
    async def runner():
        now = datetime.utcnow()
        delay = (view.end_time - now).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
        await view.end_giveaway()
    asyncio.create_task(runner())


@bot.event
async def on_ready():
    """Bot ready event"""
    logger.info(f'{bot.user} has connected to Discord!')
    print(f'Logged in as {bot.user}')
    
    # Load games cog
    if not hasattr(bot, '_games_cog_loaded'):
        try:
            games_module = importlib.import_module('games')
            await games_module.setup(bot, economy)
            logger.info('Games cog loaded successfully')
            bot._games_cog_loaded = True
        except Exception as e:
            logger.error(f'Failed to load games cog: {e}')
            import traceback
            traceback.print_exc()
    
    logger.info(f'Starting ready handler with application_id={bot.application_id}')
    try:
        await bot.tree.sync()
        logger.info('Slash commands synced successfully globally')
    except Exception as e:
        logger.error(f'Failed to sync slash commands: {e}')
    
    if not hasattr(bot, '_status_task_started') or not bot._status_task_started:
        bot.loop.create_task(update_status_loop())
        bot._status_task_started = True

    if not hasattr(bot, '_verification_server_started') or not bot._verification_server_started:
        bot.loop.create_task(start_verification_server())
        bot._verification_server_started = True
    
    embed = discord.Embed(
        title="🤖 Bot Started",
        description=f"Logger bot is online",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Timestamp: {get_timestamp()}")
    await send_log(embed, 'message')

def is_counting_message_content(content: str) -> bool:
    """Check whether a message content is a counting-style numeric/math message."""
    if not content:
        return False
    return bool(re.match(r'^[0-9+\-*/().\s]+$', content)) and not content.startswith('!')


def parse_counting_value(content: str):
    """Parse a counting message into an integer if possible."""
    try:
        return counting_bot.evaluate_math_expression(content.strip())
    except Exception:
        return None


@bot.event
async def on_message(message):
    """Log messages and handle counting game"""
    if message.author == bot.user:
        return

    # Log all server messages to server-specific JSON files
    if message.guild:
        try:
            log_message(message.guild.id, message)
        except Exception as e:
            logger.error(f"Failed to log message: {e}")

    # Handle crosschat
    if CROSSCHAT_CHANNEL_ID and message.channel.id == CROSSCHAT_CHANNEL_ID and message.guild:
        discord_username = message.author.display_name
        content = message.content.strip()
        if content:
            crosschat_messages.append({
                'username': discord_username,
                'message': content,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })

    # Moderation checks
    if message.guild and message.content:
        content = message.content.strip()
        word_count = len(re.findall(r"\w+", content))

        if contains_bad_word(content, SLUR_WORDS):
            suppressed_message_delete_ids.add(message.id)
            try:
                await message.delete()
            except Exception:
                pass

            try:
                await message.author.send(
                    "Please stop using hateful or slur language. Your message has been removed and staff have been notified."
                )
            except Exception:
                pass

            if isinstance(message.author, discord.Member):
                try:
                    timeout_until = datetime.utcnow() + timedelta(minutes=10)
                    await message.author.timeout(timeout_until, reason='Used a slur')
                except Exception as e:
                    logger.error(f"Failed to timeout user for slur: {e}")

            await alert_staff(
                title='🚨 Slur detected',
                message='A user used a slur and was timed out.',
                author=message.author,
                channel=message.channel,
                details=f'Message content: {content}'
            )
            return

        if is_spamming(message.author.id):
            suppressed_message_delete_ids.add(message.id)
            try:
                await message.delete()
            except Exception:
                pass

            try:
                await message.author.send(
                    "Please stop spamming. Your recent messages have been removed and staff have been notified."
                )
            except Exception:
                pass

            if isinstance(message.author, discord.Member):
                try:
                    timeout_until = datetime.utcnow() + timedelta(minutes=SPAM_TIMEOUT_MINUTES)
                    await message.author.timeout(timeout_until, reason='Spamming chat')
                except Exception as e:
                    logger.error(f"Failed to timeout user for spam: {e}")

            await alert_staff(
                title='🚨 Spam detected',
                message='A user is spamming messages and was timed out.',
                author=message.author,
                channel=message.channel,
                details=f'Message content: {content}'
            )
            return

        if len(content) > MAX_MESSAGE_LENGTH or word_count > MAX_WORDS_PER_MESSAGE:
            suppressed_message_delete_ids.add(message.id)
            try:
                await message.delete()
            except Exception:
                pass

            try:
                await message.author.send(
                    "Please avoid sending very large messages. Your message has been removed and staff have been notified."
                )
            except Exception:
                pass

            await alert_staff(
                title='⚠️ Large message detected',
                message='A user sent an overly large message.',
                author=message.author,
                channel=message.channel,
                details=f'Message length: {len(content)}, word count: {word_count}'
            )
            return

        if contains_bad_word(content, SWEAR_WORDS):
            suppressed_message_delete_ids.add(message.id)
            try:
                await message.delete()
            except Exception:
                pass

            try:
                await message.author.send(
                    "Please do not swear in chat. Your message has been removed and staff have been notified."
                )
            except Exception:
                pass

            await alert_staff(
                title='⚠️ Swear word detected',
                message='A user used a swear word and the message was deleted.',
                author=message.author,
                channel=message.channel,
                details=f'Message content: {content}'
            )
            return

    # Handle leveling XP for messages
    if message.guild and not message.author.bot:
        if leveling_bot.can_gain_xp(message.guild.id, message.author.id):
            leveled_up, new_level, old_level = leveling_bot.add_xp(message.guild.id, message.author.id, XP_PER_MESSAGE)
            
            # Check for role rewards
            if leveled_up:
                await leveling_bot.assign_level_role(message, new_level)
                
                # Send level up message
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"Congratulations {message.author.mention}! You reached **Level {new_level}**!",
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="Previous Level", value=old_level, inline=True)
                embed.add_field(name="New Level", value=new_level, inline=True)
                embed.set_footer(text=f"Keep chatting to level up more!")
                
                try:
                    await safe_channel_send(message.channel, embed=embed)
                except Exception:
                    pass

    # Handle counting game
    message_content = message.content.strip()
    counting_channel_active = False
    if message.guild:
        configured_counting_channel = get_server_setting(message.guild.id, 'counting_channel_id')
        if configured_counting_channel:
            counting_channel_active = message.channel.id == int(configured_counting_channel)
        elif COUNTING_CHANNEL_ID:
            counting_channel_active = message.channel.id == COUNTING_CHANNEL_ID
        else:
            # If no counting channel is configured, count in any numeric/math message channel.
            counting_channel_active = bool(re.match(r'^[0-9+\-*/().\s]+$', message_content)) and not message_content.startswith('!')

    if counting_channel_active and counting_bot.is_counting_message(message_content):
        success, response = counting_bot.process_counting_message(
            message.channel.id,
            message.author.id,
            message_content
        )
        
        if success is None:
            # Not a counting message, continue with normal processing (logging)
            pass
        elif success:
            try:
                await message.add_reaction('✅')
            except Exception:
                pass
            return
        elif response:  # Only respond if it's a counting-related error message
            embed = discord.Embed(
                description=response,
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Counted by {message.author.display_name}")
            await safe_channel_send(message.channel, embed=embed)

            try:
                await message.add_reaction('❌')
            except Exception:
                pass
            
            # Don't log counting messages to avoid spam
            return
    
    # Only log in guilds
    if message.guild:
        # Skip logging bot commands (but still process them)
        if message.content.startswith('!'):
            pass  # Commands will be processed at the end
        else:
            embed = discord.Embed(
                title="💬 Message Sent",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Author", value=f"{message.author} ({message.author.id})", inline=False)
            embed.add_field(name="Channel", value=f"{message.channel.mention}", inline=False)
            embed.add_field(name="Message", value=message.content[:1024], inline=False)
            
            if message.attachments:
                attachment_info = "\n".join([f"- {att.filename}" for att in message.attachments])
                embed.add_field(name="Attachments", value=attachment_info, inline=False)
            
            embed.set_footer(text=f"Guild: {message.guild.name} | {get_timestamp()}")
            embed.set_thumbnail(url=message.author.display_avatar.url)
            
            await send_log(embed, 'message')
    
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    """Log member joins"""
    embed = discord.Embed(
        title="👋 Member Joined",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at), inline=False)
    embed.add_field(name="Guild", value=member.guild.name, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Total Members: {member.guild.member_count} | {get_timestamp()}")
    
    await send_log(embed, 'member')

    welcome_channel_id = welcome_channel_settings.get(str(member.guild.id))
    if welcome_channel_id:
        welcome_channel = member.guild.get_channel(welcome_channel_id)
        if welcome_channel:
            welcome_embed = discord.Embed(
                title="👋 Welcome!",
                description=f"Welcome to {member.guild.name}, {member.mention}!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            welcome_embed.set_thumbnail(url=member.display_avatar.url)
            welcome_embed.set_footer(text=f"Member #{member.guild.member_count}")
            try:
                await welcome_channel.send(embed=welcome_embed)
            except Exception as e:
                logger.error(f"Failed to send welcome message in channel {welcome_channel_id}: {e}")

    # Assign auto roles on join
    if AUTO_ROLE_IDS:
        roles_to_assign = [role for role in (member.guild.get_role(role_id) for role_id in AUTO_ROLE_IDS) if role]
        if roles_to_assign:
            try:
                await member.add_roles(*roles_to_assign, reason='Auto role on join')
            except Exception as e:
                logger.error(f"Failed to assign auto roles on join for {member}: {e}")

@bot.event
async def on_member_remove(member):
    """Log member leaves"""
    embed = discord.Embed(
        title="👋 Member Left",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Member", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Joined At", value=discord.utils.format_dt(member.joined_at), inline=False)
    embed.add_field(name="Guild", value=member.guild.name, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Total Members: {member.guild.member_count} | {get_timestamp()}")
    
    await send_log(embed, 'member')

@bot.event
async def on_member_update(before, after):
    """Log member updates (nickname, roles, etc)"""
    changes = []
    embed = discord.Embed(
        title="👤 Member Updated",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Member", value=f"{after} ({after.id})", inline=False)

    if before.roles != after.roles:
        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)
        
        if added_roles:
            role_names = ", ".join([role.mention for role in added_roles])
            embed.add_field(name="Roles Added", value=role_names, inline=False)
            changes.append('roles')
        
        if removed_roles:
            role_names = ", ".join([role.mention for role in removed_roles])
            embed.add_field(name="Roles Removed", value=role_names, inline=False)
            changes.append('roles')

    if before.nick != after.nick:
        embed.add_field(name="Old Nickname", value=before.nick or "None", inline=False)
        embed.add_field(name="New Nickname", value=after.nick or "None", inline=False)
        changes.append('nickname')

    if changes:
        embed.set_footer(text=f"Guild: {after.guild.name} | {get_timestamp()}")
        embed.set_thumbnail(url=after.display_avatar.url)
        await send_log(embed, 'member')

@bot.event
async def on_guild_channel_create(channel):
    """Log channel creation"""
    embed = discord.Embed(
        title="➕ Channel Created",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Channel", value=channel.mention, inline=False)
    embed.add_field(name="Channel Type", value=str(channel.type), inline=False)
    embed.add_field(name="Channel ID", value=channel.id, inline=False)
    embed.set_footer(text=f"Guild: {channel.guild.name} | {get_timestamp()}")
    
    await send_log(embed, 'channel')

@bot.event
async def on_guild_channel_delete(channel):
    """Log channel deletion and detect rapid deletion attacks."""
    guild = channel.guild
    actor = None
    if guild:
        actor = await find_channel_delete_actor(guild, channel)
        if actor:
            delete_count = record_channel_deletion(guild.id, actor.id)
            if delete_count >= ANTI_NUKE_CHANNEL_THRESHOLD:
                await handle_nuke_detected(channel, actor, delete_count)

    embed = discord.Embed(
        title="➖ Channel Deleted",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Channel Name", value=channel.name, inline=False)
    embed.add_field(name="Channel Type", value=str(channel.type), inline=False)
    embed.add_field(name="Channel ID", value=channel.id, inline=False)
    if actor:
        embed.add_field(name="Deleted By", value=f"{actor} ({actor.id})", inline=False)
    embed.set_footer(text=f"Guild: {channel.guild.name} | {get_timestamp()}")
    
    await send_log(embed, 'channel')

@bot.event
async def on_guild_role_create(role):
    """Log role creation"""
    embed = discord.Embed(
        title="➕ Role Created",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Role", value=role.mention, inline=False)
    embed.add_field(name="Role ID", value=role.id, inline=False)
    embed.add_field(name="Color", value=str(role.color), inline=False)
    embed.set_footer(text=f"Guild: {role.guild.name} | {get_timestamp()}")
    
    await send_log(embed, 'role')

@bot.event
async def on_guild_role_delete(role):
    """Log role deletion"""
    embed = discord.Embed(
        title="➖ Role Deleted",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Role Name", value=role.name, inline=False)
    embed.add_field(name="Role ID", value=role.id, inline=False)
    embed.set_footer(text=f"Guild: {role.guild.name} | {get_timestamp()}")
    
    await send_log(embed, 'role')

@bot.event
async def on_message_delete(message):
    """Log deleted messages"""
    if message.author == bot.user:
        return

    if message.id in suppressed_message_delete_ids:
        suppressed_message_delete_ids.discard(message.id)
        return

    content = (message.content or '').strip()
    counting_channel_active = False
    if message.guild and content and is_counting_message_content(content):
        if COUNTING_CHANNEL_ID:
            counting_channel_active = message.channel.id == COUNTING_CHANNEL_ID
        else:
            counting_channel_active = True

    if counting_channel_active:
        parsed_value = parse_counting_value(content)
        if parsed_value is not None:
            try:
                await message.channel.send(f"🗑️ {message.author.display_name} deleted their number {parsed_value}")
            except Exception:
                pass

    if message.guild:
        channel_id = str(message.channel.id)
        sticky = sticky_messages.get(channel_id)
        if sticky and sticky.get('message_id') == message.id:
            try:
                restored = await message.channel.send(sticky['content'])
                await restored.pin(reason='Restored sticky message after deletion')
                sticky_messages[channel_id]['message_id'] = restored.id
                save_sticky_messages()
            except Exception as e:
                logger.error(f"Failed to restore sticky message in channel {message.channel.id}: {e}")

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.dark_red(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Author", value=f"{message.author} ({message.author.id})", inline=False)
        embed.add_field(name="Channel", value=f"{message.channel.mention}", inline=False)
        embed.add_field(name="Message", value=message.content[:1024] or "[No content]", inline=False)
        embed.set_footer(text=f"Guild: {message.guild.name} | {get_timestamp()}")
        embed.set_thumbnail(url=message.author.display_avatar.url)
        
        await send_log(embed, 'message')
@bot.event
async def on_message_edit(before, after):
    """Log edited messages"""
    if after.author == bot.user:
        return
    
    if before.content != after.content and after.guild:
        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Author", value=f"{after.author} ({after.author.id})", inline=False)
        embed.add_field(name="Channel", value=f"{after.channel.mention}", inline=False)
        embed.add_field(name="Before", value=before.content[:1024] or "[No content]", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "[No content]", inline=False)
        embed.set_footer(text=f"Guild: {after.guild.name} | {get_timestamp()}")
        embed.set_thumbnail(url=after.author.display_avatar.url)
        
        await send_log(embed, 'message')

@bot.event
async def on_reaction_add(reaction, user):
    """Handle leveling XP for reactions"""
    if user.bot:
        return
    
    # Only give XP for reactions on messages in guilds
    if reaction.message.guild and leveling_bot.can_gain_xp(reaction.message.guild.id, user.id):
        leveled_up, new_level, old_level = leveling_bot.add_xp(reaction.message.guild.id, user.id, XP_PER_REACTION)
        
        # Check for role rewards
        if leveled_up:
            await leveling_bot.assign_level_role(reaction.message, new_level)
            
            # Send level up message
            embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"Congratulations {user.mention}! You reached **Level {new_level}**!",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Previous Level", value=old_level, inline=True)
            embed.add_field(name="New Level", value=new_level, inline=True)
            embed.set_footer(text=f"Keep reacting to level up more!")
            
            try:
                await safe_channel_send(reaction.message.channel, embed=embed)
            except Exception:
                pass


def get_reaction_role_message_map(message_id, emoji_key):
    return reaction_roles.get(str(message_id), {}).get(emoji_key)


@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id is None or payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            return

    channel = bot.get_channel(payload.channel_id)
    channel_text = channel.mention if channel else f"<#{payload.channel_id}>"
    embed = discord.Embed(
        title="😊 Emoji Reaction Added",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Emoji", value=str(payload.emoji), inline=False)
    embed.add_field(name="Channel", value=channel_text, inline=False)
    embed.add_field(name="Message ID", value=str(payload.message_id), inline=False)
    embed.set_footer(text=f"Guild: {guild.name} | {get_timestamp()}")
    await send_log(embed, 'emoji')

    emoji_key = normalize_emoji(payload.emoji)
    role_id = get_reaction_role_message_map(payload.message_id, emoji_key)
    if not role_id:
        return

    role = guild.get_role(role_id)
    if role is None:
        return

    member = guild.get_member(payload.user_id)
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            return

    role = guild.get_role(role_id)
    if role is None:
        return

    try:
        await member.add_roles(role, reason='Reaction role added')
    except Exception as e:
        logger.error(f"Failed to add reaction role: {e}")


@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id is None or payload.user_id == bot.user.id:
        return

    emoji_key = normalize_emoji(payload.emoji)
    role_id = get_reaction_role_message_map(payload.message_id, emoji_key)
    if not role_id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except Exception:
            return

    role = guild.get_role(role_id)
    if role is None:
        return

    try:
        await member.remove_roles(role, reason='Reaction role removed')
    except Exception as e:
        logger.error(f"Failed to remove reaction role: {e}")


@commands.guild_only()
@bot.command(name='ping', aliases=['p'])
async def ping(ctx):
    """Ping command"""
    await ctx.send(f'🏓 Pong! {round(bot.latency * 1000)}ms')

@commands.guild_only()
@bot.command(name='link_minecraft', aliases=['linkmc', 'verifymc'])
async def link_minecraft(ctx, minecraft_username: str):
    """Start Minecraft account verification for your Discord account."""
    if not minecraft_username:
        await ctx.send("❌ Please provide your Minecraft username.")
        return

    code = create_minecraft_verification(ctx.author.id, minecraft_username)
    await ctx.send(
        f"✅ {ctx.author.mention}, a verification code has been generated for `{minecraft_username}`."
        f"\n\nPlease paste the following code in your Minecraft account's chat or share it with a server admin so they can confirm the account ownership:\n`{code}`"
        f"\n\nThen run `!confirm_minecraft {code}` in Discord to complete the link. The code expires in 1 hour."
    )


@commands.guild_only()
@bot.command(name='confirm_minecraft', aliases=['confirmmc', 'verifyminecraft'])
async def confirm_minecraft(ctx, code: str):
    """Confirm a pending Minecraft account link using a verification code."""
    if not code:
        await ctx.send("❌ Please provide your verification code.")
        return

    pending = get_pending_minecraft_verification(ctx.author.id)
    if not pending:
        await ctx.send("❌ You do not have a pending Minecraft verification request. Use `!link_minecraft <username>` first.")
        return

    if pending.get('code') != code:
        await ctx.send("❌ That verification code does not match. Please use the code shown by `!link_minecraft`.")
        return

    set_minecraft_link(ctx.author.id, pending['minecraft_username'])
    remove_pending_minecraft_verification(ctx.author.id)
    await ctx.send(f"✅ {ctx.author.mention}, your Discord account is now verified and linked to Minecraft username `{pending['minecraft_username']}`.")


@commands.guild_only()
@bot.command(name='cancel_minecraft', aliases=['cancelmc'])
async def cancel_minecraft(ctx):
    """Cancel a pending Minecraft verification request."""
    if remove_pending_minecraft_verification(ctx.author.id):
        await ctx.send(f"✅ {ctx.author.mention}, your pending Minecraft verification request has been cancelled.")
    else:
        await ctx.send("❌ You do not have a pending Minecraft verification request to cancel.")


@commands.guild_only()
@bot.command(name='unlink_minecraft', aliases=['unlinkmc'])
async def unlink_minecraft(ctx):
    """Remove your linked Minecraft account."""
    if remove_minecraft_link(ctx.author.id):
        await ctx.send(f"✅ {ctx.author.mention}, your Minecraft account link has been removed.")
    else:
        await ctx.send("❌ You don't have a linked Minecraft account.")


@commands.guild_only()
@bot.command(name='minecraft', aliases=['mcinfo'])
async def minecraft_info(ctx, member: discord.Member = None):
    """Show the linked Minecraft account for a user."""
    target = member or ctx.author
    link = get_minecraft_link(target.id)
    if link:
        await ctx.send(f"🔗 {target.display_name} is linked to Minecraft username `{link}`.")
    else:
        if member:
            await ctx.send(f"❌ {target.display_name} does not have a linked Minecraft account.")
        else:
            await ctx.send("❌ You do not have a linked Minecraft account.")


@commands.guild_only()
@bot.command(name='kudos', aliases=['kudo', 'rep', 'reputation'])
async def give_kudos_cmd(ctx, member: discord.Member, *, reason: str = None):
    """Give kudos to a member to recognize their contribution"""
    if member == ctx.author:
        await ctx.send("❌ You can't give kudos to yourself!")
        return
    
    if member.bot:
        await ctx.send("❌ You can't give kudos to a bot!")
        return
    
    give_kudos(ctx.author.id, member.id, reason)
    
    embed = discord.Embed(
        title="🏆 Kudos Given!",
        description=f"{ctx.author.mention} gave kudos to {member.mention}",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"{member.display_name} now has {get_kudos(member.id)} kudos!")
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='myreputation', aliases=['myrep', 'mykudos'])
async def my_reputation(ctx, member: discord.Member = None):
    """Check your or someone's reputation/kudos count"""
    target = member or ctx.author
    kudos_count = get_kudos(target.id)
    details = get_kudos_details(target.id)
    
    embed = discord.Embed(
        title="🏆 Reputation",
        description=f"{target.display_name}'s Kudos Score",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Total Kudos", value=str(kudos_count), inline=True)
    
    if details.get('from'):
        top_givers = sorted(details['from'].items(), key=lambda x: x[1]['count'], reverse=True)[:3]
        givers_text = "\n".join([f"<@{gid}>: {gdata['count']}" for gid, gdata in top_givers])
        embed.add_field(name="Top Givers", value=givers_text, inline=True)
    
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='kudosleaderboard', aliases=['repleaderboard', 'repboard', 'kudoslb'])
async def kudos_leaderboard(ctx, limit: int = 10):
    """Show the kudos leaderboard"""
    if limit > 25:
        limit = 25
    if limit < 1:
        limit = 10
    
    leaderboard = get_kudos_leaderboard(limit)
    
    if not leaderboard:
        await ctx.send("❌ No kudos have been given yet!")
        return
    
    embed = discord.Embed(
        title="🏆 Kudos Leaderboard",
        description="Top community contributors",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    medals = ['🥇', '🥈', '🥉']
    for idx, (user_id, count) in enumerate(leaderboard):
        medal = medals[idx] if idx < 3 else f"{idx+1}."
        embed.add_field(name=f"{medal} <@{user_id}>", value=f"{count} kudos", inline=False)
    
    await ctx.send(embed=embed)


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='award_kudos', aliases=['awardkudos', 'giverep'])
async def award_kudos_cmd(ctx, member: discord.Member, amount: int = 1, *, reason: str = None):
    """Award kudos to a member (Admin only)"""
    if amount <= 0:
        await ctx.send("❌ Amount must be positive!")
        return
    
    award_kudos(member.id, amount)
    
    embed = discord.Embed(
        title="🏆 Kudos Awarded",
        description=f"{ctx.author.mention} awarded {amount} kudos to {member.mention}",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"{member.display_name} now has {get_kudos(member.id)} kudos!")
    await ctx.send(embed=embed)


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='remove_kudos', aliases=['removekudos', 'removerep'])
async def remove_kudos_cmd(ctx, member: discord.Member, amount: int = 1):
    """Remove kudos from a member (Admin only)"""
    if amount <= 0:
        await ctx.send("❌ Amount must be positive!")
        return
    
    remove_kudos(member.id, amount)
    
    embed = discord.Embed(
        title="🏆 Kudos Removed",
        description=f"{ctx.author.mention} removed {amount} kudos from {member.mention}",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"{member.display_name} now has {get_kudos(member.id)} kudos!")
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='commands', aliases=['cmds', 'help'])
async def commands_list(ctx):
    """Display help"""
    embed = discord.Embed(
        title="📚 Logger Bot Commands",
        description="Available commands:",
        color=discord.Color.blue()
    )
    embed.add_field(name="!ping", value="Check bot latency", inline=False)
    embed.add_field(name="!commands", value="Show this help message", inline=False)
    embed.add_field(name="!status", value="Show logging status", inline=False)
    embed.add_field(name="!stats", value="Show logging statistics", inline=False)
    embed.add_field(name="!ticket <reason>", value="Open a new ticket", inline=False)
    embed.add_field(name="!ticket close", value="Close the current ticket channel", inline=False)
    embed.add_field(name="!toggle", value="Toggle logging on/off (Admin only)", inline=False)
    embed.add_field(name="!log <type> #channel", value="Set a log channel for events (Admin only)", inline=False)
    embed.add_field(name="!moderationlog #channel", value="Set moderation alert channel (Admin only)", inline=False)
    embed.add_field(name="!log emoji_log #channel", value="Set emoji reaction logging channel (Admin only)", inline=False)
    embed.add_field(name="!log command_log #channel", value="Set command usage logging channel (Admin only)", inline=False)
    embed.add_field(name="!config [feature]" , value="Configure server features (Admin only)", inline=False)
    embed.add_field(name="!warnings [@user]", value="View warnings for you or a member", inline=False)
    embed.add_field(name="!suggest <content>", value="Suggest a feature or improvement", inline=False)
    embed.add_field(name="!selfrolesinfo", value="Show available self-roles", inline=False)
    embed.add_field(name="!addrole <role> <emoji>", value="Add a role to self-roles (Admin only)", inline=False)
    embed.add_field(name="!removerole <emoji>", value="Remove a role from self-roles (Admin only)", inline=False)
    embed.add_field(name="!messagelog [limit]", value="View recent messages logged for this server (Admin only)", inline=False)
    embed.add_field(name="!logstats", value="Show message log statistics (Admin only)", inline=False)
    embed.add_field(name="!clearlog confirm", value="Clear all message logs for this server (Admin only)", inline=False)
    embed.add_field(name="!clear_warnings <@user>", value="Clear all warnings for a member (Admin only)", inline=False)
    embed.add_field(name="!role_all <role> [exclude_bots]", value="Give a role to everyone, optionally excluding bots", inline=False)
    embed.add_field(name="!clear <type> confirm", value="Clear log channels (Manage Messages permission required)", inline=False)
    embed.add_field(name="!counting_status", value="Show current counting status", inline=False)
    embed.add_field(name="!reload_counting", value="Reload counting data from file (Admin only)", inline=False)
    embed.add_field(name="!reset_counting", value="Reset counting for this channel (Admin only)", inline=False)
    embed.add_field(name="!set_count <number>", value="Set counting number for this channel (Admin only)", inline=False)
    embed.add_field(name="!set_welcome_channel #channel", value="Set the welcome channel for this server (Admin only)", inline=False)
    embed.add_field(name="!score [@user]", value="Show counting score and stats", inline=False)
    embed.add_field(name="!leaderboard level/counting [limit]", value="Show leveling or counting leaderboard", inline=False)
    embed.add_field(name="!level [@user]", value="Show your level or another member's level", inline=False)
    embed.add_field(name="!give_save <@user> [amount]", value="Give saves to a user (Admin only)", inline=False)
    embed.add_field(name="!xp set <@user> <amount>", value="Set a user's XP (Admin only)", inline=False)
    embed.add_field(name="!xp add <@user> <amount>", value="Add XP to a user (Admin only)", inline=False)
    embed.add_field(name="!xp remove <@user> <amount>", value="Remove XP from a user (Admin only)", inline=False)
    embed.add_field(name="/stickymessage <message> [channel]", value="Create or update a sticky message in a channel", inline=False)
    embed.add_field(name="!counting_help", value="Show counting game help", inline=False)
    embed.add_field(name="!trivia", value="Start a multiplayer trivia round", inline=False)
    embed.add_field(name="/trivia", value="Start a multiplayer trivia round", inline=False)
    embed.add_field(name="!hangman", value="Start a multiplayer hangman game", inline=False)
    embed.add_field(name="/hangman", value="Start a multiplayer hangman game", inline=False)
    embed.add_field(name="!guess <letter|word>", value="Guess in an active hangman game", inline=False)
    embed.add_field(name="/guess <letter|word>", value="Guess in an active hangman game", inline=False)
    embed.add_field(name="!endhangman", value="End the current hangman game", inline=False)
    embed.add_field(name="/endhangman", value="End the current hangman game", inline=False)
    embed.add_field(name="!link_minecraft <username>", value="Start Minecraft account verification", inline=False)
    embed.add_field(name="!cancel_minecraft", value="Cancel a pending Minecraft verification request", inline=False)
    embed.add_field(name="!unlink_minecraft", value="Unlink your Minecraft account", inline=False)
    embed.add_field(name="!minecraft [@user]", value="Show a user's linked Minecraft account", inline=False)
    embed.add_field(name="!kudos <@user> [reason]", value="Give kudos to recognize someone", inline=False)
    embed.add_field(name="!myreputation [@user]", value="Check your or someone's kudos score", inline=False)
    embed.add_field(name="!kudosleaderboard [limit]", value="Show top contributors", inline=False)
    embed.add_field(name="!award_kudos <@user> <amount> [reason]", value="Award kudos to a member (Admin only)", inline=False)
    embed.add_field(name="!remove_kudos <@user> <amount>", value="Remove kudos from a member (Admin only)", inline=False)
    embed.add_field(name="/work", value="Work every 30 seconds to earn money", inline=False)
    embed.add_field(name="/blackjack <amount>", value="Bet on blackjack with HIT/STAND/DOUBLE buttons", inline=False)
    embed.add_field(name="/roulette <red|black|green|odd|even|0-36> <amount>", value="Bet on roulette", inline=False)
    embed.add_field(name="/higher_or_lower <higher|lower> <amount>", value="Higher or lower bet", inline=False)
    embed.add_field(name="/higherlower <higher|lower> <amount>", value="Higher or lower alias", inline=False)
    embed.add_field(name="/crime", value="Attempt a crime for a chance to win or lose money", inline=False)
    embed.add_field(name="/deposit <amount>", value="Deposit money into your bank", inline=False)
    embed.add_field(name="/withdraw <amount>", value="Withdraw money from your bank", inline=False)
    embed.add_field(name="/rob <@user>", value="Steal from another user's wallet", inline=False)
    embed.add_field(name="/pay <@user> <amount>", value="Send money to another user", inline=False)
    embed.add_field(name="/bal", value="Show wallet and bank balance", inline=False)
    embed.add_field(name="/lb", value="Show economy leaderboard", inline=False)
    embed.add_field(name="/leaderboards [type] [limit]", value="Show all leaderboards or select type (level/counting/economy)", inline=False)
    embed.add_field(name="!dm <@members> <message>", value="Send DM to members (Admin only)", inline=False)
    embed.add_field(name="!announcement <#channel> <message>", value="Send announcement to channel (Admin only)", inline=False)
    embed.add_field(name="!say <#channel> <message>", value="Send a plain message to a channel (Admin only)", inline=False)
    embed.add_field(name="/announcement <channel> <message>", value="Send announcement to channel (Admin only)", inline=False)
    embed.add_field(name="/say <channel> <message>", value="Send a plain message to a channel (Admin only)", inline=False)
    embed.add_field(name="!embed <title> [color] [#channel] <description>", value="Create and send embed (Admin only)", inline=False)
    embed.add_field(name="/embed <title> <description> [color] [channel]", value="Create and send embed (Admin only)", inline=False)
    embed.add_field(name="/broadcast <message> [role]", value="DM everyone or a role with a message (Admin only)", inline=False)
    await ctx.send(embed=embed)


@bot.tree.command(name='commands', description='Show available commands')
async def slash_commands(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 Logger Bot Commands",
        description="Available commands:",
        color=discord.Color.blue()
    )
    embed.add_field(name="/commands", value="Show this help message", inline=False)
    embed.add_field(name="!commands", value="Show this help message", inline=False)
    embed.add_field(name="!status", value="Show logging status", inline=False)
    embed.add_field(name="!stats", value="Show logging statistics", inline=False)
    embed.add_field(name="!ticket <reason>", value="Open a new ticket", inline=False)
    embed.add_field(name="!ticket close", value="Close the current ticket channel", inline=False)
    embed.add_field(name="!ticketpanel", value="Post a ticket panel embed with a button", inline=False)
    embed.add_field(name="!toggle", value="Toggle logging on/off (Admin only)", inline=False)
    embed.add_field(name="!role_all <role> [exclude_bots]", value="Give a role to everyone, optionally excluding bots", inline=False)
    embed.add_field(name="!clear <type> confirm", value="Clear log channels (Admin only)", inline=False)
    embed.add_field(name="/score [@user]", value="Show counting score and stats", inline=False)
    embed.add_field(name="/count_leaderboard [limit]", value="Show counting leaderboard", inline=False)
    embed.add_field(name="/level [@user]", value="Show your level or another member's level", inline=False)
    embed.add_field(name="/level_leaderboard [limit]", value="Show leveling leaderboard", inline=False)
    embed.add_field(name="/reset reload", value="Reload counting data from file (Admin only)", inline=False)
    embed.add_field(name="/set_count <number>", value="Set counting number for this channel (Admin only)", inline=False)
    embed.add_field(name="/set_welcome_channel <channel>", value="Set the welcome channel for this server (Admin only)", inline=False)
    embed.add_field(name="/stickymessage <message> [channel]", value="Create or update a sticky message in a channel", inline=False)
    embed.add_field(name="/log <type> <channel>", value="Set a log channel for events (Admin only)", inline=False)
    embed.add_field(name="/moderationlog <channel>", value="Set the moderation alert channel (Admin only)", inline=False)
    embed.add_field(name="/log emoji_log <channel>", value="Set emoji reaction logging channel (Admin only)", inline=False)
    embed.add_field(name="/log command_log <channel>", value="Set command usage logging channel (Admin only)", inline=False)
    embed.add_field(name="/timeout <member> <duration> [reason]", value="Temporarily timeout a member (Admin only)", inline=False)
    embed.add_field(name="/warn <member> [reason]", value="Warn a member and DM them (Manage Members permission)", inline=False)
    embed.add_field(name="/warnings [@user]", value="View warnings for you or a member", inline=False)
    embed.add_field(name="/suggest <content>", value="Suggest a feature or improvement", inline=False)
    embed.add_field(name="/kick <member> [reason]", value="Kick a member from the server (Manage Members permission)", inline=False)
    embed.add_field(name="/ban <member> <duration> [reason]", value="Temporarily ban a member (Manage Members permission)", inline=False)
    embed.add_field(name="/mute <member> <duration> [reason]", value="Mute a member (Manage Members permission)", inline=False)
    embed.add_field(name="/info user", value="Show moderation history for a user", inline=False)
    embed.add_field(name="/xp set <@user> <amount>", value="Set a user's XP (Admin only)", inline=False)
    embed.add_field(name="/xp add <@user> <amount>", value="Add XP to a user (Admin only)", inline=False)
    embed.add_field(name="/xp remove <@user> <amount>", value="Remove XP from a user (Admin only)", inline=False)
    embed.add_field(name="/give_save <@user> [amount]", value="Give saves to a user (Admin only)", inline=False)
    embed.add_field(name="!trivia", value="Start a multiplayer trivia round", inline=False)
    embed.add_field(name="/trivia", value="Start a multiplayer trivia round", inline=False)
    embed.add_field(name="!hangman", value="Start a multiplayer hangman game", inline=False)
    embed.add_field(name="/hangman", value="Start a multiplayer hangman game", inline=False)
    embed.add_field(name="!guess <letter|word>", value="Guess in an active hangman game", inline=False)
    embed.add_field(name="/guess <letter|word>", value="Guess in an active hangman game", inline=False)
    embed.add_field(name="!endhangman", value="End the current hangman game", inline=False)
    embed.add_field(name="/endhangman", value="End the current hangman game", inline=False)
    embed.add_field(name="/work", value="Work every 30 seconds to earn money", inline=False)
    embed.add_field(name="/blackjack <amount>", value="Bet on blackjack with HIT/STAND/DOUBLE buttons", inline=False)
    embed.add_field(name="/roulette <red|black|green|odd|even|0-36> <amount>", value="Bet on roulette", inline=False)
    embed.add_field(name="/higher_or_lower <higher|lower> <amount>", value="Higher or lower bet", inline=False)
    embed.add_field(name="/higherlower <higher|lower> <amount>", value="Higher or lower alias", inline=False)
    embed.add_field(name="/crime", value="Attempt a crime for a chance to win or lose money", inline=False)
    embed.add_field(name="/deposit <amount>", value="Deposit money into your bank", inline=False)
    embed.add_field(name="/withdraw <amount>", value="Withdraw money from your bank", inline=False)
    embed.add_field(name="/rob <@user>", value="Steal from another user's wallet", inline=False)
    embed.add_field(name="/pay <@user> <amount>", value="Send money to another user", inline=False)
    embed.add_field(name="/bal", value="Show wallet and bank balance", inline=False)
    embed.add_field(name="/lb", value="Show economy leaderboard", inline=False)
    embed.add_field(name="/leaderboards [type] [limit]", value="Show all leaderboards or select type (level/counting/economy)", inline=False)
    embed.add_field(name="!dm <@members> <message>", value="Send DM to members (Admin only)", inline=False)
    embed.add_field(name="!announcement <#channel> <message>", value="Send announcement to channel (Admin only)", inline=False)
    embed.add_field(name="!say <#channel> <message>", value="Send a plain message to a channel (Admin only)", inline=False)
    embed.add_field(name="/announcement <channel> <message>", value="Send announcement to channel (Admin only)", inline=False)
    embed.add_field(name="/say <channel> <message>", value="Send a plain message to a channel (Admin only)", inline=False)
    embed.add_field(name="!embed <title> [color] [#channel] <description>", value="Create and send embed (Admin only)", inline=False)
    embed.add_field(name="/embed <title> <description> [color] [channel]", value="Create and send embed (Admin only)", inline=False)
    embed.add_field(name="/broadcast <message> [role]", value="DM everyone or a role with a message (Admin only)", inline=False)
    embed.add_field(name="/link_minecraft <username>", value="Start Minecraft account verification", inline=False)
    embed.add_field(name="/confirm_minecraft <code>", value="Confirm your Minecraft link with a verification code", inline=False)
    embed.add_field(name="/cancel_minecraft", value="Cancel a pending Minecraft verification request", inline=False)
    embed.add_field(name="/unlink_minecraft", value="Unlink your Minecraft account", inline=False)
    embed.add_field(name="/minecraft [@user]", value="Show a user's linked Minecraft account", inline=False)
    embed.add_field(name="/kudos <member> [reason]", value="Give kudos to recognize someone", inline=False)
    embed.add_field(name="/reputation [@user]", value="Check your or someone's kudos score", inline=False)
    embed.add_field(name="/kudos_leaderboard [limit]", value="Show top contributors", inline=False)
    embed.add_field(name="/award_kudos <member> [amount] [reason]", value="Award kudos to a member (Admin only)", inline=False)
    embed.add_field(name="/remove_kudos <member> [amount]", value="Remove kudos from a member (Admin only)", inline=False)
    embed.add_field(name="/purge <amount> [reason]", value="Delete multiple messages (Manage Messages permission required)", inline=False)
    embed.add_field(name="/set counting channel <channel>", value="Set the counting channel for this server (Admin only)", inline=False)
    embed.add_field(name="/set staffrole role <role>", value="Set the staff role for this server (Admin only)", inline=False)
    embed.add_field(name="/info server", value="Show detailed server information", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='link_minecraft', description='Start Minecraft account verification')
async def slash_link_minecraft(interaction: discord.Interaction, minecraft_username: str):
    code = create_minecraft_verification(interaction.user.id, minecraft_username)
    await interaction.response.send_message(
        f"✅ {interaction.user.mention}, a verification code has been generated for `{minecraft_username}`."
        f"\n\nPlease paste the following code in your Minecraft account's chat or share it with a server admin so they can confirm the account ownership:\n`{code}`"
        f"\n\nThen run `/confirm_minecraft {code}` in Discord to complete the link. The code expires in 1 hour.",
        ephemeral=True
    )


@bot.tree.command(name='unlink_minecraft', description='Unlink your Minecraft account')
async def slash_unlink_minecraft(interaction: discord.Interaction):
    if remove_minecraft_link(interaction.user.id):
        await interaction.response.send_message(f"✅ {interaction.user.mention}, your Minecraft account link has been removed.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ You do not have a linked Minecraft account.", ephemeral=True)


@bot.tree.command(name='minecraft', description='Show the linked Minecraft account for a member')
async def slash_minecraft(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    link = get_minecraft_link(target.id)
    if link:
        await interaction.response.send_message(f"🔗 {target.display_name} is linked to Minecraft username `{link}`.", ephemeral=True)
    else:
        if member:
            await interaction.response.send_message(f"❌ {target.display_name} does not have a linked Minecraft account.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You do not have a linked Minecraft account.", ephemeral=True)


@bot.tree.command(name='confirm_minecraft', description='Confirm your Minecraft link with a verification code')
async def slash_confirm_minecraft(interaction: discord.Interaction, code: str):
    pending = get_pending_minecraft_verification(interaction.user.id)
    if not pending:
        await interaction.response.send_message("❌ You do not have a pending Minecraft verification request. Use `/link_minecraft <username>` first.", ephemeral=True)
        return

    if pending.get('code') != code:
        await interaction.response.send_message("❌ That verification code does not match. Please use the code shown by `/link_minecraft`.", ephemeral=True)
        return

    set_minecraft_link(interaction.user.id, pending['minecraft_username'])
    remove_pending_minecraft_verification(interaction.user.id)
    await interaction.response.send_message(f"✅ {interaction.user.mention}, your Discord account is now verified and linked to Minecraft username `{pending['minecraft_username']}`.", ephemeral=True)


@bot.tree.command(name='cancel_minecraft', description='Cancel a pending Minecraft verification request')
async def slash_cancel_minecraft(interaction: discord.Interaction):
    if remove_pending_minecraft_verification(interaction.user.id):
        await interaction.response.send_message("✅ Your pending Minecraft verification request has been cancelled.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ You do not have a pending Minecraft verification request to cancel.", ephemeral=True)


@bot.tree.command(name='kudos', description='Give kudos to recognize someone\'s contribution')
@discord.app_commands.describe(member='The member to give kudos to', reason='Optional reason for the kudos')
async def slash_kudos(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    """Give kudos to a member"""
    if member == interaction.user:
        await interaction.response.send_message("❌ You can't give kudos to yourself!", ephemeral=True)
        return
    
    if member.bot:
        await interaction.response.send_message("❌ You can't give kudos to a bot!", ephemeral=True)
        return
    
    give_kudos(interaction.user.id, member.id, reason)
    
    embed = discord.Embed(
        title="🏆 Kudos Given!",
        description=f"{interaction.user.mention} gave kudos to {member.mention}",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"{member.display_name} now has {get_kudos(member.id)} kudos!")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='reputation', description='Check your or someone\'s kudos/reputation')
@discord.app_commands.describe(member='The member to check (defaults to you)')
async def slash_reputation(interaction: discord.Interaction, member: discord.Member = None):
    """Check reputation"""
    target = member or interaction.user
    kudos_count = get_kudos(target.id)
    details = get_kudos_details(target.id)
    
    embed = discord.Embed(
        title="🏆 Reputation",
        description=f"{target.display_name}'s Kudos Score",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Total Kudos", value=str(kudos_count), inline=True)
    
    if details.get('from'):
        top_givers = sorted(details['from'].items(), key=lambda x: x[1]['count'], reverse=True)[:3]
        givers_text = "\n".join([f"<@{gid}>: {gdata['count']}" for gid, gdata in top_givers])
        embed.add_field(name="Top Givers", value=givers_text, inline=True)
    
    embed.set_thumbnail(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='kudos_leaderboard', description='Show the kudos leaderboard')
@discord.app_commands.describe(limit='How many users to show (1-25, default 10)')
async def slash_kudos_leaderboard(interaction: discord.Interaction, limit: int = 10):
    """Show kudos leaderboard"""
    if limit > 25:
        limit = 25
    if limit < 1:
        limit = 10
    
    leaderboard = get_kudos_leaderboard(limit)
    
    if not leaderboard:
        await interaction.response.send_message("❌ No kudos have been given yet!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🏆 Kudos Leaderboard",
        description="Top community contributors",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    medals = ['🥇', '🥈', '🥉']
    for idx, (user_id, count) in enumerate(leaderboard):
        medal = medals[idx] if idx < 3 else f"{idx+1}."
        embed.add_field(name=f"{medal} <@{user_id}>", value=f"{count} kudos", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='award_kudos', description='Award kudos to a member (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(member='The member to award kudos to', amount='How many kudos to give', reason='Optional reason')
async def slash_award_kudos(interaction: discord.Interaction, member: discord.Member, amount: int = 1, reason: str = None):
    """Award kudos (admin)"""
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
        return
    
    award_kudos(member.id, amount)
    
    embed = discord.Embed(
        title="🏆 Kudos Awarded",
        description=f"{interaction.user.mention} awarded {amount} kudos to {member.mention}",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"{member.display_name} now has {get_kudos(member.id)} kudos!")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='remove_kudos', description='Remove kudos from a member (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(member='The member to remove kudos from', amount='How many kudos to remove')
async def slash_remove_kudos(interaction: discord.Interaction, member: discord.Member, amount: int = 1):
    """Remove kudos (admin)"""
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
        return
    
    remove_kudos(member.id, amount)
    
    embed = discord.Embed(
        title="🏆 Kudos Removed",
        description=f"{interaction.user.mention} removed {amount} kudos from {member.mention}",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"{member.display_name} now has {get_kudos(member.id)} kudos!")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='status', description='Show logging status')
async def slash_status(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✅ Logger Bot Status",
        description="Bot is actively logging events",
        color=discord.Color.green()
    )
    embed.add_field(name="Logging:", value="✅ Active" if logging_enabled else "❌ Disabled", inline=False)
    embed.add_field(name="Message Logs", value=f"<#{get_log_channel_id('message')}>", inline=False)
    embed.add_field(name="Member Logs", value=f"<#{get_log_channel_id('member')}>", inline=False)
    embed.add_field(name="Channel Logs", value=f"<#{get_log_channel_id('channel')}>", inline=False)
    embed.add_field(name="Role Logs", value=f"<#{get_log_channel_id('role')}>", inline=False)
    embed.add_field(name="Moderation Alerts", value=f"<#{get_log_channel_id('moderation')}>", inline=False)
    embed.add_field(name="Emoji Logs", value=f"<#{get_log_channel_id('emoji')}>", inline=False)
    embed.add_field(name="Command Logs", value=f"<#{get_log_channel_id('command')}>", inline=False)
    embed.add_field(name="Ticket Category ID", value=f"{TICKET_CATEGORY_ID or 'Not configured'}", inline=False)
    embed.add_field(name="Server", value=interaction.guild.name if interaction.guild else "Direct Message", inline=False)
    embed.add_field(name="Members", value=interaction.guild.member_count if interaction.guild else "N/A", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


info_group = discord.app_commands.Group(name='info', description='Information commands')

set_group = discord.app_commands.Group(name='set', description='Set server configuration')
counting_group = discord.app_commands.Group(name='counting', description='Counting configuration')
staffrole_group = discord.app_commands.Group(name='staffrole', description='Staff role configuration')
levelrole_group = discord.app_commands.Group(name='levelrole', description='Level role configuration')

@counting_group.command(name='channel', description='Set the counting channel for this server')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(channel='The channel to use for counting')
async def slash_set_counting_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    set_server_setting(interaction.guild.id, 'counting_channel_id', channel.id)

    embed = discord.Embed(
        title="✅ Counting Channel Set",
        description=f"Counting messages will now be processed in {channel.mention}.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Configured by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@staffrole_group.command(name='role', description='Set the staff role for this server')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(role='The staff role to assign for staff actions')
async def slash_set_staff_role(interaction: discord.Interaction, role: discord.Role):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    set_server_setting(interaction.guild.id, 'staff_role_id', role.id)

    embed = discord.Embed(
        title="✅ Staff Role Set",
        description=f"{role.mention} is now the configured staff role.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Configured by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@levelrole_group.command(name='set', description='Set a role for a specific level')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(level='The level to assign a role to', role='The role to give at this level')
async def slash_set_level_role(interaction: discord.Interaction, level: int, role: discord.Role):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return
    
    if level <= 0:
        await interaction.response.send_message("❌ Level must be greater than 0.", ephemeral=True)
        return

    # Get current level roles config
    level_roles = get_guild_setting(interaction.guild.id, 'level_roles', {})
    level_roles[str(level)] = role.id
    set_server_setting(interaction.guild.id, 'level_roles', level_roles)

    embed = discord.Embed(
        title="✅ Level Role Set",
        description=f"Level **{level}** will now grant {role.mention}",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Configured by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@levelrole_group.command(name='view', description='View all configured level-role mappings')
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_view_level_roles(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    level_roles = get_guild_setting(interaction.guild.id, 'level_roles', {})
    
    if not level_roles:
        await interaction.response.send_message(
            "❌ No level-role mappings configured for this server. Use `/set levelrole set` to add one.",
            ephemeral=True
        )
        return

    # Sort by level
    sorted_roles = sorted(level_roles.items(), key=lambda x: int(x[0]))
    
    embed = discord.Embed(
        title="📊 Level-Role Mappings",
        description=f"Showing {len(sorted_roles)} configured mappings",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    role_text = ""
    for level, role_id in sorted_roles:
        role = interaction.guild.get_role(int(role_id))
        if role:
            role_text += f"Level {level}: {role.mention}\n"
        else:
            role_text += f"Level {level}: Role not found (ID: {role_id})\n"
    
    if role_text:
        embed.add_field(name="Mappings", value=role_text.strip(), inline=False)
    
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@levelrole_group.command(name='remove', description='Remove a role reward for a specific level')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(level='The level to remove the role from')
async def slash_remove_level_role(interaction: discord.Interaction, level: int):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return
    
    if level <= 0:
        await interaction.response.send_message("❌ Level must be greater than 0.", ephemeral=True)
        return

    level_roles = get_guild_setting(interaction.guild.id, 'level_roles', {})
    
    if str(level) not in level_roles:
        await interaction.response.send_message(f"❌ No role configured for level {level}.", ephemeral=True)
        return

    del level_roles[str(level)]
    set_server_setting(interaction.guild.id, 'level_roles', level_roles)

    embed = discord.Embed(
        title="✅ Level Role Removed",
        description=f"Removed role reward for level **{level}**",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Configured by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


set_group.add_command(counting_group)
set_group.add_command(staffrole_group)
set_group.add_command(levelrole_group)

@info_group.command(name='server', description='Show detailed server information')
async def slash_info_server(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    guild = interaction.guild
    embed = discord.Embed(
        title=f"📊 {guild.name} Server Information",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

    # Basic info
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=True)
    embed.add_field(name="Members", value=f"{guild.member_count} members", inline=True)

    # Channels
    text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
    voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
    categories = len([c for c in guild.channels if isinstance(c, discord.CategoryChannel)])
    embed.add_field(name="Channels", value=f"{text_channels} text, {voice_channels} voice, {categories} categories", inline=True)

    # Roles
    embed.add_field(name="Roles", value=f"{len(guild.roles)} roles", inline=True)

    # Boosts
    embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier}", inline=True)
    embed.add_field(name="Boosts", value=f"{guild.premium_subscription_count} boosts", inline=True)

    # Features
    features = guild.features
    if features:
        feature_list = [f.replace('_', ' ').title() for f in features[:5]]  # Limit to 5
        embed.add_field(name="Features", value=", ".join(feature_list), inline=False)
    else:
        embed.add_field(name="Features", value="None", inline=False)

    # Description
    if guild.description:
        embed.add_field(name="Description", value=guild.description[:1024], inline=False)

    embed.set_footer(text=f"Server ID: {guild.id}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@info_group.command(name='user', description='Show moderation history for a user')
@discord.app_commands.describe(member='Member to inspect')
async def slash_info_user(interaction: discord.Interaction, member: discord.Member = None):
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    member = member or interaction.user
    record = moderation_data.get(str(member.id), DEFAULT_MODERATION_RECORD)

    embed = discord.Embed(
        title=f"👤 {member.display_name} Moderation Info",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    embed.add_field(name="Warnings", value=str(record.get('warns', 0)), inline=True)
    embed.add_field(name="Kicks", value=str(record.get('kicks', 0)), inline=True)
    embed.add_field(name="Bans", value=str(record.get('bans', 0)), inline=True)
    embed.add_field(name="Mutes", value=str(record.get('mutes', 0)), inline=True)
    embed.add_field(name="Timeouts", value=str(record.get('timeouts', 0)), inline=True)
    embed.add_field(name="Current Timeout", value=format_future_duration(record.get('current_timeout_expires')), inline=False)
    embed.add_field(name="Current Mute", value=format_future_duration(record.get('current_mute_expires')), inline=False)
    embed.add_field(name="Current Ban", value=format_future_duration(record.get('current_ban_expires')), inline=False)
    embed.set_footer(text=f"User ID: {member.id}")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='log', description='Set a log channel for events')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(log_type='Type of log to configure', channel='Channel to send log messages to')
async def slash_log(interaction: discord.Interaction, log_type: str, channel: discord.TextChannel):
    canonical = normalize_log_type(log_type)
    if not canonical:
        valid = ', '.join(sorted(LOG_TYPE_ALIASES.keys()))
        await interaction.response.send_message(
            f"❌ Invalid log type. Use one of: {valid}",
            ephemeral=True
        )
        return

    if canonical == 'all':
        for key in LOG_CHANNEL_TYPES.keys():
            log_channel_settings[key] = channel.id
            # Also save command logs to guild settings
            if key == 'command':
                set_guild_setting(interaction.guild.id, 'command_log_channel_id', channel.id)
        save_log_channels()
        save_server_settings()
        await interaction.response.send_message(
            f"✅ All log types will now go to {channel.mention}",
            ephemeral=True
        )
        return

    log_channel_settings[canonical] = channel.id
    # Also save command logs to guild settings for per-guild logging
    if canonical == 'command':
        set_guild_setting(interaction.guild.id, 'command_log_channel_id', channel.id)
        save_server_settings()
    save_log_channels()
    await interaction.response.send_message(
        f"✅ {canonical.title()} logs will now go to {channel.mention}",
        ephemeral=True
    )


@slash_log.autocomplete('log_type')
async def slash_log_autocomplete(interaction: discord.Interaction, current: str):
    suggestions = [
        ('message', 'message'),
        ('member', 'member'),
        ('channel', 'channel'),
        ('role', 'role'),
        ('moderation', 'moderation'),
        ('emoji_log', 'emoji'),
        ('command_log', 'command'),
        ('all', 'all')
    ]
    normalized = re.sub(r'[^a-z0-9]', '', current.lower())
    choices = []
    for label, value in suggestions:
        compare_label = re.sub(r'[^a-z0-9]', '', label.lower())
        if not normalized or normalized in compare_label or normalized in value:
            choices.append(discord.app_commands.Choice(name=label, value=value))
        if len(choices) >= 25:
            break
    return choices


@bot.tree.command(name='moderationlog', description='Set moderation alert channel')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(channel='Channel for moderation alerts')
async def slash_moderationlog(interaction: discord.Interaction, channel: discord.TextChannel):
    log_channel_settings['moderation'] = channel.id
    save_log_channels()
    await interaction.response.send_message(
        f"✅ Moderation alerts will now go to {channel.mention}",
        ephemeral=True
    )


@bot.tree.command(name='timeout', description='Temporarily timeout a member')
@discord.app_commands.checks.has_permissions(moderate_members=True)
@discord.app_commands.describe(
    member='Member to timeout',
    duration='Duration string like 10s, 10m, 1h, or 1d',
    reason='Reason for the timeout'
)
async def slash_timeout(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = None):
    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        await interaction.response.send_message(
            "❌ Invalid duration. Use formats like `10s`, `10m`, `1h`, or `1d`.",
            ephemeral=True
        )
        return

    timeout_until = datetime.utcnow() + timedelta(seconds=duration_seconds)
    try:
        await member.timeout(timeout_until, reason=reason or 'No reason provided')
        await interaction.response.send_message(
            f"✅ {member.mention} has been timed out for {duration}.",
            ephemeral=True
        )
        record = ensure_moderation_record(member.id)
        record['timeouts'] += 1
        record['current_timeout_expires'] = timeout_until.isoformat()
        save_moderation_data()
        await schedule_timeout_clear(interaction.guild, member.id, duration_seconds)
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I do not have permission to timeout that member.",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Failed to timeout {member}: {e}")
        await interaction.response.send_message(
            "❌ Failed to timeout the member. Please check my permissions and try again.",
            ephemeral=True
        )


@bot.tree.command(name='warn', description='Warn a member and send them a DM')
@discord.app_commands.checks.has_permissions(moderate_members=True)
@discord.app_commands.describe(member='Member to warn', reason='Reason for the warning')
async def slash_warn(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    record = ensure_moderation_record(member.id)
    record['warns'] += 1
    save_moderation_data()

    # Try to DM the member
    try:
        embed = discord.Embed(
            title="⚠️ You have been warned",
            description=f"You have been warned in **{interaction.guild.name}**.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Total Warnings", value=record['warns'], inline=True)
        embed.set_footer(text="Please follow the server rules to avoid further action.")

        await member.send(embed=embed)
        dm_success = True
    except discord.Forbidden:
        dm_success = False

    # Respond to the moderator
    if dm_success:
        await interaction.response.send_message(
            f"✅ {member.mention} has been warned. They have been notified via DM.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"✅ {member.mention} has been warned, but I couldn't send them a DM (they may have DMs disabled).",
            ephemeral=True
        )


ticket_group = discord.app_commands.Group(name='ticket', description='Ticket commands')

@ticket_group.command(name='open', description='Open a new ticket')
@discord.app_commands.describe(reason='Reason for opening the ticket')
async def slash_ticket_open(interaction: discord.Interaction, reason: str = None):
    if not interaction.guild:
        await interaction.response.send_message("Tickets can only be opened inside a server.", ephemeral=True)
        return
    try:
        channel = await create_ticket_channel(interaction, reason=reason or "General support")
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)
    except Exception as e:
        logger.error(f"Failed to create ticket from slash command: {e}")
        await interaction.response.send_message("❌ Could not create a ticket. Please contact staff.", ephemeral=True)


@ticket_group.command(name='close', description='Close the current ticket')
@discord.app_commands.checks.has_permissions(manage_channels=True)
async def slash_ticket_close(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This command must be used inside a server ticket channel.", ephemeral=True)
        return

    if not interaction.channel.name.startswith('ticket-'):
        await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
        return

    ticket_owner_id = None
    async for msg in interaction.channel.history(limit=100, oldest_first=True):
        if msg.author == bot.user and msg.embeds:
            embed = msg.embeds[0]
            for field in embed.fields:
                if field.name == 'Ticket Owner':
                    ticket_owner_id = extract_user_id_from_mention(field.value)
                    if ticket_owner_id:
                        break
        if ticket_owner_id:
            break

    if ticket_owner_id is None:
        await interaction.response.send_message("❌ Could not determine the ticket owner for this channel.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    await close_ticket_channel(interaction.channel, interaction.user, ticket_owner_id, original_message=interaction.message)
    await interaction.followup.send("✅ Ticket closed. Transcript has been sent if configured.", ephemeral=True)


@ticket_group.command(name='reopen', description='Reopen a closed ticket')
@discord.app_commands.checks.has_permissions(manage_channels=True)
async def slash_ticket_reopen(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This command must be used inside a server ticket channel.", ephemeral=True)
        return

    if not interaction.channel.name.startswith('ticket-'):
        await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
        return

    ticket_owner_id = None
    async for msg in interaction.channel.history(limit=100, oldest_first=True):
        if msg.author == bot.user and msg.embeds:
            embed = msg.embeds[0]
            for field in embed.fields:
                if field.name == 'Ticket Owner':
                    ticket_owner_id = extract_user_id_from_mention(field.value)
                    if ticket_owner_id:
                        break
        if ticket_owner_id:
            break

    if ticket_owner_id is None:
        await interaction.response.send_message("❌ Could not determine the ticket owner for this channel.", ephemeral=True)
        return

    owner_member = interaction.guild.get_member(ticket_owner_id)
    if owner_member:
        overwrite = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True, read_message_history=True)
        await interaction.channel.set_permissions(owner_member, overwrite=overwrite)

    embed = discord.Embed(
        title="🔓 Ticket Reopened",
        description=f"Ticket reopened by {interaction.user.mention}.",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Ticket Owner", value=f"<@{ticket_owner_id}>", inline=True)
    if interaction.message:
        await interaction.message.edit(embed=embed, view=TicketControlView(owner_id=ticket_owner_id))
        await interaction.response.send_message("✅ Ticket reopened.", ephemeral=True)
    else:
        await interaction.channel.send(embed=embed, view=TicketControlView(owner_id=ticket_owner_id))
        await interaction.response.send_message("✅ Ticket reopened.", ephemeral=True)


@ticket_group.command(name='delete', description='Delete the current ticket channel')
@discord.app_commands.checks.has_permissions(manage_channels=True)
async def slash_ticket_delete(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This command must be used inside a server ticket channel.", ephemeral=True)
        return

    if not interaction.channel.name.startswith('ticket-'):
        await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
        return

    await interaction.response.send_message("🗑️ Deleting ticket channel...", ephemeral=True)
    try:
        await interaction.channel.delete(reason=f"Ticket deleted by {interaction.user}")
    except Exception as e:
        logger.error(f"Failed to delete ticket channel: {e}")
        await interaction.followup.send("❌ Failed to delete the ticket channel. Check my permissions.", ephemeral=True)


@bot.tree.command(name='ticketpanel', description='Post a ticket panel embed with a button')
@discord.app_commands.checks.has_permissions(manage_channels=True)
async def slash_ticket_panel(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used inside a server.", ephemeral=True)
        return

    await interaction.response.send_message(embed=build_ticket_panel_embed(), view=build_ticket_panel_view())


@bot.tree.command(name='tickettranscripts', description='Set the transcript channel for closed tickets')
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_ticket_transcripts(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used inside a server.", ephemeral=True)
        return

    set_server_setting(interaction.guild.id, 'ticket_transcript_channel_id', channel.id)
    await interaction.response.send_message(
        f"✅ Ticket transcripts will now be sent to {channel.mention}.",
        ephemeral=True
    )


@bot.tree.command(name='setup_ticket', description='Post a ticket panel embed with a button')
@discord.app_commands.checks.has_permissions(manage_channels=True)
async def slash_setup_ticket(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used inside a server.", ephemeral=True)
        return

    await interaction.response.send_message(embed=build_ticket_panel_embed(), view=build_ticket_panel_view())


@bot.tree.command(name='sync_commands', description='Resync application commands globally')
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_sync_commands(interaction: discord.Interaction):
    try:
        await bot.tree.sync()
        await interaction.response.send_message("✅ Slash commands synced globally.", ephemeral=True)
    except Exception as e:
        logger.error(f"Failed to sync slash commands from slash_sync_commands: {e}")
        await interaction.response.send_message("❌ Failed to sync slash commands. Check the bot logs.", ephemeral=True)


@commands.guild_only()
@bot.command(name='stats', aliases=['statistics'])
async def stats(ctx):
    """Show logging statistics"""
    embed = discord.Embed(
        title="📊 Logger Bot Statistics",
        description="Current logging activity",
        color=discord.Color.blue()
    )
    
    # Count messages in each log channel (last 100 messages)
    message_count = 0
    member_count = 0
    channel_count = 0
    role_count = 0
    emoji_count = 0
    command_count = 0
    
    try:
        msg_channel = bot.get_channel(get_log_channel_id('message'))
        if msg_channel:
            async for msg in msg_channel.history(limit=100):
                message_count += 1
    except:
        pass
    
    try:
        mem_channel = bot.get_channel(get_log_channel_id('member'))
        if mem_channel:
            async for msg in mem_channel.history(limit=100):
                member_count += 1
    except:
        pass
    
    try:
        chn_channel = bot.get_channel(get_log_channel_id('channel'))
        if chn_channel:
            async for msg in chn_channel.history(limit=100):
                channel_count += 1
    except:
        pass
    
    try:
        rol_channel = bot.get_channel(get_log_channel_id('role'))
        if rol_channel:
            async for msg in rol_channel.history(limit=100):
                role_count += 1
    except:
        pass
    
    try:
        emoji_channel = bot.get_channel(get_log_channel_id('emoji'))
        if emoji_channel:
            async for msg in emoji_channel.history(limit=100):
                emoji_count += 1
    except:
        pass
    
    try:
        command_channel = bot.get_channel(get_log_channel_id('command'))
        if command_channel:
            async for msg in command_channel.history(limit=100):
                command_count += 1
    except:
        pass
    
    embed.add_field(name="📝 Message Logs", value=f"{message_count} recent entries", inline=True)
    embed.add_field(name="👥 Member Logs", value=f"{member_count} recent entries", inline=True)
    embed.add_field(name="📺 Channel Logs", value=f"{channel_count} recent entries", inline=True)
    embed.add_field(name="🏷️ Role Logs", value=f"{role_count} recent entries", inline=True)
    embed.add_field(name="😊 Emoji Logs", value=f"{emoji_count} recent entries", inline=True)
    embed.add_field(name="⌨️ Command Logs", value=f"{command_count} recent entries", inline=True)
    embed.add_field(name="🔄 Logging Status", value="✅ Enabled" if logging_enabled else "❌ Disabled", inline=False)
    embed.add_field(name="⏰ Uptime", value=f"Bot started at {get_timestamp()}", inline=False)
    
    await ctx.send(embed=embed)

@commands.guild_only()
@bot.command(name='status', aliases=['info'])
async def status(ctx):
    """Show logging status"""
    embed = discord.Embed(
        title="✅ Logger Bot Status",
        description="Bot is actively logging events",
        color=discord.Color.green()
    )
    embed.add_field(name="Logging:", value="✅ Active" if logging_enabled else "❌ Disabled", inline=False)
    embed.add_field(name="Message Logs", value=f"<#{get_log_channel_id('message')}>", inline=False)
    embed.add_field(name="Member Logs", value=f"<#{get_log_channel_id('member')}>", inline=False)
    embed.add_field(name="Channel Logs", value=f"<#{get_log_channel_id('channel')}>", inline=False)
    embed.add_field(name="Role Logs", value=f"<#{get_log_channel_id('role')}>", inline=False)
    embed.add_field(name="Moderation Alerts", value=f"<#{get_log_channel_id('moderation')}>", inline=False)
    embed.add_field(name="Emoji Logs", value=f"<#{get_log_channel_id('emoji')}>", inline=False)
    embed.add_field(name="Command Logs", value=f"<#{get_log_channel_id('command')}>", inline=False)
    embed.add_field(name="Ticket Category ID", value=f"{TICKET_CATEGORY_ID or 'Not configured'}", inline=False)
    embed.add_field(name="Server", value=ctx.guild.name if ctx.guild else "Direct Message", inline=False)
    embed.add_field(name="Members", value=ctx.guild.member_count if ctx.guild else "N/A", inline=False)
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='log', aliases=['setlog'])
@commands.has_permissions(administrator=True)
async def set_log(ctx, log_type: str, channel: discord.TextChannel):
    canonical = normalize_log_type(log_type)
    if not canonical:
        valid = ', '.join(sorted(LOG_TYPE_ALIASES.keys()))
        await ctx.send(f"❌ Invalid log type. Use one of: {valid}")
        return

    if canonical == 'all':
        for key in LOG_CHANNEL_TYPES.keys():
            log_channel_settings[key] = channel.id
        save_log_channels()
        await ctx.send(f"✅ All log types will now go to {channel.mention}")
        return

    log_channel_settings[canonical] = channel.id
    save_log_channels()
    await ctx.send(f"✅ {canonical.title()} logs will now go to {channel.mention}")


@commands.guild_only()
@bot.command(name='moderationlog')
@commands.has_permissions(administrator=True)
async def moderation_log(ctx, channel: discord.TextChannel):
    log_channel_settings['moderation'] = channel.id
    save_log_channels()
    await ctx.send(f"✅ Moderation alerts will now go to {channel.mention}")


@commands.guild_only()
@bot.command(name='ticketpanel', aliases=['ticket-panel', 'setup_ticket', 'setup-ticket'])
@commands.has_permissions(administrator=True)
async def ticket_panel(ctx):
    """Post a ticket panel embed with a button"""
    await ctx.send(embed=build_ticket_panel_embed(), view=build_ticket_panel_view())


@commands.guild_only()
@bot.command(name='toggle', aliases=['logging'])
@commands.has_permissions(administrator=True)
async def toggle_logging(ctx):
    """Toggle logging on/off (Admin only)"""
    global logging_enabled
    logging_enabled = not logging_enabled
    
    embed = discord.Embed(
        title="🔄 Logging Toggled",
        color=discord.Color.green() if logging_enabled else discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Status", value="✅ **ENABLED**" if logging_enabled else "❌ **DISABLED**", inline=False)
    embed.add_field(name="Changed by", value=ctx.author.mention, inline=False)
    embed.set_footer(text=f"{get_timestamp()}")
    
    await ctx.send(embed=embed)
    
    # Log the toggle action
    if logging_enabled:
        log_embed = discord.Embed(
            title="🔄 Logging Re-enabled",
            description=f"Logging was turned back on by {ctx.author}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        await send_log(log_embed, 'message')


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='config', aliases=['setup', 'settings'])
async def config_command(ctx, feature: str = None, *, args: str = None):
    """Configure bot features for your server (Admin only)"""
    if not feature:
        embed = discord.Embed(
            title="⚙️ Server Configuration",
            description="Use `!config <feature> <option>` to configure features",
            color=discord.Color.blue()
        )
        embed.add_field(name="prefix <prefix>", value="Set custom command prefix (e.g., !config prefix .)", inline=False)
        embed.add_field(name="welcome enable/disable", value="Toggle welcome messages", inline=False)
        embed.add_field(name="welcome channel <#channel>", value="Set welcome message channel", inline=False)
        embed.add_field(name="welcome message <message>", value="Set welcome message (use {user} for mention, {server} for server name)", inline=False)
        embed.add_field(name="self_roles enable/disable", value="Toggle self-role system", inline=False)
        embed.add_field(name="self_roles channel <#channel>", value="Set self-roles message channel", inline=False)
        embed.add_field(name="suggestions enable/disable", value="Toggle suggestions system", inline=False)
        embed.add_field(name="suggestions channel <#channel>", value="Set suggestions channel", inline=False)
        embed.add_field(name="warnings enable/disable", value="Toggle warning system", inline=False)
        embed.add_field(name="view", value="View all current settings", inline=False)
        await ctx.send(embed=embed)
        return
    
    feature = feature.lower()
    
    if feature == 'view':
        embed = discord.Embed(
            title="⚙️ Current Settings",
            color=discord.Color.blue()
        )
        prefix = get_guild_setting(ctx.guild.id, 'prefix', '!')
        embed.add_field(name="Prefix", value=f"`{prefix}`", inline=True)
        embed.add_field(name="Welcome Enabled", value="✅ Yes" if get_guild_setting(ctx.guild.id, 'enable_welcome', False) else "❌ No", inline=True)
        embed.add_field(name="Self-Roles Enabled", value="✅ Yes" if get_guild_setting(ctx.guild.id, 'enable_self_roles', False) else "❌ No", inline=True)
        embed.add_field(name="Suggestions Enabled", value="✅ Yes" if get_guild_setting(ctx.guild.id, 'enable_suggestions', False) else "❌ No", inline=True)
        embed.add_field(name="Warnings Enabled", value="✅ Yes" if get_guild_setting(ctx.guild.id, 'enable_warnings', True) else "❌ No", inline=True)
        await ctx.send(embed=embed)
        return
    
    if feature == 'prefix':
        if not args:
            await ctx.send("❌ Please provide a prefix (e.g., `!config prefix .`)")
            return
        set_guild_setting(ctx.guild.id, 'prefix', args.split()[0])
        await ctx.send(f"✅ Prefix set to `{args.split()[0]}`")
        return
    
    if feature == 'welcome':
        if not args:
            await ctx.send("❌ Use `!config welcome enable/disable` or `!config welcome channel/message`")
            return
        
        subfeature = args.split()[0].lower()
        if subfeature == 'enable':
            set_guild_setting(ctx.guild.id, 'enable_welcome', True)
            await ctx.send("✅ Welcome messages enabled")
        elif subfeature == 'disable':
            set_guild_setting(ctx.guild.id, 'enable_welcome', False)
            await ctx.send("❌ Welcome messages disabled")
        elif subfeature == 'channel':
            if not ctx.message.channel_mentions:
                await ctx.send("❌ Please mention a channel")
                return
            set_guild_setting(ctx.guild.id, 'welcome_channel', ctx.message.channel_mentions[0].id)
            await ctx.send(f"✅ Welcome channel set to {ctx.message.channel_mentions[0].mention}")
        elif subfeature == 'message':
            msg = ' '.join(args.split()[1:])
            if not msg:
                await ctx.send("❌ Please provide a message")
                return
            set_guild_setting(ctx.guild.id, 'welcome_message', msg)
            await ctx.send("✅ Welcome message updated")
        return
    
    if feature == 'self_roles':
        if not args:
            await ctx.send("❌ Use `!config self_roles enable/disable` or `!config self_roles channel`")
            return
        
        subfeature = args.split()[0].lower()
        if subfeature == 'enable':
            set_guild_setting(ctx.guild.id, 'enable_self_roles', True)
            await ctx.send("✅ Self-roles enabled")
        elif subfeature == 'disable':
            set_guild_setting(ctx.guild.id, 'enable_self_roles', False)
            await ctx.send("❌ Self-roles disabled")
        elif subfeature == 'channel':
            if not ctx.message.channel_mentions:
                await ctx.send("❌ Please mention a channel")
                return
            set_guild_setting(ctx.guild.id, 'self_role_channel', ctx.message.channel_mentions[0].id)
            await ctx.send(f"✅ Self-roles channel set to {ctx.message.channel_mentions[0].mention}")
        return
    
    if feature == 'suggestions':
        if not args:
            await ctx.send("❌ Use `!config suggestions enable/disable` or `!config suggestions channel`")
            return
        
        subfeature = args.split()[0].lower()
        if subfeature == 'enable':
            set_guild_setting(ctx.guild.id, 'enable_suggestions', True)
            await ctx.send("✅ Suggestions enabled")
        elif subfeature == 'disable':
            set_guild_setting(ctx.guild.id, 'enable_suggestions', False)
            await ctx.send("❌ Suggestions disabled")
        elif subfeature == 'channel':
            if not ctx.message.channel_mentions:
                await ctx.send("❌ Please mention a channel")
                return
            set_guild_setting(ctx.guild.id, 'suggestions_channel', ctx.message.channel_mentions[0].id)
            await ctx.send(f"✅ Suggestions channel set to {ctx.message.channel_mentions[0].mention}")
        return
    
    if feature == 'warnings':
        if not args:
            await ctx.send("❌ Use `!config warnings enable/disable`")
            return
        
        subfeature = args.split()[0].lower()
        if subfeature == 'enable':
            set_guild_setting(ctx.guild.id, 'enable_warnings', True)
            await ctx.send("✅ Warnings enabled")
        elif subfeature == 'disable':
            set_guild_setting(ctx.guild.id, 'enable_warnings', False)
            await ctx.send("❌ Warnings disabled")
        return


@commands.guild_only()
@bot.command(name='warnings', aliases=['warns'])
async def show_warnings(ctx, member: discord.Member = None):
    """View warnings for you or another member"""
    target = member or ctx.author
    warns = get_warnings(target.id, ctx.guild.id)
    
    if not warns:
        await ctx.send(f"✅ {target.display_name} has no warnings!")
        return
    
    embed = discord.Embed(
        title=f"⚠️ Warnings for {target.display_name}",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Total Warnings", value=str(len(warns)), inline=False)
    
    for idx, warn in enumerate(warns, 1):
        embed.add_field(
            name=f"Warning #{idx}",
            value=f"**Reason:** {warn['reason']}\n**Moderator:** <@{warn['moderator_id']}>",
            inline=False
        )
    
    await ctx.send(embed=embed)


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='clear_warnings', aliases=['clearwarns'])
async def clear_member_warnings(ctx, member: discord.Member):
    """Clear all warnings for a member (Admin only)"""
    if clear_warnings(member.id, ctx.guild.id):
        await ctx.send(f"✅ Cleared all warnings for {member.mention}")
    else:
        await ctx.send(f"❌ {member.mention} has no warnings to clear")


@commands.guild_only()
@bot.command(name='suggest', aliases=['suggestion'])
async def make_suggestion(ctx, *, content: str):
    """Suggest a feature or improvement"""
    if not get_guild_setting(ctx.guild.id, 'enable_suggestions', False):
        await ctx.send("❌ Suggestions are disabled in this server")
        return
    
    add_suggestion(ctx.guild.id, ctx.author.id, content)
    
    embed = discord.Embed(
        title="💡 Suggestion Submitted",
        description=content,
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Suggested by {ctx.author.display_name}")
    await ctx.send(embed=embed)
    
    # Post to suggestions channel
    suggestion_ch_id = get_guild_setting(ctx.guild.id, 'suggestions_channel')
    if suggestion_ch_id:
        try:
            suggestion_ch = bot.get_channel(suggestion_ch_id)
            if suggestion_ch:
                await suggestion_ch.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to post suggestion: {e}")


@commands.guild_only()
@bot.command(name='selfrolesinfo', aliases=['roleslisting'])
async def self_roles_info(ctx):
    """Show available self-roles for this server"""
    roles_text = get_guild_setting(ctx.guild.id, 'self_role_roles', {})
    
    if not roles_text:
        await ctx.send("❌ No self-roles have been set up yet. Ask an admin to configure them.")
        return
    
    embed = discord.Embed(
        title="🎯 Available Self-Roles",
        description="React or click to get a role!",
        color=discord.Color.blue()
    )
    
    for emoji, role_id in roles_text.items():
        try:
            role = ctx.guild.get_role(int(role_id))
            if role:
                embed.add_field(name=f"{emoji} {role.name}", value=role.mention, inline=False)
        except:
            pass
    
    await ctx.send(embed=embed)


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='addrole', aliases=['addroleopt'])
async def add_role_option(ctx, role: discord.Role, emoji: str):
    """Add a role to the self-roles list"""
    roles_dict = get_guild_setting(ctx.guild.id, 'self_role_roles', {})
    roles_dict[emoji] = role.id
    set_guild_setting(ctx.guild.id, 'self_role_roles', roles_dict)
    await ctx.send(f"✅ Added {emoji} {role.mention} to self-roles")


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='removerole', aliases=['removeroleopt'])
async def remove_role_option(ctx, emoji: str):
    """Remove a role from the self-roles list"""
    roles_dict = get_guild_setting(ctx.guild.id, 'self_role_roles', {})
    if emoji in roles_dict:
        roles_dict.pop(emoji)
        set_guild_setting(ctx.guild.id, 'self_role_roles', roles_dict)
        await ctx.send(f"✅ Removed {emoji} from self-roles")
    else:
        await ctx.send(f"❌ {emoji} not found in self-roles")


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='messagelog', aliases=['msgs', 'msglog'])
async def message_log_cmd(ctx, limit: int = 10):
    """View recent messages logged for this server"""
    messages = load_server_messages(ctx.guild.id)
    
    if not messages:
        await ctx.send("❌ No messages logged yet")
        return
    
    # Show last N messages
    recent = messages[-limit:]
    
    embed = discord.Embed(
        title=f"📋 Recent Messages ({len(recent)})",
        description=f"Last {limit} messages in {ctx.guild.name}",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for msg in recent[-5:]:  # Show last 5 in embed
        author = msg.get('author', 'Unknown')
        content = msg.get('content', '[No content]')[:100]
        channel = msg.get('channel', 'Unknown')
        embed.add_field(
            name=f"{author} in #{channel}",
            value=content,
            inline=False
        )
    
    embed.set_footer(text=f"Total logged: {len(messages)} messages")
    await ctx.send(embed=embed)


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='clearlog', aliases=['clearmsgs'])
async def clear_log_cmd(ctx, confirm: str = None):
    """Clear all message logs for this server"""
    if confirm != 'confirm':
        await ctx.send("⚠️ This will delete all message logs for this server.\nType `!clearlog confirm` to proceed.")
        return
    
    try:
        filepath = get_server_message_log_file(ctx.guild.id)
        if os.path.exists(filepath):
            os.remove(filepath)
            await ctx.send("✅ Message logs cleared")
        else:
            await ctx.send("❌ No logs to clear")
    except Exception as e:
        await ctx.send(f"❌ Failed to clear logs: {str(e)}")


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='logstats', aliases=['loginfo'])
async def log_stats_cmd(ctx):
    """Show statistics about server message logs"""
    messages = load_server_messages(ctx.guild.id)
    
    if not messages:
        await ctx.send("❌ No message data yet")
        return
    
    # Count by author
    author_counts = {}
    for msg in messages:
        author = msg.get('author', 'Unknown')
        author_counts[author] = author_counts.get(author, 0) + 1
    
    # Count by channel
    channel_counts = {}
    for msg in messages:
        channel = msg.get('channel', 'Unknown')
        channel_counts[channel] = channel_counts.get(channel, 0) + 1
    
    top_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_channels = sorted(channel_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    embed = discord.Embed(
        title="📊 Message Log Statistics",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Total Messages", value=len(messages), inline=True)
    embed.add_field(name="Unique Authors", value=len(author_counts), inline=True)
    embed.add_field(name="Unique Channels", value=len(channel_counts), inline=True)
    
    top_authors_text = "\n".join([f"{author}: {count}" for author, count in top_authors])
    embed.add_field(name="📝 Top Authors", value=top_authors_text, inline=False)
    
    top_channels_text = "\n".join([f"#{channel}: {count}" for channel, count in top_channels])
    embed.add_field(name="💬 Top Channels", value=top_channels_text, inline=False)
    
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='role_all', aliases=['roleall'])
@commands.has_permissions(administrator=True)
async def role_all(ctx, role: discord.Role, exclude_bots: str = 'true'):
    """Give a role to everyone in the server."""
    if not ctx.guild:
        await ctx.send('❌ This command can only be used in a server.')
        return

    if not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.send('❌ I need the Manage Roles permission to assign roles.')
        return

    if role >= ctx.guild.me.top_role:
        await ctx.send('❌ I cannot assign a role equal to or higher than my highest role.')
        return

    normalized = exclude_bots.lower()
    if normalized in ('true', 'yes', 'y', '1'):
        exclude_bots_value = True
    elif normalized in ('false', 'no', 'n', '0'):
        exclude_bots_value = False
    else:
        await ctx.send('❌ Invalid value for exclude_bots. Use true or false.')
        return

    members = [member for member in ctx.guild.members if not member.bot or not exclude_bots_value]
    total = len(members)
    added = 0
    skipped = 0
    failed = 0

    status_message = await ctx.send(f'⏳ Assigning {role.mention} to {total} members...')

    for member in members:
        if role in member.roles:
            skipped += 1
            continue
        try:
            await member.add_roles(role, reason='Role all command')
            added += 1
        except Exception:
            failed += 1

    embed = discord.Embed(
        title='✅ Role Assigned to Everyone',
        description=f'Processed {total:,} members with role {role.mention}.',
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name='Role Added', value=f'{added:,}', inline=True)
    embed.add_field(name='Already Had Role', value=f'{skipped:,}', inline=True)
    embed.add_field(name='Failed', value=f'{failed:,}', inline=True)
    embed.add_field(name='Excluded Bots', value=str(exclude_bots_value), inline=True)

    await status_message.edit(content='', embed=embed)


@bot.group(name='ticket', aliases=['support'], invoke_without_command=True)
@commands.guild_only()
async def ticket(ctx, *, reason: str = None):
    """Open a ticket or show ticket help"""
    if not ctx.guild:
        await ctx.send("Tickets can only be opened inside a server.")
        return

    channel = await create_ticket_channel(ctx, reason)
    await ctx.send(f"✅ {ctx.author.mention}, your ticket has been created: {channel.mention}")


@ticket.command(name='panel')
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def ticket_panel_subcommand(ctx):
    """Post a ticket panel embed with a button"""
    embed = discord.Embed(
        title="General support",
        description="Open ticket for general support",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    view = TicketPanelView()
    await ctx.send(embed=embed, view=view)


@ticket.command(name='close')
@commands.guild_only()
async def ticket_close(ctx):
    """Close the current ticket channel"""
    if not ctx.channel.name.startswith('ticket-'):
        await ctx.send("❌ This command can only be used inside a ticket channel.")
        return

    await ctx.send("🔒 Closing this ticket channel...")
    ticket_owner_id = None
    async for msg in ctx.channel.history(limit=100, oldest_first=True):
        if msg.author == bot.user and msg.embeds:
            embed = msg.embeds[0]
            for field in embed.fields:
                if field.name == 'Ticket Owner':
                    user_id_match = re.search(r'<@!(?P<id>\d+)>|<@(?P<id2>\d+)>', field.value)
                    if user_id_match:
                        ticket_owner_id = int(user_id_match.group('id') or user_id_match.group('id2'))
                        break
        if ticket_owner_id:
            break

    if ticket_owner_id is None:
        await ctx.send("❌ Could not determine the ticket owner for this channel.")
        return

    await close_ticket_channel(ctx.channel, ctx.author, ticket_owner_id)


@commands.guild_only()
@bot.command(name='clear', aliases=['purge'])
@commands.has_permissions(manage_messages=True)
async def clear_logs(ctx, log_type: str = None, confirm: str = None):
    """Clear log channels (Manage Messages permission required)"""
    if not confirm or confirm.lower() != "confirm":
        embed = discord.Embed(
            title="⚠️ Confirmation Required",
            description="This will delete ALL messages in the specified log channel(s).\n\n**Type:** `!clear <type> confirm`\n\n**Types:** `messages`, `members`, `channels`, `roles`, `emojis`, `commands`, `all`",
            color=discord.Color.orange()
        )
        embed.add_field(name="Available Types", value="• `messages` - Clear message logs\n• `members` - Clear member logs\n• `channels` - Clear channel logs\n• `roles` - Clear role logs\n• `all` - Clear ALL log channels", inline=False)
        await ctx.send(embed=embed)
        return
    
    channels_to_clear = []
    
    if log_type == "messages" or log_type == "all":
        channels_to_clear.append((get_log_channel_id('message'), "Message Logs"))
    if log_type == "members" or log_type == "all":
        channels_to_clear.append((get_log_channel_id('member'), "Member Logs"))
    if log_type == "channels" or log_type == "all":
        channels_to_clear.append((get_log_channel_id('channel'), "Channel Logs"))
    if log_type == "roles" or log_type == "all":
        channels_to_clear.append((get_log_channel_id('role'), "Role Logs"))
    if log_type == "emojis" or log_type == "all":
        channels_to_clear.append((get_log_channel_id('emoji'), "Emoji Logs"))
    if log_type == "commands" or log_type == "all":
        channels_to_clear.append((get_log_channel_id('command'), "Command Logs"))
    
    if not channels_to_clear:
        await ctx.send("❌ Invalid log type. Use: `messages`, `members`, `channels`, `roles`, or `all`")
        return
    
    cleared_count = 0
    for channel_id, channel_name in channels_to_clear:
        try:
            channel = bot.get_channel(channel_id)
            if channel:
                deleted = await channel.purge(limit=1000)  # Clear up to 1000 messages
                cleared_count += len(deleted)
        except Exception as e:
            logger.error(f"Failed to clear {channel_name}: {e}")
    
    embed = discord.Embed(
        title="🗑️ Logs Cleared",
        description=f"Successfully cleared {cleared_count} messages from {len(channels_to_clear)} channel(s)",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Cleared by", value=ctx.author.mention, inline=False)
    embed.set_footer(text=f"{get_timestamp()}")
    
    await ctx.send(embed=embed)

# Counting Game Commands
@commands.guild_only()
@bot.command(name='counting_status', aliases=['count_status', 'cstatus'])
async def counting_status(ctx):
    """Show current counting status for this channel"""
    current_count = counting_bot.channel_counts.get(ctx.channel.id, 0)
    next_number = current_count + 1
    
    embed = discord.Embed(
        title=f"🔢 Counting Status - #{ctx.channel.name}",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Current Count", value=current_count, inline=True)
    embed.add_field(name="Next Number", value=next_number, inline=True)
    embed.add_field(name="Counting Channel", value=f"<#{COUNTING_CHANNEL_ID}>" if COUNTING_CHANNEL_ID else "Not configured", inline=False)
    
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='reload_counting', aliases=['reload_count'])
@commands.has_permissions(administrator=True)
async def reload_counting(ctx):
    """Reload counting data from file (Admin only)"""
    try:
        result = counting_bot.reload_data()
        embed = discord.Embed(
            title="🔄 Counting Data Reloaded",
            description=result,
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Reloaded by {ctx.author.display_name}")
        await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(
            title="❌ Reload Failed",
            description=f"Error reloading counting data: {str(e)}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='reset_counting', aliases=['reset_count'])
@commands.has_permissions(administrator=True)
async def reset_counting(ctx):
    """Reset the counting for this channel (Admin only)"""
    old_count = counting_bot.reset_channel_count(ctx.channel.id)
    
    embed = discord.Embed(
        title="🔄 Counting Reset",
        description=f"Counting has been reset from {old_count} to 0",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Reset by {ctx.author.display_name}")
    
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='set_count', aliases=['setcount'])
@commands.has_permissions(administrator=True)
async def set_count(ctx, new_count: int):
    """Set the counting number for this channel (Admin only)"""
    if new_count < 0:
        await ctx.send("❌ Count cannot be negative.")
        return
    
    old_count, new_count = counting_bot.set_channel_count(ctx.channel.id, new_count)
    counting_bot.save_data()
    
    embed = discord.Embed(
        title="⚙️ Counting Set",
        description=f"Counting has been set from {old_count} to {new_count}",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Set by {ctx.author.display_name}")
    
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='set_welcome_channel')
@commands.has_permissions(administrator=True)
async def set_welcome_channel(ctx, channel: discord.TextChannel):
    """Configure the welcome channel for this server."""
    welcome_channel_settings[str(ctx.guild.id)] = channel.id
    save_welcome_channels()

    embed = discord.Embed(
        title="✅ Welcome Channel Set",
        description=f"Welcome messages will now be sent in {channel.mention}.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Configured by {ctx.author.display_name}")

    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='score', aliases=['points'])
async def show_score(ctx, member: discord.Member = None):
    """Show your counting score or another member's score"""
    target = member or ctx.author
    user_data = counting_bot.get_user_data(target.id)
    
    # Calculate totals
    correct_count = user_data['score']
    incorrect_count = user_data.get('incorrect', 0)
    total_attempts = correct_count + incorrect_count
    accuracy = (correct_count / total_attempts * 100) if total_attempts > 0 else 0
    
    embed = discord.Embed(
        title=f"📊 {target.display_name}'s Counting Stats",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Score (Correct)", value=correct_count, inline=True)
    embed.add_field(name="Incorrect", value=incorrect_count, inline=True)
    embed.add_field(name="Total Attempts", value=total_attempts, inline=True)
    embed.add_field(name="Saves Available", value=user_data['saves'], inline=True)
    embed.add_field(name="Current Streak", value=user_data['streak'], inline=True)
    embed.add_field(name="Accuracy", value=f"{accuracy:.1f}%", inline=True)
    
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='level', aliases=['lvl', 'rank'])
async def show_level(ctx, member: discord.Member = None):
    """Show your level or another member's level"""
    target = member or ctx.author
    user_data = leveling_bot.get_user_data(ctx.guild.id, target.id)
    level_info = leveling_bot.format_level_info(user_data)
    
    embed = discord.Embed(
        title=f"📈 {target.display_name}'s Level",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Level", value=level_info['level'], inline=True)
    embed.add_field(name="XP", value=f"{level_info['xp']:,}", inline=True)
    embed.add_field(name="XP to Next Level", value=f"{level_info['xp_needed']:,}", inline=True)
    
    # Create progress bar
    progress = level_info['progress']
    progress_total = level_info['progress_total']
    if progress_total > 0:
        filled = int((progress / progress_total) * 10)
        bar = "█" * filled + "░" * (10 - filled)
        percentage = (progress / progress_total) * 100
        embed.add_field(name="Progress", value=f"{bar} {percentage:.1f}%", inline=False)
    
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='leaderboard', aliases=['lb', 'top'])
async def show_leaderboard(ctx, leaderboard_type: str = "level", limit: int = 10):
    """Show the leaderboard (!lb level/counting/economy [limit])"""
    if limit > 25:
        limit = 25
    
    if leaderboard_type.lower() in ['counting', 'count', 'c']:
        # Counting leaderboard
        leaderboard = counting_bot.get_leaderboard(limit)
        
        if not leaderboard:
            await ctx.send("📊 No counting scores recorded yet!")
            return
        
        embed = discord.Embed(
            title=f"🏆 Counting Leaderboard (Top {len(leaderboard)})",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        for i, (user_id, data) in enumerate(leaderboard, 1):
            try:
                user = bot.get_user(int(user_id))
                if not user:
                    user = await bot.fetch_user(int(user_id))
                name = user.display_name if hasattr(user, 'display_name') else str(user)
            except:
                name = f"User {user_id}"
            
            correct_count = data['score']
            incorrect_count = data.get('incorrect', 0)
            total_attempts = correct_count + incorrect_count
            accuracy = (correct_count / total_attempts * 100) if total_attempts > 0 else 0
            
            embed.add_field(
                name=f"{i}. {name}",
                value=f"Score: {correct_count} | Saves: {data['saves']} | Accuracy: {accuracy:.1f}%",
                inline=False
            )
    
    elif leaderboard_type.lower() in ['economy', 'eco', 'e']:
        # Economy leaderboard
        leaderboard = economy.leaderboard(limit)
        if not leaderboard:
            await ctx.send("📊 No economy data recorded yet!")
            return
        
        embed = discord.Embed(
            title=f"🏆 Economy Leaderboard (Top {len(leaderboard)})",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        for i, (user_id, data, total) in enumerate(leaderboard, 1):
            try:
                user = bot.get_user(int(user_id))
                if not user:
                    user = await bot.fetch_user(int(user_id))
                name = user.display_name if hasattr(user, 'display_name') else str(user)
            except:
                name = f"User {user_id}"
            
            wallet = data.get('wallet', 0)
            bank = data.get('bank', 0)
            embed.add_field(
                name=f"{i}. {name}",
                value=f"Total: {format_currency(total)} | Wallet: {format_currency(wallet)} | Bank: {format_currency(bank)}",
                inline=False
            )
    
    else:
        # Leveling leaderboard (default)
        leaderboard = leveling_bot.get_leaderboard(ctx.guild.id, limit)
        
        if not leaderboard:
            await ctx.send("📊 No leveling data recorded yet!")
            return
        
        embed = discord.Embed(
            title=f"🏆 Leveling Leaderboard (Top {len(leaderboard)})",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        for i, (user_id, data) in enumerate(leaderboard, 1):
            try:
                user = bot.get_user(int(user_id))
                if not user:
                    user = await bot.fetch_user(int(user_id))
                name = user.display_name if hasattr(user, 'display_name') else str(user)
            except:
                name = f"User {user_id}"
            
            embed.add_field(
                name=f"{i}. {name}",
                value=f"Level {data['level']} | {data['xp']:,} XP",
                inline=False
            )
    
    await ctx.send(embed=embed)

@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='give_save', aliases=['add_save', 'save', 'givesaves'])
async def give_save(ctx, member: discord.Member, amount: int = 1):
    """Give saves to a user (Admin only)"""
    if amount < 1:
        await ctx.send("❌ Amount must be positive.")
        return
    
    new_saves = counting_bot.give_save(member.id, amount)
    
    embed = discord.Embed(
        title="🎁 Saves Given",
        description=f"Gave {amount} save(s) to {member.mention}",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="New Save Count", value=new_saves, inline=False)
    embed.set_footer(text=f"Given by {ctx.author.display_name}")
    
    await ctx.send(embed=embed)


@bot.group(name='xp', aliases=['experience'], invoke_without_command=True)
@commands.has_permissions(administrator=True)
async def xp_management(ctx):
    """XP management commands (Admin only)"""
    embed = discord.Embed(
        title="⚙️ XP Management",
        description="Available XP commands:",
        color=discord.Color.blue()
    )
    embed.add_field(name="!xp set <@user> <amount>", value="Set a user's XP to a specific amount", inline=False)
    embed.add_field(name="!xp add <@user> <amount>", value="Add XP to a user", inline=False)
    embed.add_field(name="!xp remove <@user> <amount>", value="Remove XP from a user", inline=False)
    await ctx.send(embed=embed)


@xp_management.command(name='set')
@commands.has_permissions(administrator=True)
async def xp_set(ctx, member: discord.Member, amount: int):
    """Set a user's XP to a specific amount (Admin only)"""
    if amount < 0:
        await ctx.send("❌ XP amount cannot be negative.")
        return
    
    old_level, new_level = leveling_bot.set_xp(ctx.guild.id, member.id, amount)
    
    embed = discord.Embed(
        title="⚙️ XP Set",
        description=f"Set {member.mention}'s XP to {amount:,}",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Previous Level", value=old_level, inline=True)
    embed.add_field(name="New Level", value=new_level, inline=True)
    embed.set_footer(text=f"Set by {ctx.author.display_name}")
    
    await ctx.send(embed=embed)


@xp_management.command(name='add')
@commands.has_permissions(administrator=True)
async def xp_add(ctx, member: discord.Member, amount: int):
    """Add XP to a user (Admin only)"""
    if amount <= 0:
        await ctx.send("❌ Amount must be positive.")
        return
    
    leveled_up, new_level, old_level = leveling_bot.add_xp(ctx.guild.id, member.id, amount)
    
    embed = discord.Embed(
        title="➕ XP Added",
        description=f"Added {amount:,} XP to {member.mention}",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Previous Level", value=old_level, inline=True)
    embed.add_field(name="New Level", value=new_level, inline=True)
    
    if leveled_up:
        embed.add_field(name="🎉 Level Up!", value=f"Reached Level {new_level}!", inline=False)
    
    embed.set_footer(text=f"Added by {ctx.author.display_name}")
    
    await ctx.send(embed=embed)


@xp_management.command(name='remove')
@commands.has_permissions(administrator=True)
async def xp_remove(ctx, member: discord.Member, amount: int):
    """Remove XP from a user (Admin only)"""
    if amount <= 0:
        await ctx.send("❌ Amount must be positive.")
        return
    
    user_data = leveling_bot.get_user_data(ctx.guild.id, member.id)
    current_xp = user_data['xp']
    
    if amount > current_xp:
        amount = current_xp  # Don't go below 0
    
    new_xp = current_xp - amount
    old_level, new_level = leveling_bot.set_xp(ctx.guild.id, member.id, new_xp)
    
    embed = discord.Embed(
        title="➖ XP Removed",
        description=f"Removed {amount:,} XP from {member.mention}",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Previous Level", value=old_level, inline=True)
    embed.add_field(name="New Level", value=new_level, inline=True)
    embed.set_footer(text=f"Removed by {ctx.author.display_name}")
    
    await ctx.send(embed=embed)


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='giveaway', aliases=['g'])
async def giveaway(ctx, duration: str, winners: int, role: discord.Role = None, *, prize: str):
    """Start a giveaway with time, winners, optional role, and prize."""
    seconds = parse_duration(duration)
    if seconds is None or seconds <= 0:
        await ctx.send("❌ Invalid duration. Use formats like `30s`, `10m`, `1h`, or `1d`.")
        return
    if winners < 1:
        await ctx.send("❌ Winner count must be at least 1.")
        return

    end_time = datetime.utcnow() + timedelta(seconds=seconds)
    embed = discord.Embed(
        title="🎉 Giveaway Started!",
        description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Hosted by", value=ctx.author.mention, inline=False)
    embed.add_field(name="Required Role", value=role.mention if role else "None", inline=False)
    embed.set_footer(text=f"Ends at {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    view = GiveawayView(prize=prize, winners=winners, required_role=role, end_time=end_time)
    message = await ctx.send(embed=embed, view=view)
    view.message = message
    schedule_giveaway_end(view)

    await ctx.send(f"✅ Giveaway started! Click the button below to join.")


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='reset_score', aliases=['resetscore'])
async def reset_score(ctx, member: discord.Member):
    """Reset a user's score (Admin only)"""
    user_data = counting_bot.get_user_data(member.id)
    old_score = user_data['score']
    user_data['score'] = 0
    user_data['streak'] = 0
    counting_bot.save_data()
    
    embed = discord.Embed(
        title="🔄 Score Reset",
        description=f"Reset {member.mention}'s score from {old_score} to 0",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Reset by {ctx.author.display_name}")
    
    await ctx.send(embed=embed)


@commands.guild_only()
@bot.command(name='counting_help', aliases=['count_help', 'count', 'counts'])
async def counting_help(ctx):
    """Show counting game help"""
    embed = discord.Embed(
        title="🔢 Counting Game Help",
        description="How to play the counting game:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="How to Play",
        value="• Count sequentially: 1, 2, 3, 4, etc.\n• Use math expressions: `2*2` for 4, `6/2` for 3\n• Get it right = +1 score, +1 streak\n• Get it wrong = use save or reset to 0",
        inline=False
    )
    
    embed.add_field(
        name="Commands",
        value="• `!score [@user]` - View scores\n• `!leaderboard` - Top players\n• `!counting_status` - Current count\n• `!reload_counting` - Reload data (Admin)\n• `!give_save <@user>` - Give saves (Admin)\n• `!reset_counting` - Reset channel (Admin)",
        inline=False
    )
    
    embed.add_field(
        name="Save System",
        value="• Saves protect against score resets\n• When wrong: use save or lose all points\n• Admins can give saves with `!give_save`",
        inline=False
    )
    
    embed.add_field(
        name="No Double Counting",
        value="• You cannot count twice in a row\n• Wait for another user to count before you go again",
        inline=False
    )
# Slash commands for counting game
@bot.tree.command(name='score', description='Show your counting stats')
async def slash_score(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    user_data = counting_bot.get_user_data(target.id)
    
    # Calculate totals
    correct_count = user_data['score']
    incorrect_count = user_data.get('incorrect', 0)
    total_attempts = correct_count + incorrect_count
    accuracy = (correct_count / total_attempts * 100) if total_attempts > 0 else 0
    
    embed = discord.Embed(
        title=f"📊 {target.display_name}'s Counting Stats",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Score (Correct)", value=correct_count, inline=True)
    embed.add_field(name="Incorrect", value=incorrect_count, inline=True)
    embed.add_field(name="Total Attempts", value=total_attempts, inline=True)
    embed.add_field(name="Saves Available", value=user_data['saves'], inline=True)
    embed.add_field(name="Current Streak", value=user_data['streak'], inline=True)
    embed.add_field(name="Accuracy", value=f"{accuracy:.1f}%", inline=True)
    
    await interaction.response.send_message(embed=embed)


reset_group = discord.app_commands.Group(name='reset', description='Reset counting stats')

@reset_group.command(name='me', description='Reset your own counting stats and saves')
async def reset_me(interaction: discord.Interaction):
    user_data = counting_bot.get_user_data(interaction.user.id)
    user_data['score'] = 0
    user_data['saves'] = 0
    user_data['streak'] = 0
    user_data['incorrect'] = 0
    counting_bot.save_data()

    await interaction.response.send_message(
        "✅ Your counting stats and saves have been reset.",
        ephemeral=True
    )


@reset_group.command(name='reload', description='Reload counting data from file (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
async def reload_counting_slash(interaction: discord.Interaction):
    try:
        result = counting_bot.reload_data()
        embed = discord.Embed(
            title="🔄 Counting Data Reloaded",
            description=result,
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Reloaded by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        embed = discord.Embed(
            title="❌ Reload Failed",
            description=f"Error reloading counting data: {str(e)}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


bot.tree.add_command(reset_group)


@bot.tree.command(name='set_count', description='Set the counting number for this channel (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(count='The number to set the count to')
async def slash_set_count(interaction: discord.Interaction, count: int):
    if count < 0:
        await interaction.response.send_message("❌ Count cannot be negative.", ephemeral=True)
        return
    
    old_count, new_count = counting_bot.set_channel_count(interaction.channel.id, count)
    counting_bot.save_data()
    
    embed = discord.Embed(
        title="⚙️ Counting Set",
        description=f"Counting has been set from {old_count} to {new_count}",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Set by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='set_welcome_channel', description='Set the welcome channel for this server (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(channel='The channel where welcome messages should be posted')
async def slash_set_welcome_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    welcome_channel_settings[str(interaction.guild.id)] = channel.id
    save_welcome_channels()

    embed = discord.Embed(
        title="✅ Welcome Channel Set",
        description=f"Welcome messages will now be sent in {channel.mention}.",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Configured by {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='stickymessage', description='Create or update a sticky message in a channel')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(message='Sticky message text', channel='Channel for the sticky message')
async def slash_stickymessage(interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    target_channel = channel or interaction.channel
    if not target_channel or not isinstance(target_channel, discord.TextChannel):
        await interaction.response.send_message("❌ Invalid channel.", ephemeral=True)
        return

    sticky_data = sticky_messages.get(str(target_channel.id))
    new_message = None

    if sticky_data:
        try:
            old_message = await target_channel.fetch_message(sticky_data['message_id'])
            if old_message and old_message.author == bot.user:
                await old_message.edit(content=message)
                new_message = old_message
        except Exception:
            new_message = None

    if new_message is None:
        try:
            new_message = await target_channel.send(message)
        except Exception as e:
            logger.error(f"Failed to send sticky message to {target_channel.id}: {e}")
            await interaction.response.send_message("❌ Could not send the sticky message to that channel.", ephemeral=True)
            return

    if sticky_data and sticky_data.get('message_id') != new_message.id:
        try:
            old_message = await target_channel.fetch_message(sticky_data['message_id'])
            if old_message and old_message.author == bot.user and old_message.pinned:
                await old_message.unpin(reason='Replacing sticky message')
        except Exception:
            pass

    try:
        await new_message.pin(reason='Sticky message set by command')
    except Exception:
        pass

    sticky_messages[str(target_channel.id)] = {
        'message_id': new_message.id,
        'content': message
    }
    save_sticky_messages()

    await interaction.response.send_message(
        f"✅ Sticky message has been set in {target_channel.mention}.",
        ephemeral=True
    )


@bot.tree.command(name='count_leaderboard', description='Show the counting leaderboard')
async def slash_count_leaderboard(interaction: discord.Interaction, limit: int = 10):
    if limit > 25:
        limit = 25
    
    leaderboard = counting_bot.get_leaderboard(limit)
    
    if not leaderboard:
        await interaction.response.send_message("📊 No counting scores recorded yet!")
        return
    
    embed = discord.Embed(
        title=f"🏆 Counting Leaderboard (Top {len(leaderboard)})",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    for i, (user_id, data) in enumerate(leaderboard, 1):
        try:
            user = bot.get_user(int(user_id))
            if not user:
                user = await bot.fetch_user(int(user_id))
            name = user.display_name if hasattr(user, 'display_name') else str(user)
        except:
            name = f"User {user_id}"
        
        correct_count = data['score']
        incorrect_count = data.get('incorrect', 0)
        total_attempts = correct_count + incorrect_count
        accuracy = (correct_count / total_attempts * 100) if total_attempts > 0 else 0
        
        embed.add_field(
            name=f"{i}. {name}",
            value=f"Score: {correct_count} | Saves: {data['saves']} | Accuracy: {accuracy:.1f}%",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='level', description='Show your level or another member\'s level')
async def slash_level(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    user_data = leveling_bot.get_user_data(interaction.guild.id, target.id)
    level_info = leveling_bot.format_level_info(user_data)
    
    embed = discord.Embed(
        title=f"📈 {target.display_name}'s Level",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Level", value=level_info['level'], inline=True)
    embed.add_field(name="XP", value=f"{level_info['xp']:,}", inline=True)
    embed.add_field(name="XP to Next Level", value=f"{level_info['xp_needed']:,}", inline=True)
    
    # Create progress bar
    progress = level_info['progress']
    progress_total = level_info['progress_total']
    if progress_total > 0:
        filled = int((progress / progress_total) * 10)
        bar = "█" * filled + "░" * (10 - filled)
        percentage = (progress / progress_total) * 100
        embed.add_field(name="Progress", value=f"{bar} {percentage:.1f}%", inline=False)
    
    embed.set_thumbnail(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='level_leaderboard', description='Show the leveling leaderboard')
async def slash_leaderboard(interaction: discord.Interaction, limit: int = 10):
    if limit > 25:
        limit = 25
    
    leaderboard = leveling_bot.get_leaderboard(interaction.guild.id, limit)
    
    if not leaderboard:
        await interaction.response.send_message("📊 No leveling data recorded yet!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"🏆 Leveling Leaderboard (Top {len(leaderboard)})",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for i, (user_id, data) in enumerate(leaderboard, 1):
        try:
            user = bot.get_user(int(user_id))
            if not user:
                user = await bot.fetch_user(int(user_id))
            name = user.display_name if hasattr(user, 'display_name') else str(user)
        except:
            name = f"User {user_id}"
        
        embed.add_field(
            name=f"{i}. {name}",
            value=f"Level {data['level']} | {data['xp']:,} XP",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)


xp_commands = discord.app_commands.Group(name='xp', description='XP management commands')

@xp_commands.command(name='set', description='Set a user\'s XP to a specific amount (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_xp_set(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount < 0:
        await interaction.response.send_message("❌ XP amount cannot be negative.", ephemeral=True)
        return
    
    old_level, new_level = leveling_bot.set_xp(interaction.guild.id, member.id, amount)
    
    embed = discord.Embed(
        title="⚙️ XP Set",
        description=f"Set {member.mention}'s XP to {amount:,}",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Previous Level", value=old_level, inline=True)
    embed.add_field(name="New Level", value=new_level, inline=True)
    embed.set_footer(text=f"Set by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@xp_commands.command(name='add', description='Add XP to a user (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_xp_add(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        return
    
    leveled_up, new_level, old_level = leveling_bot.add_xp(interaction.guild.id, member.id, amount)
    
    embed = discord.Embed(
        title="➕ XP Added",
        description=f"Added {amount:,} XP to {member.mention}",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Previous Level", value=old_level, inline=True)
    embed.add_field(name="New Level", value=new_level, inline=True)
    
    if leveled_up:
        embed.add_field(name="🎉 Level Up!", value=f"Reached Level {new_level}!", inline=False)
    
    embed.set_footer(text=f"Added by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@xp_commands.command(name='remove', description='Remove XP from a user (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_xp_remove(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        return
    
    user_data = leveling_bot.get_user_data(interaction.guild.id, member.id)
    current_xp = user_data['xp']
    
    if amount > current_xp:
        amount = current_xp  # Don't go below 0
    
    new_xp = current_xp - amount
    old_level, new_level = leveling_bot.set_xp(interaction.guild.id, member.id, new_xp)
    
    embed = discord.Embed(
        title="➖ XP Removed",
        description=f"Removed {amount:,} XP from {member.mention}",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Previous Level", value=old_level, inline=True)
    embed.add_field(name="New Level", value=new_level, inline=True)
    embed.set_footer(text=f"Removed by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.tree.add_command(xp_commands)

reaction_group = discord.app_commands.Group(name='reaction', description='Reaction role commands')
role_group = discord.app_commands.Group(name='role', description='Reaction role assignment commands')

@role_group.command(name='add', description='Add a reaction role mapping')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(channel='Channel containing the message', message_id='Message ID (right-click message > Copy Message ID)')
async def slash_reaction_role_add(interaction: discord.Interaction, channel: discord.TextChannel, message_id: str, emoji: str, role: discord.Role):
    try:
        message_id_int = int(message_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid message ID. Please provide a valid numeric message ID.", ephemeral=True)
        return

    # Validate message exists
    try:
        message = await channel.fetch_message(message_id_int)
    except discord.NotFound:
        await interaction.response.send_message(f"❌ Message not found in {channel.mention}. Make sure the message ID is correct.", ephemeral=True)
        return
    except discord.Forbidden:
        await interaction.response.send_message(f"❌ I don't have permission to access messages in {channel.mention}.", ephemeral=True)
        return
    except Exception as e:
        logger.error(f"Error fetching message {message_id_int}: {e}")
        await interaction.response.send_message("❌ An error occurred while validating the message.", ephemeral=True)
        return

    message_key = str(message_id_int)
    emoji_key = normalize_emoji(emoji)
    reaction_roles.setdefault(message_key, {})[emoji_key] = role.id
    save_reaction_roles()

    embed = discord.Embed(
        title='✅ Reaction Role Added',
        description=f'Added role {role.mention} for emoji {emoji} on message `{message_id_int}` in {channel.mention}.',
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@role_group.command(name='remove', description='Remove a reaction role mapping')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(message_id='Message ID')
async def slash_reaction_role_remove(interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
    try:
        message_id_int = int(message_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid message ID. Please provide a valid numeric message ID.", ephemeral=True)
        return

    message_key = str(message_id_int)
    emoji_key = normalize_emoji(emoji)
    if message_key not in reaction_roles or reaction_roles[message_key].get(emoji_key) != role.id:
        await interaction.response.send_message('❌ This reaction role mapping does not exist.', ephemeral=True)
        return

    del reaction_roles[message_key][emoji_key]
    if not reaction_roles[message_key]:
        reaction_roles.pop(message_key, None)
    save_reaction_roles()

    embed = discord.Embed(
        title='✅ Reaction Role Removed',
        description=f'Removed role {role.mention} for emoji {emoji} on message `{message_id_int}`.',
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


reaction_group.add_command(role_group)
bot.tree.add_command(reaction_group)
bot.tree.add_command(info_group)
bot.tree.add_command(set_group)
bot.tree.add_command(ticket_group)


@bot.tree.command(name='suggest', description='Suggest a feature or improvement')
@discord.app_commands.describe(content='Your suggestion')
async def slash_suggest(interaction: discord.Interaction, content: str):
    """Suggest a feature"""
    if not get_guild_setting(interaction.guild.id, 'enable_suggestions', False):
        await interaction.response.send_message("❌ Suggestions are disabled in this server", ephemeral=True)
        return
    
    add_suggestion(interaction.guild.id, interaction.user.id, content)
    
    embed = discord.Embed(
        title="💡 Suggestion Submitted",
        description=content,
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Suggested by {interaction.user.display_name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Post to suggestions channel
    suggestion_ch_id = get_guild_setting(interaction.guild.id, 'suggestions_channel')
    if suggestion_ch_id:
        try:
            suggestion_ch = bot.get_channel(suggestion_ch_id)
            if suggestion_ch:
                await suggestion_ch.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to post suggestion: {e}")


@bot.tree.command(name='warnings', description='View warnings for you or another member')
@discord.app_commands.describe(member='Member to check (defaults to you)')
async def slash_warnings(interaction: discord.Interaction, member: discord.Member = None):
    """View warnings"""
    target = member or interaction.user
    warns = get_warnings(target.id, interaction.guild.id)
    
    if not warns:
        await interaction.response.send_message(f"✅ {target.display_name} has no warnings!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"⚠️ Warnings for {target.display_name}",
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Total Warnings", value=str(len(warns)), inline=False)
    
    for idx, warn in enumerate(warns, 1):
        embed.add_field(
            name=f"Warning #{idx}",
            value=f"**Reason:** {warn['reason']}\n**Moderator:** <@{warn['moderator_id']}>",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='role_all', description='Give a role to everyone in the server')
@discord.app_commands.checks.has_permissions(administrator=True)
async def slash_role_all(interaction: discord.Interaction, role: discord.Role, exclude_bots: bool = True):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message('❌ This command must be used in a server.', ephemeral=True)
        return

    if not guild.me.guild_permissions.manage_roles:
        await interaction.response.send_message('❌ I need the Manage Roles permission to assign roles.', ephemeral=True)
        return

    if role >= guild.me.top_role:
        await interaction.response.send_message('❌ I cannot assign a role that is equal to or higher than my highest role.', ephemeral=True)
        return

    members = [member for member in guild.members if not member.bot or not exclude_bots]
    total = len(members)
    added = 0
    skipped = 0
    failed = 0

    await interaction.response.defer(ephemeral=True)

    for member in members:
        if role in member.roles:
            skipped += 1
            continue
        try:
            await member.add_roles(role, reason='Role all command')
            added += 1
        except Exception:
            failed += 1

    embed = discord.Embed(
        title='✅ Role Assigned to Everyone',
        description=f'Processed {total:,} members with role {role.mention}.',
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name='Role Added', value=f'{added:,}', inline=True)
    embed.add_field(name='Already Had Role', value=f'{skipped:,}', inline=True)
    embed.add_field(name='Failed', value=f'{failed:,}', inline=True)
    embed.add_field(name='Excluded Bots', value=str(exclude_bots), inline=True)

    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name='work', description='Work every 30 seconds to earn money')
async def slash_work(interaction: discord.Interaction):
    await work_command(interaction)

@bot.tree.command(name='w', description='Work every 30 seconds to earn money')
async def slash_w(interaction: discord.Interaction):
    await work_command(interaction)

async def work_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    if not economy.can_work(guild_id, user_id):
        current = int(datetime.utcnow().timestamp())
        last = economy.get_user(guild_id, user_id).get('last_work', 0)
        remaining = WORK_COOLDOWN_SECONDS - (current - int(last))
        await interaction.response.send_message(f"⏳ You need to wait {remaining} seconds before working again.", ephemeral=True)
        return

    earned = economy.record_work(guild_id, user_id)
    embed = discord.Embed(
        title="💼 Work Completed",
        description=f"You worked and earned {format_currency(earned)}!",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Wallet", value=format_currency(economy.get_wallet(guild_id, user_id)), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='blackjack', description='Bet on blackjack with HIT/STAND/DOUBLE buttons')
@discord.app_commands.describe(amount='Amount to wager')
async def slash_blackjack(interaction: discord.Interaction, amount: int):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    user = economy.get_user(guild_id, user_id)
    if amount <= 0:
        await interaction.response.send_message("❌ Bet must be greater than zero.", ephemeral=True)
        return
    if amount > user['wallet']:
        await interaction.response.send_message("❌ You don't have enough money in your wallet.", ephemeral=True)
        return

    economy.add_wallet(guild_id, user_id, -amount)
    deck = Deck(2)
    player_hand = Hand()
    dealer_hand = Hand()

    player_hand.add_card(deck.draw())
    dealer_hand.add_card(deck.draw())
    player_hand.add_card(deck.draw())
    dealer_hand.add_card(deck.draw())

    total_bet = amount
    economy.add_stat(guild_id, user_id, 'blackjack_count', 1)

    if player_hand.is_blackjack() and not dealer_hand.is_blackjack():
        winnings = int(amount * 2.5)
        economy.add_wallet(guild_id, user_id, winnings)
        embed = discord.Embed(title="🎉 BLACKJACK!", color=discord.Color.gold(), timestamp=datetime.now())
        embed.add_field(name="Your Hand", value=f"`{player_hand}` = {player_hand.get_value()}")
        embed.add_field(name="Winnings", value=format_currency(winnings))
        await interaction.response.send_message(embed=embed)
        return

    if dealer_hand.is_blackjack():
        embed = discord.Embed(title="❌ DEALER BLACKJACK", color=discord.Color.red(), timestamp=datetime.now())
        embed.add_field(name="Your Hand", value=f"`{player_hand}` = {player_hand.get_value()}")
        embed.add_field(name="Dealer Hand", value=f"`{dealer_hand}` = {dealer_hand.get_value()}")
        await interaction.response.send_message(embed=embed)
        return

    msg = None
    player_stands = False

    while not player_stands:
        embed = discord.Embed(title="🎴 BLACKJACK", color=discord.Color.blue(), timestamp=datetime.now())
        embed.add_field(name="Your Hand", value=f"`{player_hand}` = **{player_hand.get_value()}**")
        embed.add_field(name="Dealer Showing", value=f"`{dealer_hand.cards[0]}`")
        embed.add_field(name="Bet", value=format_currency(total_bet))

        view = BlackjackView(user_id)
        view.children[2].disabled = len(player_hand.cards) != 2

        if msg is None:
            await interaction.response.send_message(embed=embed, view=view)
            msg = await interaction.original_response()
        else:
            await msg.edit(embed=embed, view=view)

        await view.wait()

        if view.action is None:
            for item in view.children:
                item.disabled = True
            embed = discord.Embed(title="⏰ Game Timed Out", description="No action was taken in time.", color=discord.Color.red(), timestamp=datetime.now())
            await msg.edit(embed=embed, view=view)
            return

        if view.action == "hit":
            player_hand.add_card(deck.draw())
            if player_hand.is_bust():
                for item in view.children:
                    item.disabled = True
                embed = discord.Embed(title="💥 BUST!", color=discord.Color.red(), timestamp=datetime.now())
                embed.add_field(name="Your Hand", value=f"`{player_hand}` = {player_hand.get_value()}")
                embed.add_field(name="Lost", value=format_currency(total_bet))
                await msg.edit(embed=embed, view=view)
                return

        elif view.action == "double":
            remaining_wallet = economy.get_user(guild_id, user_id).get('wallet', 0)
            if remaining_wallet < amount:
                await interaction.followup.send("❌ Not enough money to double down!", ephemeral=True)
                continue
            economy.add_wallet(guild_id, user_id, -amount)
            total_bet += amount
            player_hand.add_card(deck.draw())
            if player_hand.is_bust():
                for item in view.children:
                    item.disabled = True
                embed = discord.Embed(title="💥 BUST!", color=discord.Color.red(), timestamp=datetime.now())
                embed.add_field(name="Your Hand", value=f"`{player_hand}` = {player_hand.get_value()}")
                embed.add_field(name="Lost", value=format_currency(total_bet))
                await msg.edit(embed=embed, view=view)
                return
            player_stands = True

        elif view.action == "stand":
            player_stands = True

    while dealer_hand.get_value() < 17:
        dealer_hand.add_card(deck.draw())

    player_val = player_hand.get_value()
    dealer_val = dealer_hand.get_value()

    embed = discord.Embed(title="🎴 FINAL HANDS", color=discord.Color.blue(), timestamp=datetime.now())
    embed.add_field(name="Your Hand", value=f"`{player_hand}` = {player_val}")
    embed.add_field(name="Dealer Hand", value=f"`{dealer_hand}` = {dealer_val}")

    if dealer_val > 21:
        winnings = total_bet * 2
        economy.add_wallet(guild_id, user_id, winnings)
        embed.title = "✅ YOU WIN!"
        embed.color = discord.Color.green()
        embed.add_field(name="Result", value=f"Dealer busts! Winnings: {format_currency(winnings)}")
    elif player_val > dealer_val:
        winnings = total_bet * 2
        economy.add_wallet(guild_id, user_id, winnings)
        embed.title = "✅ YOU WIN!"
        embed.color = discord.Color.green()
        embed.add_field(name="Winnings", value=format_currency(winnings))
    elif player_val < dealer_val:
        embed.title = "❌ YOU LOST!"
        embed.color = discord.Color.red()
        embed.add_field(name="Lost", value=format_currency(total_bet))
    else:
        economy.add_wallet(guild_id, user_id, total_bet)
        embed.title = "🤝 PUSH!"
        embed.color = discord.Color.purple()
        embed.add_field(name="Returned", value=format_currency(total_bet))

    new_balance = economy.get_user(guild_id, user_id).get('wallet', 0)
    embed.add_field(name="New Balance", value=format_currency(new_balance))
    for item in view.children:
        item.disabled = True
    await msg.edit(embed=embed, view=view)


@bot.tree.command(name='roulette', description='Play roulette')
@discord.app_commands.describe(choice='red, black, green, odd, even, or specific number 0-36', amount='Amount to wager')
async def slash_roulette(interaction: discord.Interaction, choice: str, amount: int):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    user = economy.get_user(guild_id, user_id)
    if amount <= 0:
        await interaction.response.send_message("❌ Bet must be greater than zero.", ephemeral=True)
        return
    if amount > user['wallet']:
        await interaction.response.send_message("❌ You don't have enough money in your wallet.", ephemeral=True)
        return

    guess = choice.lower().strip()
    spin = random.randint(0, 36)
    result_color = 'green' if spin == 0 else 'red' if spin % 2 == 0 else 'black'
    result_text = f"{spin} ({result_color})"
    won = False
    reward = 0

    if guess in ('red', 'black'):
        won = guess == result_color
        reward = amount if won else 0
    elif guess in ('odd', 'even'):
        if spin == 0:
            won = False
        else:
            won = (guess == 'odd' and spin % 2 == 1) or (guess == 'even' and spin % 2 == 0)
        reward = amount if won else 0
    elif guess == 'green':
        won = spin == 0
        reward = amount * 14 if won else 0
    else:
        try:
            number_guess = int(guess)
            if 0 <= number_guess <= 36:
                won = number_guess == spin
                reward = amount * 35 if won else 0
            else:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Choose red, black, green, odd, even, or a number from 0-36.", ephemeral=True)
            return

    if won:
        economy.add_wallet(guild_id, user_id, reward)
        embed = discord.Embed(
            title='🎰 Roulette',
            description=f"The wheel landed on {result_text}. You won {format_currency(reward)}!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
    else:
        economy.remove_wallet(guild_id, user_id, amount)
        economy.add_stat(guild_id, user_id, 'total_lost', amount)
        embed = discord.Embed(
            title='🎰 Roulette',
            description=f"The wheel landed on {result_text}. You lost {format_currency(amount)}.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )

    embed.add_field(name='Wallet', value=format_currency(economy.get_wallet(guild_id, user_id)), inline=False)
    await interaction.response.send_message(embed=embed)


class HigherLowerView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, amount: int, first_card: str):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        self.amount = amount
        self.first_card = first_card
        self.ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the original player may use these buttons.", ephemeral=True)
            return False
        return True

    async def end_game(self, interaction: discord.Interaction, embed: discord.Embed):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    def _evaluate(self, choice: str, next_card: str):
        first_value = self.ranks.index(self.first_card)
        next_value = self.ranks.index(next_card)

        if next_value == first_value:
            if choice == 'same':
                return True, self.amount * 4, f"✅ Correct! {next_card} is the same as {self.first_card}."
            return False, 0, f"❌ Incorrect — the card was the same."

        won = ((choice == 'higher' and next_value > first_value) or
               (choice == 'lower' and next_value < first_value))
        if won:
            return True, self.amount, f"✅ Correct! {next_card} is {choice} than {self.first_card}."
        return False, 0, f"❌ Incorrect. {next_card} is not {choice} than {self.first_card}."

    async def process_choice(self, interaction: discord.Interaction, choice: str):
        next_card = random.choice(self.ranks)
        won, payout, description = self._evaluate(choice, next_card)

        user_id = self.user_id
        guild_id = self.guild_id
        economy.add_stat(guild_id, user_id, 'higher_lower_count', 1)

        if won:
            economy.add_wallet(guild_id, user_id, payout)
            color = discord.Color.green()
            outcome_text = f"You won {format_currency(payout)}!"
        else:
            economy.remove_wallet(guild_id, user_id, self.amount)
            economy.add_stat(guild_id, user_id, 'total_lost', self.amount)
            color = discord.Color.red()
            outcome_text = f"You lost {format_currency(self.amount)}."

        embed = discord.Embed(
            title='⬆️⬇️ Higher or Lower',
            description=f"{description}\n\n{outcome_text}",
            color=color,
            timestamp=datetime.now()
        )
        embed.add_field(name='First Card', value=f'`{self.first_card}`', inline=True)
        embed.add_field(name='Next Card', value=f'`{next_card}`', inline=True)
        embed.add_field(name='Wallet', value=format_currency(economy.get_wallet(guild_id, user_id)), inline=False)
        await self.end_game(interaction, embed)

    @discord.ui.button(label='Higher', style=discord.ButtonStyle.primary)
    async def higher(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, 'higher')

    @discord.ui.button(label='Lower', style=discord.ButtonStyle.primary)
    async def lower(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, 'lower')

    @discord.ui.button(label='Same', style=discord.ButtonStyle.secondary)
    async def same(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, 'same')


async def higher_or_lower_handler(interaction: discord.Interaction, amount: int):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    user = economy.get_user(guild_id, user_id)
    if amount <= 0:
        await interaction.response.send_message("❌ Bet must be greater than zero.", ephemeral=True)
        return
    if amount > user['wallet']:
        await interaction.response.send_message("❌ You don't have enough money in your wallet.", ephemeral=True)
        return

    first_card = random.choice(['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'])
    view = HigherLowerView(guild_id, user_id, amount, first_card)

    embed = discord.Embed(
        title='⬆️⬇️ Higher or Lower',
        description=f"Your starting card is `{first_card}`. Choose higher, lower, or same.",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name='Bet', value=format_currency(amount), inline=False)
    embed.set_footer(text='Same pays 4x, higher/lower pays 1x')
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name='higher-or-lower', description='Bet on higher or lower and click the result buttons')
@discord.app_commands.describe(amount='Amount to wager')
async def slash_higher_or_lower(interaction: discord.Interaction, amount: int):
    await higher_or_lower_handler(interaction, amount)


@bot.tree.command(name='higherlower', description='Bet on higher or lower and click the result buttons')
@discord.app_commands.describe(amount='Amount to wager')
async def slash_higherlower(interaction: discord.Interaction, amount: int):
    await higher_or_lower_handler(interaction, amount)


@bot.tree.command(name='crime', description='Attempt a crime with risk of losing money')
async def slash_crime(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    user = economy.get_user(guild_id, user_id)
    wallet = user['wallet']
    if wallet <= 0:
        await interaction.response.send_message("❌ You need money in your wallet before attempting crime.", ephemeral=True)
        return

    success = random.random() < 0.45
    economy.add_stat(guild_id, user_id, 'crime_count', 1)
    if success:
        reward = random.randint(20, min(100, wallet + 50))
        economy.add_wallet(guild_id, user_id, reward)
        embed = discord.Embed(
            title='💰 Crime Success',
            description=f'You successfully stole {format_currency(reward)}!',
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
    else:
        loss = min(wallet, random.randint(10, max(10, wallet // 3)))
        economy.remove_wallet(guild_id, user_id, loss)
        economy.add_stat(guild_id, user_id, 'total_lost', loss)
        embed = discord.Embed(
            title='🚓 Crime Failed',
            description=f'You got caught and lost {format_currency(loss)}.',
            color=discord.Color.red(),
            timestamp=datetime.now()
        )

    embed.add_field(name='Wallet', value=format_currency(economy.get_wallet(guild_id, user_id)), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='deposit', description='Deposit money into your bank')
@discord.app_commands.describe(amount='Amount to deposit')
async def slash_deposit(interaction: discord.Interaction, amount: int):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    user = economy.get_user(guild_id, user_id)
    if amount <= 0:
        await interaction.response.send_message("❌ Deposit amount must be greater than zero.", ephemeral=True)
        return
    if amount > user['wallet']:
        await interaction.response.send_message("❌ You don't have enough money in your wallet.", ephemeral=True)
        return

    economy.remove_wallet(guild_id, user_id, amount)
    economy.add_bank(guild_id, user_id, amount)
    embed = discord.Embed(
        title='🏦 Deposit Complete',
        description=f'Deposited {format_currency(amount)} into your bank.',
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name='Wallet', value=format_currency(economy.get_wallet(guild_id, user_id)), inline=True)
    embed.add_field(name='Bank', value=format_currency(economy.get_bank(guild_id, user_id)), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='withdraw', description='Withdraw money from your bank')
@discord.app_commands.describe(amount='Amount to withdraw')
async def slash_withdraw(interaction: discord.Interaction, amount: int):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    user = economy.get_user(guild_id, user_id)
    if amount <= 0:
        await interaction.response.send_message("❌ Withdraw amount must be greater than zero.", ephemeral=True)
        return
    if amount > user['bank']:
        await interaction.response.send_message("❌ You don't have enough money in your bank.", ephemeral=True)
        return

    economy.remove_bank(guild_id, user_id, amount)
    economy.add_wallet(guild_id, user_id, amount)
    embed = discord.Embed(
        title='🏦 Withdrawal Complete',
        description=f'Withdrew {format_currency(amount)} from your bank.',
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name='Wallet', value=format_currency(economy.get_wallet(guild_id, user_id)), inline=True)
    embed.add_field(name='Bank', value=format_currency(economy.get_bank(guild_id, user_id)), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='rob', description='Rob another user from their wallet')
@discord.app_commands.describe(member='Member to rob')
async def slash_rob(interaction: discord.Interaction, member: discord.Member):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    target_id = member.id
    if target_id == user_id:
        await interaction.response.send_message("❌ You cannot rob yourself.", ephemeral=True)
        return

    target_data = economy.get_user(guild_id, target_id)
    if target_data['wallet'] <= 0:
        await interaction.response.send_message("❌ That user has nothing in their wallet to steal. Their money is likely in the bank.", ephemeral=True)
        return

    thief_wallet = economy.get_wallet(guild_id, user_id)
    success = random.random() < 0.5
    economy.add_stat(guild_id, user_id, 'rob_attempts', 1)

    if success:
        stolen_amount = random.randint(max(1, target_data['wallet'] // 10), max(1, min(target_data['wallet'], target_data['wallet'] // 2)))
        economy.remove_wallet(guild_id, target_id, stolen_amount)
        economy.add_wallet(guild_id, user_id, stolen_amount)
        economy.add_stat(guild_id, user_id, 'rob_success', 1)
        economy.add_stat(guild_id, target_id, 'robbed_count', 1)
        economy.add_stat(guild_id, user_id, 'total_stolen', stolen_amount)
        embed = discord.Embed(
            title='🕵️‍♂️ Robbery Success',
            description=f'You stole {format_currency(stolen_amount)} from {member.mention}!',
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
    else:
        loss = min(thief_wallet, random.randint(5, max(5, target_data['wallet'] // 5)))
        economy.remove_wallet(guild_id, user_id, loss)
        economy.add_stat(guild_id, user_id, 'rob_failure', 1)
        economy.add_stat(guild_id, user_id, 'total_lost', loss)
        embed = discord.Embed(
            title='🚨 Robbery Failed',
            description=f'You were caught and lost {format_currency(loss)}.',
            color=discord.Color.red(),
            timestamp=datetime.now()
        )

    embed.add_field(name='Wallet', value=format_currency(economy.get_wallet(guild_id, user_id)), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='pay', description='Pay another user from your wallet')
@discord.app_commands.describe(member='Member to pay', amount='Amount to send')
async def slash_pay(interaction: discord.Interaction, member: discord.Member, amount: int):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    target_id = member.id
    if target_id == user_id:
        await interaction.response.send_message("❌ You cannot pay yourself.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be greater than zero.", ephemeral=True)
        return

    user = economy.get_user(guild_id, user_id)
    if amount > user['wallet']:
        await interaction.response.send_message("❌ You don't have enough money in your wallet.", ephemeral=True)
        return

    economy.remove_wallet(guild_id, user_id, amount)
    economy.add_wallet(guild_id, target_id, amount)
    embed = discord.Embed(
        title='💸 Payment Sent',
        description=f'You sent {format_currency(amount)} to {member.mention}.',
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='bal', description='Show your wallet and bank balance')
@discord.app_commands.describe(member='Show balance for another member')
async def slash_balance(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    data = economy.get_user(interaction.guild.id, target.id)
    embed = discord.Embed(
        title=f"💰 {target.display_name}'s Balance",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name='Wallet', value=format_currency(data['wallet']), inline=True)
    embed.add_field(name='Bank', value=format_currency(data['bank']), inline=True)
    embed.add_field(name='Total Assets', value=format_currency(data['wallet'] + data['bank']), inline=False)
    embed.add_field(name='Total Lost', value=format_currency(data['total_lost']), inline=True)
    embed.add_field(name='Total Stolen', value=format_currency(data['total_stolen']), inline=True)
    embed.add_field(name='Blackjack Games', value=str(data['blackjack_count']), inline=True)
    embed.add_field(name='Roulette Games', value=str(data['roulette_count']), inline=True)
    embed.add_field(name='Higher/Lower Games', value=str(data['higher_lower_count']), inline=True)
    embed.add_field(name='Crime Attempts', value=str(data['crime_count']), inline=True)
    embed.add_field(name='Rob Attempts', value=str(data['rob_attempts']), inline=True)
    embed.add_field(name='Rob Successes', value=str(data['rob_success']), inline=True)
    embed.add_field(name='Rob Failures', value=str(data['rob_failure']), inline=True)
    embed.add_field(name='Times Robbed', value=str(data['robbed_count']), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='lb', description='Show the economy leaderboard')
async def slash_economy_leaderboard(interaction: discord.Interaction, limit: int = 10):
    if limit > 25:
        limit = 25

    leaderboard = economy.leaderboard(interaction.guild.id, limit)
    if not leaderboard:
        await interaction.response.send_message("📊 No economy data recorded yet!", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🏆 Economy Leaderboard (Top {len(leaderboard)})",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    for i, (user_id, data) in enumerate(leaderboard, 1):
        try:
            user = bot.get_user(int(user_id))
            if not user:
                user = await bot.fetch_user(int(user_id))
            name = user.display_name if hasattr(user, 'display_name') else str(user)
        except:
            name = f"User {user_id}"
        total_assets = data.get('wallet', 0) + data.get('bank', 0)
        embed.add_field(
            name=f"{i}. {name}",
            value=f"Total: {format_currency(total_assets)} | Wallet: {format_currency(data.get('wallet',0))} | Bank: {format_currency(data.get('bank',0))}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='leaderboard', description='Show the economy leaderboard')
async def slash_economy_leaderboard_alias(interaction: discord.Interaction, limit: int = 10):
    await slash_economy_leaderboard(interaction, limit)


@bot.tree.command(name='leaderboards', description='Show all leaderboards or select a specific type')
@discord.app_commands.describe(
    type='Type of leaderboard to show (leave empty for all)',
    limit='Maximum number of entries to show (default: 10)'
)
@discord.app_commands.choices(type=[
    discord.app_commands.Choice(name='All Leaderboards', value='all'),
    discord.app_commands.Choice(name='Leveling', value='level'),
    discord.app_commands.Choice(name='Counting', value='counting'),
    discord.app_commands.Choice(name='Economy', value='economy')
])
async def slash_all_leaderboards(interaction: discord.Interaction, type: str = 'all', limit: int = 10):
    """Show all leaderboards or a specific type"""
    if limit > 25:
        limit = 25
    
    if type == 'all':
        # Show all leaderboards in one embed
        embed = discord.Embed(
            title="🏆 Server Leaderboards",
            description="Top performers across all categories",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        
        # Leveling leaderboard
        leveling_lb = leveling_bot.get_leaderboard(limit)
        if leveling_lb:
            level_text = ""
            for i, (user_id, data) in enumerate(leveling_lb[:5], 1):  # Show top 5 for each
                try:
                    user = bot.get_user(int(user_id))
                    if not user:
                        user = await bot.fetch_user(int(user_id))
                    name = user.display_name if hasattr(user, 'display_name') else str(user)
                except:
                    name = f"User {user_id}"
                level_text += f"{i}. {name} - Level {data['level']}\n"
            embed.add_field(name="📈 Top Levelers", value=level_text or "No data", inline=True)
        
        # Counting leaderboard
        counting_lb = counting_bot.get_leaderboard(limit)
        if counting_lb:
            count_text = ""
            for i, (user_id, data) in enumerate(counting_lb[:5], 1):
                try:
                    user = bot.get_user(int(user_id))
                    if not user:
                        user = await bot.fetch_user(int(user_id))
                    name = user.display_name if hasattr(user, 'display_name') else str(user)
                except:
                    name = f"User {user_id}"
                count_text += f"{i}. {name} - {data['score']} pts\n"
            embed.add_field(name="🔢 Top Counters", value=count_text or "No data", inline=True)
        
        # Economy leaderboard
        economy_lb = economy.leaderboard(interaction.guild.id, limit)
        if economy_lb:
            eco_text = ""
            for i, (user_id, data, total) in enumerate(economy_lb[:5], 1):
                try:
                    user = bot.get_user(int(user_id))
                    if not user:
                        user = await bot.fetch_user(int(user_id))
                    name = user.display_name if hasattr(user, 'display_name') else str(user)
                except:
                    name = f"User {user_id}"
                eco_text += f"{i}. {name} - {format_currency(total)}\n"
            embed.add_field(name="💰 Top Earners", value=eco_text or "No data", inline=True)
        
        embed.set_footer(text=f"Showing top 5 from each category | Use /leaderboards type:<type> for full lists")
        await interaction.response.send_message(embed=embed)
        
    elif type == 'level':
        # Show only leveling leaderboard
        leaderboard = leveling_bot.get_leaderboard(interaction.guild.id, limit)
        
        if not leaderboard:
            await interaction.response.send_message("📊 No leveling data recorded yet!")
            return
        
        embed = discord.Embed(
            title=f"🏆 Leveling Leaderboard (Top {len(leaderboard)})",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        for i, (user_id, data) in enumerate(leaderboard, 1):
            try:
                user = bot.get_user(int(user_id))
                if not user:
                    user = await bot.fetch_user(int(user_id))
                name = user.display_name if hasattr(user, 'display_name') else str(user)
            except:
                name = f"User {user_id}"
            
            embed.add_field(
                name=f"{i}. {name}",
                value=f"Level {data['level']} | {data['xp']:,} XP",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
        
    elif type == 'counting':
        # Show only counting leaderboard
        leaderboard = counting_bot.get_leaderboard(limit)
        
        if not leaderboard:
            await interaction.response.send_message("📊 No counting scores recorded yet!")
            return
        
        embed = discord.Embed(
            title=f"🏆 Counting Leaderboard (Top {len(leaderboard)})",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        for i, (user_id, data) in enumerate(leaderboard, 1):
            try:
                user = bot.get_user(int(user_id))
                if not user:
                    user = await bot.fetch_user(int(user_id))
                name = user.display_name if hasattr(user, 'display_name') else str(user)
            except:
                name = f"User {user_id}"
            
            correct_count = data['score']
            incorrect_count = data.get('incorrect', 0)
            total_attempts = correct_count + incorrect_count
            accuracy = (correct_count / total_attempts * 100) if total_attempts > 0 else 0
            
            embed.add_field(
                name=f"{i}. {name}",
                value=f"Score: {correct_count} | Saves: {data['saves']} | Accuracy: {accuracy:.1f}%",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
        
    elif type == 'economy':
        # Show only economy leaderboard
        leaderboard = economy.leaderboard(interaction.guild.id, limit)
        if not leaderboard:
            await interaction.response.send_message("📊 No economy data recorded yet!")
            return
        
        embed = discord.Embed(
            title=f"🏆 Economy Leaderboard (Top {len(leaderboard)})",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        for i, (user_id, data, total) in enumerate(leaderboard, 1):
            try:
                user = bot.get_user(int(user_id))
                if not user:
                    user = await bot.fetch_user(int(user_id))
                name = user.display_name if hasattr(user, 'display_name') else str(user)
            except:
                name = f"User {user_id}"
            
            wallet = data.get('wallet', 0)
            bank = data.get('bank', 0)
            embed.add_field(
                name=f"{i}. {name}",
                value=f"Total: {format_currency(total)} | Wallet: {format_currency(wallet)} | Bank: {format_currency(bank)}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)


@bot.tree.command(name='addmoney', description='Add money to a user (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(member='Member to add money to', amount='Amount to add')
async def slash_add_money(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be greater than zero.", ephemeral=True)
        return
    economy.add_wallet(interaction.guild.id, member.id, amount)
    economy.add_stat(interaction.guild.id, member.id, 'money_added', amount)
    await interaction.response.send_message(f"✅ Added {format_currency(amount)} to {member.mention}.", ephemeral=True)


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='embed', aliases=['sendembed'])
async def embed(ctx, title: str, color: str = None, channel: discord.TextChannel = None, *, description: str):
    """Create and send embed (Admin only)"""
    # Parse color
    embed_color = discord.Color.blue()  # default
    if color:
        try:
            # Try hex color
            if color.startswith('#'):
                embed_color = discord.Color(int(color[1:], 16))
            # Try named colors
            elif hasattr(discord.Color, color.lower()):
                embed_color = getattr(discord.Color, color.lower())()
            # Try RGB values like "255,0,0"
            elif ',' in color:
                r, g, b = map(int, color.split(','))
                embed_color = discord.Color.from_rgb(r, g, b)
        except:
            await ctx.send("❌ Invalid color format. Use hex (#FF0000), named colors (red, blue), or RGB (255,0,0)")
            return
    
    target_channel = channel or ctx.channel
    
    try:
        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Created by {ctx.author.display_name}")
        
        await target_channel.send(embed=embed)
        
        # Confirm to admin
        confirm_embed = discord.Embed(
            title='✅ Embed Sent',
            description=f"Embed sent to {target_channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        confirm_embed.add_field(name='Title', value=title, inline=True)
        confirm_embed.add_field(name='Channel', value=target_channel.mention, inline=True)
        confirm_embed.add_field(name='Description', value=description[:1024], inline=False)
        await ctx.send(embed=confirm_embed)
        
    except Exception as e:
        await ctx.send(f"❌ Failed to send embed: {str(e)}")


@bot.tree.command(name='embed', description='Create and send an embed message (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(
    title='The embed title',
    description='The embed description',
    color='Hex color code (e.g. #FF0000) or named color',
    channel='Channel to send to (defaults to current channel)'
)
async def slash_embed(
    interaction: discord.Interaction,
    title: str,
    description: str,
    color: str = "#3498db",
    channel: discord.TextChannel = None
):
    """Create and send an embed message (Admin only)"""
    # Parse color
    embed_color = discord.Color.blue()  # default
    try:
        # Try hex color
        if color.startswith('#'):
            embed_color = discord.Color(int(color[1:], 16))
        # Try named colors
        elif hasattr(discord.Color, color.lower()):
            embed_color = getattr(discord.Color, color.lower())()
        # Try RGB values like "255,0,0"
        elif ',' in color:
            r, g, b = map(int, color.split(','))
            embed_color = discord.Color.from_rgb(r, g, b)
    except:
        await interaction.response.send_message("❌ Invalid color format. Use hex (#FF0000), named colors (red, blue), or RGB (255,0,0)", ephemeral=True)
        return
    
    target_channel = channel or interaction.channel
    
    try:
        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Created by {interaction.user.display_name}")
        
        await target_channel.send(embed=embed)
        
        # Confirm to admin
        confirm_embed = discord.Embed(
            title='✅ Embed Sent',
            description=f"Embed sent to {target_channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        confirm_embed.add_field(name='Title', value=title, inline=True)
        confirm_embed.add_field(name='Channel', value=target_channel.mention, inline=True)
        confirm_embed.add_field(name='Description', value=description[:1024], inline=False)
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to send embed: {str(e)}", ephemeral=True)


@bot.tree.command(name='removemoney', description='Remove money from a user (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(member='Member to remove money from', amount='Amount to remove')
async def slash_remove_money(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be greater than zero.", ephemeral=True)
        return
    current_wallet = economy.get_wallet(interaction.guild.id, member.id)
    remove_amount = min(amount, current_wallet)
    economy.remove_wallet(interaction.guild.id, member.id, remove_amount)
    economy.add_stat(interaction.guild.id, member.id, 'money_removed', remove_amount)
    await interaction.response.send_message(f"✅ Removed {format_currency(remove_amount)} from {member.mention}.", ephemeral=True)


@bot.tree.command(name='broadcast', description='DM everyone or a role with a message (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(message='Message to broadcast', role='Optional role to target')
async def slash_broadcast(interaction: discord.Interaction, message: str, role: discord.Role = None):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    target_members = [member for member in interaction.guild.members if not member.bot]
    if role:
        target_members = [member for member in target_members if role in member.roles]

    if not target_members:
        await interaction.response.send_message("❌ No members found to send the broadcast to.", ephemeral=True)
        return

    sent = 0
    failed = 0
    for member in target_members:
        try:
            await member.send(f"📢 **Broadcast from {interaction.guild.name}:**\n\n{message}")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.15)

    embed = discord.Embed(
        title='📣 Broadcast Sent',
        description=f"Message delivered to {sent} members. Failed for {failed} members.",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    if role:
        embed.add_field(name='Role Target', value=role.mention, inline=False)
    embed.add_field(name='Message', value=message[:1024], inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='broadcast', aliases=['dmall'])
async def broadcast(ctx, role: discord.Role = None, *, message: str):
    """Broadcast a message to everyone or a specific role (Admin only)"""
    target_members = [member for member in ctx.guild.members if not member.bot]
    if role:
        target_members = [member for member in target_members if role in member.roles]

    if not target_members:
        await ctx.send("❌ No members found to send the broadcast to.")
        return

    sent = 0
    failed = 0
    for member in target_members:
        try:
            await member.send(f"📢 **Broadcast from {ctx.guild.name}:**\n\n{message}")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.15)

    embed = discord.Embed(
        title='📣 Broadcast Sent',
        description=f"Message delivered to {sent} members. Failed for {failed} members.",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    if role:
        embed.add_field(name='Role Target', value=role.mention, inline=False)
    embed.add_field(name='Message', value=message[:1024], inline=False)
    await ctx.send(embed=embed)


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='announcement', aliases=['announce', 'ann'])
async def announcement(ctx, channel: discord.TextChannel, *, message: str):
    """Send an announcement to a specific channel (Admin only)"""
    try:
        embed = discord.Embed(
            title='📢 Announcement',
            description=message,
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Announced by {ctx.author.display_name}")
        
        await channel.send(embed=embed)
        
        # Confirm to the admin
        confirm_embed = discord.Embed(
            title='✅ Announcement Sent',
            description=f"Announcement sent to {channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        confirm_embed.add_field(name='Channel', value=channel.mention, inline=True)
        confirm_embed.add_field(name='Message', value=message[:1024], inline=False)
        await ctx.send(embed=confirm_embed)
        
    except Exception as e:
        await ctx.send(f"❌ Failed to send announcement: {str(e)}")


@commands.guild_only()
@commands.has_permissions(administrator=True)
@bot.command(name='say', aliases=['send', 'post'])
async def say(ctx, channel: discord.TextChannel, *, message: str):
    """Send a plain message to a channel without embed formatting."""
    try:
        await channel.send(message)
        await ctx.send(f"✅ Message sent to {channel.mention}")
    except Exception as e:
        await ctx.send(f"❌ Failed to send message: {str(e)}")


@bot.tree.command(name='announcement', description='Send an announcement to a channel (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(channel='The channel to send the announcement to', message='The announcement message')
async def slash_announcement(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    """Send an announcement to a specific channel (Admin only)"""
    try:
        embed = discord.Embed(
            title='📢 Announcement',
            description=message,
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Announced by {interaction.user.display_name}")
        
        await channel.send(embed=embed)
        
        # Confirm to the admin
        confirm_embed = discord.Embed(
            title='✅ Announcement Sent',
            description=f"Announcement sent to {channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        confirm_embed.add_field(name='Channel', value=channel.mention, inline=True)
        confirm_embed.add_field(name='Message', value=message[:1024], inline=False)
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to send announcement: {str(e)}", ephemeral=True)


@bot.tree.command(name='say', description='Send a plain message to a channel (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(channel='The channel to send the message to', message='The message to send')
async def slash_say(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    """Send a plain message to a specific channel (Admin only)"""
    try:
        await channel.send(message)
        await interaction.response.send_message(f"✅ Message sent to {channel.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to send message: {str(e)}", ephemeral=True)


@bot.tree.command(name='giveaway', description='Start a giveaway')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(duration='Duration like 30s, 10m, 1h or 1d', winners='Number of winners', prize='Prize description', role='Optional role required to enter')
async def slash_giveaway(
    interaction: discord.Interaction,
    duration: str,
    winners: int,
    prize: str,
    role: discord.Role = None
):
    seconds = parse_duration(duration)
    if seconds is None or seconds <= 0:
        await interaction.response.send_message("❌ Invalid duration. Use formats like `30s`, `10m`, `1h`, or `1d`.", ephemeral=True)
        return
    if winners < 1:
        await interaction.response.send_message("❌ Winner count must be at least 1.", ephemeral=True)
        return

    end_time = datetime.utcnow() + timedelta(seconds=seconds)
    embed = discord.Embed(
        title="🎉 Giveaway Started!",
        description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Hosted by", value=interaction.user.mention, inline=False)
    embed.add_field(name="Required Role", value=role.mention if role else "None", inline=False)
    embed.set_footer(text=f"Ends at {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    view = GiveawayView(prize=prize, winners=winners, required_role=role, end_time=end_time)
    message = await interaction.response.send_message(embed=embed, view=view)
    sent = await interaction.original_response()
    view.message = sent
    schedule_giveaway_end(view)

    await interaction.followup.send("✅ Giveaway started! Click the button below to join.", ephemeral=True)


@bot.tree.command(name='give_save', description='Give saves to a user (Admin only)')
@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.describe(member='The member to give saves to', amount='Number of saves to give')
async def slash_give_save(interaction: discord.Interaction, member: discord.Member, amount: int = 1):
    if amount < 1:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
        return
    
    new_saves = counting_bot.give_save(member.id, amount)
    
    embed = discord.Embed(
        title="🎁 Saves Given",
        description=f"Gave {amount} save(s) to {member.mention}",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="New Save Count", value=new_saves, inline=False)
    embed.set_footer(text=f"Given by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='ban', description='Temporarily ban a member for a duration')
@discord.app_commands.checks.has_permissions(ban_members=True)
@discord.app_commands.describe(member='Member to ban', duration='How long to ban them, e.g. 1d, 12h, 30m', reason='Reason for the ban')
async def slash_ban(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = None):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    seconds = parse_duration(duration)
    if seconds is None or seconds <= 0:
        await interaction.response.send_message("❌ Invalid duration. Use formats like `30m`, `1h`, or `1d`.", ephemeral=True)
        return

    try:
        await interaction.guild.ban(member, reason=reason or "Temporary ban", delete_message_days=0)
        await interaction.response.send_message(f"✅ {member.mention} has been banned for {duration}.", ephemeral=True)
        record = ensure_moderation_record(member.id)
        record['bans'] += 1
        record['current_ban_expires'] = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
        save_moderation_data()
        await schedule_unban(interaction.guild, member.id, seconds)
    except Exception as e:
        logger.error(f"Failed to ban user: {e}")
        await interaction.response.send_message("❌ Could not ban that member. Check my permissions.", ephemeral=True)


@bot.tree.command(name='kick', description='Kick a member from the server')
@discord.app_commands.checks.has_permissions(kick_members=True)
@discord.app_commands.describe(member='Member to kick', reason='Reason for the kick')
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    try:
        await interaction.guild.kick(member, reason=reason or "Kicked by moderator")
        await interaction.response.send_message(f"✅ {member.mention} has been kicked.", ephemeral=True)
        record = ensure_moderation_record(member.id)
        record['kicks'] += 1
        save_moderation_data()
    except Exception as e:
        logger.error(f"Failed to kick user: {e}")
        await interaction.response.send_message("❌ Could not kick that member. Check my permissions.", ephemeral=True)


@bot.tree.command(name='mute', description='Mute a member for a duration')
@discord.app_commands.checks.has_permissions(moderate_members=True)
@discord.app_commands.describe(member='Member to mute', duration='How long to mute them, e.g. 10m, 1h, 1d', reason='Reason for the mute')
async def slash_mute(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = None):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    seconds = parse_duration(duration)
    if seconds is None or seconds <= 0:
        await interaction.response.send_message("❌ Invalid duration. Use formats like `30m`, `1h`, or `1d`.", ephemeral=True)
        return

    mute_role = await get_or_create_mute_role(interaction.guild)
    if not mute_role:
        await interaction.response.send_message("❌ Failed to create or find the mute role.", ephemeral=True)
        return

    try:
        await member.add_roles(mute_role, reason=reason or "Temporary mute")
        await schedule_unmute(interaction.guild, member, mute_role, seconds)
        await interaction.response.send_message(f"✅ {member.mention} has been muted for {duration}.", ephemeral=True)
        record = ensure_moderation_record(member.id)
        record['mutes'] += 1
        record['current_mute_expires'] = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
        save_moderation_data()
    except Exception as e:
        logger.error(f"Failed to mute user: {e}")
        await interaction.response.send_message("❌ Could not mute that member. Check my permissions.", ephemeral=True)


@bot.tree.command(name='purge', description='Delete multiple messages from the current channel')
@discord.app_commands.checks.has_permissions(manage_messages=True)
@discord.app_commands.describe(amount='Number of messages to delete (1-100)', reason='Reason for purging')
async def slash_purge(interaction: discord.Interaction, amount: int, reason: str = None):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This command must be used in a server text channel.", ephemeral=True)
        return

    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
        return

    try:
        # Defer the response since bulk delete can take time
        await interaction.response.defer(ephemeral=True)

        # Delete the command message and the specified number of messages
        deleted = await interaction.channel.purge(limit=amount, reason=reason)
        for deleted_message in deleted:
            suppressed_message_delete_ids.add(deleted_message.id)

        # Send confirmation
        embed = discord.Embed(
            title="🗑️ Messages Purged",
            description=f"Successfully deleted {len(deleted)} messages from {interaction.channel.mention}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Purged by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed, ephemeral=True)

        # Log the purge action
        log_embed = discord.Embed(
            title="🗑️ Messages Purged",
            description=f"{interaction.user.mention} purged {len(deleted)} messages in {interaction.channel.mention}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        if reason:
            log_embed.add_field(name="Reason", value=reason, inline=False)
        await send_log(log_embed, 'message')

    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to delete messages in this channel.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.followup.send(f"❌ Failed to purge messages: {e}", ephemeral=True)
    except Exception as e:
        logger.error(f"Failed to purge messages: {e}")
        await interaction.followup.send("❌ An unexpected error occurred while purging messages.", ephemeral=True)


lockdown_group = discord.app_commands.Group(name='lockdown', description='Lockdown controls for channels or the server')

@lockdown_group.command(name='channel', description='Lock or unlock the current channel')
@discord.app_commands.checks.has_permissions(manage_channels=True)
@discord.app_commands.describe(action='lock or unlock the channel')
async def lockdown_channel(interaction: discord.Interaction, action: str):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This command must be used in a server text channel.", ephemeral=True)
        return

    if action.lower() not in ('lock', 'unlock'):
        await interaction.response.send_message("❌ Action must be `lock` or `unlock`.", ephemeral=True)
        return

    lock = action.lower() == 'lock'
    try:
        await set_channel_lockdown(interaction.channel, lock=lock)
        await interaction.response.send_message(f"✅ Channel has been {'locked' if lock else 'unlocked' }.", ephemeral=True)
    except Exception as e:
        logger.error(f"Failed to change channel lockdown status: {e}")
        await interaction.response.send_message("❌ Could not change channel lockdown. Check my permissions.", ephemeral=True)


@lockdown_group.command(name='server', description='Lock or unlock all text channels on the server')
@discord.app_commands.checks.has_permissions(manage_guild=True)
@discord.app_commands.describe(action='lock or unlock the server')
async def lockdown_server(interaction: discord.Interaction, action: str):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    if action.lower() not in ('lock', 'unlock'):
        await interaction.response.send_message("❌ Action must be `lock` or `unlock`.", ephemeral=True)
        return

    lock = action.lower() == 'lock'
    try:
        await set_server_lockdown(interaction.guild, lock=lock)
        await interaction.response.send_message(f"✅ Server has been {'locked' if lock else 'unlocked' }.", ephemeral=True)
    except Exception as e:
        logger.error(f"Failed to change server lockdown status: {e}")
        await interaction.response.send_message("❌ Could not change server lockdown. Check my permissions.", ephemeral=True)


bot.tree.add_command(lockdown_group)


def main():
    """Start the bot"""
    if not TOKEN:
        logger.error("DISCORD_TOKEN not found in .env file")
        return
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
