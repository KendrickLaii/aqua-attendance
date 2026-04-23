import wx
import wx.html2 as webview

class SimpleBrowser(wx.Frame):
    def __init__(self, *args, **kw):
        super(SimpleBrowser, self).__init__(*args, **kw, style=wx.FRAME_TOOL_WINDOW)

        self.initializeUI()

    def initializeUI(self):
        self.panel = wx.Panel(self)

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create the menu
        self.menu = wx.Menu()
        self.menu.Append(wx.ID_ANY, "Toggle Menu")

        # Create the web browser component
        self.browser = webview.WebView.New(self.panel)
        self.browser.LoadURL("http://198.13.43.246:9915") # Replace with your website URL

        main_sizer.Add(self.browser, 1, wx.EXPAND)

        self.panel.SetSizer(main_sizer)

        # Set size to fullscreen
        self.SetSize(wx.DisplaySize())

        # Center the frame
        self.Center()

        # Zoom out by default when the page loads
        self.browser.Bind(webview.EVT_WEBVIEW_LOADED, self.on_page_load)

    def on_page_load(self, event):
        # Run JavaScript to set the zoom level to 80% (zoomed out)
        self.browser.RunScript("document.getElementById('app').style.zoom = '100%'")

app = wx.App(False)
frame = SimpleBrowser(None, wx.ID_ANY, "Simple Browser")
frame.ShowFullScreen(True)
app.MainLoop()