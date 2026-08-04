' Task Scheduler invisible launcher - runs the pipeline with no console window.
' (A visible cmd window gets closed by accident, killing the whole pipeline.)
' Output still goes to logs\pipeline_task.log via the bat.
Dim shell, root
Set shell = CreateObject("WScript.Shell")
root = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
' 0 = hidden window, True = wait so the task state/time limit tracks the pipeline
shell.Run """" & root & "Beef_Daily_Update_Task.bat""", 0, True
