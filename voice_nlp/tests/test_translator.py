def test_translator_imports():
    from pipeline.translator import translate_to_english
    assert callable(translate_to_english)

def test_apply_correction_kiribath():
    from pipeline.translator import apply_correction
    result = apply_correction("patches of kiribath on the leaf")
    assert "leaf blast" in result.lower()

def test_apply_correction_noop():
    from pipeline.translator import apply_correction
    text = "diamond shaped gray lesion on paddy leaf"
    assert apply_correction(text) == text
