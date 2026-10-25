"""The runtime is English only.

``t()`` used to pick a Chinese sentence when the locale or ``maia_lang`` said
so. Those catalogs are gone: the English sentence is the one that is returned.
"""

from common import i18n


def test_t_returns_the_english_sentence_even_if_a_caller_asks_for_chinese():
    i18n.set_language("zh")
    i18n.resolve_language("zh-Hant")
    assert i18n.get_language() == "en"
    assert i18n.is_zh() is False
    assert i18n.t("Cancelled") == "Cancelled"
