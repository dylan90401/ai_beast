#!/usr/bin/env python3
"""Resume parsing module for AI Beast.

Extracts structured data from resume documents (PDF, DOCX) using LLM-based extraction.
"""
import hashlib
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ResumeParser:
    """Parse resumes and extract structured data using LLMs."""

    def __init__(
        self,
        ollama_host: str = "http://127.0.0.1:11434",
        model: str = "llama3.2:latest",
        storage_dir: str | None = None,
    ):
        """Initialize resume parser.

        Args:
            ollama_host: Ollama API endpoint
            model: LLM model to use for extraction
            storage_dir: Directory to store parsed resumes
        """
        self.ollama_host = ollama_host
        self.model = model
        self.storage_dir = Path(storage_dir) if storage_dir else Path("data/resumes")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text content
        """
        try:
            import pypdf
        except ImportError:
            logger.error("pypdf not installed. Install: pip install pypdf")
            raise ImportError("pypdf required for PDF parsing")

        text_parts = []
        try:
            with open(file_path, "rb") as f:
                pdf_reader = pypdf.PdfReader(f)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
        except Exception as e:
            logger.error(f"Failed to extract PDF text: {e}")
            raise

        return "\n\n".join(text_parts)

    def extract_text_from_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file.

        Args:
            file_path: Path to DOCX file

        Returns:
            Extracted text content
        """
        try:
            from docx import Document
        except ImportError:
            logger.error("python-docx not installed. Install: pip install python-docx")
            raise ImportError("python-docx required for DOCX parsing")

        text_parts = []
        try:
            doc = Document(file_path)
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
        except Exception as e:
            logger.error(f"Failed to extract DOCX text: {e}")
            raise

        return "\n".join(text_parts)

    def extract_text(self, file_path: Path) -> str:
        """Extract text from resume document.

        Args:
            file_path: Path to resume file

        Returns:
            Extracted text content

        Raises:
            ValueError: If file format is not supported
        """
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            return self.extract_text_from_pdf(file_path)
        elif suffix in (".docx", ".doc"):
            return self.extract_text_from_docx(file_path)
        elif suffix == ".txt":
            return file_path.read_text(encoding="utf-8", errors="ignore")
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def call_ollama(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        """Call Ollama API for LLM inference.

        Args:
            prompt: User prompt
            system: System prompt (optional)

        Returns:
            Response from Ollama API
        """
        import requests

        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            raise

    def extract_structured_data(self, text: str) -> dict[str, Any]:
        """Extract structured data from resume text using LLM.

        Args:
            text: Resume text content

        Returns:
            Structured resume data as dictionary
        """
        system_prompt = """You are an expert resume parser. Extract structured information from resumes and return ONLY valid JSON. Do not include any explanatory text, markdown formatting, or code blocks - just the raw JSON object.

Extract the following information:
- personal_info: name, email, phone, location (city, state, country), linkedin, github, website
- summary: professional summary or objective
- experience: array of jobs with company, position, location, start_date, end_date, current, description, responsibilities, achievements
- education: array of degrees with institution, degree, field_of_study, location, start_date, end_date, gpa, honors
- skills: technical skills, languages with proficiency, soft_skills, certifications
- projects: array with name, description, role, technologies, url, dates
- awards: array with title, issuer, date, description
- publications: array with title, authors, publisher, date, url

Return a valid JSON object with these fields. Use null for missing data."""

        user_prompt = f"""Parse this resume and extract structured data as JSON:

{text}

Remember: Return ONLY the JSON object, no other text."""

        try:
            response = self.call_ollama(user_prompt, system_prompt)
            response_text = response.get("response", "")

            # Clean up the response - remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Parse JSON
            structured_data = json.loads(response_text)
            return structured_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response was: {response.get('response', '')[:500]}")
            # Return minimal structure
            return {
                "personal_info": {},
                "summary": "",
                "experience": [],
                "education": [],
                "skills": {},
                "projects": [],
                "awards": [],
                "publications": [],
            }
        except Exception as e:
            logger.error(f"Structured data extraction failed: {e}")
            raise

    def parse_resume(
        self, file_path: Path | str, save: bool = True
    ) -> dict[str, Any]:
        """Parse a resume file and extract structured data.

        Args:
            file_path: Path to resume file
            save: Whether to save parsed data to storage

        Returns:
            Complete resume data including raw text and structured fields
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Resume file not found: {file_path}")

        logger.info(f"Parsing resume: {file_path.name}")

        # Extract text
        raw_text = self.extract_text(file_path)

        # Generate unique ID
        resume_id = hashlib.md5(
            f"{file_path.name}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        # Extract structured data
        structured_data = self.extract_structured_data(raw_text)

        # Build complete resume object
        resume_data = {
            "id": resume_id,
            "uploaded_at": datetime.utcnow().isoformat() + "Z",
            "filename": file_path.name,
            "raw_text": raw_text,
            **structured_data,
            "metadata": {
                "parsed_at": datetime.utcnow().isoformat() + "Z",
                "parser_version": "1.0.0",
                "model_used": self.model,
                "confidence_score": 0.85,  # Could be calculated based on completeness
                "verified": False,
                "verified_at": None,
            },
        }

        # Save if requested
        if save:
            self.save_resume(resume_data)

        logger.info(f"Resume parsed successfully: {resume_id}")
        return resume_data

    def save_resume(self, resume_data: dict[str, Any]) -> Path:
        """Save parsed resume data to storage.

        Args:
            resume_data: Complete resume data dictionary

        Returns:
            Path to saved file
        """
        resume_id = resume_data["id"]
        file_path = self.storage_dir / f"{resume_id}.json"

        with open(file_path, "w") as f:
            json.dump(resume_data, f, indent=2)

        logger.info(f"Resume saved: {file_path}")
        return file_path

    def load_resume(self, resume_id: str) -> dict[str, Any] | None:
        """Load parsed resume data from storage.

        Args:
            resume_id: Resume ID

        Returns:
            Resume data or None if not found
        """
        file_path = self.storage_dir / f"{resume_id}.json"

        if not file_path.exists():
            return None

        with open(file_path) as f:
            return json.load(f)

    def list_resumes(self) -> list[dict[str, Any]]:
        """List all parsed resumes.

        Returns:
            List of resume summaries (id, filename, uploaded_at)
        """
        resumes = []

        for file_path in self.storage_dir.glob("*.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)
                    resumes.append(
                        {
                            "id": data["id"],
                            "filename": data["filename"],
                            "uploaded_at": data["uploaded_at"],
                            "name": data.get("personal_info", {}).get("full_name", ""),
                            "email": data.get("personal_info", {}).get("email", ""),
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to load resume {file_path}: {e}")

        # Sort by upload date, newest first
        resumes.sort(key=lambda x: x["uploaded_at"], reverse=True)
        return resumes

    def delete_resume(self, resume_id: str) -> bool:
        """Delete a parsed resume.

        Args:
            resume_id: Resume ID

        Returns:
            True if deleted, False if not found
        """
        file_path = self.storage_dir / f"{resume_id}.json"

        if not file_path.exists():
            return False

        file_path.unlink()
        logger.info(f"Resume deleted: {resume_id}")
        return True

    def update_resume(
        self, resume_id: str, updates: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update parsed resume data (for manual corrections).

        Args:
            resume_id: Resume ID
            updates: Dictionary of fields to update

        Returns:
            Updated resume data or None if not found
        """
        resume_data = self.load_resume(resume_id)

        if not resume_data:
            return None

        # Deep merge updates
        def deep_update(base: dict, updates: dict) -> dict:
            for key, value in updates.items():
                if (
                    isinstance(value, dict)
                    and key in base
                    and isinstance(base[key], dict)
                ):
                    deep_update(base[key], value)
                else:
                    base[key] = value
            return base

        resume_data = deep_update(resume_data, updates)

        # Mark as verified if this is a manual update
        if "metadata" in resume_data:
            resume_data["metadata"]["verified"] = True
            resume_data["metadata"]["verified_at"] = (
                datetime.utcnow().isoformat() + "Z"
            )

        self.save_resume(resume_data)
        return resume_data


if __name__ == "__main__":
    # Example usage
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python parser.py <resume_file>")
        sys.exit(1)

    parser = ResumeParser()
    result = parser.parse_resume(sys.argv[1])
    print(json.dumps(result, indent=2))
