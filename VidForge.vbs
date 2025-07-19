Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' Get the folder where this VBS file is located
scriptPath = WScript.ScriptFullName
scriptFolder = fso.GetParentFolderName(scriptPath)

' Build the command to run python script from the same folder
pythonCmd = "python """ & scriptFolder & "\VidForge.py"""

' Run the command, hide the window, do not wait
shell.Run pythonCmd, 0, False
