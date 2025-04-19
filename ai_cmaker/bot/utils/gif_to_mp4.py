import asyncio
import tempfile 
import ffmpeg
import requests
import uuid
from pathlib import Path
import yaml

# temp = tempfile.NamedTemporaryFile(prefix='pre_', suffix='_suf')
async def convert_gif_to_mp4(gif_url: str, number: int, output_filename: str) -> Path:
    FONT_PATH = "assets/fonts/Montserrat-Bold.ttf"
    
    # Get the GIF data
    gif_data = requests.get(gif_url).content 
    
    # Create a temporary directory that will be automatically cleaned up
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a unique filename for the input GIF
        unique_id = str(uuid.uuid4())
        input_path = Path(temp_dir) / f"input_{unique_id}.gif"
        
        # Write the GIF data to the temporary file
        with open(input_path, "wb") as f:
            f.write(gif_data)
        
        # Create the output directory if it doesn't exist
        output_dir = Path("assets/videos")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / Path(output_filename).with_suffix(".mp4")
        
        # Convert GIF to MP4 with text overlay
        ffmpeg.input(str(input_path))\
            .output(str(output_path),
                vf=f"drawtext=fontfile='{FONT_PATH}':text='{number}':fontcolor=white:fontsize=64:x=20:y=20",
                pix_fmt="yuv420p",
                movflags="+faststart")\
            .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
    # At this point, the temporary directory and all its contents are automatically deleted
    return output_path


async def process_all_gifs():
    # Load the YAML config
    with open("config.yml", "r") as f:
        config = yaml.safe_load(f)
   
    gif_urls = []
    
    for str_number, value in config["video_editing"]["subtitle_styles"].items():
        gif_urls.append(value["gif_url"])
        
    tasks = []
    for idx, gif_url in enumerate(gif_urls, 1):
        tasks.append(asyncio.create_task(convert_gif_to_mp4(gif_url, idx, f"gif_{idx}")))
        
    return await asyncio.gather(*tasks)
   
   

if __name__ == "__main__":
    # Process all GIFs and print the resulting paths
    paths = asyncio.run(process_all_gifs())
    for idx, path in enumerate(paths, 1):
        print(f"GIF {idx} converted to: {path}")