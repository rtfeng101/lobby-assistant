import discord
import json
import re
import random
import asyncio
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from lobby import Lobby

with open('config.json') as config_file:
    config = json.load(config_file)

BOT_TOKEN = config['token']
CHANNEL_ID = config['channel_id']
bot = commands.Bot(command_prefix = "$", intents = discord.Intents.all())

# array of active lobbies
active_lobbies = []

# array of emotes
EMOTES = ["👍", "🎮", "🔥", "🚀", "✨", "🕹️", "🏆", "🎲"]

"""
Startup
"""
@bot.event
async def on_ready():
    print("On standby")
    channel = bot.get_channel(CHANNEL_ID)
    await channel.send("On standby")
    if not lobby_checker.is_running():
        lobby_checker.start()  # start the background task
        print("Lobby checker task started")
    if not inactivity_checker.is_running():
        inactivity_checker.start()  # start the inactivity checker task
        print("Inactivity checker task started")

"""
Randomizes games using weighted probabilities using input pairs <game> <probability> ...
Or equally randomizes games using the input <game> <game> ...
"""
@bot.command(name = "pickgame")
async def pick_game(ctx, *args):
    # input check
    if not args:
        await ctx.send("Please provide at least one game name, or pairs of game names and their probabilities.")
        return
    
    games = []
    probabilities = []
    
    # check if input is game-probability pairs to use normalized weighted probabilities
    if len(args) % 2 == 0 and all(is_float(args[i + 1]) for i in range(0, len(args), 2)):
        # create game probability array pairs
        for i in range(0, len(args), 2):
            game = args[i]
            probability = float(args[i + 1])
            
            # probability check
            if probability <= 0:
                await ctx.send("Probability values must be greater than zero.")
                return
            
            games.append(game)
            probabilities.append(probability)
        
        # choose the game using weighted probabilities
        chosen_game = random.choices(games, weights=probabilities, k=1)[0]
    
    # else use equal probabilities
    else:
        games = list(args)
        
        # choose the game using equal probabilities        
        chosen_game = random.choice(games)

    # sending initial message
    message = await ctx.send("The selected game is: ")
    
    # simulate roulette effect through editing a message
    last_game = None
    for _ in range(5): # how many rolls
        while True:
            current_game = random.choice(games)
            if current_game != last_game:
                break
        current_game = random.choice(games)
        # edit message
        await message.edit(content=f"The selected game is: {current_game}")
        await asyncio.sleep(0.3)  # roll speed
    
    # final result
    await message.edit(content=f":sparkles: The selected game is: {chosen_game} :sparkles:")

"""
Starts a lobby using the input <game> <now or hr:mn am/pm>
Players join lobby using reactions on an initial lobby announcement message
Players are pinged when it is time for the lobby to start through an alert message
"""
@bot.command(name = "startlobby")
async def start_lobby(ctx, *args):    
    # input check
    if len(args) != 2:
        await ctx.send("Invalid input. Use the format: `$startlobby <game> <time>`")
        return

    game, time = args
    
    # get the current time
    now = datetime.now()

    if time.lower() == "now":
        time_message = "now"
        start_time = now
    else:
        # match time in hh:mm AM/PM format
        match = re.match(r'(\d+):(\d+)\s?(AM|PM|am|pm)', time)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            period = match.group(3).upper()

            # adjust for 24 hour time system
            if period == 'PM' and hours != 12:
                hours += 12
            if period == 'AM' and hours == 12:
                hours = 0

            start_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            
            # if the time is in the past, assume it's for the next day
            if start_time < now:
                start_time += timedelta(days=1)

            time_message = f"at {hours % 12}:{minutes:02d} {period}"
        else:
            await ctx.send("Invalid time format. Please use 'xx:xx AM/PM' or 'now'.")
            return
    
    # create lobby object with a placeholder for message_id and message
    lobby = Lobby(game, start_time, message_id = None, message = None, channel_id = ctx.channel.id)
    active_lobbies.append(lobby)

    # send the lobby message including the lobby ID (created by lobby object)
    lobby_message = await ctx.send(f'{game} lobby (ID: {lobby.id}) starting {time_message}! React to join!')
    
    # update the lobby object with the actual message ID and message content
    lobby.message_id = lobby_message.id
    lobby.message = lobby_message.content

    # add a reaction for user quality of life
    random_emote = random.choice(EMOTES)
    await lobby_message.add_reaction(random_emote)

    # lobby function to add names of players
    await lobby.update_message(bot)
    

"""
Stops a lobby using the unique lobby id
Displays message if removal was successful
"""
@bot.command(name = "stoplobby")
async def stop_lobby(ctx, *args):
    # input check
    if len(args) != 1:
        await ctx.send("Invalid input. Use the format: `$stoplobby <ID>`")
        return

    id = args[0]
    
    if not re.fullmatch(r"-?\d+", id):
        await ctx.send("Invalid ID format. ID should be an integer.")
        return

    # integer for comparison
    id = int(id) 
    
    # check all lobbies for matching id (O(n))
    for lobby in active_lobbies:
        if lobby.id == id:
            active_lobbies.remove(lobby)
            await ctx.send(f"Lobby {id} removed.")
            return

    # if no lobby is found
    await ctx.send(f"Lobby {id} does not exist.")
    

"""
Displays all active lobbies using embed
Includes info about game, start time, and players
"""
@bot.command(name = "listlobbies")
async def list_lobbies(ctx):
    # no active lobbies
    if not active_lobbies:
        await ctx.send("There are no active lobbies.")
        return
    
    # active lobbies displayed using embed
    embed = discord.Embed(title="Active Lobbies", color = discord.Color.blue())
    
    # for each lobby add the relevant embed info
    for lobby in active_lobbies:
        start_time_str = lobby.start_time.strftime("%Y-%m-%d %I:%M %p")
        reactor_names = ', '.join([member.display_name for member in lobby.reactors])
        channel = bot.get_channel(lobby.channel_id)
        embed.add_field(name=lobby.game, value=f"""Start Time: {start_time_str}\n
                        Players: {reactor_names}\n
                        Channel: {channel.mention}\nID: {lobby.id}""", inline=False)
    
    await ctx.send(embed=embed)
    

"""
Moves all players in a lobby to an empty voice channel if one is available
"""
@bot.command(name="clearcomms")
async def clear_comms(ctx, *args):
    # input check
    if (len(args) != 1):
        await ctx.send("Invalid input. Use the format: `$clearcomms <ID>`")
        
    lobby_id = args
    
    # find the lobby with the given ID
    lobby = next((lobby for lobby in active_lobbies if lobby.id == lobby_id), None)
    
    if not lobby:
        await ctx.send(f"Lobby with ID {lobby_id} not found.")
        return
    
    # find an empty voice channel
    guild = ctx.guild
    empty_channel = next((channel for channel in guild.voice_channels if len(channel.members) == 0), None)
    
    if not empty_channel:
        await ctx.send("No empty voice channels available.")
        return
    
    # move all players in the lobby to the empty voice channel
    for member in lobby.reactors:
        if member.voice:
            await member.move_to(empty_channel)
    
    await ctx.send(f"All players in lobby {lobby_id} have been moved to {empty_channel.name}.")
    
    
"""
Handles voice state updates to remove empty lobbies and update last activity
"""
@bot.event
async def on_voice_state_update(member, before, after):
    # check if the member joined or left a voice channel
    for lobby in active_lobbies:
        if member in lobby.reactors:
            if before.channel is None and after.channel is not None:
                # member joined a voice channel
                lobby.last_voice_activity = datetime.now()
                
            elif before.channel is not None and after.channel is None:
                # member left a voice channel
                all_members_left = all(not m.voice or not m.voice.channel for m in lobby.reactors)
                if all_members_left:
                    lobby.last_voice_activity = datetime.now()
                    
            break
    
"""
Background task to check lobbies and ping players once at the start time
"""
@tasks.loop(seconds=60)  # check every minute
async def lobby_checker():
    now = datetime.now()
    
    # ping players belonging to starting lobbies
    for lobby in active_lobbies:
        if now >= lobby.start_time and lobby.pinged == False:
            lobby.pinged = True
            await lobby.ping_players(bot)
            
"""
Background task to check for inactive lobbies and removes them from the active list
Wait time: 5 mins
"""
@tasks.loop(seconds=60)  # check every minute
async def inactivity_checker():
    now = datetime.now()
    
    # close lobbies that have been idle for 5 mins
    for lobby in active_lobbies:
        all_members_inactive = all(not m.voice or not m.voice.channel for m in lobby.reactors)
        if all_members_inactive and (now - lobby.last_voice_activity).total_seconds() > 300:
            active_lobbies.remove(lobby)
            await bot.get_channel(lobby.channel_id).send(f"Lobby {lobby.id} has been removed due to inactivity.")

"""
Updates lobby message on reaction add
"""
@bot.event
async def on_raw_reaction_add(payload):
    # ignore reactions from bot (self)
    if payload.user_id == bot.user.id:
        return
    
    # for any reaction belonging to a lobby message (message_id)
    for lobby in active_lobbies:
        if payload.message_id == lobby.message_id and payload.channel_id == lobby.channel_id:
            # get the user
            guild = bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            
            # if user is not stored as a reactor, add them
            if member and member not in lobby.reactors:
                lobby.reactors.append(member)
                await lobby.update_message(bot)

"""
Updates lobby message on reaction remove
"""
@bot.event
async def on_raw_reaction_remove(payload):
    # ignore reactions from bot (self)
    if payload.user_id == bot.user.id:
        return  
    
    # for any reaction belonging to a lobby message (message_id)
    for lobby in active_lobbies:
        if payload.message_id == lobby.message_id and payload.channel_id == lobby.channel_id:
            # get the user
            guild = bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            
            # if user is stored as a reactor, remove them
            if member and member in lobby.reactors:
                lobby.reactors.remove(member)
                await lobby.update_message(bot)
        
"""
Helper function for pick_game() in order to determine which mode to roulette in
"""        
def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False
                
bot.run(BOT_TOKEN)