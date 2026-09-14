import sys
import os
import subprocess
import shutil
import imageio_ffmpeg

user_site = os.path.expanduser('~\\AppData\\Roaming\\Python\\Python314\\site-packages')
if user_site not in sys.path:
    sys.path.append(user_site)

from moviepy import AudioFileClip

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
video_path = os.path.join(output_dir, "prototype_explanation_video.mp4")
concat_txt = os.path.join(output_dir, "concat.txt")

lines = []
for i in range(1, 8):
    png = os.path.join(output_dir, f"scene_{i}.png").replace("\\", "/")
    mp3 = os.path.join(output_dir, f"scene_{i}.mp3")
    
    dur = AudioFileClip(mp3).duration
    lines.append(f"file '{png}'")
    lines.append(f"duration {dur:.3f}")

png7 = os.path.join(output_dir, "scene_7.png").replace("\\", "/")
lines.append(f"file '{png7}'")

with open(concat_txt, "w") as f:
    f.write("\n".join(lines))

audio_txt = os.path.join(output_dir, "audio.txt")
with open(audio_txt, "w") as f:
    for i in range(1, 8):
        mp3 = os.path.join(output_dir, f"scene_{i}.mp3").replace("\\", "/")
        f.write(f"file '{mp3}'\n")

merged_audio = os.path.join(output_dir, "full_narration.mp3")

# Mux full audio
subprocess.run([ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", audio_txt, "-c", "copy", merged_audio], check=True)

# Mux video slides with full audio track using ultrafast preset & stillimage tune
cmd = [
    ffmpeg_exe, "-y",
    "-f", "concat", "-safe", "0", "-i", concat_txt,
    "-i", merged_audio,
    "-vf", "scale=1920:1080",
    "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "15",
    "-c:a", "aac", "-b:a", "192000",
    "-shortest",
    video_path
]

print("Executing ultrafast ffmpeg video encoding...")
subprocess.run(cmd, check=True)

# Copy video to artifact directory for embedded HTML5 video playback
artifact_dir = "C:\\Users\\manik\\.gemini\\antigravity\\brain\\5cfbd37f-d724-44db-aa7f-93d733df7b78"
if os.path.exists(artifact_dir):
    artifact_mp4 = os.path.join(artifact_dir, "prototype_explanation_video.mp4")
    shutil.copy2(video_path, artifact_mp4)
    print(f"Copied MP4 video to artifact directory: {artifact_mp4}")

print(f"SUCCESS! Rendered complete MP4 Video to: {video_path}")
