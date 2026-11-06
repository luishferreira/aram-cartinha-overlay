$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
while ($null -ne ($line = [Console]::ReadLine())) {
    $request = $null
    try {
        $request = $line | ConvertFrom-Json
        $screen = & "$PSScriptRoot/capture_game.ps1" -OutputPath $request.image -InputImage $request.image -Ocr -NativeTitles:([bool]$request.native_titles)
        $screen = $screen | ConvertFrom-Json
        @{id=$request.id; screen=$screen} | ConvertTo-Json -Depth 16 -Compress
    } catch {
        @{id=$request.id; screen=@{status='ocr_error'; ocr_status='error'; ocr_error=$_.Exception.Message}} | ConvertTo-Json -Depth 4 -Compress
    }
}
