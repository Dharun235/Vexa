from pathlib import Path

from vexa import model


def test_clean_install_uses_bundled_model(tmp_path, monkeypatch):
    monkeypatch.delenv("VEXA_MODEL_PATH", raising=False)
    monkeypatch.setattr(model, "user_data_path", lambda *args, **kwargs: tmp_path)
    package = tmp_path / "package"
    bundled = package / "data" / "yolo11n.onnx"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"bundled model")
    monkeypatch.setattr(model, "__file__", str(package / "model.py"))
    path = model.model_path()
    assert path.name == "yolo11n.onnx"
    assert path.parent == Path(model.__file__).with_name("data")
    assert path.is_file()


def test_user_model_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("VEXA_MODEL_PATH", raising=False)
    monkeypatch.setattr(model, "user_data_path", lambda *args, **kwargs: tmp_path)
    user = model.user_model_path()
    user.parent.mkdir(parents=True)
    user.write_bytes(b"user model")
    assert model.model_path() == user
