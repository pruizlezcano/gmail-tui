import base64
import os.path
from typing import Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gmail_tui.client.message import Message
from gmail_tui.client.thread import Thread

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


class Gmail:
    def __init__(self):
        creds = self._authenticate()
        self._service = build("gmail", "v1", credentials=creds)

    def _authenticate(self):
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open("token.json", "w", encoding="UTF-8") as token:
                token.write(creds.to_json())
        return creds

    def get_threads(
        self,
        labels: Union[list[str], None] = None,
        page_token: str = "",
        query: str = None,
        max_results: int = 10,
        include_spam: bool = False,
    ) -> (list[Thread], str):
        try:
            threads = (
                self._service.users()
                .threads()
                .list(
                    userId="me",
                    labelIds=labels,
                    pageToken=page_token,
                    q=query,
                    maxResults=max_results,
                    includeSpamTrash=include_spam,
                )
                .execute()
            )
            if "threads" not in threads:
                return []

            return (
                [Thread(self._service, thread["id"]) for thread in threads["threads"]],
                threads["nextPageToken"] if "nextPageToken" in threads else "",
            )

        except HttpError as error:
            raise error

    def get_unread_threads(self) -> list[Thread]:
        return self.get_threads(labels=["UNREAD"])

    def send_message(self, to: str, subject: str, body: str) -> Message:
        try:
            message = (
                self._service.users()
                .messages()
                .send(
                    userId="me",
                    body={
                        "raw": base64.urlsafe_b64encode(
                            f"From: <me>\nTo: {to}\nSubject: {subject}\n\n{body}".encode()
                        ).decode(),
                    },
                )
                .execute()
            )
            return Message(self._service, message["id"], message)
        except HttpError as error:
            raise error

    def get_messages(
        self,
        labels: Union[list[str], None] = None,
        page_token: str = "",
        query: str = None,
        max_results: int = 10,
        include_spam: bool = False,
    ) -> (list[Message], str):
        try:
            messages = (
                self._service.users()
                .messages()
                .list(
                    userId="me",
                    labelIds=labels,
                    pageToken=page_token,
                    q=query,
                    maxResults=max_results,
                    includeSpamTrash=include_spam,
                )
                .execute()
            )
            if "messages" not in messages:
                return []
            return (
                [
                    Message(self._service, message["id"])
                    for message in messages["messages"]
                ],
                messages["nextPageToken"] if "nextPageToken" in messages else "",
            )
        except HttpError as error:
            raise error

    def get_unread_messages(self):
        return self.get_messages(labels=["UNREAD"])
