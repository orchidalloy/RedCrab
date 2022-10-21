import discord
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from discord.ext import tasks
from redbot.core import commands, Config
from redbot.core.bot import Red
from typing import *

log = logging.getLogger("red.crab-cogs.gamealert")

@dataclass(init=True, order=True)
class Alert(dict):
    game_name: str
    response: str
    delay_minutes: int
    channel_id: int


class GameAlert(commands.Cog):
    """Sends a configured message when a user has been playing a specific game for too long."""

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=6761656165)
        self.alerts: Dict[int, List[Alert]] = {}
        self.alerted: List[int] = []
        self.config.register_guild(alerts=[])

    async def load_config(self):
        all_config = await self.config.all_guilds()
        self.alerts = {guild_id: conf['alerts'] for guild_id, conf in all_config.items()}

    async def red_delete_data_for_user(self, requester: str, user_id: int):
        pass

    # Loop

    @tasks.loop(seconds=15)
    async def alert_loop(self):
        for guild in self.bot.guilds:
            if guild.id not in self.alerts:
                continue
            if await self.bot.cog_disabled_in_guild(self, guild):
                continue
            for member in guild.members:
                if member.activity:
                    log.debug(f"{member.activity.name} {datetime.utcnow() - member.activity.start}")
                    alert = next(iter(a for a in self.alerts[guild.id] if a.game_name == member.activity.name), None)
                    if alert and (datetime.utcnow() - member.activity.start) > timedelta.min(alert.delay_minutes):
                        if member.id in self.alerted or not await self.bot.allowed_by_whitelist_blacklist(member):
                            continue
                        channel = guild.get_channel(alert.channel_id)
                        message = alert.response\
                            .replace("{user}", member.nick)\
                            .replace("{mention}", member.mention)
                        try:
                            await channel.send(message)
                            self.alerted.append(member.id)
                        except Exception as error:
                            log.warning(f"Failed to send game alert in {alert.channel_id} - {type(error).__name__}: {error}", exc_info=True)
                elif member.id in self.alerted:
                    self.alerted.remove(member.id)

    # Commands

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def gamealert(self, ctx: commands.Context):
        """Send a message when someone is playing a game too long."""
        await ctx.send_help()

    @gamealert.command()
    @commands.has_permissions(manage_guild=True)
    async def add(self, ctx: commands.Context, game: str, delay: int, *, message: str):
        """Add a new game alert to this channel. Usage:
        `[p]gamealert add \"game\" <delay in minutes> <message>`
        The message may contain {user} or {mention}"""
        if len(message) > 1000:
            await ctx.send("Sorry, the message may not be longer than 1000 characters.")
            return
        async with self.config.guild(ctx.guild).alerts() as alerts:
            alert = Alert(game, message, max(delay, 0), ctx.channel.id)
            old_alert = [a for a in alerts if a.game_name == alert.game_name]
            for a in old_alert:
                alerts.remove(a)
            alerts.append(alert)
            self.alerts[ctx.guild.id] = list(alerts)
            await ctx.react_quietly("✅")

    @gamealert.command()
    @commands.has_permissions(manage_guild=True)
    async def remove(self, ctx: commands.Context, *, game: str):
        """Remove an existing game alert by its game name."""
        async with self.config.guild(ctx.guild).autoreacts() as alerts:
            old_alert = [a for a in alerts if a.game_name == game]
            for a in old_alert:
                alerts.remove(a)
            self.alerts[ctx.guild.id] = list(alerts)
            if old_alert:
                await ctx.react_quietly("✅")
            else:
                await ctx.send("No alerts found for that game.")

    @gamealert.command()
    async def list(self, ctx: commands.Context, page: int = 1):
        """Shows all game alerts."""
        embed = discord.Embed(title="Server Game Alerts", color=await ctx.embed_color(), description="None")
        embed.set_footer(text=f"Page {page}")
        if ctx.guild.id in self.alerts and self.alerts[ctx.guild.id]:
            alerts = [f"- {alert.game_name} in <#{alert.channel_id}> after {alert.delay_minutes} minutes"
                          for alert in self.alerts[ctx.guild.id]]
            alerts = alerts[10*(page-1):10*page]
            if alerts:
                embed.description = '\n'.join(alerts)
        await ctx.send(embed=embed)

    @gamealert.command()
    async def show(self, ctx: commands.Context, *, game: str):
        """Shows the message for an alert for a game."""
        alert = None
        if ctx.guild.id in self.alerts and self.alerts[ctx.guild.id]:
            alerts = [a for a in self.alerts[ctx.guild.id] if a.game_name == game]
            if alerts:
                alert = alerts[0]
        await ctx.send(f"```\n{alert.response}```" if alert else "No alert found for that game.")
