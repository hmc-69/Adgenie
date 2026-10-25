import unittest
from decimal import Decimal
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.campaign import Campaign
from app.models.creative import Creative
from app.models.user import User
from app.services.campaign_service import delete_campaign
from app.services.storage.supabase_storage import SupabaseStorageNotFoundError


class CampaignMediaCleanupTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.session = sessionmaker(bind=self.engine)()
        user = User(name="Owner", email="media-owner@example.test", password_hash="hash")
        self.session.add(user)
        self.session.flush()
        self.campaign = Campaign(
            user_id=user.id, name="Campaign", product_name="Product", description="Description",
            target_audience="Audience", platform="Instagram", objective="Sales", tone="Friendly",
            budget=Decimal("100.00"), status="Draft",
        )
        self.session.add(self.campaign)
        self.session.flush()
        self.creative = Creative(
            campaign_id=self.campaign.id, type="video", generated_content={
                "scene_assets": [{"storage_path": "campaigns/1/video-scenes/2/scene.webp"}],
            }, image_path="campaigns/1/creatives/2/image.png",
            video_path="campaigns/1/creatives/2/render.mp4",
        )
        self.session.add(self.creative)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_cleanup_deletes_image_video_and_scene_objects_before_campaign(self):
        storage = Mock()
        with patch("app.services.campaign_service.get_supabase_storage_service", return_value=storage):
            delete_campaign(self.session, self.campaign.id, self.campaign.user_id)
        storage.delete_image.assert_any_call("campaigns/1/creatives/2/image.png")
        storage.delete_video.assert_called_once_with("campaigns/1/creatives/2/render.mp4")
        storage.delete_image.assert_any_call("campaigns/1/video-scenes/2/scene.webp")
        self.assertIsNone(self.session.get(Campaign, self.campaign.id))

    def test_missing_objects_are_idempotent_and_campaign_is_deleted(self):
        storage = Mock()
        storage.delete_image.side_effect = SupabaseStorageNotFoundError("missing")
        storage.delete_video.side_effect = SupabaseStorageNotFoundError("missing")
        with patch("app.services.campaign_service.get_supabase_storage_service", return_value=storage):
            delete_campaign(self.session, self.campaign.id, self.campaign.user_id)
        self.assertIsNone(self.session.get(Campaign, self.campaign.id))

    def test_provider_failure_retains_campaign_and_paths_for_retry(self):
        storage = Mock()
        storage.delete_image.side_effect = RuntimeError("provider unavailable")
        with patch("app.services.campaign_service.get_supabase_storage_service", return_value=storage):
            with self.assertRaises(HTTPException) as raised:
                delete_campaign(self.session, self.campaign.id, self.campaign.user_id)
        self.assertEqual(raised.exception.status_code, 503)
        retained = self.session.get(Campaign, self.campaign.id)
        self.assertIsNotNone(retained)
        self.assertEqual(retained.creatives[0].image_path, "campaigns/1/creatives/2/image.png")

    def test_non_owner_cannot_trigger_media_cleanup(self):
        storage = Mock()
        with patch("app.services.campaign_service.get_supabase_storage_service", return_value=storage):
            with self.assertRaises(HTTPException) as raised:
                delete_campaign(self.session, self.campaign.id, self.campaign.user_id + 100)
        self.assertEqual(raised.exception.status_code, 404)
        storage.delete_image.assert_not_called()
        storage.delete_video.assert_not_called()


if __name__ == "__main__":
    unittest.main()
