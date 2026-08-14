from dataclasses import dataclass, field
from typing import List


@dataclass
class Job:
    """
    Represents a job collected by JobAgent.
    """

    title: str
    company: str
    location: str = ""

    description: str = ""
    url: str = ""

    source: str = ""

    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)

    experience_requirements: str = ""

    # Optional metadata
    employment_type: str = ""
    posted_date: str = ""

    def to_dict(self) -> dict:
        """
        Convert Job object into a dictionary.
        """

        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "experience_requirements": self.experience_requirements,
            "employment_type": self.employment_type,
            "posted_date": self.posted_date,
        }