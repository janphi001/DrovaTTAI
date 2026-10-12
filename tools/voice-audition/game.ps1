param([string]$Action = "launch")
$g = "D:\Games\Steam\steamapps\common\Drova - Forsaken Kin"
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public class GW {
 public delegate bool EnumProc(IntPtr h, IntPtr l);
 [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc p, IntPtr l);
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll")] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 public static IntPtr Find(uint pid) { IntPtr r = IntPtr.Zero; EnumWindows((h,x)=>{ uint p; GetWindowThreadProcessId(h,out p); if(p==pid){ var sb=new StringBuilder(64); GetWindowText(h,sb,64); if(sb.ToString()=="Drova") r=h; } return true;}, IntPtr.Zero); return r; }
}
"@
if ($Action -eq "launch") { Start-Process -FilePath "$g\Drova.exe" -WorkingDirectory $g; Start-Sleep 5 }
for ($i=0; $i -lt 60; $i++) { $p = Get-Process Drova -ErrorAction SilentlyContinue; if ($p) { $h = [GW]::Find([uint32]$p.Id); if ($h -ne [IntPtr]::Zero) { break } }; Start-Sleep 2 }
if ($h -ne [IntPtr]::Zero) { [GW]::ShowWindow($h, 9) | Out-Null; Start-Sleep 1; [GW]::SetForegroundWindow($h) | Out-Null; "focused $h" } else { "kein Fenster" }
