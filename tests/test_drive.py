from cs2demo_analyse.drive import list_public_drive_folder_files


def test_list_public_drive_folder_files_reads_embedded_folder_entries(monkeypatch):
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            pass

    responses = [
        FakeResponse("""
            <div class="flip-entry" id="entry-1F-CJXPsvD0_YdKQlETfDwlz2SeJYmIH7">
              <div class="flip-entry-title">20260717_dust2_full_win_13_07.zip</div>
            </div>
            <div class="flip-entry" id="entry-1USBtCmLvpn6LBc4ufNHn3P35ujGB5wjM">
              <div class="flip-entry-title">20260718_dust2_full_win_13_06.zip</div>
            </div>
        """),
        FakeResponse(""),
    ]

    def fake_get(url, params=None, timeout=None):
        return responses.pop(0)

    monkeypatch.setattr("requests.get", fake_get)

    files = list_public_drive_folder_files("folder-id")

    assert [file["name"] for file in files] == [
        "20260717_dust2_full_win_13_07.zip",
        "20260718_dust2_full_win_13_06.zip",
    ]
    assert [file["id"] for file in files] == [
        "1F-CJXPsvD0_YdKQlETfDwlz2SeJYmIH7",
        "1USBtCmLvpn6LBc4ufNHn3P35ujGB5wjM",
    ]
