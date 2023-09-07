from googleapiclient.errors import HttpError

from gmail_tui.client.message import Message


class Thread:
    def __init__(self, service, thread_id):
        self._service = service
        self.id = thread_id
        self.messages: list[Message] = None
        self.last_message: Message = None
        self.get_thread_info()

    def get_thread_info(self):
        """Get the thread info from the API and store it in the object"""
        try:
            thread = (
                self._service.users().threads().get(userId="me", id=self.id).execute()
            )
            self.messages = [
                Message(self._service, message["id"], message)
                for message in thread["messages"]
            ]
            self.last_message = self.messages[-1]
        except HttpError as error:
            raise error

    def add_label(self, label: str) -> dict:
        try:
            thread = (
                self._service.users()
                .threads()
                .modify(
                    userId="me", id=self.id, body={"addLabelIds": [f"{label.upper()}"]}
                )
                .execute()
            )
            return thread

        except HttpError as error:
            raise error

    def remove_label(self, label: str) -> dict:
        try:
            thread = (
                self._service.users()
                .threads()
                .modify(
                    userId="me",
                    id=self.id,
                    body={"removeLabelIds": [f"{label.upper()}"]},
                )
                .execute()
            )
            return thread
        except HttpError as error:
            raise error

    def mark_as_read(self) -> dict:
        return self.remove_label("UNREAD")

    def mark_as_unread(self) -> dict:
        return self.add_label("UNREAD")

    def mark_as_important(self) -> dict:
        return self.add_label("IMPORTANT")

    def mark_as_not_important(self) -> dict:
        return self.remove_label("IMPORTANT")

    def move_to_trash(self) -> dict:
        try:
            thread = (
                self._service.users().threads().trash(userId="me", id=self.id).execute()
            )
            return thread
        except HttpError as error:
            raise error

    def move_to_inbox(self) -> dict:
        try:
            thread = (
                self._service.users()
                .threads()
                .untrash(userId="me", id=self.id)
                .execute()
            )
            return thread
        except HttpError as error:
            raise error

    def delete(self) -> dict:
        try:
            thread = (
                self._service.users()
                .threads()
                .delete(userId="me", id=self.id)
                .execute()
            )
            return thread
        except HttpError as error:
            raise error
