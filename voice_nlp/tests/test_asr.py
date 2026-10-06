def test_asr_imports():
    from pipeline.asr import transcribe_audio
    assert callable(transcribe_audio)
