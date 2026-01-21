from mad_os.core.mode import Mode, resolve_mode


def test_mode_enum_members():
    assert Mode.OBSERVER.value == "observer"
    assert Mode.OPERATOR.value == "operator"
    assert Mode.APPRENTICE.value == "apprentice"
    assert Mode.LOCKED.value == "locked"


def test_resolve_mode_defaults_to_observer():
    assert resolve_mode({}) == Mode.OBSERVER


def test_resolve_mode_prefers_ct_mode():
    assert resolve_mode({"CT_MODE": "LOCKED"}) == Mode.LOCKED
    assert resolve_mode({"TAQCO_MODE": "observer"}) == Mode.OBSERVER
