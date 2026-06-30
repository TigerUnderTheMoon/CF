$ErrorActionPreference = "Stop"

$root = "D:\CF"
$figDir = Join-Path $root "paper\kbs_submission\final_source\figures"
$vsdxPath = Join-Path $figDir "fig_overall_framework.vsdx"
$pdfPath = Join-Path $figDir "fig_overall_framework.pdf"

New-Item -ItemType Directory -Force -Path $figDir | Out-Null

$cm = 1.0 / 2.54
$pageWcm = 17.0
$pageHcm = 6.5
$pageWin = $pageWcm * $cm
$pageHin = $pageHcm * $cm

function Cm($v) {
    return $v / 2.54
}

function TopToVisioY($topCm) {
    return ($pageHcm - $topCm) / 2.54
}

function RectFromTop($page, [double]$xCm, [double]$yTopCm, [double]$wCm, [double]$hCm) {
    $l = Cm $xCm
    $r = Cm ($xCm + $wCm)
    $t = TopToVisioY $yTopCm
    $b = TopToVisioY ($yTopCm + $hCm)
    return $page.DrawRectangle($l, $b, $r, $t)
}

function OvalFromTop($page, [double]$xCm, [double]$yTopCm, [double]$wCm, [double]$hCm) {
    $l = Cm $xCm
    $r = Cm ($xCm + $wCm)
    $t = TopToVisioY $yTopCm
    $b = TopToVisioY ($yTopCm + $hCm)
    return $page.DrawOval($l, $b, $r, $t)
}

function LineFromTop($page, [double]$x1Cm, [double]$y1TopCm, [double]$x2Cm, [double]$y2TopCm) {
    return $page.DrawLine((Cm $x1Cm), (TopToVisioY $y1TopCm), (Cm $x2Cm), (TopToVisioY $y2TopCm))
}

function TextFromTop($page, [double]$xCm, [double]$yTopCm, [double]$wCm, [double]$hCm, [string]$text, [double]$sizePt, [bool]$bold = $false, [string]$align = "center") {
    $shape = RectFromTop $page $xCm $yTopCm $wCm $hCm
    $shape.Text = $text
    Set-NoLineFill $shape
    Set-TextStyle $shape $sizePt $bold $false $align
    return $shape
}

function Set-Cell($shape, [string]$cell, [string]$formula) {
    try {
        $shape.CellsU($cell).FormulaU = $formula
    } catch {
        # Keep construction robust across localized Visio builds.
    }
}

function Set-NoLineFill($shape) {
    Set-Cell $shape "LinePattern" "0"
    Set-Cell $shape "FillPattern" "0"
}

function Set-Line($shape, [string]$colorFormula, [string]$weightFormula, [int]$pattern = 1) {
    Set-Cell $shape "LineColor" $colorFormula
    Set-Cell $shape "LineWeight" $weightFormula
    Set-Cell $shape "LinePattern" "$pattern"
}

function Set-Fill($shape, [string]$colorFormula, [int]$pattern = 1) {
    Set-Cell $shape "FillForegnd" $colorFormula
    Set-Cell $shape "FillPattern" "$pattern"
}

function Set-TextStyle($shape, [double]$sizePt, [bool]$bold = $false, [bool]$italic = $false, [string]$align = "center") {
    Set-Cell $shape "Char.Font" "23"
    Set-Cell $shape "Char.Size" "$sizePt pt"
    $style = 0
    if ($bold) { $style += 17 }
    if ($italic) { $style += 2 }
    Set-Cell $shape "Char.Style" "$style"
    Set-Cell $shape "Para.HorzAlign" $(if ($align -eq "left") { "0" } elseif ($align -eq "right") { "2" } else { "1" })
    Set-Cell $shape "VerticalAlign" "1"
    Set-Cell $shape "TextBkgnd" "0"
    Set-Cell $shape "TxtPinX" "Width*0.5"
    Set-Cell $shape "TxtPinY" "Height*0.5"
    Set-Cell $shape "LeftMargin" "0.01 in"
    Set-Cell $shape "RightMargin" "0.01 in"
    Set-Cell $shape "TopMargin" "0.005 in"
    Set-Cell $shape "BottomMargin" "0.005 in"
}

function Style-Module($shape) {
    Set-Fill $shape "RGB(248,248,248)" 1
    Set-Line $shape "RGB(90,90,90)" "0.75 pt" 1
    Set-Cell $shape "Rounding" "6 pt"
}

function Add-LayerShape($layer, $shape) {
    try {
        $layer.Add($shape, 0) | Out-Null
    } catch {
    }
}

function Add-Arrow($page, $fromShape, $toShape, [string]$label, [double]$labelXcm, [double]$labelYcm, [bool]$thin = $false) {
    $conn = $page.Drop($script:visio.ConnectorToolDataObject, 0, 0)
    Set-Cell $conn "BeginX" "0"
    try { $conn.CellsU("BeginX").GlueTo($fromShape.CellsU("PinX")) } catch {}
    try { $conn.CellsU("EndX").GlueTo($toShape.CellsU("PinX")) } catch {}
    Set-Cell $conn "EndArrow" "4"
    Set-Line $conn "RGB(95,95,95)" $(if ($thin) { "0.5 pt" } else { "1.2 pt" }) 1
    Add-LayerShape $script:connectorsLayer $conn
    $txt = TextFromTop $page ($labelXcm - 0.48) $labelYcm 0.96 0.18 $label 5.6 $false "center"
    Add-LayerShape $script:connectorsLayer $txt
    return $conn
}

$script:visio = New-Object -ComObject Visio.Application
$script:visio.Visible = $false
$script:visio.AlertResponse = 7

try {
    $doc = $script:visio.Documents.Add("")
    $page = $script:visio.ActivePage
    $page.Name = "Figure 1"

    Set-Cell $page.PageSheet "PageWidth" "$pageWin in"
    Set-Cell $page.PageSheet "PageHeight" "$pageHin in"
    Set-Cell $page.PageSheet "DrawingScale" "1 in"
    Set-Cell $page.PageSheet "PageScale" "1 in"
    Set-Cell $page.PageSheet "DrawingResizeType" "0"

    $script:backgroundLayer = $page.Layers.Add("Background")
    $script:modulesLayer = $page.Layers.Add("Modules")
    $script:connectorsLayer = $page.Layers.Add("Connectors")

    $title = TextFromTop $page 0.60 0.14 15.80 0.36 "SC-FMA: Structurally-Calibrated Functional Attribution for Audit Prioritization" 7.8 $true "center"
    Add-LayerShape $script:modulesLayer $title

    $modules = @(
        @{Name="Observable audit object"; X=0.45; Y=1.15; W=2.55; H=4.35},
        @{Name="Audit graph representation"; X=3.25; Y=1.15; W=2.35; H=4.35},
        @{Name="Structural diagnostics"; X=5.85; Y=1.15; W=2.35; H=4.35},
        @{Name="SCU calibration"; X=8.45; Y=1.15; W=5.10; H=4.35},
        @{Name="Audit readout"; X=13.80; Y=1.15; W=2.75; H=4.35}
    )

    $box = @{}
    foreach ($m in $modules) {
        $s = RectFromTop $page $m.X $m.Y $m.W $m.H
        Style-Module $s
        Add-LayerShape $script:modulesLayer $s
        $box[$m.Name] = $s
        $hline = LineFromTop $page $m.X ($m.Y + 0.50) ($m.X + $m.W) ($m.Y + 0.50)
        Set-Line $hline "RGB(180,180,180)" "0.5 pt" 1
        Add-LayerShape $script:modulesLayer $hline
        $displayName = $m.Name
        if ($m.Name -eq "Observable audit object") { $displayName = "Observable`naudit object" }
        if ($m.Name -eq "Audit graph representation") { $displayName = "Audit graph`nrepresentation" }
        if ($m.Name -eq "Structural diagnostics") { $displayName = "Structural`ndiagnostics" }
        if ($m.Name -eq "SCU calibration") { $displayName = "SCU calibration" }
        if ($m.Name -eq "Audit readout") { $displayName = "Audit readout" }
        $mt = TextFromTop $page ($m.X + 0.08) ($m.Y + 0.07) ($m.W - 0.16) 0.36 $displayName 6.6 $true "center"
        Add-LayerShape $script:modulesLayer $mt
    }

    # Module 1: observable audit object.
    TextFromTop $page 0.62 1.73 2.20 0.18 "trace T=(s1,...,sk)" 5.8 $false "center" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
    $rows1 = @(
        @("s1", "retrieve"),
        @("s2", "rel. check"),
        @("s3", "constraint"),
        @("...", "final check")
    )
    $rowY = 2.06
    for ($i=0; $i -lt $rows1.Count; $i++) {
        $y = $rowY + $i * 0.43
        $r = RectFromTop $page 0.68 $y 2.08 0.28
        Set-Fill $r $(if ($i % 2 -eq 0) { "RGB(247,247,247)" } else { "RGB(255,255,255)" }) 1
        Set-Line $r "RGB(190,190,190)" "0.5 pt" 1
        Add-LayerShape $script:modulesLayer $r
        TextFromTop $page 0.76 ($y + 0.055) 0.28 0.16 $rows1[$i][0] 5.8 $true "left" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
        TextFromTop $page 1.10 ($y + 0.055) 1.48 0.16 $rows1[$i][1] 5.8 $false "left" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
    }
    TextFromTop $page 0.75 4.35 1.90 0.34 "fidelity / utility`nanchor u" 5.8 $false "center" | ForEach-Object { Add-LayerShape $script:connectorsLayer $_ }

    # Module 2: graph DAG.
    TextFromTop $page 3.82 1.72 1.15 0.20 "G=(V,E)" 6.2 $true "center" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
    $nodes = @{
        s1 = @{X=3.55; Y=3.15}
        s2 = @{X=4.08; Y=2.47}
        s3 = @{X=4.78; Y=2.12}
        s4 = @{X=4.44; Y=3.30}
        s5 = @{X=5.05; Y=2.85}
    }
    $nodeShapes = @{}
    foreach ($k in @("s1","s2","s3","s4","s5")) {
        $n = $nodes[$k]
        $o = OvalFromTop $page $n.X $n.Y 0.25 0.25
        Set-Fill $o "RGB(255,255,255)" 1
        Set-Line $o "RGB(70,70,70)" "0.75 pt" 1
        $o.Text = $k
        Set-TextStyle $o 5.5 $true $false "center"
        Add-LayerShape $script:modulesLayer $o
        $nodeShapes[$k] = $o
    }
    $graphEdges = @(
        @("s1","s2",1),
        @("s2","s3",1),
        @("s2","s4",1),
        @("s3","s5",1),
        @("s4","s5",1),
        @("s1","s4",2)
    )
    foreach ($e in $graphEdges) {
        $src = $nodeShapes[$e[0]]
        $dst = $nodeShapes[$e[1]]
        $c = $page.Drop($script:visio.ConnectorToolDataObject, 0, 0)
        try { $c.CellsU("BeginX").GlueTo($src.CellsU("PinX")) } catch {}
        try { $c.CellsU("EndX").GlueTo($dst.CellsU("PinX")) } catch {}
        Set-Cell $c "EndArrow" "4"
        Set-Line $c "RGB(110,110,110)" "0.5 pt" $e[2]
        Add-LayerShape $script:connectorsLayer $c
    }
    TextFromTop $page 3.60 4.60 1.64 0.32 "steps as nodes;`nrelations as edges" 5.5 $false "center" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }

    # Module 3: diagnostics table.
    $diagRows = @(
        @("necessity n", "graph exposure"),
        @("redun. R", "overlap"),
        @("bottleneck b", "dependency")
    )
    for ($i=0; $i -lt $diagRows.Count; $i++) {
        $y = 2.12 + $i * 0.72
        $r = RectFromTop $page 5.98 $y 2.06 0.42
        Set-Fill $r $(if ($i % 2 -eq 0) { "RGB(247,247,247)" } else { "RGB(255,255,255)" }) 1
        Set-Line $r "RGB(190,190,190)" "0.5 pt" 1
        Add-LayerShape $script:modulesLayer $r
        TextFromTop $page 6.04 ($y + 0.08) 0.94 0.14 $diagRows[$i][0] 4.8 $true "left" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
        TextFromTop $page 7.04 ($y + 0.08) 0.86 0.14 $diagRows[$i][1] 4.8 $false "left" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
    }

    # Module 4: SCU calibration.
    TextFromTop $page 10.08 1.73 1.85 0.22 "SCU objective" 6.8 $true "center" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
    $eqText = "min_w L(w) = fidelity + necessity`n+ redundancy penalty + bottleneck barrier`nsubject to sum_i w_i = 1, w_i >= 0"
    $eq = RectFromTop $page 8.90 2.22 4.20 1.26
    $eq.Text = $eqText
    Set-Fill $eq "RGB(255,255,255)" 1
    Set-Line $eq "RGB(160,160,160)" "0.5 pt" 1
    Set-TextStyle $eq 6.0 $false $false "center"
    Add-LayerShape $script:modulesLayer $eq
    TextFromTop $page 9.04 3.92 3.90 0.34 "signal preservation with`nstructural decomposition" 5.9 $false "center" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }

    # Module 5: readout.
    TextFromTop $page 14.25 1.72 1.86 0.22 "top-k review queue" 6.0 $true "center" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
    $queueRows = @(
        @("rank 1", "s3"),
        @("rank 2", "s1"),
        @("rank 3", "s5")
    )
    for ($i=0; $i -lt $queueRows.Count; $i++) {
        $y = 2.12 + $i * 0.32
        TextFromTop $page 14.18 $y 0.82 0.16 $queueRows[$i][0] 5.8 $false "left" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
        TextFromTop $page 15.35 $y 0.35 0.16 $queueRows[$i][1] 5.8 $true "right" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
    }
    $sep = LineFromTop $page 14.06 3.20 16.32 3.20
    Set-Line $sep "RGB(185,185,185)" "0.5 pt" 1
    Add-LayerShape $script:modulesLayer $sep
    TextFromTop $page 14.40 3.26 1.50 0.20 "Audit Card" 6.0 $true "center" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
    $cardRows = @(
        @("fidelity", "high"),
        @("necessity", "high"),
        @("redun.", "low"),
        @("bottleneck", "yes"),
        @("action", "inspect")
    )
    for ($i=0; $i -lt $cardRows.Count; $i++) {
        $y = 3.55 + $i * 0.25
        TextFromTop $page 14.05 $y 1.06 0.15 $cardRows[$i][0] 4.9 $false "left" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
        TextFromTop $page 15.12 $y 1.04 0.15 $cardRows[$i][1] 4.9 $true "right" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }
    }
    TextFromTop $page 14.32 5.03 1.70 0.18 "fixed review budget" 5.4 $false "center" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }

    # External connectors. These are dynamic connectors glued to module boundaries.
    Add-Arrow $page $box["Observable audit object"] $box["Audit graph representation"] "graph" 3.12 0.77 $false | Out-Null
    Add-Arrow $page $box["Audit graph representation"] $box["Structural diagnostics"] "diagnostics" 5.70 0.77 $false | Out-Null
    Add-Arrow $page $box["Structural diagnostics"] $box["SCU calibration"] "structural" 8.32 0.77 $false | Out-Null
    Add-Arrow $page $box["Observable audit object"] $box["SCU calibration"] "fidelity anchor" 5.00 5.67 $true | Out-Null
    Add-Arrow $page $box["SCU calibration"] $box["Audit readout"] "ranking" 13.68 0.77 $false | Out-Null

    # Semantic legend.
    $legend = RectFromTop $page 12.65 5.72 3.90 0.48
    Set-Fill $legend "RGB(255,255,255)" 1
    Set-Line $legend "RGB(200,200,200)" "0.5 pt" 1
    Add-LayerShape $script:modulesLayer $legend
    TextFromTop $page 12.80 5.79 3.55 0.28 "solid = flow   dashed = semantic   thin = input" 5.4 $false "left" | ForEach-Object { Add-LayerShape $script:modulesLayer $_ }

    # Basic page-wide quality adjustments.
    foreach ($shape in $page.Shapes) {
        try {
            Set-Cell $shape "LockTextEdit" "0"
            Set-Cell $shape "LockMoveX" "0"
            Set-Cell $shape "LockMoveY" "0"
        } catch {}
    }

    if (Test-Path -LiteralPath $vsdxPath) { Remove-Item -LiteralPath $vsdxPath -Force }
    if (Test-Path -LiteralPath $pdfPath) { Remove-Item -LiteralPath $pdfPath -Force }
    $doc.SaveAs($vsdxPath)
    try {
        $doc.ExportAsFixedFormat(1, $pdfPath, 1, 0)
    } catch {
        $page.Export($pdfPath)
    }
    $doc.Close()
    Write-Output "created: $vsdxPath"
    Write-Output "created: $pdfPath"
} finally {
    try { $script:visio.Quit() } catch {}
}
