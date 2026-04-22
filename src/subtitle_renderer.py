import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


class SubtitleRenderer:
    def __init__(self, config: dict):
        sub_cfg = config["subtitle"]
        vid_cfg = config["video"]
        self.width = vid_cfg["width"]
        self.height = vid_cfg["height"]
        self.font_size = sub_cfg.get("font_size", 60)
        self.font_color = sub_cfg.get("font_color", "#FFFFFF")
        self.stroke_color = sub_cfg.get("stroke_color", "#000000")
        self.stroke_width = sub_cfg.get("stroke_width", 3)
        self.position = sub_cfg.get("position", "center")
        self.max_chars = sub_cfg.get("max_chars_per_line", 15)
        font_path = sub_cfg.get("font_path", "")
        try:
            self.font = ImageFont.truetype(font_path, self.font_size)
        except (OSError, IOError):
            self.font = ImageFont.load_default()

    def render_frame(self, text: str) -> Image.Image:
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        wrapped = textwrap.fill(text, width=self.max_chars)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=self.font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        x = (self.width - text_w) // 2
        if self.position == "top":
            y = int(self.height * 0.15)
        elif self.position == "bottom":
            y = int(self.height * 0.75)
        else:
            y = (self.height - text_h) // 2

        draw.multiline_text(
            (x, y),
            wrapped,
            font=self.font,
            fill=self.font_color,
            stroke_fill=self.stroke_color,
            stroke_width=self.stroke_width,
            align="center",
        )
        return img

    def generate_subtitle_clips(
        self, word_timestamps: list[dict], output_dir: Path
    ) -> list[dict]:
        clips = []
        group_text = ""
        group_start = 0.0
        group_end = 0.0

        for i, word in enumerate(word_timestamps):
            if not group_text:
                group_start = word["offset"]
            group_text += word["text"]
            group_end = word["offset"] + word["duration"]

            is_last = i == len(word_timestamps) - 1
            if len(group_text) >= self.max_chars or is_last:
                frame = self.render_frame(group_text)
                frame_path = output_dir / f"sub_{i:04d}.png"
                frame.save(str(frame_path))
                clips.append(
                    {
                        "image": str(frame_path),
                        "start": group_start,
                        "end": group_end,
                        "text": group_text,
                    }
                )
                group_text = ""

        return clips
