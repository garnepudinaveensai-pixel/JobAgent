from app.cli import build_parser


def test_discover_source_defaults_to_greenhouse():
    parser = build_parser()

    args = parser.parse_args(
        [
            "discover",
            "--board-url",
            "https://boards.greenhouse.io/example",
            "--keywords",
            "electrical engineer",
        ]
    )

    assert args.source == "greenhouse"


def test_discover_accepts_lever_source():
    parser = build_parser()

    args = parser.parse_args(
        [
            "discover",
            "--source",
            "lever",
            "--board-url",
            "https://jobs.lever.co/example",
            "--keywords",
            "software engineer",
        ]
    )

    assert args.source == "lever"


def test_discover_accepts_workday_source():
    parser = build_parser()

    args = parser.parse_args(
        [
            "discover",
            "--source",
            "workday",
            "--board-url",
            "https://example.workday.com",
            "--keywords",
            "engineer",
        ]
    )

    assert args.source == "workday"


def test_discover_preserves_location():
    parser = build_parser()

    args = parser.parse_args(
        [
            "discover",
            "--source",
            "lever",
            "--board-url",
            "https://jobs.lever.co/example",
            "--keywords",
            "engineer",
            "--location",
            "Hyderabad",
        ]
    )

    assert args.source == "lever"
    assert args.location == "Hyderabad"


def test_discover_store_flag():
    parser = build_parser()

    args = parser.parse_args(
        [
            "discover",
            "--source",
            "workday",
            "--board-url",
            "https://example.workday.com",
            "--keywords",
            "engineer",
            "--store",
        ]
    )

    assert args.store is True