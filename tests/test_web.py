from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture()
def client():
    from web_app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestTaxonomyPresets:
    def test_returns_list(self, client):
        resp = client.get("/api/taxonomy/presets")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_each_preset_has_name_and_file(self, client):
        data = client.get("/api/taxonomy/presets").get_json()
        for item in data:
            assert "name" in item
            assert "file" in item
            assert item["file"].startswith("taxonomies/")

    def test_lavoro_preset_present(self, client):
        data = client.get("/api/taxonomy/presets").get_json()
        names = [item["name"] for item in data]
        assert "lavoro" in names


class TestConfigGet:
    def test_returns_config_keys(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "anthropic_set" in data
        assert "gemini_set" in data
        assert "ollama_model" in data
        assert "active_provider" in data

    def test_api_keys_masked(self, client):
        resp = client.get("/api/config")
        data = resp.get_json()
        # values ending with … are masked; empty keys show "(vuota)"
        key_val = data.get("anthropic_key", "")
        assert "…" in key_val or key_val == "(vuota)" or len(key_val) <= 8


class TestAuth:
    def test_open_when_no_token_configured(self, client):
        with patch("drive_organizer.config.settings") as mock_settings:
            mock_settings.web_auth_token = ""
            resp = client.get("/api/taxonomy/presets")
        assert resp.status_code == 200

    def test_401_when_token_set_and_missing(self, client):
        with patch("drive_organizer.config.settings") as mock_settings:
            mock_settings.web_auth_token = "secret123"
            resp = client.get("/api/taxonomy/presets")
        assert resp.status_code == 401

    def test_200_with_correct_header(self, client):
        with patch("drive_organizer.config.settings") as mock_settings:
            mock_settings.web_auth_token = "secret123"
            resp = client.get("/api/taxonomy/presets", headers={"X-Auth-Token": "secret123"})
        assert resp.status_code == 200

    def test_200_with_correct_query_param(self, client):
        with patch("drive_organizer.config.settings") as mock_settings:
            mock_settings.web_auth_token = "secret123"
            resp = client.get("/api/taxonomy/presets?token=secret123")
        assert resp.status_code == 200

    def test_status_open_without_token(self, client):
        """/ and /api/status are always accessible."""
        with patch("drive_organizer.config.settings") as mock_settings:
            mock_settings.web_auth_token = "secret123"
            # /api/status tries Drive auth but should pass the auth middleware
            # We patch get_drive_service to avoid real OAuth
            with patch("drive_organizer.auth.google_auth.get_drive_service", side_effect=Exception("no drive")):
                resp = client.get("/api/status")
        # status 200 with error payload — middleware allowed it through
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("connected") is False
