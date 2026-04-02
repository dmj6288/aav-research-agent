from __future__ import annotations

import base64
import logging
import os
import re
from dataclasses import dataclass, asdict
from email import message_from_bytes
from email.message import Message
from pathlib import Path
from typing import List, Optional
from bs4 import BeautifulSoup

import html
import quopri
from urllib.parse import urlparse, parse_qs, unquote

from bs4 import BeautifulSoup

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


LOGGER = logging.getLogger(__name__)

# Read-only scope is enough for ingestion
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          "https://www.googleapis.com/auth/gmail.send",]


@dataclass
class ScholarEmail:
    message_id: str
    thread_id: str
    subject: str
    sender: str
    internal_date: str
    snippet: str
    plain_text: str
    html_text: str


@dataclass
class ScholarPaperCandidate:
    title: str
    link: str
    source_email_subject: str
    source_email_id: str


class GmailIngestor:
    def __init__(
        self,
        credentials_path: str | Path,
        token_path: str | Path,
    ) -> None:
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.service = self._build_service()

    def _build_service(self):
        creds: Optional[Credentials] = None

        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                LOGGER.info("Refreshing Gmail OAuth token.")
                creds.refresh(Request())
            else:
                LOGGER.info("Launching Gmail OAuth flow.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path),
                    SCOPES,
                )
                creds = flow.run_local_server(port=0)

            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")

        return build("gmail", "v1", credentials=creds)

    def search_message_ids(
        self,
        query: str = 'from:(scholaralerts-noreply@google.com) OR from:(scholar.google.com) newer_than:7d',
        max_results: int = 10,
    ) -> List[str]:
        response = (
            self.service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=max_results,
            )
            .execute()
        )

        messages = response.get("messages", [])
        return [m["id"] for m in messages]

    def get_message(self, message_id: str) -> ScholarEmail:
        msg = (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="raw")
            .execute()
        )

        raw_bytes = base64.urlsafe_b64decode(msg["raw"].encode("ASCII"))
        mime_msg = message_from_bytes(raw_bytes)

        plain_text, html_text = self._extract_message_bodies(mime_msg)

        headers = self._headers_to_dict(mime_msg)

        return ScholarEmail(
            message_id=msg["id"],
            thread_id=msg["threadId"],
            subject=headers.get("Subject", ""),
            sender=headers.get("From", ""),
            internal_date=msg.get("internalDate", ""),
            snippet=msg.get("snippet", ""),
            plain_text=plain_text,
            html_text=html_text,
        )

    def fetch_scholar_emails(
        self,
        query: str = 'from:(scholaralerts-noreply@google.com) OR from:(scholar.google.com) newer_than:7d',
        max_results: int = 10,
    ) -> List[ScholarEmail]:
        message_ids = self.search_message_ids(query=query, max_results=max_results)
        emails: List[ScholarEmail] = []

        for message_id in message_ids:
            try:
                emails.append(self.get_message(message_id))
            except Exception as exc:
                LOGGER.exception("Failed to fetch message %s: %s", message_id, exc)

        return emails

    @staticmethod
    def _headers_to_dict(mime_msg: Message) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key, value in mime_msg.items():
            headers[key] = value
        return headers

    @staticmethod
    def _extract_message_bodies(mime_msg: Message) -> tuple[str, str]:
        plain_parts: List[str] = []
        html_parts: List[str] = []

        if mime_msg.is_multipart():
            for part in mime_msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition.lower():
                    continue

                payload = part.get_payload(decode=True)
                if payload is None:
                    continue

                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")

                if content_type == "text/plain":
                    plain_parts.append(text)
                elif content_type == "text/html":
                    html_parts.append(text)
        else:
            payload = mime_msg.get_payload(decode=True)
            if payload is not None:
                charset = mime_msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if mime_msg.get_content_type() == "text/html":
                    html_parts.append(text)
                else:
                    plain_parts.append(text)

        return "\n".join(plain_parts), "\n".join(html_parts)


def extract_google_scholar_candidates(email_obj: ScholarEmail) -> List[ScholarPaperCandidate]:
    raw_html = email_obj.html_text
    if not raw_html:
        return []

    cleaned_html = _normalize_scholar_html(raw_html)
    soup = BeautifulSoup(cleaned_html, "lxml")

    candidates: List[ScholarPaperCandidate] = []

    # Scholar result titles in alert emails are usually in h3.gs_rt
    for h3 in soup.select("h3.gs_rt"):
        a = h3.find("a", href=True)
        if not a:
            continue

        title = a.get_text(" ", strip=True)
        link = a["href"].strip()
        link = _extract_real_url(link)

        if not title or len(title) < 10:
            continue
        if not link.startswith("http"):
            continue

        candidates.append(
            ScholarPaperCandidate(
                title=title,
                link=link,
                source_email_subject=email_obj.subject,
                source_email_id=email_obj.message_id,
            )
        )

    # Fallback: if the h3 selector fails, scan all links conservatively
    if not candidates:
        for a in soup.find_all("a", href=True):
            title = a.get_text(" ", strip=True)
            link = _extract_real_url(a["href"].strip())

            if not title or len(title) < 25:
                continue
            if not link.startswith("http"):
                continue
            if "scholar.google.com" in link:
                continue
            if title.lower() in {"view all", "cancel alert", "save", "twitter", "facebook"}:
                continue

            candidates.append(
                ScholarPaperCandidate(
                    title=title,
                    link=link,
                    source_email_subject=email_obj.subject,
                    source_email_id=email_obj.message_id,
                )
            )

    # deduplicate
    unique = {}
    for c in candidates:
        unique[(c.title.strip(), c.link.strip())] = c

    return list(unique.values())

def _normalize_scholar_html(raw_html: str) -> str:
    """
    Clean Google Scholar alert HTML that may still contain
    quoted-printable artifacts and escaped HTML entities.
    """
    text = raw_html

    # quoted-printable cleanup if artifacts remain
    if "=3D" in text or "=\n" in text or "=\r\n" in text:
        try:
            text = quopri.decodestring(text).decode("utf-8", errors="replace")
        except Exception:
            text = text.replace("=3D", "=").replace("=\r\n", "").replace("=\n", "")

    # HTML entity unescape
    text = html.unescape(text)

    return text


def _extract_real_url(link: str) -> str:
    """
    Google Scholar alert links are often redirect URLs with the real target
    inside a 'url=' query parameter.
    """
    try:
        parsed = urlparse(link)
        qs = parse_qs(parsed.query)

        if "url" in qs and qs["url"]:
            return unquote(qs["url"][0])

        return link
    except Exception:
        return link

def _guess_title_from_text_block(text: str, url: str) -> str:
    """
    Very rough title guesser.
    This is a temporary bridge until you switch to BeautifulSoup parsing.
    """
    text = text.replace("\r", "\n")
    idx = text.find(url)
    if idx == -1:
        return ""

    window_start = max(0, idx - 300)
    window = text[window_start:idx].strip()

    lines = [line.strip() for line in window.splitlines() if line.strip()]
    if not lines:
        return ""

    # Usually the last meaningful line before a URL is the visible paper title.
    candidate = lines[-1]

    # Filter obvious junk
    if len(candidate) < 15:
        return ""
    if "google scholar" in candidate.lower():
        return ""
    if candidate.lower().startswith("http"):
        return ""

    return candidate


def demo_run() -> None:
    project_root = Path(__file__).resolve().parents[3]

    credentials_path = project_root / "data" / "raw" / "gmail_credentials.json"
    token_path = project_root / "data" / "raw" / "gmail_token.json"

    print(f"Project root: {project_root}")
    print(f"Credentials path: {credentials_path}")
    print(f"Credentials exists: {credentials_path.exists()}")
    print(f"Token path: {token_path}")
    print(f"Token exists: {token_path.exists()}")

    ingestor = GmailIngestor(
        credentials_path=credentials_path,
        token_path=token_path,
    )

    emails = ingestor.fetch_scholar_emails(max_results=5)

    print(f"Fetched {len(emails)} emails.\n")

    for email_obj in emails:
        print("=" * 80)
        print(f"Subject: {email_obj.subject}")
        print(f"From: {email_obj.sender}")
        print(f"Message ID: {email_obj.message_id}")

        candidates = extract_google_scholar_candidates(email_obj)
        print(f"Extracted {len(candidates)} candidate papers")

        for i, paper in enumerate(candidates[:5], start=1):
            print(f"  {i}. {paper.title}")
            print(f"     {paper.link}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo_run()