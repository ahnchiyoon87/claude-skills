# 로컬(Windows) 설치: ~/.claude/skills/<이름> 을 이 레포의 skills/<이름> 으로 하나씩 연결(Junction)한다.
# ~/.claude/skills 폴더 통째로 연결하지 않는다 — 데스크톱 앱이 쓰는 synced/ 와 npm 스킬(agent-browser)이 같이 있다.
# 같은 이름의 실제 폴더가 있으면 지우지 않고 ~/.claude/skills-backup/<시각>/ 으로 옮긴다.
# 다른 곳을 가리키는 링크가 있으면 건드리지 않고 알린다.
# ~/.claude/CLAUDE.md 에 이 레포 CLAUDE.md 를 불러오는 줄(@...)이 없으면 한 줄 추가한다.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$src = Join-Path $repo 'skills'
$dst = Join-Path $HOME '.claude\skills'
$backup = Join-Path $HOME (".claude\skills-backup\" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force $dst | Out-Null

foreach ($skill in Get-ChildItem $src -Directory) {
    $link = Join-Path $dst $skill.Name
    $item = Get-Item $link -Force -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType) {
        $target = @($item.Target)[0] -replace '^\\\\\?\\', ''
        if ((Resolve-Path $target -ErrorAction SilentlyContinue).Path -eq $skill.FullName) {
            Write-Output "그대로  $($skill.Name)"
        } else {
            Write-Output "건너뜀  $($skill.Name) — 다른 곳을 가리키는 링크($target)"
        }
        continue
    }
    if ($item) {
        New-Item -ItemType Directory -Force $backup | Out-Null
        Move-Item $link (Join-Path $backup $skill.Name)
        Write-Output "보관    $($skill.Name) → $backup"
    }
    New-Item -ItemType Junction -Path $link -Target $skill.FullName | Out-Null
    Write-Output "연결    $($skill.Name)"
}

# 레포에서 사라진 스킬을 가리키는 끊긴 링크를 알린다(지우지는 않는다)
foreach ($item in Get-ChildItem $dst -Force | Where-Object LinkType) {
    $target = @($item.Target)[0] -replace '^\\\\\?\\', ''
    if ($target.StartsWith($src, [StringComparison]::OrdinalIgnoreCase) -and -not (Test-Path $target)) {
        Write-Output "끊김    $($item.Name) → $target (레포에서 빠진 스킬. 직접 지우세요)"
    }
}

$claudeMd = Join-Path $HOME '.claude\CLAUDE.md'
$import = '@' + ((Join-Path $repo 'CLAUDE.md') -replace '\\', '/')
$current = if (Test-Path $claudeMd) { Get-Content $claudeMd -Encoding UTF8 } else { @() }
if ($current -notcontains $import) {
    Add-Content $claudeMd -Value $import -Encoding UTF8
    Write-Output "추가    ~/.claude/CLAUDE.md 에 $import"
} else {
    Write-Output "그대로  ~/.claude/CLAUDE.md 불러오기 줄"
}
