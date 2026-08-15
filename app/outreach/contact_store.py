from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.outreach.contact_finder import Contact


class ContactStore:
    """
    Persistent storage for professional contacts discovered
    for job opportunities.

    Contacts are stored separately from jobs so that outreach
    data can evolve independently from the job database.

    Default storage:
        data/jobs/contacts.json
    """

    VALID_STATUSES = {
        "not_contacted",
        "selected",
        "sent",
        "failed",
        "replied",
    }

    def __init__(
        self,
        storage_path: str = "data/jobs/contacts.json",
    ):
        self.storage_path = Path(storage_path)

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._data = self._load()

    # ========================================================
    # LOAD / SAVE
    # ========================================================

    def _load(self) -> dict:
        """
        Load contact storage safely.
        """

        if not self.storage_path.exists():
            return {"contacts": {}}

        try:
            with self.storage_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return {"contacts": {}}

            if not isinstance(
                data.get("contacts"),
                dict,
            ):
                data["contacts"] = {}

            return data

        except (
            json.JSONDecodeError,
            OSError,
        ):
            return {"contacts": {}}

    def _save(self) -> None:
        """
        Persist contact data atomically.
        """

        temporary_path = self.storage_path.with_suffix(
            ".tmp"
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                self._data,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary_path.replace(
            self.storage_path
        )

    # ========================================================
    # CONTACT ID
    # ========================================================

    @staticmethod
    def _contact_id(
        job_id: str,
        email: str,
    ) -> str:
        """
        Generate a stable contact identifier.

        The same email for different jobs remains a separate
        outreach record because outreach is job-specific.
        """

        job_id = str(job_id).strip()

        email = str(email).strip().lower()

        if not job_id:
            raise ValueError(
                "job_id cannot be empty."
            )

        if not email:
            raise ValueError(
                "email cannot be empty."
            )

        return f"{job_id}|{email}"

    # ========================================================
    # ADD CONTACT
    # ========================================================

    def add_contact(
        self,
        job_id: str,
        contact: Contact | dict,
        status: str = "not_contacted",
    ) -> str:
        """
        Add a contact for a specific job.

        Existing contacts are updated rather than duplicated.

        Returns:
            Stable contact ID.
        """

        if status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid contact status: {status}"
            )

        if isinstance(contact, Contact):
            contact_data = contact.to_dict()
        elif isinstance(contact, dict):
            contact_data = dict(contact)
        else:
            raise TypeError(
                "contact must be a Contact or dict."
            )

        email = str(
            contact_data.get(
                "email",
                "",
            )
        ).strip().lower()

        if not email:
            raise ValueError(
                "Contact must contain an email."
            )

        job_id = str(job_id).strip()

        if not job_id:
            raise ValueError(
                "job_id cannot be empty."
            )

        contact_id = self._contact_id(
            job_id,
            email,
        )

        existing = self._data[
            "contacts"
        ].get(
            contact_id,
            {},
        )

        record = {
            **existing,
            **contact_data,
            "contact_id": contact_id,
            "job_id": job_id,
            "email": email,
            "status": existing.get(
                "status",
                status,
            ),
        }

        self._data[
            "contacts"
        ][contact_id] = record

        self._save()

        return contact_id

    # ========================================================
    # ADD MANY
    # ========================================================

    def add_contacts(
        self,
        job_id: str,
        contacts: list[Contact | dict],
        status: str = "not_contacted",
    ) -> list[str]:
        """
        Add multiple contacts for a job.

        Duplicate email addresses are automatically handled
        by the stable contact ID.
        """

        contact_ids = []

        for contact in contacts:
            try:
                contact_id = self.add_contact(
                    job_id=job_id,
                    contact=contact,
                    status=status,
                )

                contact_ids.append(
                    contact_id
                )

            except (
                ValueError,
                TypeError,
            ):
                continue

        return contact_ids

    # ========================================================
    # GET CONTACT
    # ========================================================

    def get_contact(
        self,
        contact_id: str,
    ) -> Optional[dict]:
        """
        Return one contact.
        """

        return self._data[
            "contacts"
        ].get(contact_id)

    # ========================================================
    # GET BY JOB
    # ========================================================

    def get_contacts_for_job(
        self,
        job_id: str,
    ) -> list[dict]:
        """
        Return all contacts associated with a job.
        """

        job_id = str(job_id).strip()

        return [
            contact
            for contact in self._data[
                "contacts"
            ].values()
            if contact.get("job_id") == job_id
        ]

    # ========================================================
    # GET BY EMAIL
    # ========================================================

    def get_contact_for_job_by_email(
        self,
        job_id: str,
        email: str,
    ) -> Optional[dict]:
        """
        Find one contact for a job by email.
        """

        contact_id = self._contact_id(
            job_id,
            email,
        )

        return self.get_contact(
            contact_id
        )

    # ========================================================
    # UPDATE
    # ========================================================

    def update_contact(
        self,
        contact_id: str,
        updates: dict,
    ) -> bool:
        """
        Update an existing contact.

        Returns:
            True if updated.
            False if contact does not exist.
        """

        contact = self.get_contact(
            contact_id
        )

        if contact is None:
            return False

        if not isinstance(
            updates,
            dict,
        ):
            raise TypeError(
                "updates must be a dictionary."
            )

        if "status" in updates:
            status = updates["status"]

            if status not in self.VALID_STATUSES:
                raise ValueError(
                    f"Invalid contact status: {status}"
                )

        if "email" in updates:
            email = str(
                updates["email"]
            ).strip().lower()

            if not email:
                raise ValueError(
                    "email cannot be empty."
                )

            # Changing an email changes the stable ID.
            old_job_id = contact["job_id"]

            new_contact_id = self._contact_id(
                old_job_id,
                email,
            )

            updated = {
                **contact,
                **updates,
                "email": email,
                "contact_id": new_contact_id,
            }

            del self._data[
                "contacts"
            ][contact_id]

            self._data[
                "contacts"
            ][new_contact_id] = updated

        else:
            contact.update(updates)

        self._save()

        return True

    # ========================================================
    # STATUS
    # ========================================================

    def update_status(
        self,
        contact_id: str,
        status: str,
    ) -> bool:
        """
        Update contact outreach status.
        """

        if status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid contact status: {status}"
            )

        contact = self.get_contact(
            contact_id
        )

        if contact is None:
            return False

        contact["status"] = status

        self._save()

        return True

    def get_status(
        self,
        contact_id: str,
    ) -> Optional[str]:
        """
        Return the current outreach status.
        """

        contact = self.get_contact(
            contact_id
        )

        if contact is None:
            return None

        return contact.get("status")

    # ========================================================
    # FILTER
    # ========================================================

    def get_contacts_by_status(
        self,
        status: str,
    ) -> list[dict]:
        """
        Return contacts having a specific status.
        """

        if status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid contact status: {status}"
            )

        return [
            contact
            for contact in self._data[
                "contacts"
            ].values()
            if contact.get("status") == status
        ]

    # ========================================================
    # DUPLICATE CHECK
    # ========================================================

    def has_contact(
        self,
        job_id: str,
        email: str,
    ) -> bool:
        """
        Check whether a contact already exists for a job.
        """

        contact_id = self._contact_id(
            job_id,
            email,
        )

        return contact_id in self._data[
            "contacts"
        ]

    # ========================================================
    # COUNT
    # ========================================================

    def count(self) -> int:
        """
        Return total number of stored contacts.
        """

        return len(
            self._data["contacts"]
        )

    def count_for_job(
        self,
        job_id: str,
    ) -> int:
        """
        Return number of contacts for a job.
        """

        return len(
            self.get_contacts_for_job(
                job_id
            )
        )