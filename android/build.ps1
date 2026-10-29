param(
    [string[]]$Tasks = @('assembleDebug', 'lintDebug', 'testDebugUnitTest')
)

# Keep the caller's working directory; project files and writable caches belong here.
$env:GRADLE_USER_HOME = Join-Path $PSScriptRoot '.gradle-work'
& (Join-Path $PSScriptRoot 'gradlew.bat') -p $PSScriptRoot @Tasks
$buildExitCode = $LASTEXITCODE

# Clean obsolete APKs only after all requested tasks succeed.
if ($buildExitCode -eq 0) {
    $apkRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'app/build/outputs/apk'))
    if (Test-Path -LiteralPath $apkRoot) {
        $apks = @(Get-ChildItem -LiteralPath $apkRoot -Filter '*.apk' -File -Recurse |
            Sort-Object LastWriteTimeUtc -Descending)
        foreach ($apk in ($apks | Select-Object -Skip 1)) {
            $resolvedApk = [IO.Path]::GetFullPath($apk.FullName)
            if (-not $resolvedApk.StartsWith($apkRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'APK cleanup target is outside the build output directory.'
            }
            Remove-Item -LiteralPath $resolvedApk
        }
    }
}
exit $buildExitCode
