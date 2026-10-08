"""Security utility regression tests."""

from app.core.security import (
    TEMPORARY_PASSWORD_SPECIAL_CHARACTERS,
    generate_temporary_password,
)


def test_temporary_password_has_four_letters_and_two_special_characters() -> None:
    for _ in range(100):
        password = generate_temporary_password()

        assert len(password) == 6
        assert sum(character.isalpha() for character in password) == 4
        assert sum(
            character in TEMPORARY_PASSWORD_SPECIAL_CHARACTERS
            for character in password
        ) == 2
