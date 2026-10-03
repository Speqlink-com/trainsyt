"""Excel export for trainer and administrator attendance registers."""

from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.core.security import utcnow
from app.schemas.training import AttendanceRowResponse

BRAND = "9B1B36"
DARK = "334155"
LIGHT = "F8FAFC"
GRID = "E2E8F0"
GREEN_FILL = "ECFDF5"
GREEN_TEXT = "047857"
AMBER_FILL = "FFFBEB"
AMBER_TEXT = "B45309"


def build_attendance_workbook(rows: list[AttendanceRowResponse]) -> bytes:
    """Build a compact, filterable `.xlsx` register entirely in memory."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Attendance"
    worksheet.sheet_view.showGridLines = False
    worksheet.freeze_panes = "A7"
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0
    worksheet.print_title_rows = "1:6"

    headers = [
        "Programme",
        "Trainer",
        "Training date",
        "Location",
        "Participant",
        "Role",
        "Participant code",
        "Email",
        "Phone",
        "Joined programme",
        "Attendance status",
        "Attendance marked",
    ]
    last_column = len(headers)

    worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_column)
    title = worksheet.cell(1, 1, "Jubilee training attendance register")
    title.font = Font(name="Arial", size=16, bold=True, color="171D25")
    title.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[1].height = 26

    worksheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_column)
    generated = worksheet.cell(2, 1, f"Generated {utcnow():%d %b %Y %H:%M} UTC")
    generated.font = Font(name="Arial", size=10, italic=True, color="64748B")

    present_count = sum(row.attendance_status == "present" for row in rows)
    summary = [
        ("Programme joins", len(rows)),
        ("Marked present", present_count),
        ("Awaiting attendance", len(rows) - present_count),
    ]
    for index, (label, value) in enumerate(summary):
        start_column = 1 + index * 4
        worksheet.merge_cells(
            start_row=4,
            start_column=start_column,
            end_row=4,
            end_column=start_column + 2,
        )
        cell = worksheet.cell(4, start_column, f"{label}: {value}")
        cell.font = Font(name="Arial", size=11, bold=True, color=BRAND)
        cell.fill = PatternFill("solid", fgColor="F7ECEF")
        cell.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[4].height = 23

    header_row = 6
    for column, header in enumerate(headers, start=1):
        cell = worksheet.cell(header_row, column, header)
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=DARK)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    worksheet.row_dimensions[header_row].height = 27

    thin_border = Border(bottom=Side(style="hair", color=GRID))
    for row_index, row in enumerate(rows, start=header_row + 1):
        values = [
            row.training_title,
            row.trainer_name,
            row.scheduled_at,
            row.location,
            row.participant_name,
            row.role.value.replace("_", " ").title(),
            row.participant_code,
            row.email,
            row.phone,
            row.joined_at,
            "Present" if row.attendance_status == "present" else "Joined - not present",
            row.checked_in_at,
        ]
        for column, value in enumerate(values, start=1):
            cell = worksheet.cell(row_index, column, value)
            cell.font = Font(name="Arial", size=10, color="1E293B")
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = thin_border
            if row_index % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=LIGHT)
        worksheet.cell(row_index, 3).number_format = "dd-mmm-yyyy hh:mm"
        worksheet.cell(row_index, 10).number_format = "dd-mmm-yyyy hh:mm:ss"
        worksheet.cell(row_index, 12).number_format = "dd-mmm-yyyy hh:mm:ss"
        status_cell = worksheet.cell(row_index, 11)
        if row.attendance_status == "present":
            status_cell.fill = PatternFill("solid", fgColor=GREEN_FILL)
            status_cell.font = Font(name="Arial", size=10, bold=True, color=GREEN_TEXT)
        else:
            status_cell.fill = PatternFill("solid", fgColor=AMBER_FILL)
            status_cell.font = Font(name="Arial", size=10, bold=True, color=AMBER_TEXT)

    widths = [32, 24, 20, 30, 24, 20, 20, 30, 18, 22, 22, 22]
    for column, width in enumerate(widths, start=1):
        worksheet.column_dimensions[get_column_letter(column)].width = width

    worksheet.auto_filter.ref = f"A{header_row}:L{max(header_row, header_row + len(rows))}"
    worksheet.print_area = f"A1:L{max(header_row, header_row + len(rows))}"

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    # Reopen before returning so a corrupt serialization can never be served.
    verified = load_workbook(output, read_only=True, data_only=False)
    if verified.sheetnames != ["Attendance"]:
        raise RuntimeError("Attendance workbook verification failed")
    verified.close()
    output.seek(0)
    return output.getvalue()
