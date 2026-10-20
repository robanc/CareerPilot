<#
.SYNOPSIS
Runs the backend tests against the isolated test PostgreSQL container.

.DESCRIPTION
Runs pytest against the disposable PostgreSQL 16 container defined in
docker-compose.test.yml, which must ALREADY be running and healthy. This
script never creates, starts, stops, recreates, or removes a container and
never runs docker compose; it only reads Docker state ("docker ps",
"docker inspect", "docker volume ls", "docker network ls"). Start the
container yourself when needed:

  docker compose -p careerpilot-test -f docker-compose.test.yml up --detach --wait

The previous values of every variable it sets or clears are restored
afterwards, even after an error or Ctrl+C, so a later development
"docker compose up" never sees the test values.

Safety checks. Any failure refuses the run (exit 3):
- The careerpilot-test project must contain exactly one container (service
  db-test), no volumes, and only its default network. No other running
  container may publish host port 5433, and nothing else may listen on it.
  A stopped container configured for 5433 only produces a warning, because
  it cannot hold the port.
- That container must be running and healthy, with
  image postgres:16-alpine and only 127.0.0.1:5433->5432/tcp. Its Compose
  labels must name this repository's docker-compose.test.yml and working
  directory, and it must not be a one-off container. Its command must be
  exactly the test postgres command (hba_file and cluster_name), and its
  only network the project's default network. It must have no volumes, a
  tmpfs data directory, and exactly three read-only bind mounts, each from
  its expected repository file: the Stage A scripts 01 and 02 (mounted as
  single files into /docker-entrypoint-initdb.d) and pg_hba.conf.
- Before pytest: a connection to 127.0.0.1:5433 with the test credentials
  (the same endpoint pytest uses) must report cluster_name =
  careerpilot-test, hba_file = /etc/careerpilot/pg_hba.conf,
  current_database() = careerpilot_test, current_user =
  careerpilot_test_admin, PostgreSQL major version 16, and data_directory
  = /var/lib/postgresql/data (the tmpfs mount).
- Immediately before pytest starts, the same container (same ID) is checked
  again in full.

Environment for the pytest run (and the marker check):
- POSTGRES_HOST/PORT/USER/PASSWORD/DB are set to the fixed, non-secret test
  values from docker-compose.test.yml (127.0.0.1:5433, careerpilot_test).
- PYTHON_DOTENV_DISABLED=1 disables python-dotenv, so database.py never
  reads .env during the run: no POSTGRES_* or CAREERPILOT_* value from .env
  can reach pytest.
- CAREERPILOT_MODE=local, and the application database variables
  (DATABASE_URL, CAREERPILOT_DEMO_DATABASE_URL,
  CAREERPILOT_ADMIN_DATABASE_URL, CAREERPILOT_SEED_DATABASE_URL) and RENDER
  are cleared.
- The libpq PG* connection variables (PGHOST, PGHOSTADDR, PGSERVICE, ...)
  are cleared, because libpq would otherwise apply them to connections that
  leave them unspecified; PGHOSTADDR, for example, can redirect a
  connection that names host 127.0.0.1.
This script reads no .env file and never reads or prints the values it
saves and restores.

The container keeps running afterwards. Reset it (deliberately, yourself)
with:

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
# Container destination -> source file, relative to the repository root.
# Exactly these, all read-only. Stage B drafts are never mounted.
$ExpectedBindMounts = [ordered]@{
    '/docker-entrypoint-initdb.d/01_test_reader_role.sql'   = 'backend\tests\sql\01_test_reader_role.sql'
    '/docker-entrypoint-initdb.d/02_test_reader_grants.sql' = 'backend\tests\sql\02_test_reader_grants.sql'
    '/etc/careerpilot/pg_hba.conf'                          = 'backend\tests\postgres\pg_hba.conf'
}
$ExpectedCommand = 'postgres|-c|hba_file=/etc/careerpilot/pg_hba.conf|-c|cluster_name=careerpilot-test'
$ExpectedDataDir = '/var/lib/postgresql/data'
$ExpectedMarkers = "careerpilot-test|/etc/careerpilot/pg_hba.conf|careerpilot_test|careerpilot_test_admin|16|$ExpectedDataDir"

# libpq reads these when a connection leaves the setting unspecified, so
# they could redirect or alter the marker check and pytest's connections.
# Cleared for the run and restored afterwards; never read or printed.
$LibpqVariables = @(
    'PGHOST', 'PGHOSTADDR', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD',
    'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGSYSCONFDIR', 'PGOPTIONS',
    'PGTARGETSESSIONATTRS', 'PGLOADBALANCEHOSTS', 'PGREQUIREAUTH'
)

# Application settings that select a mode or a database other than the
# POSTGRES_* test target. Cleared for the run and restored afterwards;
# never read or printed. (CAREERPILOT_MODE is set to local instead.)
$AppVariables = @(
    'DATABASE_URL', 'CAREERPILOT_DEMO_DATABASE_URL',
    'CAREERPILOT_ADMIN_DATABASE_URL', 'CAREERPILOT_SEED_DATABASE_URL', 'RENDER'
)

# Reads the cluster identity through the same endpoint and credentials
# pytest will use. Read-only: a single SELECT. Sent on stdin, so Windows
# PowerShell 5.1 does not mangle its quotes. On failure it prints only the
# exception type: never a message, URL, or credential.
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
            "SELECT current_setting('cluster_name'),"
            " current_setting('hba_file'),"
            " current_database(),"
            " current_user,"
            " current_setting('server_version_num')::integer / 10000,"
            " current_setting('data_directory')"
        ).fetchone()
except Exception as exc:
    print("marker check could not connect: " + type(exc).__name__, file=sys.stderr)
    sys.exit(1)
print("|".join(str(value) for value in row))
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

# The only container this script will use: the project's existing db-test
# container, already running and healthy, matching docker-compose.test.yml.
# Read-only; it never creates, starts, stops, or recreates anything, so the
# run is refused when the container is missing, stopped, or unhealthy.
function Get-ExistingTestContainer {
    $containers = @(Get-ProjectContainers)
    Assert-ProjectComposition $containers
    if ($containers.Count -ne 1) {
        throw "project $ProjectName has no $ServiceName container. Start it yourself (docker compose -p $ProjectName -f docker-compose.test.yml up --detach --wait); this script never creates or starts containers."
    }
    $container = $containers[0]
    if (-not $container.State.Running -or $container.State.Health.Status -ne 'healthy') {
        throw "container $(Get-ContainerName $container) is not running and healthy (status '$($container.State.Status)', health '$($container.State.Health.Status)'). Start it yourself; this script never starts, restarts, or recreates containers."
    }
    Assert-TestContainer $container
    $container
}

# Case-insensitive comparison of two full Windows paths. A missing or
# differently shaped path (for example a WSL-style source) never matches.
function Test-SamePath([string]$Actual, [string]$Expected) {
    if ([string]::IsNullOrEmpty($Actual) -or [string]::IsNullOrEmpty($Expected)) { return $false }
    try {
        $actualFull = [System.IO.Path]::GetFullPath($Actual).TrimEnd('\')
        $expectedFull = [System.IO.Path]::GetFullPath($Expected).TrimEnd('\')
    }
    catch {
        return $false
    }
    [string]::Equals($actualFull, $expectedFull, [System.StringComparison]::OrdinalIgnoreCase)
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

    # Compose identity: started from this repository's test compose file.
    $labels = $Container.Config.Labels
    $composeFile = Join-Path $repoRoot 'docker-compose.test.yml'
    if ((Get-ProjectLabel $Container) -ne $ProjectName -or (Get-ServiceLabel $Container) -ne $ServiceName) {
        $problems += "compose project/service labels are not $ProjectName/$ServiceName"
    }
    if (-not (Test-SamePath $labels.'com.docker.compose.project.config_files' $composeFile)) {
        $problems += "compose config file label is not $composeFile"
    }
    if (-not (Test-SamePath $labels.'com.docker.compose.project.working_dir' $repoRoot)) {
        $problems += "compose working directory label is not $repoRoot"
    }
    if ($labels.'com.docker.compose.oneoff' -ne 'False') {
        $problems += 'is a one-off (compose run) container'
    }

    $command = @($Container.Config.Cmd) -join '|'
    if ($command -ne $ExpectedCommand) {
        $problems += "command is not the test postgres command (hba_file, cluster_name)"
    }

    $networks = @($Container.NetworkSettings.Networks.PSObject.Properties.Name)
    if ($Container.HostConfig.NetworkMode -ne $ExpectedNetwork -or
        $networks.Count -ne 1 -or $networks[0] -ne $ExpectedNetwork) {
        $problems += "networks are '$($networks -join ', ')', expected only $ExpectedNetwork"
    }

    $otherMounts = @($Container.Mounts | Where-Object { $_.Type -ne 'bind' })
    if ($otherMounts.Count -gt 0) {
        $problems += "has non-bind mounts: $(($otherMounts | ForEach-Object { "$($_.Type) $($_.Destination)" }) -join ', ')"
    }

    # Exactly the expected bind mounts: same destinations, each from its
    # expected repository file, all read-only.
    $bindMounts = @($Container.Mounts | Where-Object { $_.Type -eq 'bind' })
    $destinations = ($bindMounts | ForEach-Object { $_.Destination } | Sort-Object) -join ','
    $expectedDestinations = ($ExpectedBindMounts.Keys | Sort-Object) -join ','
    if ($destinations -ne $expectedDestinations) {
        $problems += "bind mount destinations are '$destinations', expected '$expectedDestinations'"
    }
    foreach ($mount in $bindMounts) {
        if (-not $ExpectedBindMounts.Contains($mount.Destination)) { continue }
        $expectedSource = Join-Path $repoRoot $ExpectedBindMounts[$mount.Destination]
        if (-not (Test-SamePath $mount.Source $expectedSource)) {
            $problems += "bind mount $($mount.Destination) is not from $expectedSource"
        }
        if ($mount.RW -ne $false) {
            $problems += "bind mount $($mount.Destination) is writable"
        }
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
        throw "127.0.0.1:$TestPort is not the isolated test cluster: cluster_name|hba_file|database|user|major version|data_directory is '$actual', expected '$ExpectedMarkers'."
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$testEnv = [ordered]@{
    POSTGRES_HOST          = '127.0.0.1'
    POSTGRES_PORT          = $TestPort
    POSTGRES_USER          = 'careerpilot_test_admin'
    POSTGRES_PASSWORD      = 'careerpilot_test_admin_password'
    POSTGRES_DB            = 'careerpilot_test'
    # database.py calls load_dotenv(); this makes python-dotenv skip .env.
    PYTHON_DOTENV_DISABLED = '1'
    CAREERPILOT_MODE       = 'local'
}
$clearedVariables = @($LibpqVariables) + @($AppVariables)

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
foreach ($name in @($testEnv.Keys) + $clearedVariables) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$exitCode = 1
Push-Location -LiteralPath $repoRoot
try {
    # Read-only checks only: the existing container, the port, the project.
    $container = Get-ExistingTestContainer
    Assert-NoOtherPublisher
    Assert-PortFree @($container)

    foreach ($name in $testEnv.Keys) {
        [Environment]::SetEnvironmentVariable($name, $testEnv[$name], 'Process')
    }
    # Setting a variable to $null removes it from this process.
    foreach ($name in $clearedVariables) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }

    # The endpoint pytest will use is the isolated cluster.
    Assert-ClusterMarkers

    # Immediately before pytest: still the same, healthy, matching container.
    $recheck = Get-ExistingTestContainer
    if ($recheck.Id -ne $container.Id) {
        throw "the $ServiceName container changed (different container ID) during the checks."
    }
    Assert-NoOtherPublisher -NoWarning

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
