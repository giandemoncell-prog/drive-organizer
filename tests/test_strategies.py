from datetime import datetime, timezone

from drive_organizer.strategies.by_date import DateStrategy
from drive_organizer.strategies.by_type import FileTypeStrategy
from tests.helpers import make_file


class TestFileTypeStrategy:
    def setup_method(self):
        self.strategy = FileTypeStrategy()

    def test_pdf_by_mime(self):
        f = make_file(mime_type="application/pdf")
        res = self.strategy.classify_without_ai(f)
        assert res.target_path == "PDF"
        assert res.confidence == 1.0
        assert res.provider == "deterministic"

    def test_gdoc(self):
        f = make_file(mime_type="application/vnd.google-apps.document")
        assert self.strategy.classify_without_ai(f).target_path == "Documenti"

    def test_gsheet(self):
        f = make_file(mime_type="application/vnd.google-apps.spreadsheet")
        assert self.strategy.classify_without_ai(f).target_path == "Fogli"

    def test_image_by_mime(self):
        f = make_file(mime_type="image/jpeg")
        assert self.strategy.classify_without_ai(f).target_path == "Immagini"

    def test_video_by_mime(self):
        f = make_file(mime_type="video/mp4")
        assert self.strategy.classify_without_ai(f).target_path == "Video"

    def test_extension_fallback(self):
        f = make_file(mime_type="application/octet-stream", file_extension="py")
        assert self.strategy.classify_without_ai(f).target_path == "Codice"

    def test_extension_case_insensitive(self):
        f = make_file(mime_type="application/octet-stream", file_extension="PDF")
        assert self.strategy.classify_without_ai(f).target_path == "PDF"

    def test_unknown_falls_to_altro(self):
        f = make_file(mime_type="application/octet-stream", file_extension="xyz")
        assert self.strategy.classify_without_ai(f).target_path == "Altro"

    def test_does_not_require_ai(self):
        assert self.strategy.requires_ai() is False

    def test_allowed_folders_includes_altro(self):
        assert "Altro" in self.strategy.allowed_folders()

    def test_allowed_folders_includes_pdf(self):
        assert "PDF" in self.strategy.allowed_folders()

    def test_mime_takes_precedence_over_extension(self):
        f = make_file(mime_type="application/pdf", file_extension="doc")
        assert self.strategy.classify_without_ai(f).target_path == "PDF"


class TestDateStrategy:
    def test_year_month(self):
        strategy = DateStrategy()
        f = make_file(modified_time=datetime(2023, 7, 4, tzinfo=timezone.utc))
        assert strategy.classify_without_ai(f).target_path == "2023/Luglio"

    def test_year_only(self):
        strategy = DateStrategy(year_only=True)
        f = make_file(modified_time=datetime(2021, 1, 15, tzinfo=timezone.utc))
        assert strategy.classify_without_ai(f).target_path == "2021"

    def test_uses_created_time(self):
        strategy = DateStrategy(use_created=True)
        f = make_file(
            created_time=datetime(2020, 12, 1, tzinfo=timezone.utc),
            modified_time=datetime(2023, 7, 4, tzinfo=timezone.utc),
        )
        assert strategy.classify_without_ai(f).target_path == "2020/Dicembre"

    def test_uses_modified_time_by_default(self):
        strategy = DateStrategy()
        f = make_file(
            created_time=datetime(2020, 12, 1, tzinfo=timezone.utc),
            modified_time=datetime(2023, 7, 4, tzinfo=timezone.utc),
        )
        assert strategy.classify_without_ai(f).target_path == "2023/Luglio"

    def test_all_months(self):
        strategy = DateStrategy()
        expected = [
            "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
        ]
        for month_num, month_name in enumerate(expected, 1):
            f = make_file(modified_time=datetime(2024, month_num, 1, tzinfo=timezone.utc))
            assert strategy.classify_without_ai(f).target_path == f"2024/{month_name}"

    def test_confidence_is_one(self):
        assert DateStrategy().classify_without_ai(make_file()).confidence == 1.0

    def test_provider_is_deterministic(self):
        assert DateStrategy().classify_without_ai(make_file()).provider == "deterministic"

    def test_does_not_require_ai(self):
        assert DateStrategy().requires_ai() is False
