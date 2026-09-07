"""
OpenRouter LLM Provider with Native Tool Calling + Fallback

Phase 1 Updated: Uses OpenRouter's native function calling API with
fallback to JSON parsing for models that don't support function calling.
Fix: transient connection errors/timeouts/5xx now retry properly instead
of being wrapped as APIError and failing immediately.
"""

import os
import json
import time
import re
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class LLMError(Exception):
    """Base exception for LLM-related errors"""
    pass


class ConfigurationError(LLMError):
    """Raised when API key or config is missing/invalid"""
    pass


class RateLimitError(LLMError):
    """Raised when rate limited by API. Retried with backoff."""
    pass


class ConnectionIssueError(LLMError):
    """Raised for transient network problems (timeout, connection reset, 5xx). Retried with backoff."""
    pass


class APIError(LLMError):
    """General, non-transient API errors (bad request, etc). NOT retried."""
    pass


class FunctionCallingNotSupported(LLMError):
    """Raised when model doesn't support function calling"""
    pass


@dataclass
class LLMResponse:
    """Structured response from LLM"""
    content: Optional[str] = None
    tool_calls: List[Dict] = field(default_factory=list)
    model: str = ""
    usage: Optional[Dict] = None
    raw_response: Optional[Dict] = None
    finish_reason: str = ""


@dataclass
class ToolCall:
    """Represents a single tool call from LLM"""
    id: str
    name: str
    arguments: Dict[str, Any]

    def __str__(self):
        return f"ToolCall({self.name}, args={self.arguments})"


@dataclass
class ToolDefinition:
    """OpenAI-style tool definition for function calling"""
    name: str
    description: str
    parameters: Dict[str, Any]


class JSONParser:
    """Utility for parsing JSON from LLM responses (fallback mode)"""

    @staticmethod
    def extract_json(text: Any) -> Dict:
        if text is None:
            raise ValueError("Cannot extract JSON from None")

        if not isinstance(text, str):
            text = str(text)

        text = text.strip()

        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
        ]

        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        start = text.find('{')
        end = text.rfind('}') + 1

        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"No valid JSON found: {str(text)[:100]}")

    @staticmethod
    def is_json(text: str) -> bool:
        if not text:
            return False
        text = text.strip()
        return text.startswith('{') or '{' in text


class OpenRouterProvider:
    """
    OpenRouter API provider with native tool calling support.

    Supports two modes:
    1. Native function calling (preferred, if model supports it)
    2. JSON parsing fallback (for models that don't support function calling)
    """

    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "anthropic/claude-3-haiku"

    FUNCTION_CALLING_MODELS = [
        "gpt-4",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "claude-3-opus",
        "claude-3-sonnet",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: int = 60,
        max_retries: int = 3,
        force_fallback: bool = False
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY environment variable."
            )

        self.model = model or os.environ.get("OPENROUTER_MODEL") or self.DEFAULT_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

        self._use_native_tools = not force_fallback and self._supports_function_calling()

        self._messages: List[Dict] = []

        if not REQUESTS_AVAILABLE:
            raise ConfigurationError("requests library required")

    def _supports_function_calling(self) -> bool:
        model_lower = self.model.lower()
        for supported in self.FUNCTION_CALLING_MODELS:
            if supported in model_lower:
                return True
        return False

    def reset_conversation(self):
        self._messages = []

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> LLMResponse:
        """Simple completion without tools."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self._request(messages)

    def complete_with_tools(
        self,
        prompt: str,
        tools: List[ToolDefinition],
        system_prompt: Optional[str] = None,
        reset: bool = True
    ) -> LLMResponse:
        if reset:
            self._messages = []

        if system_prompt and not self._messages:
            self._messages.append({"role": "system", "content": system_prompt})

        self._messages.append({"role": "user", "content": prompt})

        openai_tools = [self._tool_to_dict(t) for t in tools]

        if self._use_native_tools:
            return self._request_with_native_tools(self._messages, openai_tools)
        else:
            return self._request_with_json_fallback(self._messages, openai_tools)

    def add_tool_result(self, tool_call_id: str, result: str):
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(result)
        })

    def continue_conversation(self, tools: List[ToolDefinition] = None) -> LLMResponse:
        if self._use_native_tools:
            openai_tools = [self._tool_to_dict(t) for t in tools] if tools else None
            return self._request_with_native_tools(self._messages, tools=openai_tools)
        else:
            return self._request_with_json_fallback(self._messages)

    def _tool_to_dict(self, tool: ToolDefinition) -> Dict:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        }

    def _request(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> LLMResponse:
        """Core request method with retry. Retries rate limits AND transient connection issues."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://obsidian-ai.local",
            "X-Title": "Obsidian AI"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        if tools:
            payload["tools"] = tools

        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self._make_request(headers, payload)
            except (RateLimitError, ConnectionIssueError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    print(f"{type(e).__name__}: {e}. Retrying ({attempt + 1}/{self.max_retries})...")
                    time.sleep(self._calculate_backoff(attempt))
                else:
                    raise

    def _request_with_native_tools(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None
    ) -> LLMResponse:
        try:
            return self._request(messages, tools)
        except APIError as e:
            if "tool" in str(e).lower() or "function" in str(e).lower():
                self._use_native_tools = False
                return self._request_with_json_fallback(messages)
            raise

    def _request_with_json_fallback(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None
    ) -> LLMResponse:
        """Fallback: Use JSON parsing instead of native function calling."""
        enhanced_messages = self._inject_tool_instructions(messages, tools)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://obsidian-ai.local",
            "X-Title": "Obsidian AI"
        }

        payload = {
            "model": self.model,
            "messages": enhanced_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._make_raw_request(headers, payload)
                return self._parse_json_fallback_response(response)
            except (RateLimitError, ConnectionIssueError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    print(f"{type(e).__name__}: {e}. Retrying ({attempt + 1}/{self.max_retries})...")
                    time.sleep(self._calculate_backoff(attempt))
                else:
                    raise

    def _inject_tool_instructions(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None
    ) -> List[Dict]:
        if not tools:
            return messages

        tool_descriptions = []
        for t in tools:
            func = t.get("function", {})
            name = func.get("name", "")
            desc = func.get("description", "")
            params = func.get("parameters", {}).get("properties", {})

            param_str = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in params.items())
            tool_descriptions.append(f"- {name}({param_str}): {desc}")

        tools_text = "\n".join(tool_descriptions)

        new_messages = []
        has_system = False

        for msg in messages:
            if msg.get("role") == "system":
                has_system = True
                new_messages.append({
                    "role": "system",
                    "content": msg["content"] + f"\n\nAVAILABLE TOOLS:\n{tools_text}\n\nWhen you need to use a tool, respond with ONLY this JSON format:\n{{\"action\": \"tool_name\", \"action_input\": {{\"param\": \"value\"}}}}\n\nWhen done, respond with:\n{{\"action\": \"final\", \"content\": \"your answer\"}}"
                })
            else:
                new_messages.append(msg)

        if not has_system:
            new_messages.insert(0, {
                "role": "system",
                "content": f"You have access to these tools:\n{tools_text}\n\nWhen you need to use a tool, respond with ONLY this JSON format:\n{{\"action\": \"tool_name\", \"action_input\": {{\"param\": \"value\"}}}}\n\nWhen done, respond with:\n{{\"action\": \"final\", \"content\": \"your answer\"}}"
            })

        return new_messages

    def _parse_json_fallback_response(self, data: Dict) -> LLMResponse:
        choices = data.get("choices", [])
        if not choices:
            raise APIError("No choices in response")

        choice = choices[0]
        message = choice.get("message", {})

        content = message.get("content")
        if content is not None and not isinstance(content, str):
            content = str(content)

        tool_calls = []

        if content:
            try:
                parsed = JSONParser.extract_json(content)
                action = parsed.get("action", "")

                if action == "final":
                    return LLMResponse(
                        content=str(parsed.get("content", content)),
                        tool_calls=[],
                        model=data.get("model", self.model),
                        usage=data.get("usage"),
                        raw_response=data,
                        finish_reason="stop"
                    )

                if action and action != "final":
                    import uuid
                    tool_calls.append(ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name=action,
                        arguments=parsed.get("action_input", {})
                    ))

                    return LLMResponse(
                        content=None,
                        tool_calls=tool_calls,
                        model=data.get("model", self.model),
                        usage=data.get("usage"),
                        raw_response=data,
                        finish_reason="tool_calls"
                    )
            except (ValueError, json.JSONDecodeError):
                pass

        return LLMResponse(
            content=content,
            tool_calls=[],
            model=data.get("model", self.model),
            usage=data.get("usage"),
            raw_response=data,
            finish_reason=choice.get("finish_reason", "stop")
        )

    def _make_request(self, headers: Dict, payload: Dict) -> LLMResponse:
        """Make HTTP request. Transient failures raise ConnectionIssueError (retried)."""
        url = f"{self.BASE_URL}/chat/completions"

        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=self.timeout
            )

            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            if response.status_code == 401:
                raise ConfigurationError("Invalid API key")
            if response.status_code == 400:
                error = response.json().get("error", {})
                raise APIError(f"Bad request: {error.get('message', 'Unknown')}")
            if response.status_code in (500, 502, 503, 504):
                raise ConnectionIssueError(f"Server error: {response.status_code}")
            if response.status_code != 200:
                raise APIError(f"API error: {response.status_code}")

            return self._parse_response(response.json())

        except requests.exceptions.Timeout:
            raise ConnectionIssueError(f"Timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise ConnectionIssueError(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            raise ConnectionIssueError(f"Request failed: {e}")

    def _make_raw_request(self, headers: Dict, payload: Dict) -> Dict:
        """Make raw HTTP request, return JSON. Transient failures raise ConnectionIssueError (retried)."""
        url = f"{self.BASE_URL}/chat/completions"

        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=self.timeout
            )

            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            if response.status_code == 401:
                raise ConfigurationError("Invalid API key")
            if response.status_code in (500, 502, 503, 504):
                raise ConnectionIssueError(f"Server error: {response.status_code}")
            if response.status_code != 200:
                raise APIError(f"API error: {response.status_code} - {response.text[:200]}")

            return response.json()

        except requests.exceptions.Timeout:
            raise ConnectionIssueError(f"Timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise ConnectionIssueError(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            raise ConnectionIssueError(f"Request failed: {e}")

    def _parse_response(self, data: Dict) -> LLMResponse:
        choices = data.get("choices", [])
        if not choices:
            raise APIError("No choices in response")

        choice = choices[0]
        message = choice.get("message", {})

        tool_calls = []
        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=func.get("name", ""),
                arguments=json.loads(func.get("arguments", "{}"))
            ))

        content = message.get("content")
        if content is not None and not isinstance(content, str):
            content = str(content)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model=data.get("model", self.model),
            usage=data.get("usage"),
            raw_response=data,
            finish_reason=choice.get("finish_reason", "")
        )

    def _calculate_backoff(self, attempt: int) -> float:
        delay = min(1.0 * (2 ** attempt), 60.0)
        import random
        return delay + random.uniform(0, 0.5)


def test_provider() -> bool:
    try:
        provider = OpenRouterProvider()
        response = provider.complete("Say 'Test passed'")
        print(f"Provider working: {response.content}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    test_provider()
