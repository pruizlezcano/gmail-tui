from typing import Union

from googleapiclient.errors import HttpError


class Label:
    def __init__(self, service, label_id):
        self._service = service
        self.id = label_id
        self.name: str
        self.message_list_visibility: str
        self.label_list_visibility: str
        self.type: str
        self.messages_total: int
        self.messages_unread: int
        self.threads_total: int
        self.threads_nread: int
        self.color: Union[dict, None]
        self.get_label_info()

    def get_label_info(self):
        try:
            label = (
                self._service.users().labels().get(userId="me", id=self.id).execute()
            )
            self.name = label["name"]
            self.message_list_visibility = (
                label["messageListVisibility"]
                if "messageListVisibility" in label
                else None
            )
            self.label_list_visibility = (
                label["labelListVisibility"] if "labelListVisibility" in label else None
            )
            self.type = label["type"]
            self.messages_total = label["messagesTotal"]
            self.messages_unread = label["messagesUnread"]
            self.threads_total = label["threadsTotal"]
            self.threads_unread = label["threadsUnread"]
            self.color = label["color"] if "color" in label else None
        except HttpError as error:
            raise error
