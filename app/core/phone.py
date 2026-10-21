import re

DEFAULT_COUNTRY_CODE = "855"  # Cambodia

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_KH = re.compile(r"^\+855[1-9]\d{7,8}$")  # 8-9 digits after 855


def normalize_phone(v: str | None, default_cc: str = DEFAULT_COUNTRY_CODE) -> str | None:
    """Convert user input to E.164.

    0974242347      -> +855974242347
    097 424 2347    -> +855974242347
    855974242347    -> +855974242347
    +855 97 424 2347 -> +855974242347
    +8550974242347  -> +855974242347  (stray trunk zero removed)
    """
    if v is None:
        return None

    v = re.sub(r"[\s\-().]", "", v.strip())
    if not v:
        return None

    if v.startswith("00"):                      # 0085597... -> +85597...
        v = "+" + v[2:]
    elif v.startswith("+"):
        pass
    elif v.startswith("0"):                     # local: 097... -> +85597...
        v = f"+{default_cc}{v[1:]}"
    elif v.startswith(default_cc):              # 85597... -> +85597...
        v = "+" + v
    else:
        raise ValueError("Phone must start with 0 or a country code, e.g. 0974242347")

    if v.startswith(f"+{default_cc}0"):         # +85509... -> +8559...
        v = f"+{default_cc}{v[len(default_cc) + 2:]}"

    if v.startswith(f"+{default_cc}"):
        if not _KH.match(v):
            raise ValueError("Invalid Cambodian phone number")
    elif not _E164.match(v):
        raise ValueError("Invalid phone number")

    return v