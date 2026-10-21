param(
    [string]$Jar = $env:OPORA_TLC_JAR,
    [ValidateSet('all','positive','negative','stale-negative')][string]$Mode = 'all',
    [string]$OutputDirectory = (Join-Path ([System.IO.Path]::GetTempPath()) ('oporahub-tlc-' + [guid]::NewGuid().ToString('N')))
)
$ErrorActionPreference = 'Stop'
$expectedSha256 = '936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88'
if (-not $Jar -or (Get-FileHash -LiteralPath $Jar -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedSha256) {
    throw 'Set -Jar or OPORA_TLC_JAR to the external pinned v1.7.4 tla2tools.jar (SHA256 mismatch or absent).'
}
$Jar = (Resolve-Path -LiteralPath $Jar).Path
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
foreach ($name in @('ExecutionAuthority.tla','ExecutionAuthority.cfg','NoFence.cfg','NoEpochReceipt.cfg')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $OutputDirectory $name)
}
$cases = @(
    @{Config='ExecutionAuthority.cfg'; Name='positive'; Exit=0; Expected='Model checking completed. No error has been found.'},
    @{Config='NoFence.cfg'; Name='negative'; Exit=12; Expected='Error: Invariant OneActiveOwner is violated.'},
    @{Config='NoEpochReceipt.cfg'; Name='stale-negative'; Exit=12; Expected='Error: Invariant NoStaleEpochReceipt is violated.'}
)
Push-Location $OutputDirectory
try {
    foreach ($case in $cases) {
        if ($Mode -ne 'all' -and $Mode -ne $case.Name) { continue }
        $logPath = Join-Path (Get-Location) ($case.Name + '.log')
        $stateDir = Join-Path (Get-Location) ('run-' + $case.Name + '-' + [guid]::NewGuid().ToString('N'))
        & java -XX:+UseParallelGC -Xmx768m -cp $Jar tlc2.TLC -workers 1 -fp 0 -seed 1 -config $case.Config -metadir $stateDir -coverage 1 ExecutionAuthority.tla *> $logPath
        $code = $LASTEXITCODE
        $code | Set-Content ($case.Name + '.exit')
        $log = Get-Content -LiteralPath $logPath -Raw
        if ($code -ne $case.Exit -or -not $log.Contains($case.Expected)) {
            throw ('Unexpected TLC result for ' + $case.Config + ': ' + $code)
        }
        if ($case.Name -eq 'positive' -and $log -notmatch '(?m)(?:^|,\s*)0 states left on queue\.[ \t]*\r?$') {
            throw 'Positive run did not exhaust the bounded state space.'
        }
        Write-Output ($case.Name + ': expected result confirmed; ' + $logPath)
    }
} finally { Pop-Location }
