from datetime import datetime, timezone
from pathlib import Path


GENERATED_IMAGES_DIR = Path(__file__).resolve().parents[2] / "generated_images"
IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def save_generated_image_bytes(
    image_bytes: bytes,
    content_type: str,
    campaign_id: int,
    original_creative_id: int,
) -> str:
    extension = IMAGE_EXTENSIONS.get(content_type)
    if extension is None:
        raise ValueError("Unsupported generated image format")

    GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    file_name = (
        f"adgenie-campaign-{campaign_id}-creative-{original_creative_id}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}{extension}"
    )
    file_path = GENERATED_IMAGES_DIR / file_name
    file_path.write_bytes(image_bytes)
    return str(file_path)


def generated_image_path(image_path: str) -> Path:
    root = GENERATED_IMAGES_DIR.resolve()
    resolved_path = Path(image_path).resolve()
    if not resolved_path.is_relative_to(root) or not resolved_path.is_file():
        raise FileNotFoundError("Generated image does not exist")
    return resolved_path