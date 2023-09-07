from datetime import datetime

from rich.text import Text
from textual import events
from textual.app import App, Binding, ComposeResult
from textual.containers import VerticalScroll
from textual.coordinate import Coordinate
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Label, Markdown, Static

from gmail_tui.client import Contact, Gmail, Thread

gmail = Gmail()


def parse_date(date: datetime, short_format: bool = True) -> str:
    result = ""
    # if is today return time else return day
    if date.date() == datetime.today().date():
        result = date.strftime("%H:%M")
    else:
        # if is this year return day and month else return day month and year
        if date.year == datetime.today().year:
            result = date.strftime("%d %b")
        else:
            result = date.strftime("%d %b %Y")
    if short_format:
        return result

    # get relative time
    now = datetime.now()
    seconds = now.timestamp() - date.timestamp()
    intervals = (
        ("weeks", 604800),  # 60 * 60 * 24 * 7
        ("days", 86400),  # 60 * 60 * 24
        ("hours", 3600),  # 60 * 60
        ("minutes", 60),
        ("seconds", 1),
    )

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip("s")
            result += f" ({int(value)} {name} ago)"
            break
    return result


def parse_contact(contact: Contact) -> str:
    if contact.name is None:
        return contact.email
    else:
        return contact.name + " <" + contact.email + ">"


class ThreadScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Go Back")]

    def __init__(self, thread: Thread):
        super().__init__(thread)
        self.thread = thread
        self.mail = thread.last_message

    def compose(self) -> ComposeResult:
        yield VerticalScroll(
            Static(
                Text(self.mail.subject, style="black on white justify-center"),
                classes="mail-screen-attr",
            ),
            Static(
                Text("From: " + parse_contact(self.mail.sender)),
                classes="mail-screen-attr",
            ),
            Static(
                Text(
                    "To: "
                    + ", ".join(
                        [parse_contact(receiver) for receiver in self.mail.receiver]
                    )
                ),
                classes="mail-screen-attr",
            ),
            Label(
                "Date: " + parse_date(self.mail.date, short_format=False),
                classes="mail-screen-attr",
            ),
            Static(
                "Labels: "
                + " ".join(
                    [
                        str(
                            Text(
                                label.name,
                                style="white on blue",
                            )
                        )
                        for label in [
                            label
                            for label in self.mail.labels
                            if label is not None
                            and label.message_list_visibility == "show"
                        ]
                    ]
                ),
                classes="mail-screen-attr",
            ),
            Label("-------------------------------", classes="mail-screen-attr"),
            Markdown(self.mail.body),
            classes="mail-screen",
        )
        yield Footer()

    def _on_mount(self) -> None:
        self.page = self.query_one(VerticalScroll)

    def action_cursor_down(self):
        self.page.action_scroll_down()


class LoadingScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Label("Loading...")


class Main(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "toggle_dark", "Toggle dark mode"),
    ]

    CSS_PATH = "style.css"

    def compose(self) -> ComposeResult:
        yield DataTable(classes="table")
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(LoadingScreen())
        self.max_results = 25
        self.next_page_token = ""
        self.threads, self.next_page_token = gmail.get_threads(
            max_results=self.max_results, page_token=self.next_page_token
        )
        self.pop_screen()
        self.table = self.query_one(DataTable)
        self.table.cursor_type = "row"
        self.table.add_column("", key="is_unread", width=1)
        self.table.add_column("From", key="sender", width=20)
        self.table.add_column("Subject", key="subject", width=20)
        self.table.add_column("Date", key="date", width=None)
        self.table.columns["subject"].auto_width = False
        self.table.action_select_cursor = self.action_select_cursor
        self.table.action_cursor_down = self.action_cursor_down
        self.add_threads(self.threads)

    def add_threads(self, threads: list[Thread]) -> None:
        for thread in threads:
            self.table.add_row(
                Text("✉")
                if "UNREAD" in [label.name for label in thread.last_message.labels]
                else "",
                Text(
                    thread.last_message.sender.name
                    if thread.last_message.sender.name is not None
                    else thread.last_message.sender.email,
                    no_wrap=True,
                    overflow="ellipsis",
                ),
                Text(thread.last_message.subject, no_wrap=True, overflow="ellipsis")
                + (
                    Text(
                        " - " + thread.last_message.snippet
                        if thread.last_message.snippet is not None
                        else "",
                        style="magenta",
                        no_wrap=True,
                        overflow="ellipsis",
                    )
                ),
                parse_date(thread.last_message.date),
                key=thread.id,
            )
        self.table.add_row("+", "Load more...", key="load_more")

    def on_resize(self, event: events.Resize) -> None:
        self.table.columns["subject"].width = event.size.width - 37
        self.table.refresh_column(2)

    def action_cursor_down(self):
        row = self.table.cursor_row
        if row == 100:
            new_threads, self.next_page_token = gmail.get_threads(
                max_results=self.max_results, page_token=self.next_page_token
            )
            self.add_threads(new_threads)
            self.threads += new_threads

        self.table.move_cursor(row=row + 1)

    def action_select_cursor(self):
        row = self.table.cursor_row
        if self.table.get_row_at(row)[0] == "+":
            new_threads, self.next_page_token = gmail.get_threads(
                max_results=self.max_results, page_token=self.next_page_token
            )
            self.table.remove_row("load_more")
            self.add_threads(new_threads)
            self.threads += new_threads
        else:
            thread = self.threads[row]
            thread.last_message.mark_as_read()
            self.table.update_cell_at(Coordinate(row=row, column=0), value="")
            self.push_screen(ThreadScreen(thread))
