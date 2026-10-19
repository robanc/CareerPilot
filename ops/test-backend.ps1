<#
.SYNOPSIS
Runs the backend tests against the isolated test PostgreSQL container.

.DESCRIPTION
Starts (or reuses) the disposable PostgreSQL 16 container defined in
docker-compose.test.yml, then runs pytest with POSTGRES_* pointing at it.
The previous POSTGRES_* values of this PowerShell session are restored
afterwards, even after an error or Ctrl+C, so a later development
"docker compose up" never sees the test values.

Safety checks. They only read Docker and port state; they never stop,
change, or remove anything. Any failure refuses the run (exit 3):
- Before startup: the careerpilot-test project may contain at most one
  container (service db-test), no volumes, and only its default network.
  No other running container may publish host port 5433, and nothing else
  may listen on it. A stopped container configured for 5433 only produces
  a warning, because it cannot hold the port.
- After startup: exactly one db-test container, running and healthy, with
  image postgres:16-alpine, only 127.0.0.1:5433->5432/tcp, only its two
  read-only bind mounts, no volumes, and a tmpfs data directory.
- Before pytest: a connection to 127.0.0.1:5433 with the test credentials
  (the same endpoint pytest uses) must report
  cluster_name = careerpilot-test and hba_file = /etc/careerpilot/pg_hba.conf.

The test credentials are the fixed, non-secret values from
docker-compose.test.yml. This script reads no .env values and prints none.
database.py loads .env without overriding variables that are already set,
so the values set here win for the pytest run.

The container keeps running afterwards. Reset it with:

  docker compose -p careerpilot-test -f docker-compose.test.yml down

Exit codes: pytest's own exit code; 2 for an invalid -Path or a missing
tool; 3 when a safety check refuses the run. Unknown parameters are
rejected by PowerShell's own parameter binding (exit 1, which is also
pytest's "tests failed" code).

.PARAMETER Path
What pytest runs, relative to the repository root. Defaults to the full
backend suite (backend/tests). Pass a single test file, or a single
"file::test" node ID, to run only that. It must be inside backend/tests.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\test-backend.ps1 -Path backend/tests/test_health.py
#>
[CmdletBinding()]
param(
    [ValidateNotNullOrEmpty()]
    [string]$Path = 'backend/tests'
)

# Dot-sourcing would run in the caller's scope, where "exit" closes the
# interactive shell. Refuse instead.
if ($MyInvocation.InvocationName -eq '.') {
    Write-Error 'Do not dot-source this script. Run it as .\ops\test-backend.ps1 or with powershell -File.'
    return
}

# Not 'Stop': Windows PowerShell 5.1 can turn a native command's stderr
# (docker progress output) into a terminating error. Native exit codes are
# checked explicitly, and the safety checks below use "throw".
$ErrorActionPreference = 'Continue'

$ProjectName = 'careerpilot-test'
$ServiceName = 'db-test'
$TestPort = '5433'
$ProjectFilter = "label=com.docker.compose.project=$ProjectName"
$ExpectedImage = 'postgres:16-alpine'
$ExpectedNetwork = "${ProjectName}_default"
$ExpectedBindMounts = '/docker-entrypoint-initdb.d:False,/etc/careerpilot/pg_hba.conf:False'
$ExpectedDataDir = '/var/lib/postgresql/data'
$ExpectedMarkers = 'careerpilot-test|/etc/careerpilot/pg_hba.conf'

# Reads both markers through the same endpoint and credentials pytest will
# use. Sent on stdin, so Windows PowerShell 5.1 does not mangle its quotes.
# On failure it prints only the exception type: never a message, URL, or
# credential.
$MarkerCheck = @'
import os
import sys

import psycopg

try:
    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
        connect_timeout=10,
    ) as conn:
        row = conn.execute(
            "SELECT current_setting('cluster_name'), current_setting('hba_file')"
        ).fetchone()
except Exception as exc:
    print("marker check could not connect: " + type(exc).__name__, file=sys.stderr)
    sys.exit(1)
print(row[0] + "|" + row[1])
'@

function Write-Failure([string]$Message) {
    Write-Host "test-backend: $Message" -ForegroundColor Red
}

function Write-Caution([string]$Message) {
    Write-Host "test-backend: warning: $Message" -ForegroundColor Yellow
}

# Runs docker and returns its non-empty stdout lines; throws on failure.
function Invoke-Docker([string[]]$Arguments) {
    $output = & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker $($Arguments[0]) $($Arguments[1]) failed (exit $LASTEXITCODE)."
    }
    $output | Where-Object { $_ }
}

# Parsed "docker inspect" objects. JSON is used instead of --format
# templates, whose inner quotes Windows PowerShell 5.1 would strip.
function Get-ContainerDetails([string[]]$Ids) {
    if (-not $Ids) { return }
    $json = (Invoke-Docker (@('inspect') + $Ids)) -join "`n"
    foreach ($container in (ConvertFrom-Json -InputObject $json)) { $container }
}

function Get-ContainerName($Container) {
    $Container.Name.TrimStart('/')
}

function Get-ServiceLabel($Container) {
    $Container.Config.Labels.'com.docker.compose.service'
}

function Get-ProjectLabel($Container) {
    $Container.Config.Labels.'com.docker.compose.project'
}

# One object per configured host port binding.
function Get-HostBindings($Container) {
    $bindings = $Container.HostConfig.PortBindings
    if ($null -eq $bindings) { return }
    foreach ($port in $bindings.PSObject.Properties) {
        foreach ($binding in @($port.Value)) {
            if ($null -eq $binding) { continue }
            [pscustomobject]@{
                ContainerPort = $port.Name
                HostIp        = $binding.HostIp
                HostPort      = $binding.HostPort
            }
        }
    }
}

function Test-PublishesTestPort($Container) {
    @(Get-HostBindings $Container | Where-Object { $_.HostPort -eq $TestPort }).Count -gt 0
}

function Get-ProjectContainers {
    $ids = @(Invoke-Docker @('ps', '--all', '--quiet', '--filter', $ProjectFilter))
    Get-ContainerDetails $ids
}

# The project may hold only its own db-test container, no volumes, and only
# its default network.
function Assert-ProjectComposition([object[]]$Containers) {
    $unexpected = @($Containers | Where-Object { (Get-ServiceLabel $_) -ne $ServiceName })
    if ($unexpected.Count -gt 0) {
        $names = ($unexpected | ForEach-Object { Get-ContainerName $_ }) -join ', '
        throw "project $ProjectName contains unexpected containers: $names."
    }
    if ($Containers.Count -gt 1) {
        throw "project $ProjectName has $($Containers.Count) $ServiceName containers; expected at most one."
    }

    $volumes = @(Invoke-Docker @('volume', 'ls', '--quiet', '--filter', $ProjectFilter))
    if ($volumes.Count -gt 0) {
        throw "project $ProjectName has $($volumes.Count) volume(s); it must have none (its data is tmpfs)."
    }

    $networks = @(Invoke-Docker @('network', 'ls', '--format', '{{.Name}}', '--filter', $ProjectFilter))
    $extraNetworks = @($networks | Where-Object { $_ -ne $ExpectedNetwork })
    if ($extraNetworks.Count -gt 0) {
        throw "project $ProjectName has unexpected networks: $($extraNetworks -join ', ')."
    }
}

# Containers outside the project whose configuration publishes host port
# 5433. Running ones refuse the run; stopped ones only warn (once, unless
# -NoWarning is given on the repeat check after startup).
function Assert-NoOtherPublisher([switch]$NoWarning) {
    $ids = @(Invoke-Docker @('ps', '--all', '--quiet'))
    foreach ($container in @(Get-ContainerDetails $ids)) {
        if ((Get-ProjectLabel $container) -eq $ProjectName) { continue }
        if (-not (Test-PublishesTestPort $container)) { continue }
        $name = Get-ContainerName $container
        if ($container.State.Running) {
            throw "running container $name publishes host port $TestPort."
        }
        if (-not $NoWarning) {
            Write-Caution "stopped container $name is configured to publish host port $TestPort; starting it would conflict."
        }
    }
}

function Get-PortListeners {
    if (-not (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue)) {
        throw "Get-NetTCPConnection is unavailable, so port $TestPort cannot be checked."
    }
    Get-NetTCPConnection -LocalPort ([int]$TestPort) -State Listen -ErrorAction SilentlyContinue
}

# A listener on 5433 is expected only when this project's own container is
# already running with that binding (Docker's port forwarder holds it).
function Assert-PortFree([object[]]$Containers) {
    $listeners = @(Get-PortListeners)
    if ($listeners.Count -eq 0) { return }
    $ours = @($Containers | Where-Object { $_.State.Running -and (Test-PublishesTestPort $_) })
    if ($ours.Count -gt 0) { return }
    $owners = ($listeners | ForEach-Object {
            $process = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
            if ($process) { "$($process.ProcessName) (PID $($_.OwningProcess))" } else { "PID $($_.OwningProcess)" }
        } | Sort-Object -Unique) -join ', '
    throw "port $TestPort is already in use by $owners, not by the $ProjectName container."
}

# The container actually started must match docker-compose.test.yml.
function Assert-TestContainer($Container) {
    $problems = @()
    if (-not $Container.State.Running) { $problems += 'not running' }
    if ($Container.State.Health.Status -ne 'healthy') {
        $problems += "health is '$($Container.State.Health.Status)'"
    }
    if ($Container.Config.Image -ne $ExpectedImage) {
        $problems += "image is '$($Container.Config.Image)'"
    }

    $bindings = @(Get-HostBindings $Container)
    if ($bindings.Count -ne 1 -or $bindings[0].ContainerPort -ne '5432/tcp' -or
        $bindings[0].HostIp -ne '127.0.0.1' -or $bindings[0].HostPort -ne $TestPort) {
        $problems += "port bindings are not exactly 127.0.0.1:$TestPort->5432/tcp"
    }

    $otherMounts = @($Container.Mounts | Where-Object { $_.Type -ne 'bind' })
    if ($otherMounts.Count -gt 0) {
        $problems += "has non-bind mounts: $(($otherMounts | ForEach-Object { "$($_.Type) $($_.Destination)" }) -join ', ')"
    }
    $bindMounts = ($Container.Mounts | Where-Object { $_.Type -eq 'bind' } |
            ForEach-Object { "$($_.Destination):$($_.RW)" } | Sort-Object) -join ','
    if ($bindMounts -ne $ExpectedBindMounts) {
        $problems += "bind mounts are '$bindMounts'"
    }

    $tmpfs = $Container.HostConfig.Tmpfs
    if ($null -eq $tmpfs -or -not ($tmpfs.PSObject.Properties.Name -contains $ExpectedDataDir)) {
        $problems += "$ExpectedDataDir is not tmpfs"
    }

    if ($problems.Count -gt 0) {
        throw "container $(Get-ContainerName $Container) does not match docker-compose.test.yml: $($problems -join '; ')."
    }
}

function Assert-ClusterMarkers {
    $output = @($MarkerCheck | & python -)
    if ($LASTEXITCODE -ne 0) {
        throw "could not read the cluster markers through 127.0.0.1:$TestPort."
    }
    $actual = if ($output.Count -gt 0) { [string]$output[-1] } else { '' }
    if ($actual -ne $ExpectedMarkers) {
        throw "127.0.0.1:$TestPort is not the isolated test cluster: cluster_name|hba_file is '$actual', expected '$ExpectedMarkers'."
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$composeArgs = @(
    'compose',
    '--project-name', $ProjectName,
    '--file', (Join-Path $repoRoot 'docker-compose.test.yml')
)
$testEnv = [ordered]@{
    POSTGRES_HOST     = '127.0.0.1'
    POSTGRES_PORT     = $TestPort
    POSTGRES_USER     = 'careerpilot_test_admin'
    POSTGRES_PASSWORD = 'careerpilot_test_admin_password'
    POSTGRES_DB       = 'careerpilot_test'
}

# Exactly one pytest target: the default suite, or the one selected path.
$selector = $Path.Trim()
$filePart = ($selector -split '::', 2)[0]
$testsRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot 'backend\tests'))
$target = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($repoRoot, $filePart))
$insideTests = ($target -eq $testsRoot) -or $target.StartsWith(
    $testsRoot + [System.IO.Path]::DirectorySeparatorChar,
    [System.StringComparison]::OrdinalIgnoreCase)

if (-not $insideTests) {
    Write-Failure "-Path must be inside backend/tests: $selector"
    exit 2
}
if (-not (Test-Path -LiteralPath $target)) {
    Write-Failure "-Path does not exist: $selector"
    exit 2
}
foreach ($tool in 'docker', 'python') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Failure "$tool was not found on PATH."
        exit 2
    }
}

$saved = @{}
foreach ($name in $testEnv.Keys) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$exitCode = 1
Push-Location -LiteralPath $repoRoot
try {
    # Before startup: read-only checks of the project and the port.
    $before = @(Get-ProjectContainers)
    Assert-ProjectComposition $before
    Assert-NoOtherPublisher
    Assert-PortFree $before

    & docker @composeArgs up --detach --wait
    if ($LASTEXITCODE -ne 0) {
        throw "the isolated test database did not become healthy. Inspect it with: docker compose -p $ProjectName -f docker-compose.test.yml logs $ServiceName"
    }

    # After startup: the container that is actually running.
    $after = @(Get-ProjectContainers)
    Assert-ProjectComposition $after
    if ($after.Count -ne 1) {
        throw "project $ProjectName has no $ServiceName container after startup."
    }
    Assert-TestContainer $after[0]
    Assert-NoOtherPublisher -NoWarning

    foreach ($name in $testEnv.Keys) {
        [Environment]::SetEnvironmentVariable($name, $testEnv[$name], 'Process')
    }

    # Before pytest: the endpoint pytest will use is the isolated cluster.
    Assert-ClusterMarkers

    & python -m pytest $selector -v
    $exitCode = $LASTEXITCODE
}
catch {
    Write-Failure "refusing to run the tests: $($_.Exception.Message)"
    $exitCode = 3
}
finally {
    # Restores the previous values; a variable that was unset is removed.
    foreach ($name in $saved.Keys) {
        [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process')
    }
    Pop-Location
}

# Ends only this script (it is never dot-sourced; see above).
exit $exitCode
