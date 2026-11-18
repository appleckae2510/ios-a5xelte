#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$AdbPath,
    [string]$OutputDirectory,
    [switch]$Hardware,
    [switch]$BootCheck
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:SelectedDevice = $null
$script:AdbExecutable = $null
$script:RunFolder = $null
$script:BootAlias = $null
$script:ExpectedDeviceCode = $null
$script:Utf8 = New-Object System.Text.UTF8Encoding($false)

function Write-Utf8([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text, $script:Utf8)
}

function Write-BackupLog([string]$Text) {
    if ($script:RunFolder) {
        [System.IO.File]::AppendAllText((Join-Path $script:RunFolder 'SICHERUNG-PROTOKOLL.txt'),
            ((Get-Date -Format 'HH:mm:ss') + ' ' + $Text + "`r`n"), $script:Utf8)
    }
}

function Quote-Argument([string]$Value) {
    # CommandLineToArgvW quoting; also preserves Windows paths ending in '\'.
    $escaped = [regex]::Replace($Value, '(\\*)("|$)', {
        param($match)
        if ($match.Groups[2].Value -eq '"') {
            return $match.Groups[1].Value + $match.Groups[1].Value + '\"'
        }
        return $match.Groups[1].Value + $match.Groups[1].Value
    })
    return '"' + $escaped + '"'
}

function Invoke-Adb {
    param(
        [Parameter(Mandatory=$true)][string[]]$AdbArguments,
        [string]$OutputFile,
        [int]$TimeoutSeconds = 30,
        [switch]$AllowFailure,
        [switch]$NoDevice
    )
    $allArguments = @()
    if (-not $NoDevice) {
        if (-not $script:SelectedDevice) { throw 'Kein Geraet ausgewaehlt.' }
        $allArguments += @('-s', $script:SelectedDevice)
    }
    $allArguments += $AdbArguments
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $script:AdbExecutable
    $start.Arguments = (($allArguments | ForEach-Object { Quote-Argument $_ }) -join ' ')
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    $stream = $null
    $started = $false
    try {
        if ($OutputFile) {
            $stream = [System.IO.File]::Open($OutputFile, [System.IO.FileMode]::CreateNew,
                [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        } else {
            $stream = New-Object System.IO.MemoryStream
        }
        $started = $process.Start()
        if (-not $started) { throw 'ADB konnte nicht gestartet werden.' }
        # Binary pipe: PowerShell 5.1's native '>' redirection would corrupt boot.img.
        $copy = $process.StandardOutput.BaseStream.CopyToAsync($stream)
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill() } catch { }
            throw ('ADB-Zeitlimit (' + $TimeoutSeconds + ' Sekunden): ' + ($AdbArguments -join ' '))
        }
        if (-not $copy.Wait(10000) -or -not $stderr.Wait(10000)) {
            throw 'ADB-Datenuebertragung wurde nicht sauber beendet.'
        }
        [void]$copy.GetAwaiter().GetResult()
        $errorText = $stderr.GetAwaiter().GetResult()
        $stream.Flush()
        if ($process.ExitCode -ne 0 -and -not $AllowFailure) {
            throw ('ADB-Fehler, Exitcode ' + $process.ExitCode + ': ' + $errorText.Trim())
        }
        $bytes = $null
        if (-not $OutputFile) { $bytes = $stream.ToArray() }
        return [pscustomobject]@{ ExitCode = $process.ExitCode; Bytes = $bytes; ErrorText = $errorText }
    } finally {
        if ($started) {
            try { if (-not $process.HasExited) { $process.Kill() } } catch { }
        }
        if ($stream) { $stream.Dispose() }
        $process.Dispose()
    }
}

function Read-AdbText {
    param([string[]]$AdbArguments, [switch]$Optional, [switch]$NoDevice)
    $result = Invoke-Adb -AdbArguments $AdbArguments -AllowFailure:$Optional -NoDevice:$NoDevice
    if ($result.ExitCode -ne 0) { return '' }
    return [System.Text.Encoding]::UTF8.GetString($result.Bytes).Trim()
}

function Get-DeviceProperty([string]$Name) {
    return Read-AdbText -AdbArguments @('shell', 'getprop', $Name)
}

function Save-OptionalRead([string]$Name, [string[]]$Arguments) {
    $path = Join-Path $script:RunFolder $Name
    try {
        $result = Invoke-Adb -AdbArguments $Arguments -OutputFile $path -AllowFailure
        if ($result.ExitCode -ne 0 -or (Get-Item -LiteralPath $path).Length -eq 0) {
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
            return $false
        }
        return $true
    } catch {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        return $false
    }
}

function Find-Adb([string]$ExplicitPath) {
    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) { throw 'Der angegebene ADB-Pfad fehlt.' }
        return (Get-Item -LiteralPath $ExplicitPath).FullName
    }
    $package = Split-Path -Parent $PSScriptRoot
    $candidates = @(
        (Join-Path $package 'platform-tools\adb.exe'),
        (Join-Path $package 'adb.exe'),
        (Join-Path $PSScriptRoot 'adb.exe')
    )
    if ($env:LOCALAPPDATA) { $candidates += Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe' }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return (Get-Item -LiteralPath $candidate).FullName }
    }
    $command = Get-Command 'adb.exe' -CommandType Application -ErrorAction SilentlyContinue
    if (-not $command) { $command = Get-Command 'adb' -CommandType Application -ErrorAction SilentlyContinue }
    if ($command) { return $command.Source }
    throw "ADB fehlt. Entpacke Googles SDK Platform-Tools fuer Windows und lege den Ordner 'platform-tools' neben das Startskript."
}

function Confirm-BackupSource([string]$BootPath, [long]$BootSize) {
    # Wait only for the originally selected serial. Never switch phones after a disconnect.
    # wait-for-device excludes the 'recovery' state on some ADB versions.
    $wait = [System.Diagnostics.Stopwatch]::StartNew()
    $ready = $false
    do {
        try {
            $state = Invoke-Adb -AdbArguments @('get-state') -TimeoutSeconds 3 -AllowFailure
            if ($state.ExitCode -eq 0 -and [System.Text.Encoding]::UTF8.GetString($state.Bytes).Trim() -in @('device', 'recovery')) {
                $ready = $true; break
            }
        } catch { Write-BackupLog ('Warte auf urspruengliches Geraet: ' + $_.Exception.Message) }
        Start-Sleep -Milliseconds 500
    } while ($wait.Elapsed.TotalSeconds -lt 20)
    if (-not $ready) { throw 'Das urspruengliche A3 ist nach 20 Sekunden nicht wieder in ADB/TWRP erreichbar.' }
    if ((Read-AdbText @('shell', 'id', '-u')) -ne '0' -or
        -not (Get-DeviceProperty 'ro.twrp.version')) { throw 'TWRP-Root-Zugriff verloren.' }
    if ((Get-DeviceProperty 'ro.product.device') -ne $script:ExpectedDeviceCode) {
        throw 'Die Geraetekennung hat sich geaendert. Sicherung gestoppt.'
    }
    $target = Read-AdbText @('shell', 'readlink', '-f', $script:BootAlias)
    $size = Read-AdbText @('shell', 'blockdev', '--getsize64', $BootPath)
    if ($target -ne $BootPath -or $size -ne [string]$BootSize) {
        throw 'Die BOOT-Zuordnung oder Partitionsgroesse hat sich geaendert.'
    }
}

function Save-BootChunks([string]$BootPath, [long]$BootSize, [string]$Destination) {
    $chunkFile = $Destination + '.chunk.part'
    $destinationStream = $null
    try {
        $destinationStream = [System.IO.File]::Open($Destination, [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        for ([long]$offset = 0; $offset -lt $BootSize; $offset += 1MB) {
            $expected = [long][math]::Min(1MB, $BootSize - $offset)
            $skipBlocks = [long]($offset / 65536)
            $countBlocks = [int][math]::Ceiling($expected / 65536.0)
            $copied = $false
            for ($attempt = 1; $attempt -le 3; $attempt++) {
                try {
                    if ($attempt -gt 1) { Confirm-BackupSource $BootPath $BootSize }
                    # exec-out uses a raw stream: remote stderr is merged into stdout.
                    # Suppress dd's record counters ON THE PHONE, before transport.
                    # Never trim an oversized result: it may contain damaged data.
                    $command = 'dd if=' + $BootPath + ' bs=65536 skip=' + $skipBlocks +
                        ' count=' + $countBlocks + ' 2>/dev/null'
                    [void](Invoke-Adb -AdbArguments @('exec-out', $command) -OutputFile $chunkFile -TimeoutSeconds 120)
                    $actual = (Get-Item -LiteralPath $chunkFile).Length
                    if ($actual -ne $expected) {
                        throw ('Abschnitt bei Byte ' + $offset + ': erwartet ' + $expected +
                            ' Bytes, empfangen ' + $actual + ' Bytes.')
                    }
                    $copied = $true
                    break
                } catch {
                    $reason = $_.Exception.Message
                    Write-BackupLog ('Abschnitt ' + $offset + ', Versuch ' + $attempt + '/3: ' + $reason)
                    Remove-Item -LiteralPath $chunkFile -Force -ErrorAction SilentlyContinue
                    if ($attempt -eq 3) {
                        throw ('BOOT-Abschnitt konnte nach 3 Versuchen nicht gelesen werden. ' + $reason +
                            ' Die Ursache steht im SICHERUNG-PROTOKOLL.txt; ein Kabelfehler ist damit nicht festgestellt.')
                    }
                    Write-Host ('Abschnitt wird erneut gelesen (' + ($attempt + 1) + '/3): ' + $reason)
                }
            }
            if (-not $copied) { throw 'Interner Sicherungsfehler: kein vollstaendiger Abschnitt.' }
            $chunkStream = [System.IO.File]::OpenRead($chunkFile)
            try { $chunkStream.CopyTo($destinationStream) } finally { $chunkStream.Dispose() }
            Remove-Item -LiteralPath $chunkFile -Force
            Write-Host ('BOOT: ' + [math]::Round(($offset + $expected) / 1MB, 2) +
                ' / ' + [math]::Round($BootSize / 1MB, 2) + ' MiB')
        }
        $destinationStream.Flush()
    } finally {
        if ($destinationStream) { $destinationStream.Dispose() }
        Remove-Item -LiteralPath $chunkFile -Force -ErrorAction SilentlyContinue
    }
    if ((Get-Item -LiteralPath $Destination).Length -ne $BootSize) {
        throw 'Die zusammengefuegte BOOT-Datei hat eine unerwartete Groesse.'
    }
}

function Get-RemoteFileHash([string]$BootPath) {
    foreach ($tool in @('sha256sum', 'busybox sha256sum', 'toybox sha256sum')) {
        try {
            $result = Invoke-Adb -AdbArguments @('shell', ($tool + ' ' + $BootPath + ' 2>/dev/null')) -TimeoutSeconds 180 -AllowFailure
            $text = [System.Text.Encoding]::UTF8.GetString($result.Bytes).Trim()
            if ($result.ExitCode -eq 0 -and $text -match '^([a-fA-F0-9]{64})\s+(\S+)\s*$' -and
                $Matches[2] -eq $BootPath) {
                return $Matches[1].ToLowerInvariant()
            }
        } catch { Write-BackupLog ('Pruefsumme mit ' + $tool + ': ' + $_.Exception.Message) }
    }
    return $null
}

function Save-HardwareFirmware([string]$RelativePath) {
    $name = 'firmware/' + [System.IO.Path]::GetFileName($RelativePath)
    $destination = Join-Path $script:RunFolder $name
    $partName = $name + '.part'
    $secondName = $name + '.second.part'
    $part = Join-Path $script:RunFolder $partName
    $second = Join-Path $script:RunFolder $secondName
    foreach ($prefix in @('', '/system', '/system/system')) {
        $source = $prefix + '/vendor/' + $RelativePath
        $sizeText = Read-AdbText -AdbArguments @('shell', ('stat -c %s ' + $source + ' 2>/dev/null')) -Optional
        $size = [long]0
        if (-not [long]::TryParse($sizeText, [ref]$size) -or $size -le 0 -or $size -gt 64MB) { continue }
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                $remoteHash = Get-RemoteFileHash $source
                if (-not (Save-OptionalRead $partName @('exec-out', ('cat ' + $source + ' 2>/dev/null')))) { continue }
                if ((Get-Item -LiteralPath $part).Length -ne $size) { continue }
                $hash = (Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLowerInvariant()
                $integrity = 'device-sha256'
                if ($remoteHash) {
                    if ($hash -ne $remoteHash) { continue }
                } else {
                    if (-not (Save-OptionalRead $secondName @('exec-out', ('cat ' + $source + ' 2>/dev/null')))) { continue }
                    if ((Get-Item -LiteralPath $second).Length -ne $size -or
                        (Get-FileHash -LiteralPath $second -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) { continue }
                    $integrity = 'matching-independent-reads'
                }
                Move-Item -LiteralPath $part -Destination $destination
                return [ordered]@{ file = $name; source = $source; size = $size; sha256 = $hash; integrity = $integrity }
            } finally {
                Remove-Item -LiteralPath $part, $second -Force -ErrorAction SilentlyContinue
            }
        }
    }
    return [ordered]@{ file = $name; status = 'missing-or-unverified'; relative_source = $RelativePath }
}

function Save-VerifiedBoot([string]$BootPath, [long]$BootSize) {
    $part = Join-Path $script:RunFolder 'boot.img.part'
    $verification = Join-Path $script:RunFolder 'boot.verify.part'
    $bootFile = Join-Path $script:RunFolder 'boot.img'
    try {
        for ($pass = 1; $pass -le 2; $pass++) {
            Confirm-BackupSource $BootPath $BootSize
            Save-BootChunks $BootPath $BootSize $part
            Write-Host 'Pruefe Integritaet der BOOT-Sicherung ...'
            $localHash = (Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLowerInvariant()
            $remoteHash = Get-RemoteFileHash $BootPath
            $method = 'device-sha256'
            if (-not $remoteHash) {
                Write-Host 'TWRP bietet keine SHA-256-Pruefsumme. Vergleiche eine zweite vollstaendige Lesung ...'
                Confirm-BackupSource $BootPath $BootSize
                Save-BootChunks $BootPath $BootSize $verification
                $remoteHash = (Get-FileHash -LiteralPath $verification -Algorithm SHA256).Hash.ToLowerInvariant()
                $method = 'two-independent-reads-sha256'
                Remove-Item -LiteralPath $verification -Force
            }
            if ($localHash -eq $remoteHash) {
                Move-Item -LiteralPath $part -Destination $bootFile
                Write-BackupLog ('BOOT vollstaendig und geprueft: ' + $BootSize + ' Bytes; ' + $method + '; SHA-256 ' + $localHash)
                return [pscustomobject]@{ File = $bootFile; Method = $method; Sha256 = $localHash }
            }
            Write-BackupLog ('Pruefsummen stimmen nicht ueberein, Durchlauf ' + $pass + '/2. PC=' + $localHash + '; Vergleich=' + $remoteHash)
            Remove-Item -LiteralPath $part -Force
            if ($pass -eq 2) { throw 'BOOT-Pruefsummen stimmen auch nach erneuter Sicherung nicht ueberein. Keine gueltige Sicherung erstellt.' }
            Write-Host 'Pruefsummen stimmen nicht ueberein. Wiederhole die gesamte Sicherung einmal ...'
        }
    } finally {
        Remove-Item -LiteralPath $part, $verification -Force -ErrorAction SilentlyContinue
    }
}

function Main {
    Write-Host ''
    if ($BootCheck) {
        Write-Host 'GALAXY A3 SM-A320FL - BOOT-Vergleich mit Panicfix v0.7.1'
        Write-Host 'TWRP bleibt offen. Das PC-Programm liest BOOT und legt bei Bedarf ein Image in /tmp bereit.'
    } else {
        Write-Host 'GALAXY A3 (2017) - DIAGNOSE FUER WINDOWS v1.1'
        Write-Host 'Liest TWRP-Daten und sichert BOOT. Es wird nichts auf das Handy geschrieben.'
    }
    Write-Host ''
    $script:AdbExecutable = Find-Adb $AdbPath
    $deviceList = Read-AdbText -AdbArguments @('devices', '-l') -NoDevice
    $devices = @()
    foreach ($line in ($deviceList -split "`r?`n")) {
        if ($line -match '^([^\s]+)\s+(device|recovery|unauthorized|offline|sideload)(?:\s|$)') {
            $devices += [pscustomobject]@{ Serial = $Matches[1]; State = $Matches[2] }
        }
    }
    if ($devices.Count -eq 0) { throw 'Kein ADB-Geraet gefunden. A3 in TWRP starten, Datenkabel und Samsung-USB-Treiber pruefen.' }
    if ($devices.Count -ne 1) { throw 'Mehrere ADB-Geraete gefunden. Bitte nur das A3 angeschlossen lassen.' }
    if ($devices[0].State -notin @('device', 'recovery')) {
        throw ('ADB-Zustand: ' + $devices[0].State + '. Bitte TWRP normal starten; ADB-Sideload beenden.')
    }
    $script:SelectedDevice = $devices[0].Serial
    if ((Read-AdbText -AdbArguments @('shell', 'id', '-u')) -ne '0') {
        throw 'Kein TWRP-Root-Zugriff. Bitte TWRP manuell starten. Es wird kein Root installiert.'
    }
    $properties = [ordered]@{}
    foreach ($key in @('ro.product.device', 'ro.product.model', 'ro.build.product',
        'ro.board.platform', 'ro.product.cpu.abi', 'ro.bootloader', 'ro.twrp.version')) {
        $properties[$key] = Get-DeviceProperty $key
    }
    $codes = @('a3y17lte', 'a3y17ltexx', 'a3y17ltexc', 'a3y17ltelk')
    $reported = @($properties['ro.product.device'].ToLowerInvariant(), $properties['ro.build.product'].ToLowerInvariant())
    $matchesA3 = @($reported | Where-Object { $_ -in $codes }).Count -gt 0
    if (-not $matchesA3) { throw 'Dieses Geraet wird nicht eindeutig als a3y17lte erkannt. Abbruch.' }
    if (-not $properties['ro.twrp.version']) { throw 'TWRP nicht erkannt. Bitte TWRP manuell starten.' }

    if ($BootCheck) {
        . (Join-Path $PSScriptRoot 'A3-Bootvergleich.ps1')
        Invoke-A3BootCheck $properties
        return
    }

    if (-not $OutputDirectory) { $OutputDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) 'Ergebnisse' }
    [void][System.IO.Directory]::CreateDirectory($OutputDirectory)
    $runName = 'A3-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 6)
    $script:RunFolder = Join-Path $OutputDirectory $runName
    [void][System.IO.Directory]::CreateDirectory($script:RunFolder)
    Write-Utf8 (Join-Path $script:RunFolder 'device.json') ($properties | ConvertTo-Json -Depth 5)
    $script:ExpectedDeviceCode = $properties['ro.product.device']
    Write-BackupLog 'Windows-Diagnose v1.1: BOOT wird abschnittsweise gelesen und vor Freigabe geprueft.'
    Write-Host ('Erkannt: ' + $properties['ro.product.model'] + ' / ' + $properties['ro.product.device'])
    Write-Host 'Lese Hardwaredaten ...'
    $optional = [ordered]@{
        'live.dtb' = '/sys/firmware/fdt'; 'cmdline.txt' = '/proc/cmdline'
        'iomem.txt' = '/proc/iomem'; 'partitions.txt' = '/proc/partitions'
        'fb-size.txt' = '/sys/class/graphics/fb0/virtual_size'
        'fb-stride.txt' = '/sys/class/graphics/fb0/stride'
        'fb-bpp.txt' = '/sys/class/graphics/fb0/bits_per_pixel'
        'fb-modes.txt' = '/sys/class/graphics/fb0/modes'
        'dt-model.bin' = '/proc/device-tree/model'
        'dt-memory-lower.bin' = '/proc/device-tree/memory@40000000/reg'
        'dt-memory-upper.bin' = '/proc/device-tree/memory@80000000/reg'
        'dt-fb-handover.bin' = '/proc/device-tree/reserved-memory/bootloader_fb/reg'
        'dt-touch-compatible.bin' = '/proc/device-tree/i2c@13890000/touchscreen@50/compatible'
    }
    $missing = @()
    foreach ($entry in $optional.GetEnumerator()) {
        if (-not (Save-OptionalRead $entry.Key @('exec-out', ('cat ' + $entry.Value + ' 2>/dev/null')))) { $missing += $entry.Key }
    }
    [void](Save-OptionalRead 'dmesg.txt' @('exec-out', 'dmesg 2>/dev/null'))

    $listing = Read-AdbText -AdbArguments @('shell', 'find /dev/block -type d -name by-name 2>/dev/null')
    $directories = @($listing -split "`r?`n" | Where-Object { $_ -match '^/dev/block/[A-Za-z0-9_./-]+$' })
    $bootPath = $null
    $bootSize = [long]0
    foreach ($directory in $directories) {
        foreach ($name in @('BOOT', 'boot')) {
            $target = Read-AdbText -AdbArguments @('shell', 'readlink', '-f', ($directory + '/' + $name)) -Optional
            if ($target -notmatch '^/dev/block/(mmcblk\d+p\d+|sd[a-z]\d+)$') { continue }
            $lengthText = Read-AdbText -AdbArguments @('shell', 'blockdev', '--getsize64', $target) -Optional
            $length = [long]0
            if (-not [long]::TryParse($lengthText, [ref]$length)) { continue }
            if ($length -lt 1MB -or $length -gt 64MB) { continue }
            $bootPath = $target; $bootSize = $length; $script:BootAlias = $directory + '/' + $name; break
        }
        if ($bootPath) { break }
    }
    if (-not $bootPath) { throw 'BOOT wurde nicht eindeutig per by-name gefunden. Keine Sicherung angelegt.' }
    Write-Host ('Sichere BOOT (' + [math]::Round($bootSize / 1MB, 1) + ' MiB). Bitte USB verbunden lassen ...')
    $backup = Save-VerifiedBoot $bootPath $bootSize
    $bootFile = $backup.File
    $bootFormat = 'unknown'
    $bootBytes = [System.IO.File]::ReadAllBytes($bootFile)
    if ([System.Text.Encoding]::ASCII.GetString($bootBytes, 0, 8) -eq 'ANDROID!') {
        $bootFormat = 'android-boot'
        if ([BitConverter]::ToUInt32($bootBytes, 36) -eq 2048) { $bootFormat = 'android-samsung-legacy-2048' }
    }
    if ($bootFormat -ne 'android-samsung-legacy-2048') {
        Write-Host 'Hinweis: BOOT ist gesichert, sein Format muss manuell geprueft werden.'
    }
    if ($directories.Count -gt 0) {
        [void](Save-OptionalRead 'by-name.txt' @('shell', ('ls -l ' + ($directories -join ' '))))
    }
    if ($Hardware) {
        Confirm-BackupSource $bootPath $bootSize
        Write-Host 'Lese ausgewaehlte Hersteller-Firmware fuer Funk, Ton und Kamera ...'
        [void][System.IO.Directory]::CreateDirectory((Join-Path $script:RunFolder 'firmware'))
        $firmware = @()
        foreach ($relative in @('etc/firmware/nvm_tlv_tf_1.1.bin', 'etc/firmware/rampatch_tlv_tf_1.1.tlv',
            'firmware/qwlan30.bin', 'firmware/bdwlan30.bin', 'firmware/bdwlan32.bin', 'firmware/otp30.bin',
            'etc/Tfa9896.cnt', 'etc/mixer_paths.xml', 'etc/mixer_gains.xml', 'firmware/fimc_is_lib.bin',
            'firmware/setfile_imx219.bin', 'firmware/setfile_imx258.bin')) {
            $firmware += Save-HardwareFirmware $relative
        }
        Write-Utf8 (Join-Path $script:RunFolder 'hardware-firmware.json') (ConvertTo-Json -InputObject $firmware -Depth 6)
    }
    Write-Utf8 (Join-Path $script:RunFolder 'BITTE-LESEN.txt') "Private A3-Diagnose und BOOT-Sicherung. Nicht oeffentlich hochladen.`r`nDie Daten zeigen den TWRP-Zustand, nicht den S-Boot-Handoff. Keine Partition wurde beschrieben.`r`n"
    $hashes = [ordered]@{}
    foreach ($file in (Get-ChildItem -LiteralPath $script:RunFolder -Recurse -File | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($script:RunFolder.Length + 1).Replace('\', '/')
        $hashes[$relative] = [ordered]@{ size = $file.Length; sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
    $manifest = [ordered]@{
        format = 1; target = 'a3y17lte'; collector = 'windows-powershell-1.1'
        boot_partition = $bootPath; boot_format = $bootFormat; phone_writes = $false
        boot_integrity = $backup.Method
        hardware_firmware_requested = [bool]$Hardware
        observation = 'TWRP state, NOT S-Boot state'; missing_optional = $missing; files = $hashes
    }
    Write-Utf8 (Join-Path $script:RunFolder 'manifest.json') ($manifest | ConvertTo-Json -Depth 8)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = Join-Path $OutputDirectory ($runName + '.zip')
    [System.IO.Compression.ZipFile]::CreateFromDirectory($script:RunFolder, $archive,
        [System.IO.Compression.CompressionLevel]::Optimal, $false)
    # Keep every run separate, including the original BOOT backup.
    $niceArchive = Join-Path $script:RunFolder 'A3-Diagnose.zip'
    Move-Item -LiteralPath $archive -Destination $niceArchive
    Write-Host ''
    Write-Host 'FERTIG - keine Daten auf dem Handy veraendert.' -ForegroundColor Green
    Write-Host ('Bitte diese Datei im Chat schicken: ' + $niceArchive)
    Write-Host 'BOOT-Sicherung und Diagnose bitte privat aufbewahren.'
}

try {
    Main
    exit 0
} catch {
    Write-Host ''
    Write-Host ('ABBRUCH: ' + $_.Exception.Message) -ForegroundColor Red
    if ($script:RunFolder) {
        $details = $_.Exception.Message + "`r`n`r`n" + $_.InvocationInfo.PositionMessage + "`r`n" + $_.ScriptStackTrace
        Write-Utf8 (Join-Path $script:RunFolder 'FEHLER.txt') $details
        Write-BackupLog ('ABBRUCH: ' + $_.Exception.Message)
        Write-Host ('Bisherige PC-Dateien: ' + $script:RunFolder)
    }
    Write-Host 'Es wurde kein Flash-Befehl ausgefuehrt.'
    exit 1
}
