from app.outreach.contact_finder import Contact
from app.outreach.contact_store import ContactStore


def make_contact(
    email="hr@example.com",
    name="Jane Recruiter",
):
    return Contact(
        email=email,
        full_name=name,
        position="Technical Recruiter",
        department="Recruiting",
        company="Example Corp",
        confidence=95,
        source="hunter",
        verification_status="valid",
    )


def test_store_creates_storage(tmp_path):

    path = tmp_path / "contacts.json"

    store = ContactStore(
        storage_path=str(path)
    )

    assert path.parent.exists()
    assert store.count() == 0


def test_add_contact(tmp_path):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    contact_id = store.add_contact(
        "job-123",
        make_contact(),
    )

    assert contact_id == (
        "job-123|hr@example.com"
    )

    assert store.count() == 1


def test_get_contact(tmp_path):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    contact_id = store.add_contact(
        "job-123",
        make_contact(),
    )

    contact = store.get_contact(
        contact_id
    )

    assert contact is not None
    assert contact["email"] == (
        "hr@example.com"
    )
    assert contact["job_id"] == "job-123"


def test_get_contacts_for_job(tmp_path):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    store.add_contact(
        "job-123",
        make_contact(
            "hr@example.com"
        ),
    )

    store.add_contact(
        "job-123",
        make_contact(
            "recruiter@example.com"
        ),
    )

    store.add_contact(
        "job-456",
        make_contact(
            "other@example.com"
        ),
    )

    contacts = store.get_contacts_for_job(
        "job-123"
    )

    assert len(contacts) == 2


def test_duplicate_contact_not_created(
    tmp_path,
):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    first = store.add_contact(
        "job-123",
        make_contact(),
    )

    second = store.add_contact(
        "job-123",
        make_contact(),
    )

    assert first == second
    assert store.count() == 1


def test_same_email_different_jobs_is_allowed(
    tmp_path,
):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    first = store.add_contact(
        "job-123",
        make_contact(),
    )

    second = store.add_contact(
        "job-456",
        make_contact(),
    )

    assert first != second
    assert store.count() == 2


def test_add_contacts(tmp_path):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    contacts = [
        make_contact(
            "hr@example.com"
        ),
        make_contact(
            "recruiter@example.com"
        ),
    ]

    ids = store.add_contacts(
        "job-123",
        contacts,
    )

    assert len(ids) == 2
    assert store.count_for_job(
        "job-123"
    ) == 2


def test_update_status(tmp_path):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    contact_id = store.add_contact(
        "job-123",
        make_contact(),
    )

    assert store.update_status(
        contact_id,
        "selected",
    )

    assert store.get_status(
        contact_id
    ) == "selected"


def test_get_contacts_by_status(
    tmp_path,
):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    first = store.add_contact(
        "job-123",
        make_contact(
            "hr@example.com"
        ),
    )

    second = store.add_contact(
        "job-123",
        make_contact(
            "recruiter@example.com"
        ),
    )

    store.update_status(
        first,
        "selected",
    )

    store.update_status(
        second,
        "sent",
    )

    selected = (
        store.get_contacts_by_status(
            "selected"
        )
    )

    assert len(selected) == 1
    assert selected[0]["email"] == (
        "hr@example.com"
    )


def test_has_contact(tmp_path):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    store.add_contact(
        "job-123",
        make_contact(),
    )

    assert store.has_contact(
        "job-123",
        "hr@example.com",
    )

    assert not store.has_contact(
        "job-123",
        "missing@example.com",
    )


def test_update_contact(tmp_path):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    contact_id = store.add_contact(
        "job-123",
        make_contact(),
    )

    assert store.update_contact(
        contact_id,
        {
            "position": "Senior Recruiter"
        },
    )

    contact = store.get_contact(
        contact_id
    )

    assert contact["position"] == (
        "Senior Recruiter"
    )


def test_update_email_changes_id(
    tmp_path,
):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    contact_id = store.add_contact(
        "job-123",
        make_contact(),
    )

    assert store.update_contact(
        contact_id,
        {
            "email": (
                "newhr@example.com"
            )
        },
    )

    assert (
        store.get_contact(
            contact_id
        )
        is None
    )

    new_id = (
        "job-123|newhr@example.com"
    )

    contact = store.get_contact(
        new_id
    )

    assert contact is not None
    assert contact["email"] == (
        "newhr@example.com"
    )


def test_persistence(tmp_path):

    path = tmp_path / "contacts.json"

    store = ContactStore(
        storage_path=str(path)
    )

    contact_id = store.add_contact(
        "job-123",
        make_contact(),
    )

    new_store = ContactStore(
        storage_path=str(path)
    )

    contact = new_store.get_contact(
        contact_id
    )

    assert contact is not None
    assert contact["email"] == (
        "hr@example.com"
    )


def test_invalid_status_rejected(
    tmp_path,
):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    try:
        store.add_contact(
            "job-123",
            make_contact(),
            status="invalid",
        )

        assert False

    except ValueError:
        assert True


def test_missing_email_rejected(
    tmp_path,
):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    try:
        store.add_contact(
            "job-123",
            {
                "full_name": "Jane Recruiter"
            },
        )

        assert False

    except ValueError:
        assert True


def test_missing_job_id_rejected(
    tmp_path,
):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    try:
        store.add_contact(
            "",
            make_contact(),
        )

        assert False

    except ValueError:
        assert True


def test_update_missing_contact(
    tmp_path,
):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    assert not store.update_status(
        "missing",
        "sent",
    )


def test_invalid_update_status(
    tmp_path,
):

    store = ContactStore(
        storage_path=str(
            tmp_path / "contacts.json"
        )
    )

    contact_id = store.add_contact(
        "job-123",
        make_contact(),
    )

    try:
        store.update_status(
            contact_id,
            "invalid",
        )

        assert False

    except ValueError:
        assert True