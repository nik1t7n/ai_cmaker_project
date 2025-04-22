import asyncio
import os
import tempfile
import subprocess
from dotenv import load_dotenv
import httpx
import uuid
from services.s3 import S3Service

load_dotenv()

async def merge_video_and_music(video_url: str, music_url: str, music_volume: float = 0.01) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        # Загружаем видео и музыку
        video_response = await client.get(video_url)
        video_response.raise_for_status()
        video_bytes = video_response.content

        music_response = await client.get(music_url)
        music_response.raise_for_status()
        music_bytes = music_response.content

    # Инициализируем сервис S3
    s3_service = S3Service(
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        access_key=os.getenv("S3_ACCESS_KEY"),
        secret_key=os.getenv("S3_SECRET_KEY"),
        region=os.getenv("S3_REGION_NAME"),
        bucket_name=os.getenv("S3_BUCKET_NAME"),
    )

    with (
        tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_video,
        tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio,
        tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_output,
    ):
        # Сохраняем файлы во временные файлы
        tmp_video_path = tmp_video.name
        tmp_audio_path = tmp_audio.name
        tmp_output_path = tmp_output.name
        
        tmp_video.write(video_bytes)
        tmp_video.flush()
        tmp_audio.write(music_bytes)
        tmp_audio.flush()

        # Получаем длительность видео с помощью ffprobe
        ffprobe_cmd = [
            'ffprobe', 
            '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            tmp_video_path
        ]
        video_duration = float(subprocess.check_output(ffprobe_cmd).decode('utf-8').strip())
        
        # Создаем команду ffmpeg для объединения видео и музыки
        # С сохранением оригинальной аудиодорожки и добавлением музыки с пониженной громкостью
        fade_in_duration = 3
        fade_out_duration = min(3, video_duration)
        fade_out_start = max(video_duration - fade_out_duration, 0)
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', tmp_video_path,          # Входное видео
            '-i', tmp_audio_path,          # Входная музыка
            '-filter_complex',
            f'[1:a]volume={music_volume},aloop=loop=-1:size=0:start=0,atrim=0:{video_duration},'
            f'afade=t=in:st=0:d={fade_in_duration},'
            f'afade=t=out:st={fade_out_start}:d={fade_out_duration}[music];'
            f'[0:a][music]amix=inputs=2:duration=first[a]',
            '-map', '0:v',                 # Сохраняем видеодорожку
            '-map', '[a]',                 # Используем смикшированное аудио
            '-c:v', 'copy',                # Видео копируем без перекодирования
            '-c:a', 'aac',                 # Аудио кодируем в AAC
            '-shortest',                   # Остановить, когда закончится кратчайший поток
            '-y',                          # Перезаписать выходной файл, если он существует
            tmp_output_path
        ]
        
        # Выполняем команду
        subprocess.run(ffmpeg_cmd, check=True)
        
        # Читаем результат
        with open(tmp_output_path, "rb") as f:
            final_bytes = f.read()
            
    # Удаляем временные файлы
    for file_path in [tmp_video_path, tmp_audio_path, tmp_output_path]:
        if os.path.exists(file_path):
            os.unlink(file_path)
    
    # Загружаем результат в S3
    output_key = f"final/{uuid.uuid4()}.mp4"
    result = await s3_service.upload_file(
        key=output_key,
        data=final_bytes,
        content_type="video/mp4"
    )
    if result["status"] != 200:
        raise Exception(f"Failed to upload merged to S3: {result}")

    return result["url"]

async def main():
    video_url = "https://files2.heygen.ai/aws_pacific/avatar_tmp/b5f764924b88466aa850190ca9f346c6/8566f21f3dde438a83d7f9277b52034f.mp4?Expires=1745510570&Signature=O2g1klgr7457dvTzKIdEh5wn83iVKX4Zm9NLI1dYKGbUlIIPgjkPFa3Zb6oeduXPuPNOVfYffUurq0is~4pOCnySYhrhb0uN3uQfyjkQneEwRUO5vGrAsVBWhGogrUuCCdVIPEMuS6vemCk-99NXbGHU9O1jN1RIo~HH8W8aAbK463JXuwnD8g8Ey006z4yn4Xdly5mZjWUp84x2U7IqSZ~JSedy~cEAF6epDPL0EGWOVsQqtXTCZYtp9sjnUWdN00znMKL-PNmvLk9LNOK46RjNdVEYNxuH85jPDL-dDjjVVNSWLeyJzCANDulgstDNTzekkIXkHG6I-3zwt5KB1w__&Key-Pair-Id=K38HBHX5LX3X2H"
    music_url = "https://cdn.aimlapi.com/octopus/files/5553c03eedad4ec9b1ee14f92f51ae41_tmpkqc_xkrv.wav"
    
    url = await merge_video_and_music(video_url=video_url, music_url=music_url)
    print(f"\n\n{url}\n\n")

if __name__ == "__main__":
    asyncio.run(main())
