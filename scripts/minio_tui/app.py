from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, DataTable, Input, Static, Button
from textual.widgets.data_table import RowDoesNotExist
from textual.screen import ModalScreen
from .minio_client import MinioClient

# --- Modal Screens ---

class CreateBucketScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Create New Bucket", classes="modal-title")
            yield Input(placeholder="Enter bucket name", id="bucket_name_input")
            with Horizontal(classes="modal-buttons"):
                yield Button("Create", variant="primary", id="create")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            value = self.query_one("#bucket_name_input").value
            self.dismiss(value)
        else:
            self.dismiss(None)

class UploadFileScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Upload File", classes="modal-title")
            yield Input(placeholder="Local file path", id="file_path_input")
            yield Input(placeholder="Object name (optional)", id="object_name_input")
            with Horizontal(classes="modal-buttons"):
                yield Button("Upload", variant="primary", id="upload")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "upload":
            file_path = self.query_one("#file_path_input").value
            object_name = self.query_one("#object_name_input").value
            self.dismiss((file_path, object_name))
        else:
            self.dismiss(None)

class DownloadFileScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Download File", classes="modal-title")
            yield Input(placeholder="Local save path", id="file_path_input")
            with Horizontal(classes="modal-buttons"):
                yield Button("Download", variant="primary", id="download")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download":
            value = self.query_one("#file_path_input").value
            self.dismiss(value)
        else:
            self.dismiss(None)

class ConfirmDeleteScreen(ModalScreen):
    def __init__(self, item_to_delete: str, **kwargs):
        super().__init__(**kwargs)
        self.item_to_delete = item_to_delete

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static(f"Permanently delete '{self.item_to_delete}'?", classes="modal-title")
            with Horizontal(classes="modal-buttons"):
                yield Button("Delete", variant="error", id="delete")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "delete")

class ShowURLScreen(ModalScreen):
    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-container"):
            yield Static("Presigned URL", classes="modal-title")
            yield Input(value=self.url, readonly=True)
            yield Button("Close", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


# --- Main App ---

class MinioTUI(App):
    CSS_PATH = "app.css"

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("c", "create_bucket", "Create Bucket"),
        ("x", "delete_item", "Delete"),
        ("u", "upload_file", "Upload"),
        ("l", "download_file", "Download"),
        ("p", "presign_url", "Get URL"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, minio_client: MinioClient, **kwargs):
        super().__init__(**kwargs)
        self.minio_client = minio_client
        self.current_bucket = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main_container"):
            with Vertical(id="buckets_panel"):
                yield DataTable(id="buckets_table", cursor_type="row")
                yield Static(id="bucket_status", classes="status-bar")
            with Vertical(id="objects_panel"):
                yield DataTable(id="objects_table", cursor_type="row")
                yield Static(id="object_status", classes="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.show_buckets()
        self.query_one("#buckets_table").focus()

    def show_buckets(self):
        buckets_table = self.query_one("#buckets_table")
        buckets_table.clear(columns=True)
        buckets_table.add_columns("Buckets")
        self.query_one("#bucket_status").update("")  # Clear status
        try:
            buckets = self.minio_client.list_buckets()
            rows = [[bucket] for bucket in buckets]
            if rows:
                buckets_table.add_rows(rows)
            self.query_one("#bucket_status").update(f"{len(buckets)} buckets found.")
        except Exception as e:
            self.set_status(f"Error: {e}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        if event.control.id == "buckets_table":
            try:
                self.current_bucket = event.data_table.get_row(event.cursor_row)[0]
                self.show_objects(self.current_bucket)
                self.query_one("#objects_table").focus()
            except RowDoesNotExist:
                self.current_bucket = None
                self.clear_objects_table()

    def show_objects(self, bucket_name: str):
        objects_table = self.query_one("#objects_table")
        objects_table.clear(columns=True)
        objects_table.add_columns(f"Objects in '{bucket_name}'")
        self.query_one("#object_status").update("")  # Clear status
        try:
            objects = self.minio_client.list_objects(bucket_name)
            rows = [[obj] for obj in objects]
            if rows:
                objects_table.add_rows(rows)
            self.query_one("#object_status").update(f"{len(objects)} objects found.")
        except Exception as e:
            self.set_status(f"Error: {e}")

    def clear_objects_table(self):
        objects_table = self.query_one("#objects_table")
        objects_table.clear(columns=True)
        self.query_one("#object_status").update("")

    def set_status(self, message: str):
        self.query_one("#object_status").update(message)

    def action_create_bucket(self):
        def on_submit(bucket_name: str):
            if bucket_name:
                try:
                    self.minio_client.create_bucket(bucket_name)
                    self.set_status(f"Bucket '{bucket_name}' created.")
                    self.show_buckets()
                except Exception as e:
                    self.set_status(f"Error: {e}")
        self.push_screen(CreateBucketScreen(), on_submit)

    def action_delete_item(self):
        focused_table = self.focused
        if not isinstance(focused_table, DataTable):
            return

        try:
            item_name = focused_table.get_row_at(focused_table.cursor_row)[0]
        except RowDoesNotExist:
            return

        def on_confirm(confirmed: bool):
            if confirmed:
                try:
                    if focused_table.id == "buckets_table":
                        self.minio_client.delete_bucket(item_name)
                        self.set_status(f"Bucket '{item_name}' deleted.")
                        self.show_buckets()
                        self.clear_objects_table()
                    elif focused_table.id == "objects_table":
                        self.minio_client.delete_object(self.current_bucket, item_name)
                        self.set_status(f"Object '{item_name}' deleted.")
                        self.show_objects(self.current_bucket)
                except Exception as e:
                    self.set_status(f"Error: {e}")
        self.push_screen(ConfirmDeleteScreen(item_name), on_confirm)

    def action_upload_file(self):
        if not self.current_bucket:
            self.set_status("Select a bucket before uploading.")
            return
        def on_submit(data):
            if data:
                file_path, object_name = data
                if not object_name:
                    object_name = file_path.split("/")[-1]
                try:
                    self.minio_client.upload_file(self.current_bucket, object_name, file_path)
                    self.set_status(f"File '{file_path}' uploaded.")
                    self.show_objects(self.current_bucket)
                except Exception as e:
                    self.set_status(f"Error: {e}")
        self.push_screen(UploadFileScreen(), on_submit)

    def action_download_file(self):
        if self.focused.id != "objects_table" or not self.current_bucket:
            self.set_status("Select an object to download.")
            return
        try:
            object_name = self.focused.get_row_at(self.focused.cursor_row)[0]
        except RowDoesNotExist:
            return
        def on_submit(file_path: str):
            if file_path:
                try:
                    self.minio_client.download_file(self.current_bucket, object_name, file_path)
                    self.set_status(f"File '{object_name}' downloaded to '{file_path}'.")
                except Exception as e:
                    self.set_status(f"Error: {e}")
        self.push_screen(DownloadFileScreen(), on_submit)

    def action_presign_url(self):
        if self.focused.id != "objects_table" or not self.current_bucket:
            self.set_status("Select an object to get a URL.")
            return
        try:
            object_name = self.focused.get_row_at(self.focused.cursor_row)[0]
            url = self.minio_client.generate_presigned_url(self.current_bucket, object_name)
            self.push_screen(ShowURLScreen(url))
        except RowDoesNotExist:
            return
        except Exception as e:
            self.set_status(f"Error: {e}")

if __name__ == "__main__":
    pass
