import intentkit


def test_public_version_matches_release_candidate() -> None:
    assert intentkit.__version__ == "0.3.0"
