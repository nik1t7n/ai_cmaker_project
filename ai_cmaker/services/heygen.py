import asyncio
import logging
import os
from typing import Optional, Tuple, Dict, Any
import aiohttp
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class HeygenAPIError(Exception):
    """Base exception for Heygen API errors"""
    def __init__(self, status_code: int, error_data: Dict[str, Any]):
        self.status_code = status_code
        self.error_data = error_data
        self.error_code = error_data.get("error", {}).get("code", "unknown_error")
        self.error_message = error_data.get("error", {}).get("message", "Unknown error")
        
        # Формируем читаемое сообщение об ошибке
        message = f"Heygen API Error: {status_code} - {self.error_code}: {self.error_message}"
        super().__init__(message)


class AuthenticationError(HeygenAPIError):
    """Error for invalid API key or authentication issues"""
    pass


class ResourceNotFoundError(HeygenAPIError):
    """Error for invalid resources like avatar_id or voice_id"""
    pass


class InvalidParameterError(HeygenAPIError):
    """Error for invalid parameters in the request"""
    pass


class VideoGenerationConfig(BaseModel):
    """Configuration model for video generation"""
    content: Optional[str] = None
    voice_id: str = Field(..., description="Heygen voice ID")
    avatar_id: str = Field(..., description="Heygen avatar ID")
    dimensions: Tuple[int, int] = Field(
        default=(720, 1280), description="Video dimensions (width, height)"
    )
    speed: float = Field(default=1.0, description="Speech speed")


class HeygenProcessor:
    """
    Asynchronous processor for generating videos using Heygen API.
    Handles video generation requests and status checking.
    """
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.heygen.com",
        polling_interval: int = 60,
        max_retries: int = 3,
    ):
        """
        Initialize the Heygen processor.
        Args:
            api_key: Heygen API key
            base_url: Base URL for Heygen API
            polling_interval: Interval in seconds between status checks
            max_retries: Maximum number of retries for failed requests
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.polling_interval = polling_interval
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        self._headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
        self.logger.debug("HeygenProcessor initialized with base_url '{}' and polling_interval {} seconds.".format(
            self.base_url, self.polling_interval))

    def _build_generation_payload(self, config: VideoGenerationConfig) -> dict:
        """
        Build the payload for video generation request.
        Args:
            config: Video generation configuration
        Returns:
            Dictionary containing the request payload
        """
        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": config.avatar_id,
                        "avatar_style": "normal",
                    },
                    "voice": {
                        "type": "text",
                        "input_text": config.content,
                        "voice_id": config.voice_id,
                        "speed": config.speed,
                    },
                }
            ],
            "dimension": {
                "width": config.dimensions[0],
                "height": config.dimensions[1],
            },
            "test": False
        }
        self.logger.debug("Built generation payload for video: avatar_id '{}', voice_id '{}', dimensions {}.".format(
            config.avatar_id, config.voice_id, config.dimensions))
        return payload

    async def _make_request(
        self, session: aiohttp.ClientSession, method: str, endpoint: str, **kwargs
    ): 
        """
        Make an HTTP request to Heygen API with retry logic.
        Args:
            session: aiohttp client session
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional arguments for the request
        Returns:
            JSON response from the API
        Raises:
            AuthenticationError: For authentication issues (401)
            ResourceNotFoundError: For resource not found issues (404)
            InvalidParameterError: For invalid parameter issues (400)
            HeygenAPIError: For other API errors
            Exception: If the request fails after max retries
        """
        url = f"{self.base_url}{endpoint}"
        self.logger.debug("Making {} request to URL '{}'.".format(method, url))
        
        for attempt in range(self.max_retries):
            try:
                async with session.request(method, url, headers=self._headers, **kwargs) as response:
                    # Получаем тело ответа
                    response_text = await response.text()
                    try:
                        response_data = await response.json()
                    except Exception:
                        response_data = {"error": {"code": "parse_error", "message": f"Failed to parse response: {response_text}"}}
                    
                    # Проверяем статус ответа
                    if not response.ok:
                        self.logger.warning(f"Request failed with status code: {response.status}. Response: {response_data}")
                        
                        # Обработка различных HTTP статусов
                        if response.status == 401:
                            raise AuthenticationError(response.status, response_data)
                        elif response.status == 404:
                            raise ResourceNotFoundError(response.status, response_data)
                        elif response.status == 400:
                            # Проверяем содержимое ошибки для определения типа
                            error_code = response_data.get("error", {}).get("code", "")
                            error_message = response_data.get("error", {}).get("message", "")
                            
                            if "Voice not found" in error_message:
                                raise InvalidParameterError(response.status, response_data)
                            elif "Avatar" in error_message and "not found" in error_message:
                                raise ResourceNotFoundError(response.status, response_data)
                            else:
                                raise InvalidParameterError(response.status, response_data)
                        else:
                            raise HeygenAPIError(response.status, response_data)
                    
                    # Проверяем структуру данных
                    if not isinstance(response_data, dict):
                        raise HeygenAPIError(response.status, {"error": {"code": "invalid_response", "message": "Response is not a dictionary"}})
                    
                    if "data" not in response_data and "error" not in response_data:
                        raise HeygenAPIError(response.status, {"error": {"code": "invalid_response_format", "message": "Response missing 'data' and 'error' fields"}})
                    
                    self.logger.debug("Request successful on attempt {} for URL '{}'.".format(attempt + 1, url))
                    return response_data
                    
            except (AuthenticationError, ResourceNotFoundError, InvalidParameterError) as e:
                # Эти ошибки мы не хотим повторять, они должны быть переданы выше
                self.logger.error(f"API error encountered: {str(e)}")
                raise
                
            except HeygenAPIError as e:
                # Для общих ошибок API мы можем попытаться повторить, но только если у нас есть еще попытки
                self.logger.warning(f"HeygenAPIError on attempt {attempt + 1}: {str(e)}")
                raise
                
            except Exception as e:
                # Для прочих исключений (сетевые и т.д.)
                self.logger.warning("Request attempt {} failed: {}".format(attempt + 1, e))
                raise

    async def _check_video_status(
        self, session: aiohttp.ClientSession, video_id: str
    ) -> Optional[str]:
        """
        Check the status of a video generation request.
        Args:
            session: aiohttp client session
            video_id: ID of the video to check
        Returns:
            Video URL if completed, None if still processing
        Raises:
            Exception: If the video generation failed or status check returns unexpected status
        """
        self.logger.info("Checking status for video_id '{}'.".format(video_id))
        status_data = await self._make_request(
            session, "GET", "/v1/video_status.get", params={"video_id": video_id}
        )
        
        data = status_data.get("data", {})
        status = data.get("status")
        self.logger.debug("Video status for ID '{}' is '{}'.".format(video_id, status))
        
        if status == "completed":
            video_url = data.get("video_url")
            if not video_url:
                self.logger.error("Completed status received but video URL not found for video_id '{}'.".format(video_id))
                raise Exception("Video URL not found in completed status")
            
            # Дополнительно можно логировать другие доступные URL и метаданные
            duration = data.get("duration")
            gif_url = data.get("gif_url")
            caption_url = data.get("caption_url")
            thumbnail_url = data.get("thumbnail_url")
            
            self.logger.info(
                "Video completed. Duration: {}, GIF URL: {}, Caption URL: {}, Thumbnail URL: {}".format(
                    duration, gif_url, caption_url, thumbnail_url
                )
            )
            
            return video_url
        
        elif status in ["waiting", "processing", "pending"]:
            # Теперь обрабатываем также статус "pending"
            self.logger.info("Video is in '{}' state for video_id '{}'. Continuing to wait.".format(status, video_id))
            return None
        
        elif status == "failed":
            # Обработка случая неудачной генерации видео
            error = data.get("error", {})
            error_code = error.get("code", "unknown")
            error_message = error.get("message", "Unknown error")
            error_detail = error.get("detail", "No details provided")
            
            error_info = "Video generation failed. Error code: {}, Message: {}, Detail: {}".format(
                error_code, error_message, error_detail
            )
            
            self.logger.error(error_info)
            raise HeygenAPIError(500, {"error": {"code": error_code, "message": error_message, "detail": error_detail}})
        
        else:
            # Обработка любых других неожиданных статусов
            self.logger.error("Unexpected video status '{}' for video_id '{}'.".format(status, video_id))
            raise HeygenAPIError(500, {"error": {"code": "unexpected_status", "message": f"Unexpected status: {status}"}})

    async def generate_video(self, config: VideoGenerationConfig) -> str:
        """
        Generate a video using Heygen API.
        Args:
            config: Video generation configuration
        Returns:
            URL of the generated video
        Raises:
            HeygenAPIError and subclasses for API errors
            Exception: For other errors
        """
        self.logger.info("Initiating video generation via HeygenProcessor.")
        print("GENERATING VIDEO")
        print(f"VOICE_ID: {config.voice_id}")
        print(f"AVATAR ID: {config.avatar_id}")
        
        async with aiohttp.ClientSession() as session:
            generation_data = await self._make_request(
                session,
                "POST",
                "/v2/video/generate",
                json=self._build_generation_payload(config),
            )
            
            video_id = generation_data.get("data", {}).get("video_id")
            if not video_id:
                self.logger.critical("Video ID not found in generation response.")
                raise HeygenAPIError(500, {"error": {"code": "missing_video_id", "message": "Video ID not found in generation response"}})
            
            self.logger.info("Video generation initiated. Video ID: '{}'.".format(video_id))
            
            while True:
                video_url = await self._check_video_status(session, video_id)
                if video_url:
                    self.logger.info("Video generation completed successfully. Video URL: '{}'.".format(video_url))
                    return video_url
                self.logger.info("Video not ready yet. Waiting {} seconds before next check for video_id '{}'.".format(
                    self.polling_interval, video_id))
                await asyncio.sleep(self.polling_interval)


if __name__ == "__main__":
    load_dotenv()
    HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
    HEYGEN_VOICE_ID = os.getenv("HEYGEN_VOICE_ID")
    HEYGEN_AVATAR_ID = os.getenv("HEYGEN_AVATAR_ID")
    print(f"{HEYGEN_API_KEY}")
    print(f"{HEYGEN_VOICE_ID}")
    print(f"{HEYGEN_AVATAR_ID}")
    processor = HeygenProcessor(api_key=HEYGEN_API_KEY)
    config = VideoGenerationConfig(
        content="Я - Рамис и на меня сегодня подписался Ян Топлес! Я очень рад!",
        voice_id=HEYGEN_VOICE_ID,
        avatar_id=HEYGEN_AVATAR_ID,
        dimensions=(720, 1280),
        speed=1.0,
    )
    try:
        video_url = asyncio.run(processor.generate_video(config))
        logging.info("Generated video URL: '{}'.".format(video_url))
        print(f"Generated video URL: {video_url}")
    except Exception as e:
        logging.critical("Error during video generation: {}".format(e))
        print(f"Error: {e}")
