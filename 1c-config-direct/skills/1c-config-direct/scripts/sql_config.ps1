# Sync the rows of a 1C configuration table (Config by default) from MS SQL into a cache folder: one file per FileName,
# parts (PartNo) concatenated. Incremental: only files whose Modified / size / part count changed are fetched again.
# Windows authentication only; the database is only read (SELECT). Prints one summary line.
param(
	[string]$Server = '.',
	[Parameter(Mandatory = $true)][string]$Base,
	[Parameter(Mandatory = $true)][string]$Out,
	[string]$Table = 'Config',
	[switch]$Full
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
if ($Table -notmatch '^[A-Za-z_]+$') { throw "bad table name: $Table" }
$sw = [Diagnostics.Stopwatch]::StartNew()
New-Item -ItemType Directory -Force $Out | Out-Null
$manifestPath = Join-Path $Out '_manifest.tsv'

$cn = New-Object System.Data.SqlClient.SqlConnection ("Server={0};Database={1};Integrated Security=SSPI;Application Name=1c-config-direct" -f $Server, $Base)
$cn.Open()
try {
	$cmd = $cn.CreateCommand()
	$cmd.CommandTimeout = 600
	$cmd.CommandText = "SELECT FileName, ISNULL(CONVERT(varchar(33), MAX(Modified), 126), ''), ISNULL(SUM(CAST(DATALENGTH(BinaryData) AS bigint)), 0), COUNT(*) FROM [$Table] GROUP BY FileName"
	$now = @{}
	$r = $cmd.ExecuteReader()
	while ($r.Read()) { $now[$r.GetString(0)] = '{0}|{1}|{2}' -f $r.GetString(1), $r.GetInt64(2), $r.GetInt32(3) }
	$r.Close()

	$old = @{}
	if (-not $Full -and (Test-Path $manifestPath)) {
		foreach ($line in [IO.File]::ReadAllLines($manifestPath)) {
			$p = $line.Split("`t")
			if ($p.Count -eq 2) { $old[$p[0]] = $p[1] }
		}
	}
	$changed = New-Object System.Collections.Generic.HashSet[string]
	foreach ($k in $now.Keys) {
		if ($old[$k] -ne $now[$k] -or -not (Test-Path -LiteralPath (Join-Path $Out $k))) { [void]$changed.Add($k) }
	}
	$removed = 0
	foreach ($k in $old.Keys) {
		if (-not $now.ContainsKey($k)) {
			$f = Join-Path $Out $k
			if (Test-Path -LiteralPath $f) { Remove-Item -LiteralPath $f -Force }
			$removed++
		}
	}

	$fetched = 0L
	function Save-Rows($reader) {
		$cur = $null; $fs = $null
		while ($reader.Read()) {
			$name = $reader.GetString(0)
			if ($name -ne $cur) {
				if ($fs) { $fs.Close() }
				$fs = $null; $cur = $name
				if ($changed.Contains($name)) { $fs = [IO.File]::Create((Join-Path $Out $name)) }
			}
			if ($fs -and -not $reader.IsDBNull(2)) {
				$b = [byte[]]$reader.GetValue(2)
				$fs.Write($b, 0, $b.Length)
				$script:fetched += $b.Length
			}
		}
		if ($fs) { $fs.Close() }
		$reader.Close()
	}
	if ($changed.Count -gt 0) {
		if ($Full -or $changed.Count -gt 1500) {
			$cmd.CommandText = "SELECT FileName, PartNo, BinaryData FROM [$Table] ORDER BY FileName, PartNo"
			Save-Rows $cmd.ExecuteReader()
		} else {
			$names = @($changed)
			for ($i = 0; $i -lt $names.Count; $i += 200) {
				$chunk = $names[$i..([Math]::Min($i + 199, $names.Count - 1))]
				$c2 = $cn.CreateCommand()
				$c2.CommandTimeout = 600
				$ps = @()
				for ($j = 0; $j -lt $chunk.Count; $j++) {
					[void]$c2.Parameters.AddWithValue("@p$j", $chunk[$j])
					$ps += "@p$j"
				}
				$c2.CommandText = "SELECT FileName, PartNo, BinaryData FROM [$Table] WHERE FileName IN (" + ($ps -join ',') + ") ORDER BY FileName, PartNo"
				Save-Rows $c2.ExecuteReader()
			}
		}
	}
	$lines = New-Object System.Collections.Generic.List[string]
	foreach ($k in $now.Keys) { $lines.Add("$k`t$($now[$k])") }
	[IO.File]::WriteAllLines($manifestPath, $lines)

	# side facts for "info": rows of ConfigSave (saved but not applied to the database) and installed extensions
	$info = New-Object System.Collections.Generic.List[string]
	$cmd.CommandText = "SELECT CASE WHEN OBJECT_ID('ConfigSave') IS NULL THEN -1 ELSE (SELECT COUNT(*) FROM ConfigSave) END"
	$info.Add("configsave_rows`t" + $cmd.ExecuteScalar())
	$cmd.CommandText = "SELECT CASE WHEN OBJECT_ID('_ExtensionsInfo') IS NULL THEN 0 ELSE 1 END"
	if ($cmd.ExecuteScalar() -eq 1) {
		$cmd.CommandText = "SELECT _ExtName FROM _ExtensionsInfo ORDER BY _ExtensionOrder"
		$r = $cmd.ExecuteReader()
		while ($r.Read()) { $info.Add("extension`t" + $r.GetString(0)) }
		$r.Close()
	}
	[IO.File]::WriteAllLines((Join-Path $Out '_info.tsv'), [string[]]$info, (New-Object System.Text.UTF8Encoding($false)))
} finally {
	$cn.Close()
}
"{0}.{1}: {2} files, fetched {3} ({4:N1} MB), removed {5}, {6:N1}s" -f $Base, $Table, $now.Count, $changed.Count, ($fetched / 1MB), $removed, $sw.Elapsed.TotalSeconds
