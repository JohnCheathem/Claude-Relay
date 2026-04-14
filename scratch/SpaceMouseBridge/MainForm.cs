using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading;
using System.Windows.Forms;
using HidSharp;

namespace SpaceMouseBridge
{
    // ── Settings ──────────────────────────────────────────────────────────────
    public class Settings
    {
        public double Deadzone       { get; set; } = 0.08;
        public double Sensitivity    { get; set; } = 1.0;
        public double CurveExponent  { get; set; } = 1.4;
        public bool   InvertX        { get; set; } = false;
        public bool   InvertY        { get; set; } = true;
        public int    PollHz         { get; set; } = 60;
        public string Button0        { get; set; } = "X";
        public string Button1        { get; set; } = "B";
    }

    // ── ViGEm virtual gamepad (P/Invoke to ViGEmClient.dll) ───────────────────
    // Users need ViGEmBus driver installed. We ship ViGEmClient.dll alongside the exe.
    static class ViGEm
    {
        const string DLL = "ViGEmClient.dll";

        [DllImport(DLL)] public static extern IntPtr vigem_alloc();
        [DllImport(DLL)] public static extern int    vigem_connect(IntPtr client);
        [DllImport(DLL)] public static extern void   vigem_free(IntPtr client);
        [DllImport(DLL)] public static extern void   vigem_disconnect(IntPtr client);
        [DllImport(DLL)] public static extern IntPtr vigem_target_x360_alloc();
        [DllImport(DLL)] public static extern int    vigem_target_add(IntPtr client, IntPtr target);
        [DllImport(DLL)] public static extern int    vigem_target_remove(IntPtr client, IntPtr target);
        [DllImport(DLL)] public static extern void   vigem_target_free(IntPtr target);
        [DllImport(DLL)] public static extern int    vigem_target_x360_update(IntPtr client, IntPtr target, XUSB_REPORT report);

        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct XUSB_REPORT
        {
            public ushort wButtons;
            public byte   bLeftTrigger;
            public byte   bRightTrigger;
            public short  sThumbLX;
            public short  sThumbLY;
            public short  sThumbRX;
            public short  sThumbRY;
        }

        public const ushort XUSB_GAMEPAD_A              = 0x1000;
        public const ushort XUSB_GAMEPAD_B              = 0x2000;
        public const ushort XUSB_GAMEPAD_X              = 0x4000;
        public const ushort XUSB_GAMEPAD_Y              = 0x8000;
        public const ushort XUSB_GAMEPAD_LEFT_SHOULDER  = 0x0100;
        public const ushort XUSB_GAMEPAD_RIGHT_SHOULDER = 0x0200;
        public const ushort XUSB_GAMEPAD_START          = 0x0010;
        public const ushort XUSB_GAMEPAD_BACK           = 0x0020;
        public const ushort XUSB_GAMEPAD_LEFT_THUMB     = 0x0040;
        public const ushort XUSB_GAMEPAD_RIGHT_THUMB    = 0x0080;

        public static readonly Dictionary<string, ushort> ButtonMap = new()
        {
            ["A"]     = XUSB_GAMEPAD_A,
            ["B"]     = XUSB_GAMEPAD_B,
            ["X"]     = XUSB_GAMEPAD_X,
            ["Y"]     = XUSB_GAMEPAD_Y,
            ["LB"]    = XUSB_GAMEPAD_LEFT_SHOULDER,
            ["RB"]    = XUSB_GAMEPAD_RIGHT_SHOULDER,
            ["START"] = XUSB_GAMEPAD_START,
            ["BACK"]  = XUSB_GAMEPAD_BACK,
            ["LS"]    = XUSB_GAMEPAD_LEFT_THUMB,
            ["RS"]    = XUSB_GAMEPAD_RIGHT_THUMB,
        };
    }

    // ── Signal processing ─────────────────────────────────────────────────────
    static class Signal
    {
        public static double Deadzone(double v, double dz)
        {
            if (Math.Abs(v) < dz) return 0.0;
            double s = v > 0 ? 1.0 : -1.0;
            return s * Math.Min((Math.Abs(v) - dz) / (1.0 - dz), 1.0);
        }
        public static double Curve(double v, double exp)
        {
            if (v == 0.0) return 0.0;
            double s = v > 0 ? 1.0 : -1.0;
            return s * Math.Pow(Math.Abs(v), exp);
        }
        public static double Process(double raw, Settings cfg, bool invert)
        {
            double v = Deadzone(raw, cfg.Deadzone);
            v = Curve(v, cfg.CurveExponent);
            v = v * cfg.Sensitivity;
            if (invert) v = -v;
            return Math.Max(-1.0, Math.Min(1.0, v));
        }
        public static short ToShort(double v) => (short)(v * 32767.0);
    }

    // ── Main Form ─────────────────────────────────────────────────────────────
    public class MainForm : Form
    {
        // colours
        static readonly Color BG       = Color.FromArgb(15,  15,  18);
        static readonly Color SURFACE  = Color.FromArgb(26,  26,  32);
        static readonly Color SURFACE2 = Color.FromArgb(34,  34,  42);
        static readonly Color BORDER   = Color.FromArgb(46,  46,  58);
        static readonly Color ACCENT   = Color.FromArgb(108, 99,  255);
        static readonly Color GREEN    = Color.FromArgb(61,  220, 132);
        static readonly Color RED      = Color.FromArgb(255, 79,  79);
        static readonly Color AMBER    = Color.FromArgb(255, 179, 71);
        static readonly Color TEXT     = Color.FromArgb(232, 232, 240);
        static readonly Color MUTED    = Color.FromArgb(120, 120, 160);

        static readonly string CFG_PATH = Path.Combine(
            AppDomain.CurrentDomain.BaseDirectory, "jak_spacemouse_settings.json");

        Settings cfg = new();

        // bridge state
        Thread?  bridgeThread;
        bool     bridgeRunning;
        IntPtr   vigem  = IntPtr.Zero;
        IntPtr   target = IntPtr.Zero;
        double   liveX, liveY;
        bool     liveB0, liveB1;

        // controls we need to update
        Label   statusDot = null!, statusLbl = null!;
        Button  runBtn    = null!;
        Panel   barX = null!, barY = null!;
        Label   valX = null!, valY = null!;
        Label   ind0 = null!, ind1 = null!;
        Label   installStatus = null!;
        TrackBar tbDead = null!, tbSens = null!, tbCurve = null!, tbPoll = null!;
        Label   lblDead = null!, lblSens = null!, lblCurve = null!, lblPoll = null!;
        CheckBox cbInvX = null!, cbInvY = null!;
        ComboBox ddBtn0 = null!, ddBtn1 = null!;

        public MainForm()
        {
            LoadSettings();
            BuildUI();
            _ = new System.Windows.Forms.Timer { Interval = 50, Enabled = true }
                .Tick += (s, e) => UpdateLiveDisplay();
        }

        // ── Settings I/O ─────────────────────────────────────────────────────
        void LoadSettings()
        {
            if (!File.Exists(CFG_PATH)) return;
            try { cfg = JsonSerializer.Deserialize<Settings>(File.ReadAllText(CFG_PATH)) ?? new(); }
            catch { }
        }
        void SaveSettings()
        {
            File.WriteAllText(CFG_PATH,
                JsonSerializer.Serialize(cfg, new JsonSerializerOptions { WriteIndented = true }));
        }

        // ── UI construction ───────────────────────────────────────────────────
        void BuildUI()
        {
            Text            = "SpaceMouse → OpenGOAL";
            Size            = new Size(500, 660);
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox     = false;
            BackColor       = BG;
            Font            = new Font("Segoe UI", 10f);

            var scroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true, BackColor = BG };
            Controls.Add(scroll);

            var body = new FlowLayoutPanel
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                FlowDirection = FlowDirection.TopDown,
                WrapContents = false,
                BackColor = BG,
                Padding = new Padding(0),
                Width = 480,
            };
            scroll.Controls.Add(body);

            // Header
            var hdr = MakePanel(SURFACE, 480, 60);
            hdr.Controls.Add(MakeLabel("SpaceMouse  →  OpenGOAL", TEXT, 14, bold: true,
                x: 0, y: 10, w: 480, center: true));
            hdr.Controls.Add(MakeLabel("Jak & Daxter movement bridge", MUTED, 9,
                x: 0, y: 36, w: 480, center: true));
            body.Controls.Add(hdr);

            // Section 1: install
            body.Controls.Add(SectionHeader("1  Packages"));
            var pkgPanel = MakePanel(BG, 480, 30);
            pkgPanel.Controls.Add(MakeLabel("pyspacemouse + vgamepad (auto-installed on first run)", MUTED, 9, x: 18, y: 8));
            body.Controls.Add(pkgPanel);
            installStatus = MakeLabel("", MUTED, 9, x: 18, y: 0, w: 444);
            var isWrap = MakePanel(BG, 480, 22);
            isWrap.Controls.Add(installStatus);
            body.Controls.Add(isWrap);

            // Section 2: settings
            body.Controls.Add(SectionHeader("2  Settings"));

            (tbDead,  lblDead)  = AddSlider(body, "Dead zone",    "Raise if Jak drifts at rest",      (int)(cfg.Deadzone*100),   5,  30, v => { cfg.Deadzone = v/100.0;       return $"{v/100.0:F2}"; });
            (tbSens,  lblSens)  = AddSlider(body, "Sensitivity",  "Overall speed multiplier",          (int)(cfg.Sensitivity*20), 6,  40, v => { cfg.Sensitivity = v/20.0;     return $"{v/20.0:F2}"; });
            (tbCurve, lblCurve) = AddSlider(body, "Curve",        "1.0=linear  2.0=precise  0.8=aggressive", (int)(cfg.CurveExponent*10), 5, 25, v => { cfg.CurveExponent = v/10.0; return $"{v/10.0:F1}"; });
            (tbPoll,  lblPoll)  = AddSlider(body, "Poll rate",    "Updates per second (30–120)",      cfg.PollHz,               30, 120, v => { cfg.PollHz = v;               return $"{v}"; });

            cbInvX = AddToggle(body, "Invert X  (left / right)", cfg.InvertX, v => cfg.InvertX = v);
            cbInvY = AddToggle(body, "Invert Y  (forward / back)", cfg.InvertY, v => cfg.InvertY = v);

            ddBtn0 = AddDropdown(body, "Left button  →",  cfg.Button0, v => cfg.Button0 = v);
            ddBtn1 = AddDropdown(body, "Right button →", cfg.Button1, v => cfg.Button1 = v);

            var saveRow = MakePanel(BG, 480, 40);
            saveRow.Controls.Add(MakeButton("Save settings", SURFACE2, 130, () => { SaveSettings(); Flash(installStatus, "Saved!", GREEN); }, x: 18, y: 6));
            saveRow.Controls.Add(MakeButton("Reset to defaults", SURFACE2, 150, ResetSettings, x: 158, y: 6));
            body.Controls.Add(saveRow);

            // Section 3: run
            body.Controls.Add(SectionHeader("3  Run"));

            runBtn = MakeButton("▶  Start bridge", ACCENT, 444, ToggleBridge, x: 18, y: 0);
            var runWrap = MakePanel(BG, 480, 38);
            runWrap.Controls.Add(runBtn);
            body.Controls.Add(runWrap);

            // Status bar
            var statusBar = MakePanel(SURFACE, 480, 38);
            statusDot = MakeLabel("●", MUTED, 13, x: 12, y: 10);
            statusLbl = MakeLabel("Stopped", MUTED, 10, x: 32, y: 12);
            statusBar.Controls.Add(statusDot);
            statusBar.Controls.Add(statusLbl);
            var sbWrap = MakePanel(BG, 480, 44);
            sbWrap.Padding = new Padding(18, 4, 18, 0);
            sbWrap.Controls.Add(statusBar);
            body.Controls.Add(sbWrap);

            // Axis bars
            var axisBox = MakePanel(SURFACE, 444, 66);
            axisBox.Padding = new Padding(10, 6, 10, 6);
            (barX, valX) = AddAxisRow(axisBox, "X axis", 0);
            (barY, valY) = AddAxisRow(axisBox, "Y axis", 28);
            var axWrap = MakePanel(BG, 480, 72);
            axWrap.Padding = new Padding(18, 0, 18, 0);
            axWrap.Controls.Add(axisBox);
            body.Controls.Add(axWrap);

            // Button indicators
            var indRow = MakePanel(BG, 480, 30);
            ind0 = MakeLabel("BTN 1: " + cfg.Button0, MUTED, 9, x: 18, y: 8);
            ind1 = MakeLabel("BTN 2: " + cfg.Button1, MUTED, 9, x: 120, y: 8);
            indRow.Controls.Add(ind0);
            indRow.Controls.Add(ind1);
            body.Controls.Add(indRow);

            body.Controls.Add(MakePanel(BG, 480, 20)); // bottom padding
        }

        // ── UI helpers ────────────────────────────────────────────────────────
        Panel MakePanel(Color bg, int w, int h)
        {
            return new Panel { BackColor = bg, Width = w, Height = h };
        }

        Label MakeLabel(string text, Color fg, float size, bool bold = false,
                        int x = 0, int y = 0, int w = 0, bool center = false)
        {
            var l = new Label
            {
                Text      = text,
                ForeColor = fg,
                Font      = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular),
                Location  = new Point(x, y),
                AutoSize  = w == 0,
                Width     = w > 0 ? w : 0,
                TextAlign = center ? ContentAlignment.MiddleCenter : ContentAlignment.TopLeft,
                BackColor = Color.Transparent,
            };
            return l;
        }

        Button MakeButton(string text, Color bg, int w, Action click,
                          int x = 18, int y = 6)
        {
            var b = new Button
            {
                Text      = text,
                BackColor = bg,
                ForeColor = TEXT,
                FlatStyle = FlatStyle.Flat,
                Width     = w,
                Height    = 32,
                Location  = new Point(x, y),
                Font      = new Font("Segoe UI", 10f),
                Cursor    = Cursors.Hand,
            };
            b.FlatAppearance.BorderSize = 0;
            b.Click += (s, e) => click();
            return b;
        }

        Panel SectionHeader(string title)
        {
            var p = MakePanel(BG, 480, 32);
            p.Controls.Add(MakeLabel(title.ToUpper(), ACCENT, 8, bold: true, x: 18, y: 10));
            var line = new Panel { BackColor = BORDER, Height = 1, Width = 300, Location = new Point(130, 16) };
            p.Controls.Add(line);
            return p;
        }

        (TrackBar tb, Label lbl) AddSlider(FlowLayoutPanel body, string label, string hint,
                                            int initVal, int min, int max,
                                            Func<int, string> onChange)
        {
            var p = MakePanel(BG, 480, 62);
            var lTop = MakeLabel(label, TEXT, 10, x: 18, y: 4);
            var lVal = MakeLabel(onChange(initVal), ACCENT, 10, x: 420, y: 4, w: 44);
            lVal.TextAlign = ContentAlignment.TopRight;
            var lHint = MakeLabel(hint, MUTED, 8, x: 18, y: 22);
            var tb = new TrackBar
            {
                Minimum   = min,
                Maximum   = max,
                Value     = Math.Clamp(initVal, min, max),
                Location  = new Point(14, 34),
                Width     = 452,
                Height    = 24,
                TickFrequency = (max - min) / 10,
                BackColor = BG,
            };
            tb.Scroll += (s, e) => lVal.Text = onChange(tb.Value);
            p.Controls.AddRange(new Control[] { lTop, lVal, lHint, tb });
            body.Controls.Add(p);
            return (tb, lVal);
        }

        CheckBox AddToggle(FlowLayoutPanel body, string label, bool initVal, Action<bool> onChange)
        {
            var p = MakePanel(BG, 480, 28);
            var cb = new CheckBox
            {
                Text      = label,
                Checked   = initVal,
                ForeColor = TEXT,
                BackColor = BG,
                Location  = new Point(18, 6),
                AutoSize  = true,
                Font      = new Font("Segoe UI", 10f),
            };
            cb.CheckedChanged += (s, e) => onChange(cb.Checked);
            p.Controls.Add(cb);
            body.Controls.Add(p);
            return cb;
        }

        ComboBox AddDropdown(FlowLayoutPanel body, string label, string initVal, Action<string> onChange)
        {
            var p = MakePanel(BG, 480, 32);
            p.Controls.Add(MakeLabel(label, TEXT, 10, x: 18, y: 8));
            var choices = new[] { "A","B","X","Y","LB","RB","START","BACK","LS","RS","none" };
            var dd = new ComboBox
            {
                Location     = new Point(160, 5),
                Width        = 90,
                DropDownStyle= ComboBoxStyle.DropDownList,
                BackColor    = SURFACE2,
                ForeColor    = TEXT,
                Font         = new Font("Segoe UI", 10f),
            };
            dd.Items.AddRange(choices);
            dd.SelectedItem = initVal;
            dd.SelectedIndexChanged += (s, e) => onChange((string)dd.SelectedItem!);
            p.Controls.Add(dd);
            body.Controls.Add(p);
            return dd;
        }

        (Panel bar, Label val) AddAxisRow(Panel parent, string label, int y)
        {
            parent.Controls.Add(MakeLabel(label, MUTED, 8, x: 0, y: y + 4));
            var trackBg = new Panel { BackColor = SURFACE2, Location = new Point(54, y + 6), Width = 320, Height = 8 };
            var bar = new Panel { BackColor = MUTED, Location = new Point(160, 0), Width = 0, Height = 8 };
            trackBg.Controls.Add(bar);
            parent.Controls.Add(trackBg);
            var lbl = MakeLabel("0.00", MUTED, 9, x: 380, y: y + 4, w: 44);
            lbl.TextAlign = ContentAlignment.TopRight;
            parent.Controls.Add(lbl);
            return (bar, lbl);
        }

        void Flash(Label l, string msg, Color fg)
        {
            l.Text = msg; l.ForeColor = fg;
            var t = new System.Windows.Forms.Timer { Interval = 2000 };
            t.Tick += (s, e) => { l.Text = ""; t.Stop(); t.Dispose(); };
            t.Start();
        }

        void ResetSettings()
        {
            if (MessageBox.Show("Reset all settings to defaults?", "Reset",
                    MessageBoxButtons.YesNo) != DialogResult.Yes) return;
            cfg = new Settings();
            SaveSettings();
            tbDead.Value  = (int)(cfg.Deadzone      * 100);
            tbSens.Value  = (int)(cfg.Sensitivity   * 20);
            tbCurve.Value = (int)(cfg.CurveExponent * 10);
            tbPoll.Value  = cfg.PollHz;
            cbInvX.Checked = cfg.InvertX;
            cbInvY.Checked = cfg.InvertY;
            ddBtn0.SelectedItem = cfg.Button0;
            ddBtn1.SelectedItem = cfg.Button1;
            lblDead.Text  = $"{cfg.Deadzone:F2}";
            lblSens.Text  = $"{cfg.Sensitivity:F2}";
            lblCurve.Text = $"{cfg.CurveExponent:F1}";
            lblPoll.Text  = $"{cfg.PollHz}";
        }

        // ── Live display ─────────────────────────────────────────────────────
        void UpdateLiveDisplay()
        {
            if (!bridgeRunning) return;
            double x = liveX, y = liveY;
            bool b0 = liveB0, b1 = liveB1;

            UpdateBar(barX, valX, x);
            UpdateBar(barY, valY, y);

            ind0.Text      = "BTN 1: " + cfg.Button0 + (b0 ? " ●" : "");
            ind0.ForeColor = b0 ? GREEN : MUTED;
            ind1.Text      = "BTN 2: " + cfg.Button1 + (b1 ? " ●" : "");
            ind1.ForeColor = b1 ? GREEN : MUTED;
        }

        void UpdateBar(Panel bar, Label lbl, double v)
        {
            int trackW = bar.Parent?.Width ?? 320;
            int centre = trackW / 2;
            int w = (int)(Math.Abs(v) * centre);
            int x = v >= 0 ? centre : centre - w;
            bar.Location = new Point(x, 0);
            bar.Width    = w;
            bar.BackColor = Math.Abs(v) > 0.01 ? ACCENT : MUTED;
            lbl.Text      = $"{v:+0.00;-0.00;0.00}";
            lbl.ForeColor = Math.Abs(v) > 0.01 ? ACCENT : MUTED;
        }

        // ── Bridge ───────────────────────────────────────────────────────────
        void ToggleBridge()
        {
            if (!bridgeRunning) StartBridge();
            else StopBridge();
        }

        void StartBridge()
        {
            bridgeRunning = true;
            runBtn.BackColor = RED;
            runBtn.Text      = "■  Stop bridge";
            SetStatus(AMBER, "Connecting…");

            bridgeThread = new Thread(BridgeLoop) { IsBackground = true };
            bridgeThread.Start();
        }

        void StopBridge()
        {
            bridgeRunning = false;
            runBtn.BackColor = ACCENT;
            runBtn.Text      = "▶  Start bridge";
            SetStatus(MUTED, "Stopped");
            liveX = liveY = 0;
            liveB0 = liveB1 = false;
            UpdateBar(barX, valX, 0);
            UpdateBar(barY, valY, 0);

            if (target != IntPtr.Zero && vigem != IntPtr.Zero)
                ViGEm.vigem_target_remove(vigem, target);
            if (target != IntPtr.Zero) ViGEm.vigem_target_free(target);
            if (vigem  != IntPtr.Zero) ViGEm.vigem_disconnect(vigem);
            if (vigem  != IntPtr.Zero) ViGEm.vigem_free(vigem);
            target = vigem = IntPtr.Zero;
        }

        void SetStatus(Color dot, string text) => Invoke(() => {
            statusDot.ForeColor = dot;
            statusLbl.Text      = text;
            statusLbl.ForeColor = dot;
        });

        void BridgeError(string msg)
        {
            Invoke(() => {
                StopBridge();
                MessageBox.Show(msg, "Bridge error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            });
        }

        void BridgeLoop()
        {
            // ── ViGEm setup ──────────────────────────────────────────────────
            try
            {
                vigem = ViGEm.vigem_alloc();
                if (vigem == IntPtr.Zero) throw new Exception("vigem_alloc failed");
                int r = ViGEm.vigem_connect(vigem);
                if (r != 0) throw new Exception(
                    $"vigem_connect failed ({r}).\nMake sure ViGEmBus driver is installed.\nDownload: https://github.com/nefarius/ViGEmBus/releases");
                target = ViGEm.vigem_target_x360_alloc();
                if (target == IntPtr.Zero) throw new Exception("vigem_target_x360_alloc failed");
                r = ViGEm.vigem_target_add(vigem, target);
                if (r != 0) throw new Exception($"vigem_target_add failed ({r})");
            }
            catch (DllNotFoundException)
            {
                BridgeError("ViGEmClient.dll not found.\n\nPlace ViGEmClient.dll next to this exe,\nthen install ViGEmBus from:\nhttps://github.com/nefarius/ViGEmBus/releases");
                return;
            }
            catch (Exception ex) { BridgeError(ex.Message); return; }

            // ── HID: find SpaceMouse ─────────────────────────────────────────
            HidDevice? spaceDevice = null;
            HidStream? spaceStream = null;
            try
            {
                // 3Dconnexion vendor IDs: 0x046D (Logitech era), 0x256F (newer)
                int[] vids = { 0x046D, 0x256F };
                foreach (var dev in DeviceList.Local.GetHidDevices())
                {
                    if (Array.IndexOf(vids, dev.VendorID) >= 0)
                    {
                        spaceDevice = dev;
                        break;
                    }
                }
                if (spaceDevice == null)
                    throw new Exception("SpaceMouse not found.\nMake sure it is plugged in.");

                if (!spaceDevice.TryOpen(out spaceStream))
                    throw new Exception("Could not open SpaceMouse.\nTry running as Administrator.");
                spaceStream.ReadTimeout = 100;
            }
            catch (Exception ex) { BridgeError(ex.Message); return; }

            SetStatus(GREEN, "Running — SpaceMouse active");
            Invoke(() => installStatus.Text = "");

            // ── Poll loop ────────────────────────────────────────────────────
            double rawX = 0, rawY = 0;
            bool[] prevBtns = { false, false };
            var sw = Stopwatch.StartNew();

            while (bridgeRunning)
            {
                long frameStart = sw.ElapsedMilliseconds;
                long frameMs    = 1000 / cfg.PollHz;

                try
                {
                    byte[] buf = new byte[7];
                    int read = spaceStream.Read(buf, 0, buf.Length);
                    if (read >= 7)
                    {
                        int id = buf[0];
                        if (id == 1) // translation report
                        {
                            // SpaceNavigator HID: pairs of signed 16-bit LE values
                            // channel 1: y-trans, x-trans, z-trans
                            double ytrans =  (short)(buf[1] | (buf[2] << 8)) / 350.0;
                            double xtrans =  (short)(buf[3] | (buf[4] << 8)) / 350.0;
                            rawX = Math.Max(-1.0, Math.Min(1.0, xtrans));
                            rawY = Math.Max(-1.0, Math.Min(1.0, ytrans));
                        }
                        else if (id == 3) // button report
                        {
                            prevBtns[0] = (buf[1] & 0x01) != 0;
                            prevBtns[1] = (buf[1] & 0x02) != 0;
                        }
                    }
                }
                catch (TimeoutException) { /* no data, fine */ }
                catch (Exception ex) { BridgeError($"Read error: {ex.Message}"); break; }

                double x = Signal.Process(rawX, cfg, cfg.InvertX);
                double y = Signal.Process(rawY, cfg, cfg.InvertY);

                liveX = x; liveY = y;
                liveB0 = prevBtns[0]; liveB1 = prevBtns[1];

                ushort btns = 0;
                if (prevBtns[0] && ViGEm.ButtonMap.TryGetValue(cfg.Button0, out var b0v)) btns |= b0v;
                if (prevBtns[1] && ViGEm.ButtonMap.TryGetValue(cfg.Button1, out var b1v)) btns |= b1v;

                var report = new ViGEm.XUSB_REPORT
                {
                    wButtons  = btns,
                    sThumbLX  = Signal.ToShort(x),
                    sThumbLY  = Signal.ToShort(-y),  // Y is inverted for XInput convention
                };
                ViGEm.vigem_target_x360_update(vigem, target, report);

                long elapsed = sw.ElapsedMilliseconds - frameStart;
                int sleep = (int)(frameMs - elapsed);
                if (sleep > 0) Thread.Sleep(sleep);
            }

            spaceStream?.Close();
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            bridgeRunning = false;
            base.OnFormClosing(e);
        }
    }
}
