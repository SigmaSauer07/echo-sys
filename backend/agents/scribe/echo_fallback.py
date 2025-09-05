import requests

def ask_echo(prompt: str) -> str:
    """
    Fallback: Call Echo directly if Ollama fails.
    You can use OpenRouter or your existing API key here.
    """
    # Example with OpenRouter (replace YOUR_KEY)
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": "Bearer YOUR_KEY",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o",  # or your preferred Echo model
        "messages": [
            {"role": "system", "content": "You are Echo, write exactly like the narrator for the Book of Alsania."},
            {"role": "user", "content": prompt}
        ]
    }

    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
