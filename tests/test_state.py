import json
import os
from bambu_inventory.state import StateStore


def test_get_last_seen_id_returns_none_when_file_missing(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.get_last_seen_id() is None


def test_set_then_get_last_seen_id_roundtrips(tmp_path):
    path = str(tmp_path / "state.json")
    store = StateStore(path)
    store.set_last_seen_id("12345")
    assert store.get_last_seen_id() == "12345"


def test_set_last_seen_id_persists_to_disk(tmp_path):
    path = str(tmp_path / "state.json")
    store = StateStore(path)
    store.set_last_seen_id("999")

    reloaded = StateStore(path)
    assert reloaded.get_last_seen_id() == "999"


def test_set_last_seen_id_overwrites_previous_value(tmp_path):
    path = str(tmp_path / "state.json")
    store = StateStore(path)
    store.set_last_seen_id("1")
    store.set_last_seen_id("2")
    assert store.get_last_seen_id() == "2"
