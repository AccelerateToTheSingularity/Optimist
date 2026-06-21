Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
repo = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = repo

' Run without a console window (pythonw / pyw).
On Error Resume Next
sh.Run "pyw """ & repo & "\settings_gui.py""", 0, False
If Err.Number <> 0 Then
  Err.Clear
  sh.Run "pythonw """ & repo & "\settings_gui.py""", 0, False
End If
