"""Tests for password auth: passphrase generation and user creation."""
import re
from unittest.mock import MagicMock, patch

import pytest

from app.wordlist import generate_passphrase, WORDS


class TestPassphraseGeneration:
    def test_default_four_words(self):
        phrase = generate_passphrase()
        words = phrase.split("-")
        assert len(words) == 4
        for w in words:
            assert w in WORDS

    def test_custom_word_count(self):
        phrase = generate_passphrase(6)
        assert len(phrase.split("-")) == 6

    def test_format(self):
        phrase = generate_passphrase()
        assert re.match(r"^[a-z]+-[a-z]+-[a-z]+-[a-z]+$", phrase)

    def test_uniqueness(self):
        """Generate 100 passphrases — all should be unique (with overwhelming probability)."""
        phrases = {generate_passphrase() for _ in range(100)}
        assert len(phrases) == 100

    def test_wordlist_size(self):
        assert len(WORDS) >= 200  # enough entropy


class TestCreateUserWithPassphrase:
    @patch("app.admin._get_db")
    @patch("app.admin.generate_passphrase", return_value="test-phrase-here-now")
    def test_create_new_user(self, mock_gen, mock_db):
        from app.admin import user_manager

        mock_fb_auth = MagicMock()
        mock_user = MagicMock()
        mock_user.uid = "test-uid-123"
        mock_fb_auth.create_user.return_value = mock_user

        # Mock Firestore
        mock_doc = MagicMock()
        mock_db.return_value.collection.return_value.document.return_value = mock_doc

        with patch("app.admin.fb_auth", mock_fb_auth, create=True):
            with patch.dict("sys.modules", {"firebase_admin.auth": mock_fb_auth}):
                passphrase = user_manager.create_user_with_passphrase("alice@bank.com", "admin@bank.com")

        assert passphrase == "test-phrase-here-now"

    @patch("app.admin._get_db")
    @patch("app.admin.generate_passphrase", return_value="reset-phrase-now-ok")
    def test_reset_existing_user(self, mock_gen, mock_db):
        from app.admin import user_manager

        mock_fb_auth = MagicMock()

        # Simulate EmailAlreadyExistsError
        class FakeEmailExistsError(Exception):
            pass
        mock_fb_auth.EmailAlreadyExistsError = FakeEmailExistsError
        mock_fb_auth.create_user.side_effect = FakeEmailExistsError()
        mock_user = MagicMock()
        mock_user.uid = "existing-uid"
        mock_fb_auth.get_user_by_email.return_value = mock_user

        mock_doc = MagicMock()
        mock_db.return_value.collection.return_value.document.return_value = mock_doc

        with patch.dict("sys.modules", {"firebase_admin.auth": mock_fb_auth}):
            passphrase = user_manager.create_user_with_passphrase("bob@bank.com", "admin@bank.com")

        assert passphrase == "reset-phrase-now-ok"
