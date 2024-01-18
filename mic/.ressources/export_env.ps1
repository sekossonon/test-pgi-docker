function DisablePythonFileValidation {
    New-Item -Path Env:PYDEVD_DISABLE_FILE_VALIDATION -Value 1
}
