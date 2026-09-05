"""
OpenRouter LLM Provider

Phase 1: Core LLM integration with OpenRouter API.
Handles API calls, retries, and response parsing.
"""

import os
import json
import time
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Optional: requests for HTTP calls
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
    """Raised when rate limited by API"""
    pass


class APIError(LLMError):
    """Raised for general API errors"""
    pass


@dataclass
class LLMResponse:
    """Structured response from LLM"""
    content: str
    model: str
    usage: Optional[Dict] = None
    raw_response: Optional[Dict] = None


class OpenRouterProvider:
    """
    OpenRouter API provider with retry logic and error handling.
    
    Usage:
        provider = OpenRouterProvider()
        response = provider.complete("Hello, world!")
        print(response.content)
    """
    
    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "anthropic/claude-3-haiku"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        Initialize OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key (or env: OPENROUTER_API_KEY)
            model: Model to use (default: anthropic/claude-3-haiku)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for rate limits
        """
        # Get API key
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.model = model or os.environ.get("OPENROUTER_MODEL") or self.DEFAULT_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not REQUESTS_AVAILABLE:
            raise ConfigurationError(
                "requests library required. Install with: pip install requests"
            )
    
    def complete(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """
        Send a prompt to OpenRouter and get completion.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            
        Returns:
            LLMResponse with content and metadata
        """
        # Build messages format
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return self.complete_messages(messages)
    
    def complete_messages(self, messages: List[Dict[str, str]]) -> LLMResponse:
        """
        Send message history to OpenRouter and get completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            LLMResponse with content and metadata
        """
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
        
        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._make_request(headers, payload)
                return response
            except RateLimitError as e:
                last_error = e
                wait_time = self._calculate_backoff(attempt)
                print(f"Rate limited. Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            except APIError as e:
                # Don't retry other API errors
                raise
        
        # All retries exhausted
        raise RateLimitError(
            f"Max retries ({self.max_retries}) exceeded. Last error: {last_error}"
        )
    
    def _make_request(self, headers: Dict, payload: Dict) -> LLMResponse:
        """Make HTTP request to OpenRouter API"""
        url = f"{self.BASE_URL}/chat/completions"
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            # Handle response status
            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            
            if response.status_code == 401:
                raise ConfigurationError("Invalid API key")
            
            if response.status_code == 400:
                error_detail = response.json().get("error", {}).get("message", "Bad request")
                raise APIError(f"Bad request: {error_detail}")
            
            if response.status_code != 200:
                raise APIError(f"API error: {response.status_code} - {response.text}")
            
            # Parse successful response
            data = response.json()
            
            # Extract content from response
            choices = data.get("choices", [])
            if not choices:
                raise APIError("No choices in response")
            
            message = choices[0].get("message", {})
            content = message.get("content", "")
            
            # Handle streaming (not implemented for simplicity)
            
            return LLMResponse(
                content=content,
                model=data.get("model", self.model),
                usage=data.get("usage"),
                raw_response=data
            )
            
        except requests.exceptions.Timeout:
            raise APIError(f"Request timeout after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise APIError(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed: {e}")
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff wait time"""
        base_delay = 1.0  # 1 second base
        max_delay = 60.0  # Cap at 60 seconds
        delay = min(base_delay * (2 ** attempt), max_delay)
        # Add jitter
        import random
        delay += random.uniform(0, 0.5)
        return delay
    
    def validate_config(self) -> bool:
        """
        Validate that the provider is properly configured.
        Returns True if ready, raises ConfigurationError otherwise.
        """
        if not self.api_key:
            raise ConfigurationError("API key not set")
        
        if not self.model:
            raise ConfigurationError("Model not specified")
        
        # Test API connection with a minimal request
        try:
            test_response = self.complete("Hi", system_prompt="You are a helpful assistant.")
            return True
        except Exception as e:
            raise ConfigurationError(f"API connection test failed: {e}")


class JSONParser:
    """
    Utility class for parsing JSON from LLM responses.
    Handles markdown code blocks and malformed JSON.
    """
    
    @staticmethod
    def extract_json(text: str) -> Dict:
        """
        Extract JSON object from text, handling markdown code blocks.
        
        Args:
            text: Raw LLM response text
            
        Returns:
            Parsed JSON dict
            
        Raises:
            ValueError: If no valid JSON found
        """
        # Try direct parse first
        text = text.strip()
        
        # Remove markdown code blocks
        json_patterns = [
            r'```json\s*({\s*.*?})\s*```',  # ```json {...} ```
            r'```\s*({\s*.*?})\s*```',      # ```{ ... } ```
            r'(\{\s*".*?"\s*:)',            # Starts with {
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                json_str = match.group(1) if match.lastindex else match.group(0)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        
        # Try to find any {...} block
        brace_start = text.find('{')
        if brace_start != -1:
            # Find matching closing brace
            depth = 0
            for i, char in enumerate(text[brace_start:], start=brace_start):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[brace_start:i+1])
                        except json.JSONDecodeError:
                            break
        
        raise ValueError(f"No valid JSON found in response: {text[:200]}")


# Convenience function for quick testing
def test_provider() -> bool:
    """Test the OpenRouter provider with a simple prompt"""
    try:
        provider = OpenRouterProvider()
        response = provider.complete("Say 'Hello, Obsidian!' in exactly those words.")
        print(f"✓ Provider working!")
        print(f"  Model: {response.model}")
        print(f"  Response: {response.content}")
        return True
    except ConfigurationError as e:
        print(f"✗ Configuration error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    # Run quick test
    test_provider()
