"""
PII masking helpers — mask_address, mask_email, hash_email.

SEC-010 + BACK-013 + COMP-024. DB veya HTTP gerekmez; saf birim testler.
"""
from app.core.masking import hash_email, mask_address, mask_email


# ─── mask_email (SEC-010) ────────────────────────────────────────────────────


class TestMaskEmail:
    def test_typical_email_masks_local_part(self):
        # ilk + son karakter korunur, ortasi *
        assert mask_email("celikada@gmail.com") == "c******a@gmail.com"

    def test_short_local_part_two_chars_uses_single_star(self):
        # 2 char local — orta gosterilmemeli
        assert mask_email("ab@example.com") == "*@example.com"

    def test_single_char_local_part(self):
        assert mask_email("a@example.com") == "*@example.com"

    def test_three_char_local_part(self):
        # 3 char -> "a*c" (ilk + 1 yildiz + son)
        assert mask_email("abc@example.com") == "a*c@example.com"

    def test_empty_returns_empty(self):
        assert mask_email("") == ""

    def test_none_returns_empty(self):
        assert mask_email(None) == ""

    def test_no_at_sign_returns_triple_star(self):
        # Email-shaped degil — tum string PII olabilir, generic mask
        assert mask_email("bozuk-email-string") == "***"

    def test_domain_preserved(self):
        # Domain her zaman korunur (audit/log analiz icin)
        assert mask_email("user@mailbox.kfinans.app") == "u**r@mailbox.kfinans.app"

    def test_unicode_email_handled(self):
        # IDN gibi exotic karakterler patlamamali
        result = mask_email("üye@örnek.com")
        assert result.endswith("@örnek.com")
        assert "*" in result

    def test_email_with_plus_alias(self):
        # foo+tag@gmail.com -> f*****g@gmail.com (local-part'in tamamı maskelenir)
        assert mask_email("foo+tag@gmail.com") == "f*****g@gmail.com"

    def test_full_email_not_in_output(self):
        # Asla ham email plaintext donmemeli (regex kontrol)
        for ham in ["celikada@gmail.com", "test.user+x@example.org"]:
            masked = mask_email(ham)
            local = ham.split("@")[0]
            # Local part'in tamami output'ta olmamali
            assert local not in masked


# ─── hash_email (SEC-010) ────────────────────────────────────────────────────


class TestHashEmail:
    def test_returns_8_hex_chars(self):
        h = hash_email("celikada@gmail.com")
        assert len(h) == 8
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_email_same_hash(self):
        a = hash_email("foo@bar.com")
        b = hash_email("foo@bar.com")
        assert a == b

    def test_case_insensitive(self):
        # lowercase normalize
        assert hash_email("Foo@Bar.COM") == hash_email("foo@bar.com")

    def test_different_emails_different_hashes(self):
        # Trivial collision degil — birinci 8 char yeterli ayirici
        a = hash_email("user1@example.com")
        b = hash_email("user2@example.com")
        assert a != b

    def test_empty_returns_empty(self):
        assert hash_email("") == ""
        assert hash_email(None) == ""


# ─── mask_address (existing, sanity guards) ─────────────────────────────────


class TestMaskAddress:
    def test_xpub_masked_correctly(self):
        addr = "xpub6CUGRUonZSQ4TWtTMmzXdrXDtypWKi"
        masked = mask_address(addr)
        assert masked.startswith("xpub6C")
        assert masked.endswith(addr[-4:])
        assert "..." in masked

    def test_short_address_untouched(self):
        assert mask_address("abc") == "abc"
        assert mask_address("12345678") == "12345678"

    def test_empty_returns_empty(self):
        assert mask_address("") == ""
