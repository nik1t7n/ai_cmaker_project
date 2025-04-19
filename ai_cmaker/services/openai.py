import asyncio
import os

from dotenv import load_dotenv
import httpx

load_dotenv()


class OpenAIInteractions:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.chat_base_url = "https://api.openai.com/v1/responses"
        self.default_system_prompt = """You receive a video transcript and produces a prompt for a 
        music generation model to create music that perfectly complements the video's content. The 
        generated music should enhance the video's atmosphere, emotions, and overall impact. You
        should analyze the transcript to identify key themes, emotions, and narrative arcs, determine the 
        tone and mood of the video, and specify desired music attributes such as tempo, instrumentation, and dynamics. 
        The prompt should be clear and concise, providing enough detail for the music model to understand the context 
        and desired outcome.
        
        Answer just prompt, without any other things, do not write "Hello" or other anything except the ONLY PROMPT itself!
        
        Example of output that you may provide: 
        
        'Generate music that conveys a sense of tension and expectation, 
        like in popular movies. Music should create a sense of exciting dynamics
        and increasing tension, gradually revealing the theme of the newest and most 
        powerful artificial intelligence. In the middle of the composition, add 
        a touch of inspiration and positive expectations for the future, emphasizing
        the innovations and opportunities that AI brings. The finale should be powerful 
        and encouraging, leaving the listener feeling uplifted and inspired.' """

    async def agenerate_prompt_for_music(self, script: str):

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": "gpt-4o",
            "input": [
                {"role": "system", "content": self.default_system_prompt},
                {"role": "user", "content": f"Video script:\n\n{script}"},
            ],
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                self.chat_base_url, json=payload, headers=headers
            )
            
            response.raise_for_status()
            
            data = response.json()
            return data["output"][0]["content"][0]["text"]

async def main():
    try:
        openai_interactor = OpenAIInteractions()
        text = await openai_interactor.agenerate_prompt_for_music("Коровка бесси маленькая и красивая!")
        print(text)
    except Exception as e:
        print("Произошла ошибка:", e)
    
if __name__ == "__main__":
    asyncio.run(main())