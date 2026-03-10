import asyncio
import logging
import time

from twitchio.ext import commands

import config
from claude_client import ClaudeClient
import tts
import stream_listener

# C:\Python39\python.exe -m PyInstaller --clean -y KenjiBot.spec

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
        self._last_reply_time: float = 0.0    # timestamp of last reply
        self._last_listen_time: float = 0.0   # timestamp of last listen cycle
        self._bot_start_time: float = 0.0     # timestamp of when bot connected
        self._ready_announced: bool = True    # whether we've announced readiness

    async def event_ready(self):
        logger.info("Logged in as %s", self.nick)
        logger.info("Connected to channel: %s", config.TWITCH_CHANNEL)
        self._bot_start_time = time.time()
        # Send a greeting to chat on connect
        channel = self.get_channel(config.TWITCH_CHANNEL)
        if channel:
            await channel.send(config.ANNOUNCEMENT_MESSAGE)
        # Start stream listener loop (checks config.STREAM_LISTEN_ENABLED each cycle)
        asyncio.create_task(self._stream_listen_loop())

    async def event_message(self, message):
        # Ignore messages sent by the bot itself
        if message.echo:
            return

        # Dynamic command matching using config.BOT_COMMAND
        content = message.content or ""
        command_trigger = f"!{config.BOT_COMMAND} "
        if content.startswith(command_trigger) or content.strip() == f"!{config.BOT_COMMAND}":
            await self._handle_ask_command(message)
            return

        await self.handle_commands(message)

    async def _handle_ask_command(self, message):
        """Handle !AskBot <message> commands (command name set in config.BOT_COMMAND)."""
        channel = self.get_channel(config.TWITCH_CHANNEL)

        # ── Global cooldown check ──
        now = time.time()
        elapsed = now - self._last_reply_time
        if elapsed < config.KENJI_COOLDOWN:
            remaining = int(config.KENJI_COOLDOWN - elapsed)
            mins, secs = divmod(remaining, 60)
            if channel:
                await channel.send(
                    f"Hold on, I need to recover after that last interaction... "
                    f"({mins}m {secs}s remaining)"
                )
            return

        content = message.content or ""
        command_trigger = f"!{config.BOT_COMMAND} "
        prefix_len = len(command_trigger)
        if len(content) <= prefix_len:
            if channel:
                await channel.send(
                    f"You need to say something! Usage: !{config.BOT_COMMAND} <message>"
                )
            return

        message_text = content[prefix_len:]
        user_name = message.author.display_name

        logger.info("Message from %s: %s", user_name, message_text)

        try:
            reply = await self.claude.get_response(user_name, message_text)
            logger.info("Reply: %s", reply)

            # Send reply to chat if enabled, and play TTS
            if config.CHAT_REPLIES_ENABLED and channel:
                await channel.send(reply)
            await tts.speak(reply)

            # Mark cooldown and schedule the ready announcement
            self._last_reply_time = time.time()
            self._ready_announced = False
            asyncio.create_task(self._announce_ready())
        except Exception:
            logger.exception("Error handling !%s command", config.BOT_COMMAND)
            if channel:
                await channel.send(
                    "Kenji is... unavailable right now. The feminists may be jamming his signal."
                )

    async def _announce_ready(self):
        """Wait for the cooldown to expire, then announce readiness in chat."""
        await asyncio.sleep(config.KENJI_COOLDOWN)
        if not self._ready_announced:
            self._ready_announced = True
            channel = self.get_channel(config.TWITCH_CHANNEL)
            if channel:
                await channel.send("*adjusts glasses* Ready for another comment or question")

    async def _stream_listen_loop(self):
        """Background loop: record system audio, transcribe, and react."""
        logger.info("Stream listener loop started (every %ds, recording %ds)",
                     config.LISTEN_INTERVAL, config.LISTEN_DURATION)
        while True:
            try:
                # Sleep in 1-second increments so GUI changes take effect immediately
                waited = 0
                while waited < config.LISTEN_INTERVAL:
                    await asyncio.sleep(1)
                    waited += 1

                # Check if listener is still enabled (can be toggled via GUI)
                if not config.STREAM_LISTEN_ENABLED:
                    logger.info("Stream listener disabled, skipping cycle.")
                    continue

                logger.info("Stream listener woke up, starting listen cycle...")
                self._last_listen_time = time.time()
                transcription = await stream_listener.listen_and_transcribe()
                if not transcription:
                    continue

                logger.info("Stream heard: %s", transcription[:200])
                reaction = await self.claude.get_stream_reaction(transcription)
                logger.info("Kenji stream reaction: %s", reaction)

                channel = self.get_channel(config.TWITCH_CHANNEL)
                if channel and config.CHAT_REPLIES_ENABLED:
                    await channel.send(reaction)
                    await tts.speak(reaction)
            except Exception:
                logger.exception("Error in stream listen loop")


def main():
    bot = KenjiBot()
    bot.run()


if __name__ == "__main__":
    main()
