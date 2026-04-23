import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView

class SimpleBrowser(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simple Browser")
        self.setGeometry(100, 100, 1200, 800)

        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)

        url = QUrl("http://198.13.43.246:9915/")  # Replace with your website URL
        self.browser.load(url)
        self.browser.page().runJavaScript("document.documentElement.style.zoom = '80%';")
        
app = QApplication(sys.argv)
browser = SimpleBrowser()
browser.show()
sys.exit(app.exec_())
