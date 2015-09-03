from jep.syntax import StaticSyntaxProvider


def test_empty_registry():
    provider = StaticSyntaxProvider()
    assert len(provider.get_syntaxes()) == 0
