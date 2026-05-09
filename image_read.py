import requests
import csv
import base64
import io
import os
import subprocess
import tempfile
import cv2
from PIL import Image
import argparse

LM_STUDIO_API_URL = "http://localhost:1234"
LLM_MODEL_NAME = "google/gemma-3-4b"

_PROMPT = (
    "Describe the screen content of this Android app screenshot. "
    "Identify UI elements such as buttons, views, and text fields."
)


def extract_frames(video_path, num_frames):
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Distribute evenly across the full video length
    actual_num = min(num_frames, total_frames)
    frame_indices = [int(i * total_frames / actual_num) for i in range(actual_num)]

    frame_list = []
    for frame_index in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = cap.read()
        if not ret:
            break
        frame_list.append(frame)
    cap.release()
    return frame_list


def frame_to_base64(frame):
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _frame_to_temp_file(frame) -> str:
    """Save frame to a temp JPEG file, return its path."""
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(tmp.name, format="JPEG", quality=85)
    return tmp.name


def analyze_frame_with_llm(frame, model_name):
    b64 = frame_to_base64(frame)
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
        "stream": False,
    }

    try:
        resp = requests.post(
            f"{LM_STUDIO_API_URL}/v1/chat/completions",
            json=payload,
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            print(f"LLM error {resp.status_code}: {resp.text}")
            return "Error calling LLM"
    except Exception as e:
        print(f"Request failed: {e}")
        return "Error processing request"


def analyze_frame_with_codex(frame, codex_bin: str, model: str | None = None) -> str:
    """Phân tích frame bằng codex CLI (codex exec -i <image> <prompt>)."""
    tmp_path = _frame_to_temp_file(frame)
    try:
        cmd = [codex_bin, "exec", "-i", tmp_path]
        if model:
            cmd += ["-m", model]
        cmd.append(_PROMPT)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return result.stdout.strip() or "No output from codex"
        else:
            err = result.stderr.strip()[:200]
            print(f"codex error (exit {result.returncode}): {err}")
            return "Error calling codex"
    except subprocess.TimeoutExpired:
        print("codex timed out")
        return "Error: codex timeout"
    except Exception as e:
        print(f"codex failed: {e}")
        return "Error calling codex"
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def save_to_csv(descriptions, output_csv):
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame_number", "description"])
        for i, description in enumerate(descriptions):
            writer.writerow([i + 1, description])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract frames from video and analyze with LLM."
    )
    parser.add_argument("video_path", type=str, help="Path to the input video file.")
    parser.add_argument("output_csv", type=str, help="Path to the output CSV file.")
    parser.add_argument("--num_frames", type=int, default=15, help="Number of frames to extract.")
    parser.add_argument(
        "--backend", choices=["lmstudio", "codex"], default="lmstudio",
        help="LLM backend: lmstudio (default) hoặc codex (dùng codex CLI).",
    )
    parser.add_argument(
        "--codex-bin", type=str,
        default="/Users/buitung/.vscode/extensions/openai.chatgpt-26.506.21252-darwin-arm64/bin/macos-aarch64/codex",
        help="Đường dẫn tới binary codex CLI.",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model name (lmstudio: mặc định google/gemma-3-4b; codex: mặc định theo config của codex).",
    )

    args = parser.parse_args()

    frames = extract_frames(args.video_path, args.num_frames)
    print(f"Extracted {len(frames)} frames.")

    descriptions = []
    for i, frame in enumerate(frames):
        print(f"Analyzing frame {i + 1}/{len(frames)}... (backend={args.backend})")
        if args.backend == "codex":
            desc = analyze_frame_with_codex(frame, args.codex_bin, args.model)
        else:
            model_name = args.model or LLM_MODEL_NAME
            desc = analyze_frame_with_llm(frame, model_name)
        descriptions.append(desc)

    save_to_csv(descriptions, args.output_csv)
    print(f"Saved results to: {args.output_csv}")
