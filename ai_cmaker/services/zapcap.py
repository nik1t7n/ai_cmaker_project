import asyncio
import logging
import os
import re
from typing import Optional

import httpx
from dotenv import load_dotenv


# Настройка логирования (если требуется)
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

CATEGORY_COLORS = {
    "DEBUG": "blue",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "magenta"
}


class ZapcapProcessor:
    def __init__(self, api_key: str, base_url: str = "https://api.zapcap.ai") -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {"x-api-key": self.api_key}
        self.client = httpx.AsyncClient(timeout=600)
        logging.info("ZapcapProcessor initialized with base_url '{}'.".format(self.base_url))

    async def close(self) -> None:
        """Close httpx.AsyncClient."""
        await self.client.aclose()
        logging.info("HTTP client closed.")

    async def _get_video_duration(self, video_url: str) -> Optional[int]:
        logging.info("Attempting to get video duration for URL '{}'.".format(video_url))
        try:
            cmd = ["ffmpeg", "-i", video_url, "-hide_banner"]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            duration_match = re.search(
                r"Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})", stderr.decode()
            )
            if duration_match:
                hours = int(duration_match.group(1))
                minutes = int(duration_match.group(2))
                seconds = int(duration_match.group(3))
                milliseconds = int(duration_match.group(4))
                total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 100
                logging.debug("Video duration parsed successfully: {} seconds.".format(int(total_seconds)))
                return int(total_seconds)
            logging.warning("Video duration not found in output.")
            return None
        except Exception as e:
            logging.error("Ошибка при получении длительности видео: {}".format(e))
            return None

    # ──────────────── Upload Endpoints ────────────────

    async def upload_video_by_url(self, video_url: str) -> str:
        """
        Upload video via URL.
        """
        logging.info("Uploading video by URL: '{}'.".format(video_url))
        endpoint = f"{self.base_url}/videos/url"
        payload = {"url": video_url}
        response = await self.client.post(endpoint, headers=self.headers, json=payload)
        response.raise_for_status()
        video_id = response.json()["id"]
        logging.info("Video uploaded successfully. Video ID: '{}'.".format(video_id))
        return video_id

    async def upload_local_video(self, file_path: str) -> str:
        """
        Upload local video file.
        """
        logging.info("Uploading local video from file path '{}'.".format(file_path))
        endpoint = f"{self.base_url}/videos"
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = await self.client.post(endpoint, headers=self.headers, files=files)
        response.raise_for_status()
        video_id = response.json()["id"]
        logging.info("Local video uploaded successfully. Video ID: '{}'.".format(video_id))
        return video_id

    async def upload_large_video(self, file_path: str) -> str:
        """
        Multipart upload for large video files.
        """
        logging.info("Initiating multipart upload for large video from '{}'.".format(file_path))
        file_size = os.path.getsize(file_path)
        part_size = 10 * 1024 * 1024  # 10MB
        parts_count = (file_size + part_size - 1) // part_size

        # Create upload parts description
        upload_parts = [
            {"contentLength": min(part_size, file_size - i * part_size)}
            for i in range(parts_count)
        ]
        logging.debug("Calculated {} upload parts for file size {} bytes.".format(parts_count, file_size))

        # Initialize upload
        init_endpoint = f"{self.base_url}/videos/upload"
        init_payload = {"uploadParts": upload_parts, "filename": os.path.basename(file_path)}
        init_response = await self.client.post(init_endpoint, headers=self.headers, json=init_payload)
        init_response.raise_for_status()
        init_data = init_response.json()
        logging.info("Upload initialization completed. Received uploadId: '{}' and videoId: '{}'.".format(
            init_data["uploadId"], init_data["videoId"]))

        # Upload parts
        with open(file_path, "rb") as file:
            for i, upload_url in enumerate(init_data["urls"]):
                part_start = i * part_size
                file.seek(part_start)
                part_data = file.read(part_size)
                logging.debug("Uploading part {} (bytes {} to {}).".format(i + 1, part_start, part_start + len(part_data)))
                put_response = await self.client.put(upload_url, content=part_data)
                put_response.raise_for_status()

        # Complete upload
        complete_endpoint = f"{self.base_url}/videos/upload/complete"
        complete_payload = {"uploadId": init_data["uploadId"], "videoId": init_data["videoId"]}
        complete_response = await self.client.post(complete_endpoint, headers=self.headers, json=complete_payload)
        complete_response.raise_for_status()
        logging.info("Multipart upload completed successfully. Video ID: '{}'.".format(init_data["videoId"]))
        return init_data["videoId"]

    async def upload_video(self, source: str, upload_type: str = "url") -> str:
        """
        Universal method to upload video (by URL, local file, or multipart).
        """
        logging.info("Uploading video using source '{}' with upload_type '{}'.".format(source, upload_type))
        if upload_type == "url":
            return await self.upload_video_by_url(source)
        elif upload_type == "local":
            return await self.upload_local_video(source)
        elif upload_type == "multipart":
            return await self.upload_large_video(source)
        else:
            logging.error("Unsupported upload type '{}' provided.".format(upload_type))
            raise ValueError("Неподдерживаемый тип загрузки. Используйте 'url', 'local' или 'multipart'.")

    # ──────────────── Template & Task Endpoints ────────────────

    async def get_first_template(self) -> str:
        """
        Get the first available template.
        """
        logging.info("Requesting first available template.")
        endpoint = f"{self.base_url}/templates"
        response = await self.client.get(endpoint, headers=self.headers)
        response.raise_for_status()
        templates = response.json()
        if not templates:
            logging.error("No available templates found.")
            raise Exception("Нет доступных шаблонов.")
        template_id = templates[0]["id"]
        logging.info("First template ID retrieved: '{}'.".format(template_id))
        return template_id

    async def create_video_task(self, video_id: str, template_id: str, broll_percent: int = 30) -> str:
        """
        Create a video processing task.
        """
        logging.info("Creating video task for video_id '{}' with template_id '{}' and broll_percent {}.".format(
            video_id, template_id, broll_percent))
        endpoint = f"{self.base_url}/videos/{video_id}/task"
        payload = {
            "templateId": template_id,
            "autoApprove": True,
            "transcribeSettings": {"broll": {"brollPercent": broll_percent}},
            "renderOptions": {
                "subsOptions": {
                    "emoji": True,
                    "animation": True,
                    "emphasizeKeywords": True,
                }
            },
        }
        response = await self.client.post(endpoint, headers=self.headers, json=payload)
        response.raise_for_status()
        task_id = response.json()["taskId"]
        logging.info("Video task created successfully. Task ID: '{}'.".format(task_id))
        return task_id

    async def approve_transcript(self, video_id: str, task_id: str) -> None:
        """
        Approve the transcript for a task.
        """
        logging.info("Approving transcript for video_id '{}' and task_id '{}'.".format(video_id, task_id))
        endpoint = f"{self.base_url}/videos/{video_id}/task/{task_id}/approve-transcript"
        response = await self.client.post(endpoint, headers=self.headers)
        response.raise_for_status()
        logging.info("Transcript approved successfully for video_id '{}' and task_id '{}'.".format(video_id, task_id))

    async def check_task_status(self, video_id: str, task_id: str, max_attempts: int = 30, delay: int = 60) -> str:
        """
        Check the status of a video processing task.
        """
        logging.info("Checking task status for video_id '{}' and task_id '{}'.".format(video_id, task_id))
        for attempt in range(max_attempts):
            endpoint = f"{self.base_url}/videos/{video_id}/task/{task_id}"
            response = await self.client.get(endpoint, headers=self.headers)
            response.raise_for_status()
            status_data = response.json()
            current_status = status_data.get("status", "")
            logging.debug("[Attempt {}] Task status: '{}' for video_id '{}'.".format(attempt + 1, current_status, video_id))
            logging.debug("Task details: {}".format(status_data))

            if current_status == "completed":
                download_url = status_data.get("downloadUrl")
                if download_url:
                    logging.info("Task completed successfully. Download URL: '{}'.".format(download_url))
                    return download_url
                else:
                    logging.error("Task completed but downloadUrl is missing.")
                    raise Exception("Задача завершена, но downloadUrl отсутствует.")
            if current_status == "transcriptionCompleted":
                logging.info("Transcription completed. Approving transcript...")
                await self.approve_transcript(video_id, task_id)
            if current_status == "failed":
                error_msg = status_data.get("error", "Неизвестная ошибка")
                logging.critical("Task failed with error: '{}'.".format(error_msg))
                raise Exception(f"Задача завершилась с ошибкой: {error_msg}")
            await asyncio.sleep(delay)
        logging.error("Exceeded maximum attempts ({}) for checking task status.".format(max_attempts))
        raise Exception("Превышено число попыток опроса статуса задачи.")

    async def get_transcript(self, video_id: str, task_id: str) -> str:
        """
        Get the transcript (subtitles) for a video task.
        """
        logging.info("Fetching transcript for video_id '{}' and task_id '{}'.".format(video_id, task_id))
        endpoint = f"{self.base_url}/videos/{video_id}/task/{task_id}/transcript"
        response = await self.client.get(endpoint, headers=self.headers)
        response.raise_for_status()
        transcript_items = response.json()
        transcript_str = ""
        for item in transcript_items:
            text = item.get("text", "")
            transcript_str += f"{text} "
        transcript_str = transcript_str.strip()
        logging.debug("Transcript fetched successfully. Transcript length: {} characters.".format(len(transcript_str)))
        return transcript_str

    # ──────────────── Final Method ────────────────

    async def process_video(self, source: str, upload_type: str = "url", broll_percent: int = 30, template_id: str = "14bcd077-3f98-465b-b788-1b628951c340") -> tuple[str, str, int]:
        logging.info("Starting full video processing pipeline for source '{}' with upload_type '{}'.".format(source, upload_type))
        # 1. Upload video
        video_id = await self.upload_video(source, upload_type)
        logging.info("Video uploaded. Video ID: '{}'.".format(video_id))

        logging.info("Selected template with template_id '{}'.".format(template_id))

        # 2. Create video processing task
        task_id = await self.create_video_task(video_id, template_id, broll_percent)
        logging.info("Video processing task created. Task ID: '{}'.".format(task_id))

        # 3. Wait for task completion and get download URL
        download_url = await self.check_task_status(video_id, task_id)
        logging.info("Video processed successfully. Download URL: '{}'.".format(download_url))

        # 4. Get transcript (subtitles)
        transcript = await self.get_transcript(video_id, task_id)
        logging.debug("Transcript obtained. Transcript length: {} characters.".format(len(transcript)))
        
        total_seconds = await self._get_video_duration(download_url)
        logging.info("Total video duration determined: {} seconds.".format(total_seconds if total_seconds else "unknown"))

        return download_url, transcript, total_seconds

# ──────────────── Example usage ────────────────

async def main():
    load_dotenv()
    api_key = os.getenv("ZAPCAP_API_KEY")
    if not api_key:
        logging.critical("Environment variable ZAPCAP_API_KEY is not set.")
        raise Exception("Переменная окружения ZAPCAP_API_KEY не установлена.")
    processor = ZapcapProcessor(api_key)
    try:
        download_url, transcript, duration = await processor.process_video(
            "https://files2.heygen.ai/aws_pacific/avatar_tmp/6b7d94b9222349b286a8baf9e56dce1d/93317eeceb5c458f8fc80972c3bfaac4.mp4?Expires=1739006597&Signature=WxafrZMfVThIDRlWVnG2E~49MrETfHCIS~pWGEaSwPl~FTEjK1FP6H2-L0UUBEu3WCp1IV9x5kIxfWbpXHrVzoMTz-D4jNfuaG-6qtsxl3R~6dekpvW6lPMJslTZFIjC8G0kXfT9QrcV~Nm2NasSS6aCh4bUXDZzYHvibSNJFaUmOUoWt-rBfkHwuP-R~prZPucrzj8XRK2-7Fc6nrb5~wTC9gSd8MPG9Bfo4ByLqundeBgMb8fBO0Vs-VS0cxiz5PacwezxqvBe8r0dqF288FR9-SkNr2MudO~12B~vfUBfs471wDjS7OtI4vgb0Sdre8HP13ugoivC3rl2V0ldeA__&Key-Pair-Id=K38HBHX5LX3X2H",
            upload_type="url",
            broll_percent=1,
        )
        logging.info("Video processing completed. Download URL: '{}', Transcript length: {} characters.".format(
            download_url, len(transcript)))
    except Exception as e:
        logging.critical("Ошибка обработки видео: {}".format(e))
        raise
    finally:
        await processor.close()

if __name__ == "__main__":
    asyncio.run(main())
