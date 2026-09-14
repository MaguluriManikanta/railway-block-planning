import sys
import os
import glob
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

user_site = os.path.expanduser('~\\AppData\\Roaming\\Python\\Python314\\site-packages')
if user_site not in sys.path:
    sys.path.append(user_site)

output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
video_path = os.path.join(output_dir, "prototype_explanation_video.mp4")

print(f"Compiling MP4 from scene files in {output_dir}...")

clips = []
for i in range(1, 8):
    png = os.path.join(output_dir, f"scene_{i}.png")
    mp3 = os.path.join(output_dir, f"scene_{i}.mp3")
    if os.path.exists(png) and os.path.exists(mp3):
        audio = AudioFileClip(mp3)
        video = ImageClip(png).with_duration(audio.duration).with_audio(audio)
        clips.append(video)
        print(f"Added Scene {i} (duration: {audio.duration:.1f}s)")

if clips:
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(video_path, fps=24, codec="libx264", audio_codec="aac")
    print(f"SUCCESSFULLY COMPILED: {video_path}")
else:
    print("No scene clips found!")
