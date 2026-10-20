from __future__ import annotations

from typing import Any, Dict, List

from app.services.creative.providers.provider import BaseCreativeProvider


class MockCreativeProvider(BaseCreativeProvider):
    def _safe_text(self, value: Any, default: str) -> str:
        if value is None:
            return default
        cleaned = str(value).strip()
        return cleaned if cleaned else default

    def _description_keywords(self, campaign: Dict[str, Any]) -> List[str]:
        raw = self._safe_text(campaign.get("keywords"), "")
        keywords = [piece.strip() for piece in raw.replace(",", " ").split() if piece.strip()]
        if not keywords:
            product_name = self._safe_text(campaign.get("product_name"), "Product")
            keywords = [product_name.lower()]
        return keywords[:3]

    def generate_image_brief(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        product_name = self._safe_text(campaign.get("product_name"), "Your product")
        campaign_name = self._safe_text(campaign.get("name"), "Campaign")
        audience = self._safe_text(campaign.get("target_audience"), "Your target audience")
        platform = self._safe_text(campaign.get("platform"), "social platform")
        objective = self._safe_text(campaign.get("objective"), "Product Promotion")
        tone = self._safe_text(campaign.get("tone"), "Engaging")
        description = self._safe_text(campaign.get("description"), "High-quality solution designed for everyday use.")
        keywords = self._description_keywords(campaign)

        headline = f"{product_name}: Built for {audience}"
        primary_text = (
            f"{description} Crafted for {audience} with a {tone.lower()} message designed for {platform}."
        )
        call_to_action = "Shop Now" if objective.lower() == "sales" or "sale" in objective.lower() else "Learn More"

        return {
            "headline": headline,
            "primary_text": primary_text,
            "description": description,
            "call_to_action": call_to_action,
            "hashtags": [
                f"#{product_name.replace(' ', '')}",
                f"#{campaign_name.replace(' ', '')}",
                *[f"#{keyword.title().replace(' ', '')}" for keyword in keywords],
            ][:5],
            "visual_direction": (
                f"A lifestyle scene featuring {audience.lower()} using {product_name.lower()} in a modern {platform.lower()} setting, "
                f"with vibrant lighting and a clean product focus that matches the {tone.lower()} tone for {campaign_name}."
            ),
        }

    def generate_video_script(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        product_name = self._safe_text(campaign.get("product_name"), "Your product")
        audience = self._safe_text(campaign.get("target_audience"), "your audience")
        platform = self._safe_text(campaign.get("platform"), "social media")
        tone = self._safe_text(campaign.get("tone"), "engaging")
        objective = self._safe_text(campaign.get("objective"), "Product Promotion")
        description = self._safe_text(campaign.get("description"), "A premium product designed to simplify everyday life.")
        cta = "Shop Now" if objective.lower() == "sales" or "sale" in objective.lower() else "Learn More"

        scenes = [
            {
                "scene_number": 1,
                "duration": 4,
                "visual": f"A quick lifestyle shot of {audience.lower()} engaging with {product_name.lower()} in a dynamic {platform.lower()} environment.",
                "visual_description": f"Landscape photo of {audience.lower()} using {product_name.lower()} in a lively everyday {platform.lower()} setting.",
                "visual_prompt": f"Landscape 16:9 lifestyle photograph of {audience.lower()} using {product_name.lower()} during a lively everyday moment on {platform.lower()}; natural candid composition, clear product context, bright practical lighting, no text or logos.",
                "voiceover": f"Meet {product_name}, built to fit seamlessly into everyday life.",
                "on_screen_text": product_name,
            },
            {
                "scene_number": 2,
                "duration": 6,
                "visual": f"Close-up product detail shot with clean lighting and a polished brand aesthetic.",
                "visual_description": f"Landscape close-up photo of {product_name.lower()} with clean natural lighting and a polished product setting.",
                "visual_prompt": f"Landscape 16:9 close-up product photograph of {product_name.lower()} on a clean modern surface, polished but realistic materials, soft natural side lighting, crisp product detail and uncluttered setting, no text or logos.",
                "voiceover": f"{description} Designed for {audience.lower()} who want quality without compromise.",
                "on_screen_text": "Built for You",
            },
            {
                "scene_number": 3,
                "duration": 3,
                "visual": f"Real-life usage moments showing the product in motion across work, travel, or leisure.",
                "visual_description": f"Landscape lifestyle photo of {audience.lower()} using {product_name.lower()} during work, travel, or leisure.",
                "visual_prompt": f"Landscape 16:9 candid lifestyle photograph showing {audience.lower()} using {product_name.lower()} during an everyday work, travel, or leisure moment, product visible in context, balanced cinematic framing, no text or logos.",
                "voiceover": f"From first use to everyday moments, {product_name} keeps the experience simple, fast, and {tone.lower()}.",
                "on_screen_text": "Simple. Powerful. Ready.",
            },
            {
                "scene_number": 4,
                "duration": 2,
                "visual": f"Final branded close-up with a clean CTA overlay and confident call-to-action framing.",
                "visual_description": f"Landscape photo of {product_name.lower()} arranged in a clean, premium setting with open space for a caption.",
                "visual_prompt": f"Landscape 16:9 premium product photograph of {product_name.lower()} arranged in a clean refined setting, composed with open negative space near the lower edge for a separate video caption, no text or logos.",
                "voiceover": f"Choose {product_name} and make every moment feel better.",
                "on_screen_text": cta,
            },
        ]

        return {
            "title": f"{product_name} — {objective} Campaign",
            "duration": 15,
            "scenes": scenes,
            "final_cta": cta,
        }
