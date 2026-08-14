from pathlib import Path
import json

from app.resume.loader import load_resume
from app.parser.resume_parser import parse_resume


class ResumeManager:
    """
    Manages all resumes in the resume library.

    Features:
    - Discovers PDF resumes
    - Extracts PDF text
    - Parses resumes
    - Caches parsed resumes
    - Automatically invalidates cache when PDF changes
    - Avoids OCR when cached data is available
    """

    def __init__(
        self,
        resume_directory="resumes",
        cache_directory="data/cache/resumes",
    ):
        self.resume_directory = Path(resume_directory)
        self.cache_directory = Path(cache_directory)

        self.cache_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    # =========================================================
    # DISCOVER RESUMES
    # =========================================================

    def discover_resumes(self):
        """
        Find every PDF resume in the resume directory.
        """

        if not self.resume_directory.exists():
            raise FileNotFoundError(
                f"Resume directory not found: "
                f"{self.resume_directory.resolve()}"
            )

        return sorted(
            self.resume_directory.glob("*.pdf")
        )

    # =========================================================
    # CACHE PATH
    # =========================================================

    def _cache_path(self, resume_path):
        """
        Return cache file associated with a resume.
        """

        return (
            self.cache_directory
            / f"{resume_path.stem}.json"
        )

    # =========================================================
    # FILE SIGNATURE
    # =========================================================

    def _file_signature(self, resume_path):
        """
        Create a fast signature for a PDF.

        Uses:
        - file size
        - modification time

        This is much faster than hashing the entire PDF
        every time the cache is checked.
        """

        stat = resume_path.stat()

        return {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }

    # =========================================================
    # LOAD CACHE
    # =========================================================

    def _load_cached_resume(self, resume_path):
        """
        Load parsed resume from cache if it is still valid.
        """

        cache_path = self._cache_path(
            resume_path
        )

        if not cache_path.exists():
            return None

        try:
            with open(
                cache_path,
                "r",
                encoding="utf-8",
            ) as file:

                cached = json.load(file)

            current_signature = (
                self._file_signature(
                    resume_path
                )
            )

            cached_signature = cached.get(
                "file_signature"
            )

            if (
                cached_signature
                != current_signature
            ):
                print(
                    f"Cache stale: "
                    f"{resume_path.name}"
                )

                return None

            resume = cached.get("resume")

            if not isinstance(resume, dict):
                return None

            print(
                f"Cache hit: {resume_path.name}"
            )

            return resume

        except Exception as error:

            print(
                f"Warning: Could not read cache "
                f"for {resume_path.name}: {error}"
            )

            return None

    # =========================================================
    # SAVE CACHE
    # =========================================================

    def _save_cached_resume(
        self,
        resume_path,
        resume,
    ):
        """
        Save parsed resume to cache.
        """

        cache_path = self._cache_path(
            resume_path
        )

        cache_data = {
            "file_signature": (
                self._file_signature(
                    resume_path
                )
            ),
            "resume": resume,
        }

        # Write atomically to reduce risk of
        # leaving a corrupted cache file.
        temporary_path = cache_path.with_suffix(
            ".tmp"
        )

        with open(
            temporary_path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                cache_data,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary_path.replace(
            cache_path
        )

    # =========================================================
    # PROCESS ONE RESUME
    # =========================================================

    def _process_resume(self, resume_path):
        """
        Extract and parse one PDF.

        This is the expensive operation.
        """

        print(
            f"Processing resume: "
            f"{resume_path.name}"
        )

        text = load_resume(
            str(resume_path)
        )

        if not text.strip():

            print(
                f"Warning: No text extracted "
                f"from {resume_path.name}"
            )

            return None

        parsed_resume = parse_resume(
            text
        )

        parsed_resume["_file"] = str(
            resume_path
        )

        parsed_resume["_filename"] = (
            resume_path.name
        )

        parsed_resume["_raw_text"] = text

        return parsed_resume

    # =========================================================
    # LOAD ALL RESUMES
    # =========================================================

    def load_all_resumes(self):
        """
        Load every resume.

        Cached resumes are loaded immediately.
        PDFs are processed only when:
        - no cache exists
        - cache is stale
        - cache is corrupted
        """

        resumes = []

        for resume_path in self.discover_resumes():

            try:

                cached_resume = (
                    self._load_cached_resume(
                        resume_path
                    )
                )

                if cached_resume is not None:

                    resumes.append(
                        cached_resume
                    )

                    continue

                parsed_resume = (
                    self._process_resume(
                        resume_path
                    )
                )

                if parsed_resume is None:
                    continue

                self._save_cached_resume(
                    resume_path,
                    parsed_resume,
                )

                resumes.append(
                    parsed_resume
                )

            except Exception as error:

                print(
                    f"Warning: Could not process "
                    f"{resume_path.name}: {error}"
                )

        return resumes

    # =========================================================
    # COUNT
    # =========================================================

    def get_resume_count(self):
        """
        Return number of PDF resumes.
        """

        return len(
            self.discover_resumes()
        )

    # =========================================================
    # DESCRIBE
    # =========================================================

    def describe_resumes(self):
        """
        Print a summary of the resume library.
        """

        resumes = self.load_all_resumes()

        print(
            "\n"
            + "=" * 70
        )

        print("RESUME LIBRARY")

        print(
            "=" * 70
        )

        print(
            f"Directory: "
            f"{self.resume_directory.resolve()}"
        )

        print(
            f"Resume count: {len(resumes)}"
        )

        for resume in resumes:

            filename = resume.get(
                "_filename",
                "Unknown",
            )

            raw_text = resume.get(
                "_raw_text",
                "",
            )

            print(
                f"\n- {filename}"
            )

            print(
                f"  Extracted characters: "
                f"{len(raw_text)}"
            )

            if resume.get("name"):

                print(
                    f"  Name: "
                    f"{resume['name']}"
                )

            if resume.get("degree"):

                print(
                    f"  Degree: "
                    f"{resume['degree']}"
                )

        print(
            "=" * 70
        )