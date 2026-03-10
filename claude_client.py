import anthropic
import config


class ClaudeClient:
    """Wrapper around the Anthropic Claude API for the Kenji character."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        self.system_prompt = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        with open(config.PROMPT_FILE, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
        # Inject the current Twitch channel name and description into the prompt
        prompt = prompt.replace("{TWITCH_CHANNEL}", config.TWITCH_CHANNEL)
        prompt = prompt.replace("{TWITCH_DESCRIPTION}", config.TWITCH_DESCRIPTION)
        return prompt

    async def get_response(self, user_name: str, message: str) -> str:
        """Send a chatter's message to Claude and return Kenji's reply.

        Args:
            user_name: The Twitch display name of the chatter.
            message: The text that followed ``!Kenji``.

        Returns:
            Kenji's reply, truncated to fit a single Twitch chat message.
        """
        user_message = f"[Message from chatter '{user_name}']: {message}"

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": user_message},
            ],
        )

        reply = response.content[0].text

        # If Claude hit the token limit, trim to the last complete sentence
        if response.stop_reason == "max_tokens":
            reply = self._trim_to_last_sentence(reply)

        # Twitch chat messages are limited to 500 characters
        if len(reply) > 500:
            reply = reply[:497] + "..."

        return reply

    async def get_stream_reaction(self, transcription: str) -> str:
        """Send overheard stream audio transcription to Claude for a Kenji reaction.

        Args:
            transcription: The transcribed text from stream audio.

        Returns:
            Kenji's reaction to what he overheard.
        """
        user_message = (
            f"[You just overheard the following on the stream]: {transcription}\n"
            f"React to what you heard as Kenji would. You are eavesdropping and "
            f"commenting on what you heard. Keep it brief."
        )

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": user_message},
            ],
        )

        reply = response.content[0].text

        if response.stop_reason == "max_tokens":
            reply = self._trim_to_last_sentence(reply)

        if len(reply) > 500:
            reply = reply[:497] + "..."

        return reply

    @staticmethod
    def _trim_to_last_sentence(text: str) -> str:
        """Trim text to the last sentence that ends with punctuation."""
        # Find the last sentence-ending punctuation
        last_period = text.rfind(".")
        last_exclaim = text.rfind("!")
        last_question = text.rfind("?")
        cut = max(last_period, last_exclaim, last_question)
        if cut > 0:
            return text[: cut + 1]
        return text

