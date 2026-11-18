# Called from A3-Diagnose.ps1 after it selects one rooted TWRP device.
function Get-InstalledA3BootHash([long]$ImageLength) {
    # Read only the image bytes. A raw 32 MiB partition has a device-specific tail.
    $command = @'
file=$(mktemp /tmp/a3-bootcheck.XXXXXX) || exit 1
trap 'rm -f "$file"' 0
trap 'exit 1' 1 2 15
boot=/dev/block/mmcblk0p10
n=IMAGE_LENGTH
head -c "$n" "$boot" > "$file" 2>/dev/null ||
    busybox head -c "$n" "$boot" > "$file" 2>/dev/null ||
    toybox head -c "$n" "$boot" > "$file" || exit 1
bytes=$(wc -c < "$file") || exit 1
[ "$bytes" -eq "$n" ] || { echo 'BOOT-Lesung unvollstaendig' >&2; exit 1; }
hash=$(sha256sum "$file" 2>/dev/null) ||
    hash=$(busybox sha256sum "$file" 2>/dev/null) ||
    hash=$(toybox sha256sum "$file") || exit 1
printf '%s\n' "${hash%% *}"
'@
    $command = $command.Replace('IMAGE_LENGTH', [string]$ImageLength).Replace([string][char]13, '')
    for ($attempt = 1; $attempt -le 2; $attempt++) {
        try {
            Confirm-BackupSource '/dev/block/mmcblk0p10' 33554432
            $r = Invoke-Adb -AdbArguments @('shell', $command) -TimeoutSeconds 120
            $hash = [System.Text.Encoding]::UTF8.GetString($r.Bytes).Trim()
            if ($hash -notmatch '^[0-9a-fA-F]{64}$') { throw 'TWRP lieferte keine gueltige SHA-256-Pruefsumme.' }
            return $hash.ToLowerInvariant()
        } catch {
            if ($attempt -eq 2) { throw }
            Write-Host ('Wiederhole die BOOT-Lesung: ' + $_.Exception.Message)
        }
    }
}

function Send-A3CheckedImage([string]$ImagePath, [string]$RemotePath, [string]$ExpectedHash) {
    if ((Get-RemoteFileHash $RemotePath) -eq $ExpectedHash) { return }
    $partial = '/tmp/.a3-push-' + [Guid]::NewGuid().ToString('N') + '.part'
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Confirm-BackupSource '/dev/block/mmcblk0p10' 33554432
            [void](Invoke-Adb -AdbArguments @('push', $ImagePath, $partial) -TimeoutSeconds 180)
            if ((Get-RemoteFileHash $partial) -ne $ExpectedHash) { throw 'Die uebertragene Datei hat keine passende SHA-256-Pruefsumme.' }
            [void](Invoke-Adb -AdbArguments @('shell', 'mv', '-f', $partial, $RemotePath))
            if ((Get-RemoteFileHash $RemotePath) -ne $ExpectedHash) { throw 'Das Image am TWRP-Auswahlpfad konnte nicht bestaetigt werden.' }
            return
        } catch {
            if ($attempt -eq 3) { throw }
            Write-Host ('Wiederhole die Uebertragung: ' + $_.Exception.Message)
        } finally {
            try { [void](Invoke-Adb -AdbArguments @('shell', 'rm', '-f', $partial) -TimeoutSeconds 5 -AllowFailure) } catch {}
        }
    }
}

function Get-A3BootLabel([string]$Hash, [string]$FixedHash) {
    if ($Hash -eq $FixedHash) { return 'v0.7.1' }
    if ($Hash -eq 'a521de6192b4df7a75ab09d9c01b955eec059e0a6fa52b55a0274094dc3d8fa4') { return 'v0.7' }
    return 'anderes Image'
}

function Invoke-A3BootCheck($Properties) {
    if ($Properties['ro.bootloader'] -notmatch '^A320FL' -and $Properties['ro.product.model'] -ne 'SM-A320FL') {
        throw 'Dieses Paket ist fuer das SM-A320FL. Die Modellkennung in TWRP passt nicht.'
    }
    $script:ExpectedDeviceCode = $Properties['ro.product.device']
    foreach ($alias in '/dev/block/by-name/BOOT', '/dev/block/platform/13540000.dwmmc0/by-name/BOOT') {
        if ((Read-AdbText -AdbArguments @('shell', 'readlink', '-f', $alias) -Optional) -eq '/dev/block/mmcblk0p10') {
            $script:BootAlias = $alias
            break
        }
    }
    if (-not $script:BootAlias) { throw 'TWRP meldet keine passende BOOT-Zuordnung fuer das A320FL.' }

    $expected = 'f7a14c90c37bd1f97227110de19703bb3ef76782fc107f5ab6c29b3c3d729884'
    $name = 'A3-A320FL-XNU-Panicfix-v0.7.1.img'
    $image = Get-Item -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) $name)
    if ($image.Length -ne 27256848 -or (Get-FileHash -LiteralPath $image.FullName -Algorithm SHA256).Hash -ne $expected) {
        throw 'Die Image-Datei auf dem PC ist unvollstaendig oder falsch. Entpacke das BOOT-Check-ZIP erneut.'
    }
    $before = Get-InstalledA3BootHash $image.Length
    Write-Host ('VORHER: ' + (Get-A3BootLabel $before $expected) + '  SHA-256 ' + $before)
    if ($before -ne $expected) {
        $remote = '/tmp/A3-Panicfix-0.7.1-f7a14c90.img'
        Send-A3CheckedImage $image.FullName $remote $expected
        Write-Host ('Bereit in TWRP: ' + $remote)
        Write-Host 'In TWRP: Installieren > Image installieren > obige Datei > ausschliesslich Boot.'
        Write-Host 'Streiche zur Bestaetigung. Bleibe nach der Erfolgsmeldung in TWRP.'
        $reply = Read-Host 'Dann hier am PC Enter druecken. Mit Q beenden'
        if ($reply -eq 'Q') { Write-Host 'Beendet. Nachpruefung vor dem Neustart durch erneuten Start moeglich.'; return }
        $after = Get-InstalledA3BootHash $image.Length
        Write-Host ('NACHHER: ' + (Get-A3BootLabel $after $expected) + '  SHA-256 ' + $after)
        if ($after -ne $expected) { throw 'Auf BOOT steht weiterhin ein anderes Image. Bleibe in TWRP und schicke die Zeilen VORHER und NACHHER.' }
    }
    Write-Host 'BOOT BESTAETIGT: v0.7.1' -ForegroundColor Green
    Write-Host 'Jetzt in TWRP Neustart > System waehlen. Du kannst den Start ab TWRP filmen.'
}
