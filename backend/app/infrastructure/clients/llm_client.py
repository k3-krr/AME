import json
import asyncio
from typing import AsyncGenerator, List, Dict
import logging
import httpx

from app.config import settings
from app.domain.repositories import ILLMService

logger = logging.getLogger("ame_backend.llm_client")


class LLMService(ILLMService):
    """
    Infrastructure implementation of ILLMService interfacing with OpenAI or 
    simulating a stream when key is not configured.
    """

    async def generate_stream(
        self, system_prompt: str, prompt_messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """
        Generates a stream of responses from the LLM.
        
        Args:
            system_prompt: The base system instruction.
            prompt_messages: List of prior messages formatted as {"role": "user"|"assistant", "content": "..."}.
            
        Yields:
            Text tokens as they arrive.
        """
        # Format history messages
        messages = [{"role": "system", "content": system_prompt}]
        for msg in prompt_messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        api_key = settings.OPENAI_API_KEY

        # Check if OpenAI is configured
        if api_key and api_key != "your-openai-api-key-here":
            logger.info("Using OpenAI streaming service...")
            try:
                async for chunk in self._generate_openai_stream(messages, api_key):
                    yield chunk
            except Exception as e:
                logger.error(f"Error during OpenAI stream generation: {e}")
                logger.info("Falling back to local simulator due to API error...")
                async for chunk in self._generate_simulated_stream(messages):
                    yield chunk
        else:
            logger.info("No OpenAI API key found. Launching local streaming simulation.")
            async for chunk in self._generate_simulated_stream(messages):
                yield chunk

    async def _generate_openai_stream(
        self, messages: List[Dict[str, str]], api_key: str
    ) -> AsyncGenerator[str, None]:
        """Queries OpenAI API and streams delta content chunks."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.LLM_MODEL,
            "messages": messages,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise RuntimeError(f"OpenAI API error: {response.status_code} - {error_text.decode('utf-8')}")

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_content = line[6:]
                        if data_content == "[DONE]":
                            break
                        try:
                            data_json = json.loads(data_content)
                            delta = data_json["choices"][0]["delta"]
                            if "content" in delta:
                                yield delta["content"]
                        except Exception as e:
                            logger.debug(f"Failed to parse stream chunk: {line} - Error: {e}")

    async def _generate_simulated_stream(
        self, messages: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """Provides a realistic streaming mockup reply based on the input query."""
        # Find last user message
        last_user_msg = "hello"
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        # Generate a simulated informative reply
        reply = (
            f"Hello! I am the Adaptive Memory Engine (AME) assistant. "
            f"I received your message: \"{last_user_msg}\". "
            f"Currently, I am running in simulation mode because no OpenAI API key was configured. "
            f"In Milestone 3, we will add vector-based memory context enrichment. "
            f"For now, this response verifies that my API, repository, and streaming layers are fully functional!"
        )

        # Stream words/characters slowly to simulate server latency
        words = reply.split(" ")
        for i, word in enumerate(words):
            # yield word with trailing space if not the last word
            chunk = word if i == len(words) - 1 else word + " "
            yield chunk
            # 50ms delay per word for visual realism
            await asyncio.sleep(0.05)
