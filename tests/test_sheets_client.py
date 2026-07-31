from unittest.mock import patch, MagicMock
from bambu_inventory.sheets_client import SheetsClient, HEADER


def make_client_with_mock_service(spreadsheet_id):
    with patch("bambu_inventory.sheets_client.build") as mock_build, \
         patch("bambu_inventory.sheets_client.service_account.Credentials.from_service_account_file"):
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        client = SheetsClient("creds.json", spreadsheet_id)
        return client, mock_service


def test_ensure_spreadsheet_creates_new_when_id_is_none():
    client, mock_service = make_client_with_mock_service(None)
    mock_service.spreadsheets().create().execute.return_value = {"spreadsheetId": "new-id-123"}

    result = client.ensure_spreadsheet()

    assert result == "new-id-123"
    mock_service.spreadsheets().create.assert_called()
    mock_service.spreadsheets().values().update.assert_called()


def test_ensure_spreadsheet_returns_existing_id_without_creating():
    client, mock_service = make_client_with_mock_service("existing-id")

    result = client.ensure_spreadsheet()

    assert result == "existing-id"
    mock_service.spreadsheets().create.assert_not_called()


def test_append_rows_sends_values_in_header_order():
    client, mock_service = make_client_with_mock_service("existing-id")
    row = {
        "date": "2026-07-30T09:00:00Z",
        "print_name": "Two Color Vase",
        "printer": "X1C-A",
        "status": "failed",
        "duration_min": 30,
        "ams_slot": "0-1",
        "filament_type": "PLA",
        "colour_hex": "FF0000FF",
        "weight_g": 12.5,
        "task_id": "1002",
    }

    client.append_rows([row])

    append_call = mock_service.spreadsheets().values().append
    append_call.assert_called_once()
    sent_values = append_call.call_args.kwargs["body"]["values"]
    assert sent_values == [[
        "2026-07-30T09:00:00Z", "Two Color Vase", "X1C-A", "failed", 30,
        "0-1", "PLA", "FF0000FF", 12.5, "1002",
    ]]


def test_header_constant_matches_expected_columns():
    assert HEADER == [
        "Date", "Print Name", "Printer", "Status", "Duration (min)",
        "AMS Slot", "Filament Type", "Colour (hex)", "Weight (g)", "Task ID",
    ]
