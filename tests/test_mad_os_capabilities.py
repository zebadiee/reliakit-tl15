from mad_os.capabilities import Capability, registry, register_capability


def test_registry_empty_by_default():
    assert registry() == []


def test_register_capability_appends():
    cap = Capability(name="example", explain=True)
    register_capability(cap)
    r = registry()
    assert any(c.name == "example" for c in r)
