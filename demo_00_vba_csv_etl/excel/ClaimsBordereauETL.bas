Attribute VB_Name = "ClaimsBordereauETL"
Option Explicit

' =====================================================================
'  CleanBordereau
'
'  Reads the monthly claims bordereau CSV, cleans and enriches it, and
'  writes <input>_CLEAN.csv for the pricing / reserving upload.
'
'  Author unknown. Last touched years ago. Runs row by row, so it takes
'  a couple of minutes on a full monthly file. DO NOT edit before close.
' =====================================================================

Sub CleanBordereau()
    Dim csvPath As Variant
    csvPath = Application.GetOpenFilename("CSV Files (*.csv),*.csv", , _
                                          "Select the monthly claims CSV")
    If VarType(csvPath) = vbBoolean Then Exit Sub

    Dim t0 As Double: t0 = Timer
    Dim f As Integer: f = FreeFile
    Dim line As String, cells() As String
    Dim seen As New Collection
    Dim ref As String, isoLoss As String, isoRep As String
    Dim paid As Double, outst As Double, incurred As Double
    Dim outRow As Long: outRow = 2
    Dim n As Long

    Dim ws As Worksheet
    Set ws = ThisWorkbook.Worksheets("Clean")     ' a sheet named "Clean" must exist
    ws.Cells.Clear
    ws.Range("A1:J1").Value = Array("claim_ref", "policy_ref", "loss_date", _
        "report_date", "status", "peril", "paid_gbp", "outstanding_gbp", _
        "incurred_gbp", "large_loss_flag")

    Open csvPath For Input As #f
    Line Input #f, line                            ' skip header
    Do While Not EOF(f)
        Line Input #f, line
        cells = Split(line, ",")
        If UBound(cells) < 8 Then GoTo NextRow

        ' de-duplicate: the vendor extract double-fires
        ref = Trim(cells(0))
        On Error Resume Next
        seen.Add True, ref
        If Err.Number <> 0 Then Err.Clear: On Error GoTo 0: GoTo NextRow
        On Error GoTo 0

        ' loss date must parse, or the row is skipped
        isoLoss = ParseDateISO(Trim(cells(2)))
        If isoLoss = "" Then GoTo NextRow
        isoRep = ParseDateISO(Trim(cells(3)))

        paid = ParseAmount(Trim(cells(7)))
        outst = ParseAmount(Trim(cells(8)))
        incurred = Round(paid + outst, 2)

        ws.Cells(outRow, 1).Value = ref
        ws.Cells(outRow, 2).Value = Trim(cells(1))
        ws.Cells(outRow, 3).Value = isoLoss
        ws.Cells(outRow, 4).Value = isoRep
        ws.Cells(outRow, 5).Value = MapStatus(cells(4))
        ws.Cells(outRow, 6).Value = Trim(cells(5))
        ws.Cells(outRow, 7).Value = paid
        ws.Cells(outRow, 8).Value = outst
        ws.Cells(outRow, 9).Value = incurred
        ws.Cells(outRow, 10).Value = IIf(incurred > 100000#, "Y", "N")
        outRow = outRow + 1
        n = n + 1
NextRow:
    Loop
    Close #f

    ExportClean ws, CStr(csvPath), outRow - 1
    MsgBox n & " claims cleaned in " & Format(Timer - t0, "0.0") & " seconds.", _
           vbInformation, "Bordereau ETL"
End Sub

' ------------------------------------------------------------------ helpers
' Accepts dd/mm/yyyy, yyyy-mm-dd and dd-Mon-yy. Anything else -> "".
Private Function ParseDateISO(s As String) As String
    Dim d As Long, m As Long, y As Long, p() As String
    ParseDateISO = ""
    If s = "" Then Exit Function
    On Error GoTo Bad
    If InStr(s, "/") > 0 Then
        p = Split(s, "/")
        If UBound(p) <> 2 Then Exit Function
        d = CLng(p(0)): m = CLng(p(1)): y = CLng(p(2))
    ElseIf InStr(s, "-") > 0 Then
        p = Split(s, "-")
        If UBound(p) <> 2 Then Exit Function
        If Len(p(0)) = 4 Then
            y = CLng(p(0)): m = CLng(p(1)): d = CLng(p(2))
        Else
            d = CLng(p(0)): m = MonthNo(p(1)): y = 2000 + CLng(p(2))
            If m = 0 Then Exit Function
        End If
    Else
        Exit Function
    End If
    If m < 1 Or m > 12 Or d < 1 Or d > 31 Then Exit Function
    If Day(DateSerial(y, m, d)) <> d Then Exit Function
    ParseDateISO = Format(DateSerial(y, m, d), "yyyy-mm-dd")
    Exit Function
Bad:
    ParseDateISO = ""
End Function

Private Function MonthNo(mon As String) As Long
    Select Case UCase(Left(Trim(mon), 3))
        Case "JAN": MonthNo = 1
        Case "FEB": MonthNo = 2
        Case "MAR": MonthNo = 3
        Case "APR": MonthNo = 4
        Case "MAY": MonthNo = 5
        Case "JUN": MonthNo = 6
        Case "JUL": MonthNo = 7
        Case "AUG": MonthNo = 8
        Case "SEP": MonthNo = 9
        Case "OCT": MonthNo = 10
        Case "NOV": MonthNo = 11
        Case "DEC": MonthNo = 12
        Case Else: MonthNo = 0
    End Select
End Function

' "£1234.56", "1234.56", "-", "" and "(123.45)" (negative). Chr(163) = £.
Private Function ParseAmount(s As String) As Double
    Dim t As String, neg As Boolean
    t = Trim(s)
    If t = "" Or t = "-" Then ParseAmount = 0#: Exit Function
    If Left(t, 1) = "(" And Right(t, 1) = ")" Then
        neg = True
        t = Mid(t, 2, Len(t) - 2)
    End If
    t = Replace(t, Chr(163), "")
    t = Replace(t, ",", "")
    ParseAmount = Val(t)
    If neg Then ParseAmount = -ParseAmount
End Function

Private Function MapStatus(s As String) As String
    Select Case UCase(Trim(s))
        Case "O", "OPEN": MapStatus = "Open"
        Case "RO", "REOPENED": MapStatus = "Reopened"
        Case "C", "CLOSED": MapStatus = "Closed"
        Case "CWP": MapStatus = "ClosedWithoutPayment"
        Case Else: MapStatus = "UNKNOWN"
    End Select
End Function

Private Sub ExportClean(ws As Worksheet, inputPath As String, nRows As Long)
    Dim outPath As String
    outPath = Left(inputPath, InStrRev(inputPath, ".") - 1) & "_CLEAN.csv"
    Dim wbOut As Workbook
    Set wbOut = Workbooks.Add
    ws.Range("A1").Resize(nRows, 10).Copy wbOut.Sheets(1).Range("A1")
    Application.DisplayAlerts = False
    wbOut.SaveAs Filename:=outPath, FileFormat:=xlCSV, Local:=False
    wbOut.Close SaveChanges:=False
    Application.DisplayAlerts = True
End Sub
