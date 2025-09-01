import aiohttp
from config import OPENROUTER_API_KEY

async def ask_openrouter(model: str, prompt: str):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/justaguy1Bot",
        "X-Title": "Personal AI Bot",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as resp:
            if resp.status == 200:
                result = await resp.json()
                return result['choices'][0]['message']['content']
            else:
                return f"Ошибка: {resp.status}"