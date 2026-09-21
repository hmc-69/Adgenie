from __future__ import annotations

from typing import Any, Dict


class BaseCreativeProvider:
    def generate_image_brief(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def generate_video_script(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
