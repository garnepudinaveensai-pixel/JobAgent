def test_all_resumes_contain_meaningful_content(resume_texts):

    required_signals = [
        "education",
        "skills",
        "experience",
        "project",
        "internship",
    ]

    for filename, text in resume_texts.items():

        normalized = text.lower()

        signal_count = sum(
            1
            for signal in required_signals
            if signal in normalized
        )

        assert signal_count >= 2, (
            f"{filename} does not appear to contain "
            f"enough resume content."
        )