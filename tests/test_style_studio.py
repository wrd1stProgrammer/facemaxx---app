import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anyio
from fastapi import HTTPException

from app.api.deps import RequestIdentity
from app.api.routes.style_studio import create_preview
from app.schemas.style_studio import StudioMode, StudioRequest, StudioResponse
from app.services.style_studio import EDIT_SCOPES, STYLE_CATALOG, catalog_detail, decode_photo, generate_style


PHOTO = base64.b64encode(b"\xff\xd8\xff" + b"x" * 100).decode()


class StyleStudioTests(unittest.TestCase):
    def test_catalog_has_curated_distinct_choices_per_mode(self):
        expected_counts = {"hairstyle": 100, "glasses": 100, "makeup": 100,
                           "eye-makeup": 100, "eyebrows": 75, "beard": 75,
                           "hair-color": 70, "lip-color": 70, "bangs": 50,
                           "clothing-color": 50}
        for mode in StudioMode:
            key = "hairstyle" if mode == StudioMode.SALON_CARD else mode.value
            items = STYLE_CATALOG[key]
            self.assertEqual(len(items), expected_counts[key], key)
            self.assertEqual(len({item["name"] for item in items}), len(items), key)
            self.assertEqual(len({item["detail"] for item in items}), len(items), key)
            for item in items:
                self.assertTrue(item["korean"])
                self.assertEqual(catalog_detail(mode, item["name"]), item["detail"])
                self.assertIn(item["audience"], {"men", "women", "unisex"})

    def test_catalog_thumbnail_cells_are_unique_and_in_bounds(self):
        for items in STYLE_CATALOG.values():
            assets = [item["imageAsset"] for item in items if item.get("imageAsset")]
            self.assertEqual(len(assets), len(set(assets)))
            cells = []
            for item in items:
                if "atlas" not in item:
                    continue
                self.assertLess(item["tile"], item["columns"] * item["rows"])
                cells.append((item["atlas"], item["tile"]))
            self.assertEqual(len(cells), len(set(cells)))

    def payload(self, mode=StudioMode.HAIRSTYLE):
        return StudioRequest(request_id=uuid4(), mode=mode, style="Natural style", photo_base64=PHOTO)

    def test_all_modes_reach_image_provider(self):
        async def run():
            client = MagicMock()
            client.images.edit = AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(b64_json=PHOTO)]))
            client.responses.parse = AsyncMock(return_value=SimpleNamespace(output_parsed=SimpleNamespace(
                consultation="Discuss length", cut="Soft layers", texture="Natural", styling="Air dry", maintenance="Trim")))
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=None)
            from app.schemas.style_studio import SalonInstructions
            client.responses.parse.return_value.output_parsed = SalonInstructions(
                consultation="Discuss length", cut="Soft layers", texture="Natural", styling="Air dry", maintenance="Trim")
            with patch("app.services.style_studio.AsyncOpenAI", return_value=client):
                for mode in StudioMode:
                    response = await generate_style(self.payload(mode))
                    self.assertEqual(response.mode, mode)
                    self.assertEqual(response.image_base64, PHOTO)
                    self.assertEqual(response.salon is not None, mode == StudioMode.SALON_CARD)
            self.assertEqual(client.images.edit.await_count, len(StudioMode))
            self.assertEqual(set(EDIT_SCOPES), set(StudioMode))
        anyio.run(run)

    def test_invalid_image_rejected(self):
        for value in ["not-base64", base64.b64encode(b"not an image").decode()]:
            with self.assertRaises(HTTPException):
                decode_photo(value)

    def test_paid_result_retry_is_cached_and_bound_to_input(self):
        async def run():
            payload = self.payload()
            identity = RequestIdentity(user_id=None, client_install_id=str(uuid4()))
            repository = MagicMock()
            repository.app_user_id_for_identity.return_value = identity.client_install_id
            repository.reserve_pro_scan.return_value = SimpleNamespace(allowed=True)
            response = StudioResponse(id=payload.request_id, mode=payload.mode, style=payload.style, image_base64=PHOTO)
            with tempfile.TemporaryDirectory() as directory, \
                    patch("app.api.routes.style_studio.RESULT_ROOT", Path(directory)), \
                    patch("app.api.routes.style_studio.get_settings", return_value=SimpleNamespace(openai_api_key="test")), \
                    patch("app.api.routes.style_studio.PurchaseRepository", return_value=repository), \
                    patch("app.api.routes.style_studio.generate_style", new=AsyncMock(return_value=response)) as generate:
                self.assertEqual(await create_preview(payload, identity), response)
                self.assertEqual(await create_preview(payload, identity), response)
                self.assertEqual(generate.await_count, 1)
                repository.reserve_pro_scan.assert_called_once()
                repository.refund_reserved_credit.assert_not_called()
                with self.assertRaises(HTTPException) as error:
                    await create_preview(payload.model_copy(update={"style": "Different"}), identity)
                self.assertEqual(error.exception.status_code, 409)
        anyio.run(run)

    def test_generation_failure_refunds_and_allows_retry(self):
        async def run():
            payload = self.payload()
            identity = RequestIdentity(user_id=None, client_install_id=str(uuid4()))
            repository = MagicMock()
            repository.app_user_id_for_identity.return_value = identity.client_install_id
            reservation = SimpleNamespace(allowed=True)
            repository.reserve_pro_scan.return_value = reservation
            with tempfile.TemporaryDirectory() as directory, \
                    patch("app.api.routes.style_studio.RESULT_ROOT", Path(directory)), \
                    patch("app.api.routes.style_studio.get_settings", return_value=SimpleNamespace(openai_api_key="test")), \
                    patch("app.api.routes.style_studio.PurchaseRepository", return_value=repository), \
                    patch("app.api.routes.style_studio.generate_style", new=AsyncMock(side_effect=TimeoutError)):
                with self.assertRaises(HTTPException) as error:
                    await create_preview(payload, identity)
                self.assertEqual(error.exception.status_code, 502)
                repository.refund_reserved_credit.assert_called_once_with(reservation)
                self.assertEqual(list(Path(directory).rglob("*.json")), [])
        anyio.run(run)

    def test_no_credit_never_calls_provider(self):
        async def run():
            repository = MagicMock()
            repository.app_user_id_for_identity.return_value = "guest"
            repository.reserve_pro_scan.return_value = SimpleNamespace(allowed=False)
            with tempfile.TemporaryDirectory() as directory, \
                    patch("app.api.routes.style_studio.RESULT_ROOT", Path(directory)), \
                    patch("app.api.routes.style_studio.get_settings", return_value=SimpleNamespace(openai_api_key="test")), \
                    patch("app.api.routes.style_studio.PurchaseRepository", return_value=repository), \
                    patch("app.api.routes.style_studio.generate_style", new=AsyncMock()) as generate:
                with self.assertRaises(HTTPException) as error:
                    await create_preview(self.payload(), RequestIdentity(None, "guest"))
                self.assertEqual(error.exception.status_code, 402)
                generate.assert_not_awaited()
        anyio.run(run)


if __name__ == "__main__":
    unittest.main()
