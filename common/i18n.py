# encoding:utf-8

"""English-only UI strings.

Call sites still pass a Chinese and an English sentence. The English sentence
is the one that is shown. Language detection and the old Chinese catalogs are
gone, so a system locale or a saved ``maia_lang`` cannot switch the product.
"""

EN = "en"
ZH = "zh"
ZH_HANT = "zh-Hant"
SUPPORTED = (EN,)
DEFAULT_LANG = EN

_resolved_lang = EN


def to_traditional(text):
    """Kept so older callers do not crash. Text is returned unchanged."""
    return text


def _normalize(raw):
    del raw
    return EN


def detect_language():
    return EN


def resolve_language(configured=None):
    del configured
    global _resolved_lang
    _resolved_lang = EN
    return EN


def set_language(lang):
    del lang
    global _resolved_lang
    _resolved_lang = EN
    return EN


def get_language():
    return EN


def is_zh():
    return False


def t(text, en_text=None):
    """Return the English sentence.

    Callers pass the English sentence alone, or a legacy pair whose second
    sentence is the English one.
    """
    if en_text is None:
        return text
    return en_text
