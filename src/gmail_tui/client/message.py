import base64
import html
from datetime import datetime

from bs4 import BeautifulSoup
from googleapiclient.errors import HttpError

from gmail_tui.client.attachment import Attachment
from gmail_tui.client.contact import Contact
from gmail_tui.client.label import Label


class Message:
    def __init__(self, service, message_id, raw_data=None):
        self._service = service
        self.id = message_id
        self.sender: Contact
        self.receiver: list[Contact] = []
        self.subject = None
        self.body: str
        self.attachments = None
        self.date = None
        self.labels: list[Label]
        self.snippet: str
        self.get_message_info(message=raw_data)

    def _evaluate_message_payload(
        self, payload: dict, attachments: str = "reference"
    ) -> list[dict]:
        """
        Recursively evaluates a message payload.

        Args:
            payload: The message payload object (response from Gmail API)..
            attachments: Accepted values are 'ignore' which completely ignores
                all attachments, 'reference' which includes attachment
                information but does not download the data, and 'download' which
                downloads the attachment data to store locally. Default
                'reference'.

        Returns:
            A list of message parts.

        Raises:
            googleapiclient.errors.HttpError: There was an error executing the
                HTTP request.

        """

        if "attachmentId" in payload["body"]:  # if it's an attachment
            if attachments == "ignore":
                return []

            att_id = payload["body"]["attachmentId"]
            filename = payload["filename"]
            if not filename:
                filename = "unknown"

            obj = {
                "part_type": "attachment",
                "filetype": payload["mimeType"],
                "filename": filename,
                "attachment_id": att_id,
                "data": None,
            }

            if attachments == "reference":
                return [obj]

            else:  # attachments == 'download'
                if "data" in payload["body"]:
                    data = payload["body"]["data"]
                else:
                    res = (
                        self._service.users()
                        .messages()
                        .attachments()
                        .get(userId="me", messageId=self.id, id=att_id)
                        .execute()
                    )
                    data = res["data"]

                file_data = base64.urlsafe_b64decode(data)
                obj["data"] = file_data
                return [obj]

        elif payload["mimeType"] == "text/html":
            data = payload["body"]["data"]
            data = base64.urlsafe_b64decode(data)
            body = BeautifulSoup(data, "lxml", from_encoding="utf-8").body
            return [{"part_type": "html", "body": str(body)}]

        elif payload["mimeType"] == "text/plain":
            data = payload["body"]["data"]
            data = base64.urlsafe_b64decode(data)
            body = data.decode("UTF-8")
            return [{"part_type": "plain", "body": body}]

        elif payload["mimeType"].startswith("multipart"):
            ret = []
            if "parts" in payload:
                for part in payload["parts"]:
                    ret.extend(self._evaluate_message_payload(part, attachments))
            return ret

        return []

    def get_message_info(self, message=None):
        try:
            if message is None:
                message = (
                    self._service.users()
                    .messages()
                    .get(userId="me", id=self.id)
                    .execute()
                )
            payload = message["payload"]
            headers = payload["headers"]
            self.date = datetime.fromtimestamp(float(message["internalDate"]) / 1000)
            self.snippet = html.unescape(message["snippet"]).replace("\u200c ", "")
            self.labels = [
                Label(self._service, label_id) for label_id in message["labelIds"]
            ]
            self.body = None
            self.html = None
            self.attachments = []

            for hdr in headers:
                if hdr["name"].lower() == "from":
                    sender = hdr["value"]
                    sender_name = None
                    sender_mail = sender.replace("<", "").replace(">", "")
                    if sender.find("<") > 0:
                        sender_name = sender[: sender.find("<") - 1]
                        sender_mail = sender[sender.find("<") + 1 : sender.find(">")]
                    self.sender = Contact(sender_mail, sender_name)
                elif hdr["name"].lower() == "to":
                    receivers = hdr["value"].split(", ")
                    for receiver in receivers:
                        receiver_name = None
                        receiver_mail = receiver.replace("<", "").replace(">", "")
                        if receiver.find("<") > 0:
                            receiver_name = receiver[: receiver.find("<") - 1]
                            receiver_mail = receiver[
                                receiver.find("<") + 1 : receiver.find(">")
                            ]
                        self.receiver.append(Contact(receiver_mail, receiver_name))
                elif hdr["name"].lower() == "subject":
                    self.subject = hdr["value"]
                elif hdr["name"].lower() == "cc":
                    self.cc = hdr["value"].split(", ")
                elif hdr["name"].lower() == "bcc":
                    self.bcc = hdr["value"].split(", ")

            parts = self._evaluate_message_payload(payload)
            for part in parts:
                if part["part_type"] == "plain":
                    if self.body is None:
                        self.body = part["body"]
                    else:
                        self.body += "\n" + part["body"]
                elif part["part_type"] == "html":
                    if self.html is None:
                        self.html = part["body"]
                    else:
                        self.html += "<br/>" + part["body"]
                elif part["part_type"] == "attachment":
                    attm = Attachment(self._service, part)
                    self.attachments.append(attm)

        except HttpError as error:
            raise error

    def add_label(self, label: str):
        try:
            self._service.users().messages().modify(
                userId="me", id=self.id, body={"addLabelIds": [f"{label.upper()}"]}
            ).execute()

            if label.upper() not in self.labels:
                self.labels.append(label.upper())

        except HttpError as error:
            raise error

    def remove_label(self, label: str):
        try:
            self._service.users().messages().modify(
                userId="me",
                id=self.id,
                body={"removeLabelIds": [f"{label.upper()}"]},
            ).execute()

            if label.upper() in self.labels:
                self.labels.remove(label.upper())

        except HttpError as error:
            raise error

    def mark_as_read(self):
        return self.remove_label("UNREAD")

    def mark_as_unread(self):
        return self.add_label("UNREAD")

    def mark_as_important(self):
        return self.add_label("IMPORTANT")

    def mark_as_not_important(self):
        return self.remove_label("IMPORTANT")

    def move_to_trash(self):
        try:
            self._service.users().messages().trash(userId="me", id=self.id).execute()

            if "TRASH" not in self.labels:
                self.labels.append("TRASH")
        except HttpError as error:
            raise error

    def move_to_invox(self):
        try:
            self._service.users().messages().untrash(userId="me", id=self.id).execute()

            if "TRASH" in self.labels:
                self.labels.remove("TRASH")

        except HttpError as error:
            raise error
