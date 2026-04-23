import wx
import wx.html2 as webview
import json
import requests
import tkinter as tk
from tkinter import messagebox


class SimpleBrowser(wx.Frame):
    def __init__(self, *args, **kw):
        super(SimpleBrowser, self).__init__(*args, **kw)

        # Set the initial size to 1280x580
        self.SetSize((1280, 680))
        self.initializeUI()

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

        # Read data from JSON file
        with open('log.json', encoding='utf-8') as json_file:
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
        # Generate HTML content using data from JSON
        html_content = """
        <html>
        <body style="background: url(http://198.13.43.246:9915/img/bg.acb1990a.png) no-repeat;background-size: cover;background-position: 50%;justify-content: center; font-family: sans-serif; padding:20px;color:white;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="width: 60%; background:rgba(255,255,255,0.8); color:black;border: 1px solid #ccc; padding: 20px; border-radius:10px;height:60vh;overflow:auto">
        """
        
        # Add data items from JSON data
        for item in data["data"]:
            date = item["date"]
            content = item["content"]
            html_content += f"<b>Update: {date}</b>"
            html_content += f"<p>{content}</p>"

        html_content += """
                </div>
                <div style="width: 35%; text-align: center;">
                    <div>
                        <img style="width:100px;" src="http://198.13.43.246:9915/img/aqua_logo.e982d26b.png"/>
                    </div>
                    <h2>AQUA</h2>
                    <form>
                        <div style="margin-bottom: 10px;">
                            <label for="company-code">Firm Code</label><br>
                            <input type="text" id="company-code" name="company-code" value="BR" style="width: 100%; padding: 8px;" disabled>
                        </div>
                        <div style="margin-bottom: 10px;">
                            <label for="license-no">License No.</label><br>
                            <input type="text" id="license-no" name="license-no" value="8742142151242632" style="width: 100%; padding: 8px;" disabled>
                        </div>
                        <div style="margin-bottom: 20px;">
                            <input type="checkbox" id="guest-mode" name="guest-mode">
                            <label for="guest-mode">Guest mode</label>
                        </div>
                        <div style="margin-bottom: 20px;">
                            <input type="checkbox" id="is-vip" name="is-vip">
                            <label for="is-vip">VIP</label>
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
                        <p>V1.0.20240521</p>
                    </div>
                </div>
            </div>
            <script type="text/javascript">
                document.getElementById('start-button').addEventListener('click', function() {
                    var companyCode = document.getElementById('company-code').value;
                    var licenseNo = document.getElementById('license-no').value;
                    var guestMode = document.getElementById('guest-mode').checked;
                    var isVIP = document.getElementById('is-vip').checked;

                    var url = 'webview-link://start-button-clicked?company_code=' + encodeURIComponent(companyCode) + '&license_no=' + encodeURIComponent(licenseNo) + '&guest_mode=' + guestMode + '&is_vip=' + isVIP;
                    window.location.href = url;
                });
            </script>
        </body>
        </html>
        """

        return html_content

    def on_webview_navigating(self, event):
        # Handle custom scheme navigation
        url = event.GetURL()
        if url.startswith("webview-link://"):
            self.handle_custom_scheme(url)
            event.Veto()  # Prevent the default navigation

    def handle_custom_scheme(self, request):
        #print("Custom scheme triggered:", request)
        self.browser.LoadURL("http://141.164.43.173:7002/client") # Replace with AQUA IP/ DOMAIN
        self.add_buttons()  # Add buttons after access is granted
        self.ShowFullScreen(not self.IsFullScreen())
        """
        # Parse query parameters
        query_params = request.split('?')[1].split('&')
        params_dict = {}
        for param in query_params:
            key, value = param.split('=')
            params_dict[key] = value

        # Access values
        company_code = params_dict.get('company_code')
        license_no = params_dict.get('license_no')
        guest_mode = params_dict.get('guest_mode')
        is_vip = params_dict.get('is_vip')

        print("Company Code:", company_code)
        print("License No.:", license_no)
        print("Guest Mode:", guest_mode)
        print("VIP:", is_vip)

        #API request
        # Create payload for API request
        payload = {
            "company_code": company_code,
            "token": license_no,
            "identity": "mvc", #hardcode not confirm what to get atm
            #"is_vip": is_vip
        }

        print(payload)
        # Make API request
        #response = requests.post("http://0.0.0.0:9906/t1/admin/token/verify", json=payload) # Replace with PRODUCTION IP/ DOMAIN
        response = requests.post("http://198.13.43.246:9915/t1/admin/token/verify", json=payload) 

        # Check response
        if response.status_code == 200:
            response_json = response.json()  # Parse response JSON
            message = response_json.get("content", {}).get("message")
            if message == "Fail":
                print("Access denied:", response_json.get("content", {}).get("data"))
                messagebox.showerror("Access Denied", "Access to the system is denied, Please check the CD-KEY is valid.")
                print(response_json)
            else:
                self.browser.LoadURL("http://198.13.43.246:9915") # Replace with AQUA IP/ DOMAIN
                print("Access granted!")
                self.add_buttons()  # Add buttons after access is granted
                self.ShowFullScreen(not self.IsFullScreen())
        else:
            print("API request failed:", response.text)
            messagebox.showerror("Access Denied", "Please fill in the login credential.")
        """

    def on_fullscreen_button(self, event):
        # Toggle full-screen mode
        self.ShowFullScreen(not self.IsFullScreen())

    def on_resolution_1440_1080_button(self, event):
        # Set resolution to 1440x1080
        self.SetSize((1440, 920))
        self.browser.Reload()  # Reload the page

    def on_resolution_1280_780_button(self, event):
        # Set resolution to 1280x780
        self.SetSize((1280, 780))
        self.browser.Reload()  # Reload the page

    def on_clear_cache_button(self, event):
        # JavaScript code to clear Local Storage
        script = """
        localStorage.clear();
        """
        # Execute the JavaScript code in the WebView
        self.browser.RunScript(script)
        messagebox.showinfo("Cache has been cleaned", "Please login again")

    def on_exit_button(self, event):
        # Ask for confirmation before exiting
        dlg = wx.MessageDialog(self, "Are you sure you want to exit?", "Exit Confirmation", wx.YES_NO | wx.ICON_QUESTION)
        result = dlg.ShowModal()
        dlg.Destroy()

        if result == wx.ID_YES:
            self.Close()

    def add_buttons(self):
        # Create buttons for changing screen resolution, exiting, and clearing cookies/cache
        fullscreen_button = wx.Button(self.taskbar, label="Full Screen")
        resolution_1440_1080_button = wx.Button(self.taskbar, label="1440x1080")
        resolution_1280_780_button = wx.Button(self.taskbar, label="1280x780")
        clear_cache_button = wx.Button(self.taskbar, label="Reset Config")
        exit_button = wx.Button(self.taskbar, label="Exit")

        # Bind button events
        fullscreen_button.Bind(wx.EVT_BUTTON, self.on_fullscreen_button)
        resolution_1440_1080_button.Bind(wx.EVT_BUTTON, self.on_resolution_1440_1080_button)
        resolution_1280_780_button.Bind(wx.EVT_BUTTON, self.on_resolution_1280_780_button)
        clear_cache_button.Bind(wx.EVT_BUTTON, self.on_clear_cache_button)
        exit_button.Bind(wx.EVT_BUTTON, self.on_exit_button)

        # Add buttons to the taskbar sizer
        taskbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        taskbar_sizer.Add(fullscreen_button, 0, wx.ALL, 5)
        taskbar_sizer.Add(resolution_1440_1080_button, 0, wx.ALL, 5)
        taskbar_sizer.Add(resolution_1280_780_button, 0, wx.ALL, 5)
        taskbar_sizer.Add(clear_cache_button, 0, wx.ALL, 5)
        taskbar_sizer.Add(exit_button, 0, wx.ALL, 5)
        self.taskbar.SetSizer(taskbar_sizer)

        # Refresh the layout
        self.panel.Layout()
app = wx.App(False)
frame = SimpleBrowser(None, wx.ID_ANY, "AQUAv20240721")
frame.Show()
frame.Center()
app.MainLoop()
