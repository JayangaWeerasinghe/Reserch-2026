def test_detector_imports():
    from pipeline.detector import detect_with_ood, load_model
    assert callable(detect_with_ood)
    assert callable(load_model)
