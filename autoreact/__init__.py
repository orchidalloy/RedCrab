from .autoreact import Autoreact

__red_end_user_data_statement__ = "This cog does not store any user data."

async def setup(bot):
    cog = Autoreact(bot)
    await cog.load_config()
    bot.add_cog(cog)