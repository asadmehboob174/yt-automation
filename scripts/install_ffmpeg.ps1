# AI Video Factory - FFmpeg Local Installer
# This script downloads FFmpeg from gyan.dev and installs it in c:\yt-automation\bin\ffmpeg

$InstallDir = "c:\yt-automation\bin\ffmpeg"
$ZipPath = "c:\yt-automation\temp\ffmpeg.zip"
$EnvPath = "c:\yt-automation\.env"

# 1. Create Directories
if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Force -Path $InstallDir
}
if (!(Test-Path "c:\yt-automation\temp")) {
    New-Item -ItemType Directory -Force -Path "c:\yt-automation\temp"
}

# 2. Download FFmpeg (gyan.dev essentials build)
Write-Host "Downloading FFmpeg (this may take a minute)..."
Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $ZipPath

# 3. Extract
Write-Host "Extracting..."
Expand-Archive -Path $ZipPath -DestinationPath "c:\yt-automation\temp\ffmpeg_extracted" -Force

# 4. Move binaries to bin/ffmpeg
Write-Host "Organizing files..."
$ExtractedFolder = Get-ChildItem -Path "c:\yt-automation\temp\ffmpeg_extracted" -Directory | Select-Object -First 1
Move-Item -Path "$($ExtractedFolder.FullName)\bin\*" -Destination $InstallDir -Force

# 5. Cleanup
Remove-Item $ZipPath -Force
Remove-Item -Path "c:\yt-automation\temp\ffmpeg_extracted" -Recurse -Force

Write-Host "FFmpeg installed to $InstallDir"

# 6. Update .env file automatically
Write-Host "Updating .env file..."
if (Test-Path $EnvPath) {
    # Read as a single string to avoid array issues
    $Content = Get-Content $EnvPath -Raw
    
    # Update existing keys if they exist (handling both commented and uncommented)
    if ($Content -match "FFMPEG_PATH=") {
        $Content = $Content -replace "(?m)^#? ?FFMPEG_PATH=.*", "FFMPEG_PATH=$InstallDir\ffmpeg.exe"
    } else {
        $Content = $Content + "`r`nFFMPEG_PATH=$InstallDir\ffmpeg.exe"
    }
    
    if ($Content -match "FFPROBE_PATH=") {
        $Content = $Content -replace "(?m)^#? ?FFPROBE_PATH=.*", "FFPROBE_PATH=$InstallDir\ffprobe.exe"
    } else {
        $Content = $Content + "`r`nFFPROBE_PATH=$InstallDir\ffprobe.exe"
    }
    
    $Content | Set-Content $EnvPath -NoNewline -Encoding UTF8
    Write-Host ".env updated with local FFmpeg paths."
} else {
    Write-Host ".env not found, please manually set FFMPEG_PATH to $InstallDir\ffmpeg.exe"
}

Write-Host "Setup Complete! You can now retry your video stitching."
