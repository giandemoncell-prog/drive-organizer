param(
    [int]$StartOffset = 50,
    [int]$BatchSize = 20,
    [int]$Total = 532,
    [float]$MinConf = 0.85
)

$python = ".venv\Scripts\python.exe"
$offset = $StartOffset
$batch = 1

while ($offset -lt $Total) {
    $end = [Math]::Min($offset + $BatchSize, $Total)
    Write-Host ""
    Write-Host "====== BATCH $batch file $($offset+1)-$end ======" -ForegroundColor Cyan

    & $python main.py rename --offset $offset --limit $BatchSize --min-confidence $MinConf --apply --yes

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERRORE batch offset=$offset" -ForegroundColor Red
        exit 1
    }

    $offset += $BatchSize
    $batch++
}

Write-Host ""
Write-Host "====== TUTTI I BATCH COMPLETATI ($batch batch) ======" -ForegroundColor Green
