# KFinans geliştirme ortamını başlatır:
#   1. kubectl port-forward  (PostgreSQL @ localhost:5432) — watchdog ile
#   2. uvicorn               (FastAPI @ localhost:8000)

$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("PATH", "User")

$PYTHON  = "C:\Users\celik\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$KUBECTL = (Get-Command kubectl -ErrorAction Stop).Source
$BACKEND = "C:\Users\celik\Projects\KFinans\backend"
$LOG_DIR = "$env:TEMP\kfinans-logs"

New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

function Test-Port($port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", $port)
        $tcp.Close()
        return $true
    } catch { return $false }
}

function Start-PortForward {
    Get-Process kubectl -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    Start-Process -NoNewWindow -FilePath $KUBECTL `
        -ArgumentList "port-forward -n kfinans svc/postgres-postgresql 5432:5432" `
        -RedirectStandardOutput "$LOG_DIR\pg-pf.log" `
        -RedirectStandardError  "$LOG_DIR\pg-pf-err.log"
}

# Kubernetes cluster hazır olana kadar bekle (max 120s)
Write-Host "Kubernetes bekleniyor..."
$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $deadline) {
    $nodes = & $KUBECTL get nodes --no-headers 2>$null
    if ($nodes -match "Ready") { break }
    Start-Sleep -Seconds 5
}

# İlk port-forward başlat
Write-Host "PostgreSQL port-forward baslatiliyor..."
Start-PortForward
Start-Sleep -Seconds 3

# Uvicorn'u başlat
Write-Host "Uvicorn baslatiliyor..."
Start-Process -NoNewWindow -FilePath $PYTHON `
    -ArgumentList "-m uvicorn app.main:app --reload" `
    -WorkingDirectory $BACKEND `
    -RedirectStandardOutput "$LOG_DIR\uvicorn.log" `
    -RedirectStandardError  "$LOG_DIR\uvicorn-err.log"

Write-Host "KFinans backend hazir -> http://localhost:8000"

# Watchdog: port 5432 kapanırsa yeniden başlat
while ($true) {
    Start-Sleep -Seconds 5
    if (-not (Test-Port 5432)) {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') Port-forward dustu, yeniden baslatiliyor..."
        Start-PortForward
        Start-Sleep -Seconds 3
    }
}
