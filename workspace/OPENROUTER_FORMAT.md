# OpenRouter API Format

## Endpoint

```
POST https://openrouter.ai/api/v1/chat/completions
```

## Request Format

```python
import requests

url = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": "Bearer sk-or-v1-...",      # API key
    "Content-Type": "application/json",
    "HTTP-Referer": "https://your-site.com",      # Optional, for ranking
    "X-Title": "Your App Name"                   # Optional, for ranking
}

payload = {
    "model": "anthropic/claude-3-haiku",         # Required
    "messages": [                                 # Required
        {
            "role": "system",                     # "system" | "user" | "assistant"
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Hello, how are you?"
        }
    ],
    "temperature": 0.7,                          # Optional, default 1.0
    "max_tokens": 1024,                          # Optional
    "stream": False,                              # Optional, for streaming
    "stop": None,                                 # Optional, stop sequences
    "seed": None,                                 # Optional, for reproducibility
    "top_p": None,                                # Optional, nucleus sampling
    "frequency_penalty": None,                   # Optional
    "presence_penalty": None                     # Optional
}

response = requests.post(url, headers=headers, json=payload)
```

## Response Format

```python
{
    "id": "gen-1234567890",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "I'm doing well, thank you! How can I help you today?"
            },
            "finish_reason": "stop"              # "stop" | "length" | "error"
        }
    ],
    "usage": {
        "prompt_tokens": 25,
        "completion_tokens": 30,
        "total_tokens": 55
    },
    "model": "anthropic/claude-3-haiku",
    "object": "chat.completion"
}
```

## Message Roles

| Role | Purpose | Example |
|------|---------|---------|
| `"system"` | Global instructions | "You are a helpful assistant." |
| `"user"` | User input | "Write hello world to a file" |
| `"assistant"` | Model responses | "I'll help you with that." |

## Available Models

| Model ID | Provider | Cost (in/out per 1M) | Best For |
|----------|----------|---------------------|----------|
| `anthropic/claude-3-haiku` | Anthropic | $0.25 / $1.25 | Fast, cheap tasks |
| `anthropic/claude-3-sonnet` | Anthropic | $3.00 / $15.00 | Balanced |
| `openai/gpt-4-turbo` | OpenAI | $10.00 / $30.00 | Complex reasoning |
| `google/gemini-pro-1.5` | Google | $1.25 / $5.00 | Vision + text |
| `mistralai/mixtral-8x7b` | Mistral | $0.24 / $0.24 | Free tier |

Full list: https://openrouter.ai/models

## Error Responses

```python
# 401 Unauthorized
{"error": {"code": 401, "message": "Invalid API key"}}

# 400 Bad Request  
{"error": {"code": 400, "message": "Invalid request"}}

# 429 Rate Limited
{"error": {"code": 429, "message": "Rate limit exceeded"}}
# Headers: Retry-After: 60

# 500 Server Error
{"error": {"code": 500, "message": "Internal server error"}}
```

## Our Implementation

```python
# agent_core/llm.py

class OpenRouterProvider:
    """OpenRouter API client"""
    
    API_BASE = "https://openrouter.ai/api/v1"
    
    def complete(self, prompt: str, system_prompt: str = None) -> str:
        """Single prompt completion"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return self.complete_messages(messages)
    
    def complete_messages(self, messages: list[dict]) -> str:
        """Message history completion"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://obsidian-ai.local",
            "X-Title": "Obsidian AI Agent"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        response = requests.post(
            f"{self.API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        
        response.raise_for_status()
        data = response.json()
        
        return data["choices"][0]["message"]["content"]
```

## Usage in ReAct Loop

```python
# Build conversation history for multi-turn context

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "Task: Write hello world to test.txt\n\nStep 1..."},
    {"role": "assistant", "content": '{"action": "file_write", ...}'},
    {"role": "user", "content": "Observation: Successfully wrote to test.txt\n\nStep 2..."},
    {"role": "assistant", "content": '{"action": "final", ...}'},
]

response = provider.complete_messages(messages)
```

## Streaming (Optional Enhancement)

```python
# For real-time feedback

payload["stream"] = True

response = requests.post(url, headers=headers, json=payload, stream=True)

for line in response.iter_lines():
    if line:
        data = json.loads(line.decode('utf-8').replace('data: ', ''))
        if data.get("choices"):
            content = data["choices"][0]["delta"].get("content", "")
            print(content, end="", flush=True)
```
