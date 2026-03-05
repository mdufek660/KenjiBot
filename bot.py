import asyncio
import logging
import time

from twitchio.ext import commands

import config
from claude_client import ClaudeClient
import tts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-18s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("kenji.bot")


class KenjiBot(commands.Bot):
    """Twitch chat bot that responds as the character Kenji Setou."""

    def __init__(self):
        super().__init__(
            token=config.TWITCH_ACCESS_TOKEN,
            prefix="!",
            initial_channels=[config.TWITCH_CHANNEL],
        )
        self.claude = ClaudeClient()
        self._last_reply_time: float = 0.0  # timestamp of last reply
        self._ready_announced: bool = True  # whether we've announced readiness

    async def event_ready(self):
        logger.info("Logged in as %s", self.nick)
        logger.info("Connected to channel: %s", config.TWITCH_CHANNEL)
        # Send a greeting to chat on connect
        channel = self.get_channel(config.TWITCH_CHANNEL)
        if channel:
            await channel.send("Never fear, KenjiBot is here!")

    async def event_message(self, message):
        # Ignore messages sent by the bot itself
        if message.echo:
            return
        await self.handle_commands(message)

    @commands.command(name="Kenji")
    async def kenji_command(self, ctx: commands.Context):
        """Handle !Kenji <message> commands."""
        # ── Global cooldown check (10 min between replies) ──
        now = time.time()
        elapsed = now - self._last_reply_time
        if elapsed < config.KENJI_COOLDOWN:
            remaining = int(config.KENJI_COOLDOWN - elapsed)
            mins, secs = divmod(remaining, 60)
            await ctx.send(
                f"Hold on, I need to recover after that last interaction... "
                f"({mins}m {secs}s remaining)"
            )
            return

        user_message = ctx.message.content
        # Strip the command prefix + command name to get the actual message
        # e.g. "!Kenji hello there" -> "hello there"
        prefix_len = len("!Kenji ")
        if len(user_message) <= prefix_len:
            await ctx.send("You need to say something to Kenji! Usage: !Kenji <message>")
            return

        message_text = user_message[prefix_len:]
        user_name = ctx.author.display_name

        logger.info("Message from %s: %s", user_name, message_text)

        try:
            reply = await self.claude.get_response(user_name, message_text)
            logger.info("Kenji reply: %s", reply)

            # Send reply to chat (DEBUG – remove later) and play TTS
            await ctx.send(reply)
            await tts.speak(reply)

            # Mark cooldown and schedule the ready announcement
            self._last_reply_time = time.time()
            self._ready_announced = False
            asyncio.create_task(self._announce_ready())
        except Exception:
            logger.exception("Error handling !Kenji command")
            await ctx.send("Kenji is... unavailable right now. The feminists may be jamming his signal.")

    async def _announce_ready(self):
        """Wait for the cooldown to expire, then announce readiness in chat."""
        await asyncio.sleep(config.KENJI_COOLDOWN)
        if not self._ready_announced:
            self._ready_announced = True
            channel = self.get_channel(config.TWITCH_CHANNEL)
            if channel:
                await channel.send("*adjusts glasses* Ready for another comment or question")


def main():
    bot = KenjiBot()
    bot.run()


if __name__ == "__main__":
    main()
