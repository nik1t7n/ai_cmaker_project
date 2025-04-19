import asyncio
import os
import aiohttp
from typing import Dict, Any
from dotenv import load_dotenv
import logging

class MusicGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.aimlapi.com/v2/generate/audio"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        logging.debug("Initialized MusicGenerator with provided API key.")

    async def generate_music(self, prompt: str, steps: int = 300, seconds_total: int = 10) -> str:
        """
        Generates music based on the provided prompt and returns the URL of the generated audio file.
        """
        logging.info("Starting music generation with prompt: '{}'.".format(prompt.strip()[:50] + "..."))
        generation_id = await self._start_generation(prompt, steps, seconds_total)
        logging.debug("Music generation started. Generation ID: '{}'.".format(generation_id))
        while True:
            status_response = await self._check_status(generation_id)
            logging.debug("Checked generation status: '{}' for ID: '{}'.".format(status_response.get("status"), generation_id))
            if status_response["status"] == "completed":
                logging.info("Music generation completed successfully for Generation ID: '{}'.".format(generation_id))
                return status_response["audio_file"]["url"]
            elif status_response["status"] in ["queued", "generating"]:
                logging.info("Music generation is '{}' for Generation ID: '{}'. Waiting for 10 seconds...".format(
                    status_response["status"], generation_id))
                await asyncio.sleep(10)
            else:
                logging.error("Unexpected status '{}' for Generation ID: '{}'.".format(
                    status_response["status"], generation_id))
                raise Exception(f"Unexpected status: {status_response['status']}")

    async def _start_generation(self, prompt: str, steps: int, seconds_total: int) -> str:
        """
        Initiates the music generation process.
        """
        logging.info("Initiating music generation with prompt, steps={}, seconds_total={}.".format(steps, seconds_total))
        payload = {
            "model": "stable-audio",
            "prompt": prompt,
            "steps": steps,
            "seconds_total": seconds_total,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload, headers=self.headers) as response:
                    response.raise_for_status()
                    data = await response.json()
                    generation_id = data["id"]
                    logging.debug("Music generation initiated successfully. Generation ID: '{}'.".format(generation_id))
                    return generation_id
        except Exception as e:
            logging.critical("Error initiating music generation: {}".format(e))
            raise

    async def _check_status(self, generation_id: str) -> Dict[str, Any]:
        """
        Checks the status of a generation process.
        """
        params = {
            "generation_id": generation_id
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params, headers=self.headers) as response:
                    response.raise_for_status()
                    result = await response.json()
                    logging.debug("Status for Generation ID '{}' received: '{}'.".format(generation_id, result.get("status")))
                    return result
        except Exception as e:
            logging.error("Error checking status for Generation ID '{}': {}".format(generation_id, e))
            raise

# Example usage
async def main():
    load_dotenv()
    api_key = os.getenv("AIML_API_KEY")
    if not api_key:
        logging.critical("AIML_API_KEY not found in environment variables.")
        return
    generator = MusicGenerator(api_key)
    prompt = (
        "Generate music that conveys a sense of tension and expectation, like in popular movies. "
        "Music should create a sense of exciting dynamics and increasing tension, gradually revealing "
        "the theme of the newest and most powerful artificial intelligence. In the middle of the composition, "
        "add a touch of inspiration and positive expectations for the future, emphasizing the innovations and "
        "opportunities that AI brings. The finale should be powerful and encouraging, leaving the listener feeling "
        "uplifted and inspired."
    )
    try:
        audio_url = await generator.generate_music(prompt, steps=300, seconds_total=46)
        logging.info("Generated audio URL: '{}'.".format(audio_url))
        print(f"Generated audio URL: {audio_url}")
    except Exception as e:
        logging.critical("Error generating music: {}".format(e))
        print(f"Error generating music: {e}")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(main())
