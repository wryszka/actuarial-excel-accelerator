Attribute VB_Name = "ClaimsBordereauETL"
Option Explicit

' =====================================================================
'  ClaimsBordereauETL
'
'  Imports the monthly TPA claims bordereau CSV, standardises it and
'  exports a clean CSV for the pricing-system upload.
'
'  Author unknown. Last materially changed a long time ago.
'  DO NOT TOUCH BEFORE MONTH-END.
' =====================================================================

Sub RunMonthlyETL()
    Dim csvPath As Variant
    csvPath = Application.GetOpenFilename("CSV Files (*.csv),*.csv", , _
                                          "Select the monthly bordereau CSV")
    If VarType(csvPath) = vbBoolean Then Exit Sub

    Dim wsRaw As Worksheet, wsStd As Worksheet
    Set wsRaw = PrepareSheet("Raw")
    Set wsStd = PrepareSheet("Standardised")

    ' ---- read the whole file ----
    Dim f As Integer: f = FreeFile
    Dim lines() As String, nLines As Long
    ReDim lines(1 To 60000)
    Open csvPath For Input As #f
    Do While Not EOF(f)
        nLines = nLines + 1
        If nLines > UBound(lines) Then ReDim Preserve lines(1 To UBound(lines) + 20000)
        Line Input #f, lines(nLines)
    Loop
    Close #f
    If nLines < 2 Then MsgBox "Empty file.": Exit Sub

    ' ---- dump raw as-is (audit tab) ----
    Dim rawArr() As Variant, i As Long
    ReDim rawArr(1 To nLines, 1 To 1)
    For i = 1 To nLines: rawArr(i, 1) = lines(i): Next i
    wsRaw.Range("A1").Resize(nLines, 1).Value = rawArr

    ' ---- standardise ----
    Dim outArr() As Variant
    ReDim outArr(1 To nLines, 1 To 10)
    Dim outN As Long
    Dim seen As New Collection
    Dim parts() As String
    Dim isoLoss As String, isoRep As String
    Dim paid As Double, outst As Double

    For i = 2 To nLines                       ' skip header
        parts = Split(lines(i), ",")
        If UBound(parts) < 9 Then GoTo NextRow

        ' the vendor extract double-fires: keep first occurrence per claim
        On Error Resume Next
        seen.Add True, Trim(parts(0))
        If Err.Number <> 0 Then Err.Clear: On Error GoTo 0: GoTo NextRow
        On Error GoTo 0

        isoLoss = ParseDateISO(Trim(parts(2)))
        If isoLoss = "" Then GoTo NextRow     ' loss date unusable -> skip row
        isoRep = ParseDateISO(Trim(parts(3))) ' blank if unusable

        paid = ParseAmount(Trim(parts(8)))
        outst = ParseAmount(Trim(parts(9)))

        outN = outN + 1
        outArr(outN, 1) = Trim(parts(0))              ' claim_ref
        outArr(outN, 2) = Trim(parts(1))              ' policy_no
        outArr(outN, 3) = isoLoss                     ' loss_date
        outArr(outN, 4) = isoRep                      ' report_date
        outArr(outN, 5) = MapStatus(parts(4))         ' status
        outArr(outN, 6) = Trim(parts(5))              ' peril_code
        outArr(outN, 7) = Trim(parts(6))              ' region
        outArr(outN, 8) = paid                        ' paid_gbp
        outArr(outN, 9) = outst                       ' outstanding_gbp
        outArr(outN, 10) = Round(paid + outst, 2)     ' incurred_gbp
NextRow:
    Next i

    ' ---- write the Standardised tab ----
    wsStd.Range("A1:J1").Value = Array("claim_ref", "policy_no", "loss_date", _
        "report_date", "status", "peril_code", "region", "paid_gbp", _
        "outstanding_gbp", "incurred_gbp")
    If outN > 0 Then wsStd.Range("A2").Resize(outN, 10).Value = outArr

    ExportStandardised wsStd, CStr(csvPath), outN + 1
    MsgBox outN & " claims standardised and exported.", vbInformation, "Bordereau ETL"
End Sub

' ---------------------------------------------------------------------
Private Function PrepareSheet(sheetName As String) As Worksheet
    Application.DisplayAlerts = False
    On Error Resume Next
    ThisWorkbook.Worksheets(sheetName).Delete
    On Error GoTo 0
    Application.DisplayAlerts = True
    Set PrepareSheet = ThisWorkbook.Worksheets.Add( _
        After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
    PrepareSheet.Name = sheetName
    ' keep ISO dates as text so Excel does not re-mangle them on export
    If sheetName = "Standardised" Then PrepareSheet.Columns("C:D").NumberFormat = "@"
End Function

' Accepts dd/mm/yyyy, yyyy-mm-dd and dd-Mon-yy. Anything else -> "".
Private Function ParseDateISO(s As String) As String
    Dim d As Long, m As Long, y As Long
    Dim p() As String
    ParseDateISO = ""
    If s = "" Then Exit Function
    On Error GoTo Bad
    If InStr(s, "/") > 0 Then
        p = Split(s, "/")
        If UBound(p) <> 2 Then Exit Function
        If Not (IsNumeric(p(0)) And IsNumeric(p(1)) And IsNumeric(p(2))) Then Exit Function
        d = CLng(p(0)): m = CLng(p(1)): y = CLng(p(2))
    ElseIf InStr(s, "-") > 0 Then
        p = Split(s, "-")
        If UBound(p) <> 2 Then Exit Function
        If Len(p(0)) = 4 Then                          ' yyyy-mm-dd
            If Not (IsNumeric(p(0)) And IsNumeric(p(1)) And IsNumeric(p(2))) Then Exit Function
            y = CLng(p(0)): m = CLng(p(1)): d = CLng(p(2))
        Else                                            ' dd-Mon-yy
            If Not (IsNumeric(p(0)) And IsNumeric(p(2))) Then Exit Function
            d = CLng(p(0)): m = MonthNo(p(1)): y = 2000 + CLng(p(2))
            If m = 0 Then Exit Function
        End If
    Else
        Exit Function
    End If
    If m < 1 Or m > 12 Or d < 1 Or d > 31 Then Exit Function
    If Day(DateSerial(y, m, d)) <> d Then Exit Function  ' catches 31/04 etc.
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

Private Sub ExportStandardised(ws As Worksheet, inputPath As String, nRows As Long)
    Dim outPath As String
    outPath = Left(inputPath, InStrRev(inputPath, ".") - 1) & "_STANDARDISED.csv"
    Dim wbOut As Workbook
    Set wbOut = Workbooks.Add
    ws.Range("A1").Resize(nRows, 10).Copy wbOut.Sheets(1).Range("A1")
    Application.DisplayAlerts = False
    wbOut.SaveAs Filename:=outPath, FileFormat:=xlCSV, Local:=False
    wbOut.Close SaveChanges:=False
    Application.DisplayAlerts = True
End Sub
