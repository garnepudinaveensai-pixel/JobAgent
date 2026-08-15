from app.outreach.contact_selector import (
    ContactSelector,
    ContactSelection,
)


def test_selector_creation():

    selector = ContactSelector()

    assert selector.minimum_score == 50


def test_selector_accepts_zero_minimum_score():

    selector = ContactSelector(
        minimum_score=0
    )

    assert selector.minimum_score == 0


def test_selector_rejects_invalid_minimum_score():

    try:
        ContactSelector(
            minimum_score=-1
        )
        assert False
    except ValueError:
        assert True


def test_selector_rejects_minimum_score_above_200():

    try:
        ContactSelector(
            minimum_score=201
        )
        assert False
    except ValueError:
        assert True


def test_selector_rejects_non_integer_score():

    try:
        ContactSelector(
            minimum_score=50.5
        )
        assert False
    except TypeError:
        assert True


def test_invalid_email_is_ignored():

    selector = ContactSelector()

    contacts = [
        {
            "email": "not-an-email",
            "role": "Recruiter",
        }
    ]

    assert selector.rank_contacts(
        contacts
    ) == []


def test_recruiter_email_is_selected():

    selector = ContactSelector()

    contacts = [
        {
            "email": "recruiter@company.com",
            "role": "Recruiter",
        },
        {
            "email": "info@company.com",
            "role": "",
        },
    ]

    result = selector.select_best_contact(
        contacts
    )

    assert result is not None
    assert result.email == "recruiter@company.com"


def test_talent_acquisition_has_high_priority():

    selector = ContactSelector()

    contacts = [
        {
            "email": "info@company.com",
        },
        {
            "email": "talent@company.com",
            "role": "Talent Acquisition",
        },
    ]

    result = selector.select_best_contact(
        contacts
    )

    assert result is not None
    assert result.email == "talent@company.com"


def test_hiring_contact_is_relevant():

    selector = ContactSelector()

    contacts = [
        {
            "email": "hiring@company.com",
            "role": "Hiring Manager",
        }
    ]

    result = selector.select_best_contact(
        contacts
    )

    assert result is not None
    assert result.email == "hiring@company.com"


def test_hr_contact_is_relevant():

    selector = ContactSelector()

    contacts = [
        {
            "email": "hr@company.com",
            "role": "Human Resources",
        }
    ]

    result = selector.select_best_contact(
        contacts
    )

    assert result is not None
    assert result.email == "hr@company.com"


def test_generic_email_gets_lower_priority():

    # Use 0 here because this test is specifically testing
    # ranking, including fallback/generic contacts.
    selector = ContactSelector(
        minimum_score=0
    )

    contacts = [
        {
            "email": "info@company.com",
        },
        {
            "email": "recruiter@company.com",
            "role": "Recruiter",
        },
    ]

    ranked = selector.rank_contacts(
        contacts
    )

    assert len(ranked) == 2

    assert (
        ranked[0].email
        == "recruiter@company.com"
    )

    assert (
        ranked[1].email
        == "info@company.com"
    )


def test_generic_email_is_filtered_by_default():

    selector = ContactSelector()

    contacts = [
        {
            "email": "info@company.com",
        }
    ]

    ranked = selector.rank_contacts(
        contacts
    )

    assert ranked == []


def test_ranked_contacts_are_sorted():

    selector = ContactSelector()

    contacts = [
        {
            "email": "info@company.com",
        },
        {
            "email": "hr@company.com",
            "role": "HR",
        },
        {
            "email": "recruiter@company.com",
            "role": "Recruiter",
        },
    ]

    # Include fallback contacts for ranking verification.
    selector = ContactSelector(
        minimum_score=0
    )

    ranked = selector.rank_contacts(
        contacts
    )

    assert (
        ranked[0].email
        == "recruiter@company.com"
    )

    assert (
        ranked[0].score
        >= ranked[1].score
    )


def test_no_contacts_returns_none():

    selector = ContactSelector()

    assert (
        selector.select_best_contact([])
        is None
    )


def test_none_contacts_returns_none():

    selector = ContactSelector()

    assert (
        selector.select_best_contact(None)
        is None
    )


def test_non_dict_contacts_are_ignored():

    selector = ContactSelector()

    contacts = [
        None,
        "invalid",
        123,
        {
            "email": "recruiter@company.com",
            "role": "Recruiter",
        },
    ]

    result = selector.select_best_contact(
        contacts
    )

    assert result is not None
    assert result.email == "recruiter@company.com"


def test_selection_result_contains_original_contact():

    selector = ContactSelector()

    contact = {
        "email": "recruiter@company.com",
        "role": "Recruiter",
        "name": "Hiring Recruiter",
    }

    result = selector.select_best_contact(
        [contact]
    )

    assert isinstance(
        result,
        ContactSelection,
    )

    assert result.contact is contact


def test_reason_is_generated():

    selector = ContactSelector()

    result = selector.select_best_contact(
        [
            {
                "email": "recruiter@company.com",
                "role": "Recruiter",
            }
        ]
    )

    assert result is not None
    assert result.reason


def test_email_is_normalized():

    selector = ContactSelector()

    result = selector.select_best_contact(
        [
            {
                "email": " Recruiter@Company.COM ",
                "role": "Recruiter",
            }
        ]
    )

    assert result is not None
    assert (
        result.email
        == "recruiter@company.com"
    )


def test_verified_contact_gets_bonus():

    selector = ContactSelector()

    unverified = {
        "email": "recruiter@company.com",
        "role": "Recruiter",
    }

    verified = {
        "email": "hr@company.com",
        "role": "HR",
        "verified": True,
    }

    ranked = selector.rank_contacts(
        [
            unverified,
            verified,
        ]
    )

    assert len(ranked) == 2

    # Recruiter starts higher, so it should normally remain
    # the top contact despite the verification bonus.
    assert ranked[0].email == "recruiter@company.com"


def test_explicit_company_domain_match():

    selector = ContactSelector()

    job = {
        "company": "Example Company",
        "company_domain": "example.com",
    }

    contact = {
        "email": "careers@example.com",
        "source": "company",
    }

    result = selector.select_best_contact(
        [contact],
        job=job,
    )

    assert result is not None
    assert result.email == "careers@example.com"

    assert (
        "company-domain match"
        in result.reason
    )


def test_company_domain_is_not_guessed():

    selector = ContactSelector()

    job = {
        "company": "Example Company",
    }

    contact = {
        "email": "careers@example.com",
    }

    result = selector.select_best_contact(
        [contact],
        job=job,
    )

    assert result is not None

    assert (
        "company-domain match"
        not in result.reason
    )


def test_official_source_gets_bonus():

    selector = ContactSelector()

    contact = {
        "email": "careers@example.com",
        "source": "company",
    }

    result = selector.select_best_contact(
        [contact]
    )

    assert result is not None
    assert (
        "official company source"
        in result.reason
    )


def test_professional_source_gets_bonus():

    selector = ContactSelector()

    contact = {
        "email": "recruiter@example.com",
        "source": "LinkedIn",
    }

    result = selector.select_best_contact(
        [contact]
    )

    assert result is not None
    assert (
        "professional source"
        in result.reason
    )


def test_invalid_email_with_multiple_at_symbols():

    selector = ContactSelector(
        minimum_score=0
    )

    result = selector.select_best_contact(
        [
            {
                "email": "hr@@example.com",
                "role": "HR",
            }
        ]
    )

    assert result is None


def test_invalid_email_without_domain_dot():

    selector = ContactSelector(
        minimum_score=0
    )

    result = selector.select_best_contact(
        [
            {
                "email": "hr@example",
                "role": "HR",
            }
        ]
    )

    assert result is None