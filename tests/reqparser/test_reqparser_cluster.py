import pytest


def test_country_code():
    from gluuapi.reqparser.cluster import country_code
    assert country_code("US", "countryCode") == "US"


def test_invalid_country_code():
    from gluuapi.reqparser.cluster import country_code

    with pytest.raises(ValueError):
        result = country_code("USA", "countryCode")
        assert "countryCode" in result


def test_admin_email():
    from gluuapi.reqparser.cluster import admin_email
    assert admin_email("support@example.com", "admin_email") == "support@example.com"


@pytest.mark.parametrize("email", [
    "random",
    "random@example",
    "random@",
])
def test_invalid_admin_email(email):
    from gluuapi.reqparser.cluster import admin_email

    with pytest.raises(ValueError):
        result = admin_email(email, "admin_email")
        assert "admin_email" in result
