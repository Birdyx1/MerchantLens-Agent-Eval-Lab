from merchant_agent.evaluation.reproduction import build_manifest, verify_manifest


def test_manifest_reproducible_when_files_unchanged(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("a,b\n1,2\n", encoding="utf-8")
    manifest = build_manifest(experiment="e1", data_files=[data],
                              commands=["pytest -q"], project_root=tmp_path)
    result = verify_manifest(manifest, project_root=tmp_path)
    assert result["reproducible"] is True
    assert result["checked"] == 1


def test_changed_file_is_not_reproducible(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("a,b\n1,2\n", encoding="utf-8")
    manifest = build_manifest(experiment="e1", data_files=[data],
                              commands=[], project_root=tmp_path)
    data.write_text("a,b\n9,9\n", encoding="utf-8")
    result = verify_manifest(manifest, project_root=tmp_path)
    assert result["reproducible"] is False
    assert result["mismatches"][0]["reason"] == "hash_mismatch"


def test_missing_file_is_not_reproducible(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("x", encoding="utf-8")
    manifest = build_manifest(experiment="e1", data_files=[data],
                              commands=[], project_root=tmp_path)
    data.unlink()
    result = verify_manifest(manifest, project_root=tmp_path)
    assert result["mismatches"][0]["reason"] == "missing"
