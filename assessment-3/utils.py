import datetime
from datetime import timezone
from fastapi import HTTPException
import os

def _now_iso() -> str:
    return datetime.datetime.now(timezone.utc).isoformat()

# def _require_owner(decoded, owner: str):
#     username = decoded.get("username")
#     if not username:
#         raise HTTPException(status_code=401, detail="Invalid token subject.")
#     if username != owner:
#         raise HTTPException(status_code=403, detail="Forbidden: not your resource.")

# def _ffmpeg_cmd(input_path: str, output_path: str, preset: str, crf: int, resolution: str, threads: int) -> list:
#     cmd = ["ffmpeg", "-y", "-hide_banner", "-i", input_path]
#     if resolution:
#         cmd += ["-vf", f"scale={resolution}"]
#     cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
#     if threads is not None:
#         cmd += ["-threads", str(threads)]
#     cmd += [output_path]
#     return cmd
