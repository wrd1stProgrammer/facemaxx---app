from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from unittest.mock import patch

from app.api.deps import RequestIdentity
from app.repositories.habitdot_repository import HabitdotRepository
from app.schemas.habitdot import HabitdotPaywallViewRequest


@dataclass
class FakeRpcExecutor:
    data: list[dict[str, int]]

    def execute(self) -> "FakeRpcExecutor":
        return self


@dataclass
class FakeSupabaseClient:
    rpc_name: str | None = None
    rpc_params: dict[str, str | None] = field(default_factory=dict)

    def rpc(self, name: str, params: dict[str, str | None]) -> FakeRpcExecutor:
        self.rpc_name = name
        self.rpc_params = params
        return FakeRpcExecutor(data=[{"increment_habitdot_paywall_view": 3}])


class HabitdotRepositoryTest(unittest.TestCase):
    @patch("app.repositories.habitdot_repository.get_supabase_service_client")
    def test_record_paywall_view_increments_install_counter_and_returns_count(self, get_client) -> None:
        # Given
        client = FakeSupabaseClient()
        get_client.return_value = client
        request = HabitdotPaywallViewRequest(
            locale="en-US",
            country_code="us",
            time_zone="America/Los_Angeles",
            app_version="1.0.1",
            build_number="5",
            platform="ios",
        )

        # When
        response = HabitdotRepository().record_paywall_view(
            identity=RequestIdentity(
                user_id=None,
                client_install_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            ),
            request=request,
            inferred_country_code="kr",
        )

        # Then
        self.assertTrue(response.persisted)
        self.assertEqual(response.count, 3)
        self.assertEqual(client.rpc_name, "increment_habitdot_paywall_view")
        self.assertEqual(client.rpc_params["p_client_install_id"], "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        self.assertEqual(client.rpc_params["p_country_code"], "US")
        self.assertEqual(client.rpc_params["p_inferred_country_code"], "KR")

    @patch("app.repositories.habitdot_repository.get_supabase_service_client")
    def test_record_paywall_view_skips_when_install_id_is_missing(self, get_client) -> None:
        # Given
        get_client.return_value = FakeSupabaseClient()
        request = HabitdotPaywallViewRequest(locale="ko", platform="ios")

        # When
        response = HabitdotRepository().record_paywall_view(
            identity=RequestIdentity(user_id=None, client_install_id=None),
            request=request,
        )

        # Then
        self.assertFalse(response.persisted)
        self.assertIsNone(response.count)


if __name__ == "__main__":
    unittest.main()
