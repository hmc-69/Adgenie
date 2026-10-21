import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.campaign import Campaign
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.campaign_performance import router


class CampaignPerformanceApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()
        self.owner = User(name="Owner", email="owner-performance@example.test", password_hash="hash")
        self.other = User(name="Other", email="other-performance@example.test", password_hash="hash")
        self.db.add_all([self.owner, self.other])
        self.db.flush()
        self.campaign = self.make_campaign(self.owner.id, "Owned campaign")
        self.other_campaign = self.make_campaign(self.other.id, "Other campaign")
        self.db.add_all([self.campaign, self.other_campaign])
        self.db.commit()

        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=self.owner.id)
        self.client = TestClient(self.app)

    def make_campaign(self, user_id, name):
        return Campaign(
            user_id=user_id,
            name=name,
            product_name="Product",
            description="Campaign description",
            target_audience="Audience",
            platform="Instagram",
            objective="Sales",
            tone="Friendly",
            status="Draft",
        )

    def tearDown(self):
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def payload(self, **updates):
        return {
            "date": "2026-10-20",
            "impressions": 1000,
            "clicks": 100,
            "conversions": 10,
            "spend": "50.00",
            "revenue": "150.00",
            **updates,
        }

    def record(self, **updates):
        return self.client.post(
            f"/api/campaigns/{self.campaign.id}/performance", json=self.payload(**updates)
        )

    def test_record_and_retrieve_daily_results(self):
        created = self.record()
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["campaign_id"], self.campaign.id)
        result = self.client.get(f"/api/campaigns/{self.campaign.id}/performance")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["total"], 1)
        self.assertEqual(result.json()["records"][0]["date"], "2026-10-20")

    def test_authentication_and_campaign_ownership_are_required(self):
        anonymous_app = FastAPI()
        anonymous_app.include_router(router)
        anonymous_app.dependency_overrides[get_db] = lambda: self.db
        with TestClient(anonymous_app) as anonymous_client:
            response = anonymous_client.get(f"/api/campaigns/{self.campaign.id}/performance")
        self.assertEqual(response.status_code, 401)

        response = self.client.get(f"/api/campaigns/{self.other_campaign.id}/performance")
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            f"/api/campaigns/{self.other_campaign.id}/performance", json=self.payload()
        )
        self.assertEqual(response.status_code, 404)

    def test_duplicate_campaign_date_returns_conflict(self):
        self.assertEqual(self.record().status_code, 201)
        duplicate = self.record()
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("already exists", duplicate.json()["detail"])

    def test_negative_values_and_invalid_metric_relationships_are_rejected(self):
        for invalid in (
            {"impressions": -1},
            {"clicks": -1},
            {"conversions": -1},
            {"spend": "-1.00"},
            {"revenue": "-1.00"},
            {"impressions": 4, "clicks": 5},
            {"clicks": 4, "conversions": 5},
        ):
            with self.subTest(invalid=invalid):
                response = self.record(**invalid)
                self.assertEqual(response.status_code, 422, response.text)

    def test_analytics_aggregate_numerators_before_calculating_rates(self):
        self.assertEqual(self.record().status_code, 201)
        second = self.record(
            date="2026-10-21",
            impressions=100,
            clicks=1,
            conversions=1,
            spend="10.00",
            revenue="20.00",
        )
        self.assertEqual(second.status_code, 201, second.text)
        result = self.client.get(f"/api/campaigns/{self.campaign.id}/performance/analytics")
        self.assertEqual(result.status_code, 200, result.text)
        payload = result.json()
        self.assertEqual(payload["impressions"], 1100)
        self.assertEqual(payload["clicks"], 101)
        self.assertEqual(payload["conversions"], 11)
        self.assertEqual(payload["spend"], "60.00")
        self.assertEqual(payload["revenue"], "170.00")
        self.assertEqual(payload["ctr_percent"], "9.18")
        self.assertEqual(payload["conversion_rate_percent"], "10.89")
        self.assertEqual(payload["cpc"], "0.59")
        self.assertEqual(payload["roi_percent"], "183.33")
        self.assertEqual(payload["source"], "manually_entered")

    def test_zero_denominators_missing_revenue_and_zero_spend_are_unavailable(self):
        response = self.record(impressions=0, clicks=0, conversions=0, spend="0.00", revenue=None)
        self.assertEqual(response.status_code, 201, response.text)
        payload = self.client.get(f"/api/campaigns/{self.campaign.id}/performance/analytics").json()
        self.assertIsNone(payload["ctr_percent"])
        self.assertIsNone(payload["conversion_rate_percent"])
        self.assertIsNone(payload["cpc"])
        self.assertIsNone(payload["roi_percent"])
        self.assertIsNone(payload["revenue"])

    def test_date_filtering_empty_results_and_invalid_ranges(self):
        self.assertEqual(self.record().status_code, 201)
        self.record(date="2026-10-21")
        filtered = self.client.get(
            f"/api/campaigns/{self.campaign.id}/performance",
            params={"start_date": "2026-10-21", "end_date": "2026-10-21"},
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()["total"], 1)
        empty = self.client.get(
            f"/api/campaigns/{self.campaign.id}/performance/analytics",
            params={"start_date": "2025-01-01", "end_date": "2025-01-31"},
        )
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["record_count"], 0)
        self.assertEqual(empty.json()["impressions"], 0)
        self.assertIsNone(empty.json()["ctr_percent"])
        invalid = self.client.get(
            f"/api/campaigns/{self.campaign.id}/performance",
            params={"start_date": "2026-10-22", "end_date": "2026-10-21"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_roi_is_unavailable_if_any_days_revenue_is_missing(self):
        self.assertEqual(self.record(revenue="100.00").status_code, 201)
        self.assertEqual(self.record(date="2026-10-21", revenue=None).status_code, 201)
        payload = self.client.get(f"/api/campaigns/{self.campaign.id}/performance/analytics").json()
        self.assertIsNone(payload["revenue"])
        self.assertIsNone(payload["roi_percent"])


if __name__ == "__main__":
    unittest.main()
