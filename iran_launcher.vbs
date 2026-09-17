Option Explicit
Dim sh, fso, root, scriptPath, py
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = root & "\iran_gui.pyw"
py = "C:\Program Files\Python314\pythonw.exe"
If Not fso.FileExists(scriptPath) Then
    MsgBox "iran_gui.pyw پیدا نشد.", 16, "IRAN"
    WScript.Quit 1
End If
sh.CurrentDirectory = root
sh.Run Chr(34) & py & Chr(34) & " " & Chr(34) & scriptPath & Chr(34), 1, False
