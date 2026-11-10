using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

 
 
 
 
internal static class StudioShell
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            string file, arguments = "", directory = "";
            if (args.Length == 2 && args[0] == "url")
            {
                Uri url;
                if (!Uri.TryCreate(args[1], UriKind.Absolute, out url) ||
                    url.Scheme != Uri.UriSchemeHttp || url.Host != "127.0.0.1" ||
                    url.Port < 1024 || url.Port > 65535 || url.UserInfo.Length != 0 ||
                    args[1].IndexOfAny(new[] {'\r', '\n', '\0'}) >= 0)
                    throw new ArgumentException("Expected an HTTP editor URL on 127.0.0.1 with a non-system port.");
                file = url.AbsoluteUri;
            }
            else if (args.Length == 3 && args[0] == "rained")
            {
                file = ExistingFile(args[1]);
                if (!String.Equals(Path.GetExtension(file), ".exe", StringComparison.OrdinalIgnoreCase))
                    throw new ArgumentException("Expected the Rained executable.");
                arguments = QuoteArgument(ExistingFile(args[2]));
                directory = Path.GetDirectoryName(file);
            }
            else throw new ArgumentException("Usage: StudioShell.exe url <editor-url> | rained <exe> <room-file>");

            ExecuteFromDesktop(file, arguments, directory);
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine("Explorer launch failed: " + error.Message);
            return 1;
        }
    }

    private static string ExistingFile(string path)
    {
        if (String.IsNullOrEmpty(path) || !Path.IsPathRooted(path) ||
            path.IndexOfAny(new[] {'\r', '\n', '\0'}) >= 0)
            throw new ArgumentException("Expected an absolute file path.");
        string root = Path.GetPathRoot(path);
        if (root == "\\" || root == "/" || root.EndsWith(":"))
            throw new ArgumentException("Expected a fully qualified file path.");
        string full = Path.GetFullPath(path);
        if (!File.Exists(full)) throw new FileNotFoundException("The selected file was not found.", full);
        return full;
    }

     
    internal static string QuoteArgument(string value)
    {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char ch in value)
        {
            if (ch == '\\') { slashes++; continue; }
            if (ch == '\"') result.Append('\\', slashes * 2 + 1);
            else result.Append('\\', slashes);
            slashes = 0;
            result.Append(ch);
        }
        result.Append('\\', slashes * 2);
        return result.Append('"').ToString();
    }

    private static void ExecuteFromDesktop(string file, string arguments, string directory)
    {
        object windows = null, desktop = null, browserObject = null, viewObject = null;
        object folder = null, application = null;
        try
        {
            windows = Activator.CreateInstance(Type.GetTypeFromCLSID(
                new Guid("9BA05972-F6A8-11CF-A442-00A0C90A8F39"), true));
            object location = 0, root = 0;
            int desktopWindow;
            desktop = ((dynamic)windows).FindWindowSW(ref location, ref root, 8, out desktopWindow, 1);
            if (desktop == null) throw new InvalidOperationException("The Windows desktop is unavailable.");
            Guid service = new Guid("4C96BE40-915C-11CF-99D3-00AA004AE837");
            Guid browserId = typeof(IShellBrowser).GUID;
            Marshal.ThrowExceptionForHR(((IServiceProvider)desktop).QueryService(ref service, ref browserId, out browserObject));
            var browser = (IShellBrowser)browserObject;
            IntPtr window;
            Marshal.ThrowExceptionForHR(browser.GetWindow(out window));
            uint desktopPid;
            if (GetWindowThreadProcessId(window, out desktopPid) == 0)
                throw new InvalidOperationException("The desktop process could not be identified.");
            using (var process = Process.GetProcessById(checked((int)desktopPid)))
                if (!String.Equals(process.ProcessName, "explorer", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("The desktop is not hosted by Windows Explorer.");
            Marshal.ThrowExceptionForHR(browser.QueryActiveShellView(out viewObject));
            Guid dispatch = new Guid("00020400-0000-0000-C000-000000000046");
            Marshal.ThrowExceptionForHR(((IShellView)viewObject).GetItemObject(0, ref dispatch, out folder));
            application = ((dynamic)folder).Application;
            ((dynamic)application).ShellExecute(file, arguments, directory, "open", 1);
        }
        finally
        {
            foreach (object item in new[] { application, folder, viewObject, browserObject, desktop, windows })
                if (item != null && Marshal.IsComObject(item)) Marshal.ReleaseComObject(item);
        }
    }

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);

    [ComImport, Guid("6D5140C1-7436-11CE-8034-00AA006009FA"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IServiceProvider
    {
        [PreserveSig] int QueryService(ref Guid service, ref Guid iid, [MarshalAs(UnmanagedType.Interface)] out object result);
    }

    [ComImport, Guid("000214E2-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellBrowser
    {
        [PreserveSig] int GetWindow(out IntPtr window);
        void ContextSensitiveHelp();
        void InsertMenusSB();
        void SetMenuSB();
        void RemoveMenusSB();
        void SetStatusTextSB();
        void EnableModelessSB();
        void TranslateAcceleratorSB();
        void BrowseObject();
        void GetViewStateStream();
        void GetControlWindow();
        void SendControlMsg();
        [PreserveSig] int QueryActiveShellView([MarshalAs(UnmanagedType.Interface)] out object view);
    }

    [ComImport, Guid("000214E3-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IShellView
    {
        void GetWindow();
        void ContextSensitiveHelp();
        void TranslateAccelerator();
        void EnableModeless();
        void UIActivate();
        void Refresh();
        void CreateViewWindow();
        void DestroyViewWindow();
        void GetCurrentInfo();
        void AddPropertySheetPages();
        void SaveViewState();
        void SelectItem();
        [PreserveSig] int GetItemObject(uint item, ref Guid iid, [MarshalAs(UnmanagedType.Interface)] out object result);
    }
}
