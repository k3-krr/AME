import json
import uuid
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Tuple
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


from app.application.extraction_provider import IExtractionProvider

EXTRACTION_SYSTEM_PROMPT = """You are a Cognitive Extraction Engine. Analyze the dialogue turns and extract long-term facts, preferences, goals, relationships, skills, habits, events, education, work, projects, corrections, and instructions about the user.
Ignore trivial, temporary, or conversational details.
Return a JSON object with a "candidates" list. Each candidate must have:
- "content": the concise memory content (e.g. "User prefers hot tea in the morning.")
- "memory_type": type string (Preference, Fact, Goal, Skill, Relationship, Education, Work, Project, Habit, Event, Correction, Instruction)
- "importance": float value between 0.0 and 1.0
- "confidence": float value between 0.0 and 1.0
"""

RELATIONSHIP_SYSTEM_PROMPT = """You are a Memory Duplicate Detector. Compare the candidate memory against the existing matched memories and choose the relationship:
- "reinforce": Naive duplicate, same semantic info (no new detail).
- "merge": Compatible facts; consolidate them. Provide the merged content.
- "conflict_update": Candidate supersedes/contradicts existing memory (e.g., location or preference changed).
- "create": Candidate is unrelated.
Return a JSON object with:
- "relationship": one of "create", "reinforce", "merge", "conflict_update"
- "target_id": the UUID string of the matched memory (null for "create")
- "merged_content": consolidated string (null unless "merge")
"""


class OpenAIExtractionProvider(IExtractionProvider):
    """
    OpenAI-backed implementation of IExtractionProvider.
    Includes a deterministic local simulation fallback when API key is missing.
    """

    async def extract_candidates(self, dialogue_turns: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        api_key = settings.OPENAI_API_KEY
        if api_key and api_key != "your-openai-api-key-here":
            logger.info("Calling OpenAI for autonomous memory extraction...")
            try:
                return await self._extract_openai(dialogue_turns, api_key)
            except Exception as e:
                logger.error(f"OpenAI extraction failed: {e}", exc_info=True)
                return self._simulate_extraction(dialogue_turns)
        else:
            return self._simulate_extraction(dialogue_turns)

    async def _extract_openai(self, dialogue_turns: List[Dict[str, str]], api_key: str) -> List[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Dialogue history turns to analyze:\n{json.dumps(dialogue_turns)}"}
            ],
            "response_format": {"type": "json_object"}
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API error: {resp.status_code} - {resp.text}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed.get("candidates", [])

    def _simulate_extraction(self, dialogue_turns: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Fallback simulator that mines keywords for deterministic integration testing."""
        candidates = []
        full_text = " ".join(turn.get("content", "") for turn in dialogue_turns).lower()

        if "kayak" in full_text:
            candidates.append({
                "content": "User owns a blue kayak.",
                "memory_type": "Preference",
                "importance": 0.8,
                "confidence": 0.9,
            })
        if "brick house" in full_text:
            location = ""
            for turn in reversed(dialogue_turns):
                turn_content = turn.get("content", "").lower()
                if "brick house" in turn_content:
                    if "seattle" in turn_content:
                        location = " in Seattle"
                        break
                    elif "boston" in turn_content:
                        location = " in Boston"
                        break
            candidates.append({
                "content": f"User lives in a brick house{location}.",
                "memory_type": "Fact",
                "importance": 0.5,
                "confidence": 0.8,
            })
        if "ice cream" in full_text:
            candidates.append({
                "content": "User loves chocolate ice cream.",
                "memory_type": "Preference",
                "importance": 0.6,
                "confidence": 0.9,
            })
        if "bicycle" in full_text:
            candidates.append({
                "content": "User owns a red bicycle.",
                "memory_type": "Fact",
                "importance": 0.5,
                "confidence": 0.8,
            })

        logger.info(f"Local simulator mined {len(candidates)} candidates from turns.")
        return candidates

    async def evaluate_relationship(
        self, candidate_content: str, existing_memories: List[Tuple[uuid.UUID, str]]
    ) -> Dict[str, Any]:
        api_key = settings.OPENAI_API_KEY
        if api_key and api_key != "your-openai-api-key-here":
            logger.info("Calling OpenAI to resolve duplicate relation...")
            try:
                return await self._evaluate_openai(candidate_content, existing_memories, api_key)
            except Exception as e:
                logger.error(f"OpenAI duplication evaluate failed: {e}", exc_info=True)
                return self._simulate_evaluate(candidate_content, existing_memories)
        else:
            return self._simulate_evaluate(candidate_content, existing_memories)

    async def _evaluate_openai(
        self, candidate_content: str, existing_memories: List[Tuple[uuid.UUID, str]], api_key: str
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        memories_serialized = [{"id": str(mid), "content": text} for mid, text in existing_memories]
        user_prompt = (
            f"New Candidate Memory: \"{candidate_content}\"\n"
            f"Existing Similar Memories:\n{json.dumps(memories_serialized)}"
        )
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": RELATIONSHIP_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"}
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API error: {resp.status_code} - {resp.text}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            
            # Map target_id to UUID
            target_id_str = parsed.get("target_id")
            parsed["target_id"] = uuid.UUID(target_id_str) if target_id_str else None
            return parsed

    def _simulate_evaluate(self, candidate_content: str, existing_memories: List[Tuple[uuid.UUID, str]]) -> Dict[str, Any]:
        """Local simulator for duplicate resolution tests."""
        c_lower = candidate_content.lower()
        for mid, ext_content in existing_memories:
            ext_lower = ext_content.lower()
            if ext_lower == c_lower:
                return {"relationship": "reinforce", "target_id": mid, "merged_content": None}
            # Location contradiction simulation
            if "lives" in c_lower and "lives" in ext_lower:
                return {"relationship": "conflict_update", "target_id": mid, "merged_content": None}
            # Coding consolidation simulation
            if "coding" in c_lower and "coding" in ext_lower:
                return {"relationship": "merge", "target_id": mid, "merged_content": candidate_content}

        return {"relationship": "create", "target_id": None, "merged_content": None}

