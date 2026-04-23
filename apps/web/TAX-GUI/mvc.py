import wx
import wx.html2 as webview
import json
import requests
import tkinter as tk
from tkinter import messagebox
import os
import base64
import configparser
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import sys
import datetime

# Load environment variables from .env file
load_dotenv()


def resource_path(*path_parts):
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, *path_parts)


def image_to_data_uri(relative_path: str) -> str:
    absolute_path = resource_path(relative_path)
    try:
        with open(absolute_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("ascii")
            extension = os.path.splitext(relative_path)[1][1:] or "png"
            return f"data:image/{extension};base64,{encoded}"
    except FileNotFoundError:
        print(f"Asset not found: {absolute_path}")
        return ""


def image_to_file_url(relative_path: str) -> str:
    absolute_path = resource_path(relative_path)
    path_obj = Path(absolute_path)
    if path_obj.exists():
        return path_obj.as_uri()
    print(f"Asset not found: {absolute_path}")
    return ""


config = configparser.ConfigParser()
config_path = resource_path("config.ini")
read_files = config.read(config_path, encoding="utf-8")
if not read_files:
    messagebox.showerror("Configuration Error", f"Unable to load config.ini at {config_path}")
    raise SystemExit(1)


def require_option(section: str, option: str) -> None:
    if not config.has_option(section, option):
        messagebox.showerror(
            "Configuration Error",
            f"Missing '{option}' setting in section [{section}] of config.ini."
        )
        raise SystemExit(1)


for required_url in ("aqua_url", "token_verify_dev", "token_verify_prod", "aqua_prod"):
    require_option("urls", required_url)
require_option("settings", "viewmode")
require_option("settings", "prefer_env_urls")


def should_use_env_urls() -> bool:
    try:
        return config.getboolean("settings", "prefer_env_urls")
    except ValueError:
        messagebox.showerror(
            "Configuration Error",
            "Invalid boolean value for 'prefer_env_urls' in config.ini."
        )
        raise SystemExit(1)


def get_url(key: str, env_var: Optional[str] = None) -> str:
    if env_var and should_use_env_urls() and os.getenv(env_var):
        return os.getenv(env_var)
    return config.get("urls", key)


def get_viewmode() -> bool:
    env_value = os.getenv("VIEWMODE")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    try:
        return config.getboolean("settings", "viewmode")
    except ValueError:
        messagebox.showerror(
            "Configuration Error",
            "Invalid boolean value for 'viewmode' in config.ini."
        )
        raise SystemExit(1)


viewmode = get_viewmode()


BACKGROUND_IMAGE_URI = image_to_data_uri("bg-min.png") or image_to_file_url("bg-min.png")
LOGO_IMAGE_URI = image_to_data_uri("aqua_logo-min.png") or image_to_file_url("aqua_logo-min.png")

class SimpleBrowser(wx.Frame):
    def __init__(self, *args, **kw):
        super(SimpleBrowser, self).__init__(*args, **kw, style=wx.DEFAULT_FRAME_STYLE)

        # Set the initial size to 1280x580
        self.SetSize((1280, 680))
        self.create_menu_bar()  # Add menu bar
        self.initializeUI()

    def create_menu_bar(self):
        # Create menu bar
        menubar = wx.MenuBar()
        
        # Display menu
        display_menu = wx.Menu()
        self.fullscreen_item = display_menu.Append(wx.ID_ANY, 'Full Screen\tF11', 'Toggle fullscreen mode')
        display_menu.AppendSeparator()
        self.res_1440_item = display_menu.Append(wx.ID_ANY, '1440x1080', 'Set resolution to 1440x1080')
        self.res_1280_item = display_menu.Append(wx.ID_ANY, '1280x780', 'Set resolution to 1280x780')
        menubar.Append(display_menu, 'Display')
        
        # Tools menu
        tools_menu = wx.Menu()
        self.dev_tools_item = tools_menu.Append(wx.ID_ANY, 'Developer Tools\tF12', 'Open browser developer tools')
        self.console_log_item = tools_menu.Append(wx.ID_ANY, 'Show Console Log', 'Show JavaScript console output')
        self.inspect_element_item = tools_menu.Append(wx.ID_ANY, 'Inspect Element', 'Inspect page elements')
        menubar.Append(tools_menu, 'Tools')
        
        # Exit menu
        exit_menu = wx.Menu()
        self.exit_item = exit_menu.Append(wx.ID_EXIT, 'Exit\tCtrl+Q', 'Exit application')
        menubar.Append(exit_menu, 'Exit')
        
        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_fullscreen_button, self.fullscreen_item)
        self.Bind(wx.EVT_MENU, self.on_resolution_1440_1080_button, self.res_1440_item)
        self.Bind(wx.EVT_MENU, self.on_resolution_1280_780_button, self.res_1280_item)
        self.Bind(wx.EVT_MENU, self.on_dev_tools_button, self.dev_tools_item)
        self.Bind(wx.EVT_MENU, self.on_console_log_button, self.console_log_item)
        self.Bind(wx.EVT_MENU, self.on_inspect_element_button, self.inspect_element_item)
        self.Bind(wx.EVT_MENU, self.on_exit_button, self.exit_item)
        
        # Bind F12 key for developer tools
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        
        self.SetMenuBar(menubar)

    def initializeUI(self):
        # Create a top-level panel
        self.panel = wx.Panel(self)

        # Create a sizer for the main layout
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create the Windows Explorer-like taskbar
        self.taskbar = wx.Panel(self.panel)
        self.taskbar.SetBackgroundColour(wx.Colour(240, 240, 240))

        # Create the web browser component
        self.browser = webview.WebView.New(self.panel)

        # Bind the navigation event to handle custom scheme
        self.browser.Bind(webview.EVT_WEBVIEW_NAVIGATING, self.on_webview_navigating)
        self.browser.Bind(webview.EVT_WEBVIEW_LOADED, self.on_webview_loaded)
        self.browser.Bind(webview.EVT_WEBVIEW_ERROR, self.on_webview_error)
        self.browser.Bind(webview.EVT_WEBVIEW_NEWWINDOW, self.on_webview_new_window)
        
        # Enable remote debugging for WebView2 (if available)
        self.enable_remote_debugging()
        
        # Initialize console logging
        self.console_logs = []

        # Read data from JSON file
        log_path = resource_path('log.json')
        with open(log_path, encoding='utf-8') as json_file:
            data = json.load(json_file)
            html_content = self.generate_html(data)
            self.browser.SetPage(html_content, "")

        # Add the taskbar and the browser to the main sizer
        self.main_sizer.Add(self.taskbar, 0, wx.EXPAND)
        self.main_sizer.Add(self.browser, 1, wx.EXPAND)
        self.panel.SetSizer(self.main_sizer)

        # Center the frame on the screen
        self.Center()

    def generate_html(self, data):
        # Remove local image path logic and use external link for logo
        # bg_path and logo_path are not needed anymore
        
        # Check viewmode to determine if fields should be disabled and checkboxes checked
        disabled_attr = 'disabled' if viewmode else ''
        checked_attr = 'checked' if viewmode else ''
        dimmed_style = 'opacity: 0.6; cursor: not-allowed;' if viewmode else ''
        company_placeholder = "Demonstration" if viewmode else ""
        license_placeholder = "********************" if viewmode else ""
        
        background_uri = BACKGROUND_IMAGE_URI
        logo_uri = LOGO_IMAGE_URI

        html_content = f"""
        <html>
        <head>
            <style>
                 body {{
                     background: {f"url('{background_uri}') no-repeat center center fixed" if background_uri else "#0f1134"};
                     background-size: cover;
                 }}
            </style>
        </head>
        <body style="justify-content: center; font-family: sans-serif; padding:20px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="width: 60%; background:rgba(255,255,255,0.8); color:black;border: 1px solid #ccc; padding: 20px; border-radius:10px;height:60vh;overflow:auto">
        """
        
        # Add data items from JSON data
        for item in data["data"]:
            date = item["date"]
            content = item["content"]
            html_content += f"<b>Update: {date}</b>"
            html_content += f"<p>{content}</p>"

        html_content += f"""
                </div>
                <div style="width: 35%; text-align: center;">
                    <div>
                        <img style="width:120px;" src="{logo_uri if logo_uri else ''}" alt="AQUA logo"/>
                    </div>
                    <small style="color: white;display: none;">View Mode</small>
                    <h2 style="color: white;">AQUA</h2> 
                    <form>
                        <div style="margin-bottom: 10px;">
                            <label for="company-code" style="color: white;">Firm Code</label><br>
                            <input placeholder="{company_placeholder}" type="text" id="company-code" name="company-code" value="" style="width: 100%; padding: 8px; {dimmed_style}" {disabled_attr}>
                        </div>
                        <div style="margin-bottom: 10px;">
                            <label for="license-no" style="color: white;">License No.</label><br>
                            <input placeholder="{license_placeholder}" type="text" id="license-no" name="license-no" value="" style="width: 100%; padding: 8px; {dimmed_style}" {disabled_attr}>
                        </div>
                        <div style="margin-bottom: 20px;">
                            <input type="checkbox" id="guest-mode" name="guest-mode" {checked_attr}>
                            <label for="guest-mode" style="color: white;">Guest mode</label>
                        </div>
                        <div style="margin-bottom: 20px;">
                            <input type="checkbox" id="is-vip" name="is-vip" {checked_attr}>
                            <label for="is-vip" style="color: white;">VIP</label>
                        </div>
                        <button type="button" id="start-button" style="background:#160D47; color:#fff;padding:10px 20px; font-size:16px;width:100%">Start</button>
                    </form>
                    <div style="margin-top: 20px;">
                        <button type="button" style="padding:10px 20px; font-size:16px;">Exit</button>
                        <button type="button" style="padding:10px 20px; font-size:16px;">Licenses</button>
                        <button type="button" style="padding:10px 20px; font-size:16px;">Information</button>
                        <button type="button" style="padding:10px 20px; font-size:16px;">Help</button>
                    </div>
                    <div style="margin-top: 20px; text-align: right;">
                        <p>V1.0.0</p>
                    </div>
                </div>
            </div>
            <script type="text/javascript">
                document.getElementById('start-button').addEventListener('click', function() {{
                    var companyCode = document.getElementById('company-code').value;
                    var licenseNo = document.getElementById('license-no').value;
                    var guestMode = document.getElementById('guest-mode').checked;
                    var isVIP = document.getElementById('is-vip').checked;

                    var url = 'webview-link://start-button-clicked?company_code=' + encodeURIComponent(companyCode) + '&license_no=' + encodeURIComponent(licenseNo) + '&guest_mode=' + guestMode + '&is_vip=' + isVIP;
                    window.location.href = url;
                }});
            </script>
        </body>
        </html>
        """

        return html_content

    def on_webview_navigating(self, event):
        # Handle custom scheme navigation
        url = event.GetURL()
        if url.startswith("webview-link://"):
            # Handle console log messages
            if url.startswith("webview-link://console-log"):
                try:
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(url)
                    params = parse_qs(parsed.query)
                    level = params.get('level', ['LOG'])[0]
                    message = params.get('message', [''])[0]
                    self.log_to_console(level, message)
                except Exception as exc:
                    print(f"Failed to parse console log: {exc}")
                event.Veto()
                return
            self.handle_custom_scheme(url)
            event.Veto()  # Prevent the default navigation
        # Don't reset state during normal navigation - this causes connection aborts
        # Only reset when explicitly needed (e.g., on initial load or custom scheme)

    def on_webview_error(self, event):
        """Handle WebView errors - silently bypass all errors"""
        # Silently bypass all errors to avoid interrupting navigation
        event.Skip()
    
    def on_webview_loaded(self, event):
        """Handle page load - no special handling"""
        event.Skip()

    def on_webview_new_window(self, event):
        """Open target=_blank links in a new window."""
        url = event.GetURL()
        target = event.GetTarget()
        log_action(f"New window requested (target={target}): {url}")
        new_frame = ExternalBrowserWindow(title="AQUA", initial_url=url)
        if hasattr(event, "SetWebView"):
            event.SetWebView(new_frame.browser)
        else:
            log_action("WebViewEvent.SetWebView not available; using standalone window.")
            if hasattr(event, "Veto"):
                event.Veto()
            else:
                event.Skip()
        new_frame.Show()

    def handle_custom_scheme(self, request):
        # Free access version
        # Don't reset state here - it can cause connection aborts
        # Only reset when absolutely necessary (e.g., logout, clear cache)
        aqua_url = get_url("aqua_url", env_var="AQUA_URL")  # Default fallback URL
        self.browser.LoadURL(aqua_url)

        # Token verification
        # Parse query parameters
        #query_params = request.split('?')[1].split('&')
        #params_dict = {}
        #for param in query_params:
        #    key, value = param.split('=')
        #    params_dict[key] = value
#
        ## Access values
        #company_code = params_dict.get('company_code')
        #license_no = params_dict.get('license_no')
        #guest_mode = params_dict.get('guest_mode')
        #is_vip = params_dict.get('is_vip')
#
        #print("Company Code:", company_code)
        #print("License No.:", license_no)
        #print("Guest Mode:", guest_mode)
        #print("VIP:", is_vip)
#
        ##API request
        ## Create payload for API request
        #payload = {
        #    "company_code": company_code,
        #    "token": license_no,
        #    "identity": "mvc", #hardcode not confirm what to get atm
        #    "is_vip": is_vip
        #}
#
        #print(payload)
        # Make API request
        #response = requests.post(get_url("token_verify_dev"), json=payload) # Replace with PRODUCTION IP/ DOMAIN
        ##response = requests.post(get_url("token_verify_prod"), json=payload) 
#
        ## Check response
        #if response.status_code == 200:
        #    response_json = response.json()  # Parse response JSON
        #    message = response_json.get("content", {}).get("message")
        #    if message == "Fail":
        #        print("Access denied:", response_json.get("content", {}).get("data"))
        #        messagebox.showerror("Access Denied", "Access to the system is denied, Please check the CD-KEY is valid.")
        #        print(response_json)
        #    else:
        #        self.browser.LoadURL(get_url("aqua_prod")) # Replace with AQUA IP/ DOMAIN
        #        print("Access granted!")
        #        self.add_buttons()  # Add buttons after access is granted
        #        self.ShowFullScreen(not self.IsFullScreen())
        #else:
        #    print("API request failed:", response.text)
        #    messagebox.showerror("Access Denied", "Please fill in the login credential.")


    def on_fullscreen_button(self, event):
        # Toggle full-screen mode while keeping taskbar visible
        if not self.IsFullScreen():
            # Get screen size
            screen_size = wx.Display().GetGeometry()
            # Set window size to screen size
            self.SetSize(screen_size)
            # Position window at (0,0)
            self.SetPosition((0, 0))
        else:
            # Restore original size
            self.SetSize((1280, 680))
            self.Center()

    def on_resolution_1440_1080_button(self, event):
        # Set resolution to 1440x1080
        self.SetSize((1440, 920))
        self.browser.Reload()  # Reload the page

    def on_resolution_1280_780_button(self, event):
        # Set resolution to 1280x780
        self.SetSize((1280, 780))
        self.browser.Reload()  # Reload the page

    def on_exit_button(self, event):
        # Ask for confirmation before exiting
        dlg = wx.MessageDialog(self, "Are you sure you want to exit?", "Exit Confirmation", wx.YES_NO | wx.ICON_QUESTION)
        result = dlg.ShowModal()
        dlg.Destroy()

        if result == wx.ID_YES:
            self.Close()
    
    def on_key_down(self, event):
        """Handle keyboard shortcuts"""
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_F12:
            self.open_developer_tools()
        event.Skip()
    
    def enable_remote_debugging(self):
        """Enable remote debugging for WebView2"""
        try:
            # For WebView2, we can enable remote debugging
            # This allows connecting Chrome DevTools at localhost:9222
            if hasattr(self.browser, 'EnableRemoteDebugging'):
                self.browser.EnableRemoteDebugging(True)
                print("Remote debugging enabled. Connect Chrome DevTools to: http://localhost:9222")
            elif hasattr(self.browser, 'SetRemoteDebuggingPort'):
                # Alternative method for some wxPython versions
                self.browser.SetRemoteDebuggingPort(9222)
                print("Remote debugging enabled on port 9222")
            else:
                print("Remote debugging not available in this WebView version")
        except Exception as exc:
            print(f"Failed to enable remote debugging: {exc}")
    
    def log_to_console(self, level, message):
        """Store console log messages"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.console_logs.append(log_entry)
        print(log_entry)  # Also print to Python console
        # Keep only last 1000 logs
        if len(self.console_logs) > 1000:
            self.console_logs = self.console_logs[-1000:]
    
    def on_dev_tools_button(self, event):
        """Open developer tools"""
        self.open_developer_tools()
    
    def open_developer_tools(self):
        """Open browser developer tools"""
        try:
            # Try to open DevTools using WebView2 API
            if hasattr(self.browser, 'ShowDevTools'):
                self.browser.ShowDevTools()
                print("Developer Tools opened")
            else:
                # Alternative: Open remote debugging URL in external browser
                import webbrowser
                try:
                    webbrowser.open('http://localhost:9222')
                    wx.MessageBox(
                        "Remote debugging enabled.\n"
                        "Chrome DevTools should open in your default browser.\n"
                        "If not, manually navigate to: http://localhost:9222",
                        "Developer Tools",
                        wx.OK | wx.ICON_INFORMATION
                    )
                except Exception as e:
                    wx.MessageBox(
                        f"Could not open developer tools automatically.\n"
                        f"Try connecting Chrome DevTools to: http://localhost:9222\n\n"
                        f"Error: {str(e)}",
                        "Developer Tools",
                        wx.OK | wx.ICON_WARNING
                    )
        except Exception as exc:
            wx.MessageBox(
                f"Failed to open developer tools: {str(exc)}\n\n"
                "You can still use the Console Log feature from the Tools menu.",
                "Developer Tools Error",
                wx.OK | wx.ICON_ERROR
            )
    
    def on_console_log_button(self, event):
        """Show JavaScript console log output"""
        if not self.console_logs:
            wx.MessageBox(
                "No console logs captured yet.\n"
                "Console logging will be active after the page loads.",
                "Console Log",
                wx.OK | wx.ICON_INFORMATION
            )
            return
        
        # Create a dialog to display console logs
        dialog = wx.Dialog(self, title="JavaScript Console Log", size=(800, 600))
        panel = wx.Panel(dialog)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Text control to display logs
        log_text = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP | wx.HSCROLL
        )
        log_text.SetFont(wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.NORMAL, wx.NORMAL))
        log_text.SetValue('\n'.join(self.console_logs))
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        clear_btn = wx.Button(panel, label="Clear Logs")
        refresh_btn = wx.Button(panel, label="Refresh")
        close_btn = wx.Button(panel, label="Close")
        
        button_sizer.Add(clear_btn, 0, wx.ALL, 5)
        button_sizer.Add(refresh_btn, 0, wx.ALL, 5)
        button_sizer.Add(close_btn, 0, wx.ALL, 5)
        
        sizer.Add(log_text, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        
        panel.SetSizer(sizer)
        
        def on_clear(event):
            self.console_logs = []
            log_text.Clear()
        
        def on_refresh(event):
            log_text.SetValue('\n'.join(self.console_logs))
            log_text.SetInsertionPointEnd()
        
        def on_close(event):
            dialog.Close()
        
        clear_btn.Bind(wx.EVT_BUTTON, on_clear)
        refresh_btn.Bind(wx.EVT_BUTTON, on_refresh)
        close_btn.Bind(wx.EVT_BUTTON, on_close)
        
        dialog.ShowModal()
        dialog.Destroy()
    
    def on_inspect_element_button(self, event):
        """Inspect page elements using JavaScript"""
        inspect_script = """
        (function() {
            // Get current page HTML
            return {
                html: document.documentElement.outerHTML,
                url: window.location.href,
                title: document.title,
                elements: document.querySelectorAll('*').length
            };
        })();
        """
        try:
            result = self.browser.RunScript(inspect_script)
            if result:
                # Display element information
                info = f"Page Information:\n"
                info += f"URL: {result.get('url', 'N/A')}\n"
                info += f"Title: {result.get('title', 'N/A')}\n"
                info += f"Total Elements: {result.get('elements', 'N/A')}\n"
                info += f"\nTo inspect elements, use Developer Tools (F12)"
                
                wx.MessageBox(info, "Page Inspection", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox(
                    "Could not inspect page elements.\n"
                    "Make sure the page has finished loading.",
                    "Inspection Error",
                    wx.OK | wx.ICON_WARNING
                )
        except Exception as exc:
            wx.MessageBox(
                f"Failed to inspect elements: {str(exc)}",
                "Inspection Error",
                wx.OK | wx.ICON_ERROR
            )

    def add_buttons(self):
        # Create buttons for changing screen resolution and exiting
        fullscreen_button = wx.Button(self.taskbar, label="Full Screen")
        resolution_1440_1080_button = wx.Button(self.taskbar, label="1440x1080")
        resolution_1280_780_button = wx.Button(self.taskbar, label="1280x780")
        exit_button = wx.Button(self.taskbar, label="Exit")

        # Bind button events
        fullscreen_button.Bind(wx.EVT_BUTTON, self.on_fullscreen_button)
        resolution_1440_1080_button.Bind(wx.EVT_BUTTON, self.on_resolution_1440_1080_button)
        resolution_1280_780_button.Bind(wx.EVT_BUTTON, self.on_resolution_1280_780_button)
        exit_button.Bind(wx.EVT_BUTTON, self.on_exit_button)

        # Add buttons to the taskbar sizer
        taskbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        taskbar_sizer.Add(fullscreen_button, 0, wx.ALL, 5)
        taskbar_sizer.Add(resolution_1440_1080_button, 0, wx.ALL, 5)
        taskbar_sizer.Add(resolution_1280_780_button, 0, wx.ALL, 5)
        taskbar_sizer.Add(exit_button, 0, wx.ALL, 5)
        self.taskbar.SetSizer(taskbar_sizer)

        # Refresh the layout
        self.panel.Layout()


class ExternalBrowserWindow(wx.Frame):
    def __init__(self, title: str, initial_url: str = ""):
        super().__init__(None, wx.ID_ANY, title, style=wx.DEFAULT_FRAME_STYLE)
        self.SetSize((1280, 680))
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.browser = webview.WebView.New(panel)
        self.browser.Bind(webview.EVT_WEBVIEW_NEWWINDOW, self.on_webview_new_window)
        sizer.Add(self.browser, 1, wx.EXPAND)
        panel.SetSizer(sizer)
        if initial_url:
            self.browser.LoadURL(initial_url)
        log_action(f"Opened new browser window: {initial_url}")

    def on_webview_new_window(self, event):
        url = event.GetURL()
        target = event.GetTarget()
        log_action(f"New window requested (target={target}): {url}")
        new_frame = ExternalBrowserWindow(title="AQUA", initial_url=url)
        if hasattr(event, "SetWebView"):
            event.SetWebView(new_frame.browser)
        else:
            log_action("WebViewEvent.SetWebView not available; using standalone window.")
            if hasattr(event, "Veto"):
                event.Veto()
            else:
                event.Skip()
        new_frame.Show()


def log_action(message: str) -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[ACTION] [{timestamp}] {message}")

app = wx.App(False)
frame = SimpleBrowser(None, wx.ID_ANY, "AQUAv1.0.0")
frame.Show()
frame.Center()
app.MainLoop()
