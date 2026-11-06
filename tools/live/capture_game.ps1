param([Parameter(Mandatory=$true)][string]$OutputPath, [switch]$Ocr, [string]$InputImage, [switch]$NativeTitles)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Drawing
if (-not ('GameCaptureWindow' -as [type])) {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class GameCaptureWindow {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr SetProcessDpiAwarenessContext(IntPtr c);
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
}
'@
}
[void][GameCaptureWindow]::SetProcessDpiAwarenessContext([IntPtr](-4))
if ($InputImage) {
    $OutputPath = (Resolve-Path -LiteralPath $InputImage).Path
    $result = @{status='input_image'; image=$OutputPath; ocr_status='not_requested'}
} else {
$game = Get-Process -Name 'League of Legends' -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (!$game) { @{status='game_window_unavailable'} | ConvertTo-Json -Compress; exit 0 }
$handle = $game.MainWindowHandle
if ([GameCaptureWindow]::IsIconic($handle) -or [GameCaptureWindow]::GetForegroundWindow() -ne $handle) {
    @{status='game_not_foreground'} | ConvertTo-Json -Compress; exit 0
}
$rect = New-Object GameCaptureWindow+RECT
$origin = New-Object GameCaptureWindow+POINT
if (![GameCaptureWindow]::GetClientRect($handle, [ref]$rect) -or ![GameCaptureWindow]::ClientToScreen($handle, [ref]$origin)) { throw 'Unable to determine game client bounds' }
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
if ($width -lt 100 -or $height -lt 100) { throw 'Invalid game client bounds' }
$bitmap = [System.Drawing.Bitmap]::new($width, $height, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen($origin.X, $origin.Y, 0, 0, $bitmap.Size)
    $panelVisibility = 'uncalibrated'
    if ($width -eq 1920 -and $height -eq 1080) {
        $darkCount = 0
        $borderCount = 0
        foreach ($sampleX in @(590,960,1328)) { foreach ($sampleY in @(400,620)) {
            $color = $bitmap.GetPixel($sampleX,$sampleY)
            if ($color.R -lt 45 -and $color.G -lt 60 -and $color.B -lt 65) { $darkCount++ }
        } }
        foreach ($sampleX in @(440,808,1176)) { foreach ($sampleY in @(260,500,650)) {
            $color = $bitmap.GetPixel($sampleX,$sampleY)
            if ($color.R -gt 100 -and $color.G -gt 85 -and $color.B -gt 70) { $borderCount++ }
        } }
        $panelVisibility = 'unknown'
        if ($darkCount -ge 5 -and $borderCount -ge 6) { $panelVisibility = 'present' }
        elseif ($darkCount -le 2 -or $borderCount -le 2) { $panelVisibility = 'absent' }
    }
    $bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
} finally { $graphics.Dispose(); $bitmap.Dispose() }
$result = @{status='captured'; width=$width; height=$height; image=$OutputPath; capture='visible_client_area'; ocr_status='not_requested'; panel_visibility=$panelVisibility}
}
if ($Ocr) {
    try {
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
        $null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
        $null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
        $null = [Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]
        $awaitMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 } | Select-Object -First 1
        function Await-WinRT($Operation, $ResultType) {
            $task = $awaitMethod.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
            $task.GetAwaiter().GetResult()
        }
        $result.ocr_stage = 'load_image_bytes'
        $null = [Windows.Storage.Streams.InMemoryRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime]
        $null = [Windows.Storage.Streams.DataWriter,Windows.Storage.Streams,ContentType=WindowsRuntime]
        $stream = [Windows.Storage.Streams.InMemoryRandomAccessStream]::new()
        $writer = [Windows.Storage.Streams.DataWriter]::new($stream)
        try {
            $ocrBytes = [System.IO.File]::ReadAllBytes($OutputPath)
            $offsetX = 0; $offsetY = 0; $ocrScale = 1
            if ($NativeTitles) {
                $sourceBitmap = [System.Drawing.Bitmap]::FromFile($OutputPath)
                try {
                    if ($sourceBitmap.Width -eq 1920 -and $sourceBitmap.Height -eq 1080) {
                        $offsetX = 430; $offsetY = 395; $ocrScale = 2
                        $enlarged = [System.Drawing.Bitmap]::new(2130,200,[System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
                        $resampler = [System.Drawing.Graphics]::FromImage($enlarged)
                        $encoded = [System.IO.MemoryStream]::new()
                        try {
                            $resampler.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                            $resampler.DrawImage($sourceBitmap,[System.Drawing.Rectangle]::new(0,0,2130,200),430,395,1065,100,[System.Drawing.GraphicsUnit]::Pixel)
                            $enlarged.Save($encoded,[System.Drawing.Imaging.ImageFormat]::Png)
                            $ocrBytes = $encoded.ToArray()
                            $result.ocr_region = @{x=$offsetX; y=$offsetY; scale=$ocrScale}
                        } finally { $encoded.Dispose(); $resampler.Dispose(); $enlarged.Dispose() }
                    }
                } finally { $sourceBitmap.Dispose() }
            }
            $writer.WriteBytes($ocrBytes)
            $null = Await-WinRT ($writer.StoreAsync()) ([uint32])
            $null = $writer.DetachStream()
        } finally { $writer.Dispose() }
        $stream.Seek(0)
        try {
            $result.ocr_stage = 'decode'
            $decoder = Await-WinRT ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
            $software = Await-WinRT ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
            try {
                $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('pt-BR'))
                if (!$engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
                if (!$engine) { throw 'No local OCR language is installed' }
                $result.ocr_stage = 'recognize'
                $recognized = Await-WinRT ($engine.RecognizeAsync($software)) ([Windows.Media.Ocr.OcrResult])
                $result.ocr_language = $engine.RecognizerLanguage.LanguageTag
                $result.ocr_lines = @($recognized.Lines | ForEach-Object {
                    @{text=$_.Text; words=@($_.Words | ForEach-Object {
                        @{text=$_.Text; x=($_.BoundingRect.X / $ocrScale + $offsetX); y=($_.BoundingRect.Y / $ocrScale + $offsetY); width=($_.BoundingRect.Width / $ocrScale); height=($_.BoundingRect.Height / $ocrScale)}
                    })}
                })
                $result.ocr_status = 'recognized'
            } finally { if ($software) { $software.Dispose() } }
        } finally { if ($stream) { $stream.Dispose() } }
    } catch { $result.ocr_status='error'; $result.ocr_error=$_.Exception.Message }
}
$result | ConvertTo-Json -Depth 12 -Compress
