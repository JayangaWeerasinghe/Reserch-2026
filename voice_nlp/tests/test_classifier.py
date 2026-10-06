def test_classifier_imports():
    from pipeline.classifier import classify_with_ood
    assert callable(classify_with_ood)

def test_ood_short_text():
    from pipeline.classifier import load_models, classify_with_ood
    load_models()
    result = classify_with_ood("yellow")
    assert result["is_ood"] is True

def test_ood_non_disease():
    from pipeline.classifier import load_models, classify_with_ood
    load_models()
    result = classify_with_ood("i am going to go home today")
    assert result["is_ood"] is True
