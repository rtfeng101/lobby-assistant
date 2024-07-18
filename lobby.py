# class structure for lobbies
class Lobby:
    id = 0
    
    def __init__(self, game, start_time, message_id, message, channel_id):
        self.game = game
        self.start_time = start_time
        self.message_id = message_id
        self.message = message
        self.channel_id = channel_id
        self.reactors = []
        self.id = Lobby.id 
        Lobby.id += 1 

    async def update_message(self, bot):
        channel = bot.get_channel(self.channel_id)
        message = await channel.fetch_message(self.message_id)
        
        if self.reactors:
            reactor_names = ', '.join([member.display_name for member in self.reactors])
            await message.edit(content=f"{message.content}\n\nCurrent players: {reactor_names}")
        else:
            await message.edit(content=str(self.message))
            
    async def ping_players(self, bot):
        channel = bot.get_channel(self.channel_id)
        if self.reactors:
            mentions = ' '.join([member.mention for member in self.reactors])
            await channel.send(f"The {self.game} lobby is starting now! {mentions}")