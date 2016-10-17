#!/usr/bin/env ipython
# -*- coding: utf-8 -*-

# TODO : Integrate with KDE API to queue downloads within KGet download manager
# TODO : Investigte real-debrid Chrome extension for possible API pathways to automate link generation
# TODO : Add progress bar to hoster links dialog so users is aware content is downloading

import http.client
from urllib.parse import quote_plus

from PyQt5.QtCore import (QFile, QJsonDocument, QModelIndex, QSettings, QSize, Qt,
                          QTextStream, QUrl, pyqtSlot)
from PyQt5.QtGui import (QCloseEvent, QDesktopServices, QFont, QFontDatabase,
                         QHideEvent, QIcon, QPalette, QShowEvent)
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QBoxLayout,
                             QButtonGroup, QComboBox, QDialog, QFrame,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QProgressBar, QPushButton, QSizePolicy,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, qApp)

import assets
from threads import HostersThread, ScrapeThread


class HosterLinks(QDialog):
    def __init__(self, parent, f=Qt.Tool):
        super(HosterLinks, self).__init__(parent, f)
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        self.hosters = []
        self.setContentsMargins(20, 20, 20, 20)
        self.layout = QVBoxLayout(spacing=25)
        self.setLayout(self.layout)
        self.copy_icon = QIcon(TVLinker.get_path('copy_icon.png'))
        self.open_icon = QIcon(TVLinker.get_path('open_icon.png'))
        self.download_icon = QIcon(TVLinker.get_path('download_icon.png'))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.copy_group = QButtonGroup(exclusive=False)
        self.copy_group.buttonClicked[int].connect(self.copy_link)
        self.open_group = QButtonGroup(exclusive=False)
        self.open_group.buttonClicked[int].connect(self.open_link)
        self.download_group = QButtonGroup(exclusive=False)
        self.download_group.buttonClicked[int].connect(self.download_link)
        self.setWindowTitle('Hoster Links')
        # self.resize(QSize(1000, 250))

    def clear_layout(self, layout: QBoxLayout = None) -> None:
        if layout is None:
            layout = self.layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget() is not None:
                child.widget().deleteLater()
            elif child.layout() is not None:
                self.clear_layout(child.layout())
        self.layout.setSpacing(25)

    @staticmethod
    def get_separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def show_hosters(self, hosters: list) -> None:
        self.hosters = hosters
        self.clear_layout()
        index = 0
        for hoster in hosters:
            content = QLabel(textFormat=Qt.RichText, toolTip=hoster[1])
            content.setText('''<table border="0" cellpading="6">
                                <tr nowrap valign="middle">
                                    <td align="center" width="160"><img src="%s" /></td>
                                    <td width="15">&nbsp;</td>
                                </tr>
                              <table>''' % TVLinker.get_path('/hosters/%s' % QUrl(hoster[0]).fileName()))
            copy_btn = QPushButton(self, icon=self.copy_icon, text=' COPY', toolTip='Copy to clipboard', flat=False,
                                   cursor=Qt.PointingHandCursor, iconSize=QSize(16, 16))
            copy_btn.setFixedSize(90, 30)
            self.copy_group.addButton(copy_btn, index)
            open_btn = QPushButton(self, icon=self.open_icon, text=' OPEN', toolTip='Open in browser', flat=False,
                                   cursor=Qt.PointingHandCursor, iconSize=QSize(16, 16))
            open_btn.setFixedSize(90, 30)
            self.open_group.addButton(open_btn, index)
            download_btn = QPushButton(self, icon=self.download_icon, text=' DOWNLOAD', toolTip='Download unrestricted link',
                                            flat=False, cursor=Qt.PointingHandCursor, iconSize=QSize(16, 16))
            download_btn.setFixedSize(90, 30)
            self.download_group.addButton(download_btn, index)
            layout = QHBoxLayout(spacing=10)
            layout.addWidget(content)
            layout.addWidget(copy_btn, Qt.AlignRight)
            layout.addWidget(open_btn, Qt.AlignRight)
            self.layout.addLayout(layout)
            if self.layout.count() <= len(hosters):
                self.layout.addWidget(self.get_separator())
            index += 1
        self.update()

    @pyqtSlot(int)
    def copy_link(self, button_id: int) -> None:
        clip = qApp.clipboard()
        clip.setText(self.hosters[button_id][1])
        self.hide()

    @pyqtSlot(int)
    def open_link(self, button_id: int) -> None:
        QDesktopServices.openUrl(QUrl(self.hosters[button_id][1]))
        self.hide()

    @pyqtSlot(int)
    def download_link(self, button_id: int) -> None:
        pass

    def hideEvent(self, event: QHideEvent) -> None:
        self.clear_layout()
        super(HosterLinks, self).hideEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        busy_label = QLabel('Retrieiving hoster links...', alignment=Qt.AlignCenter)
        busy_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        busy_indicator = QProgressBar(parent=self, minimum=0, maximum=0)
        self.layout.setSpacing(10)
        self.layout.addWidget(busy_label)
        self.layout.addWidget(busy_indicator)
        self.setMinimumWidth(485)
        super(HosterLinks, self).showEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.hide()
        event.accept()


class TVLinker(QDialog):
    def __init__(self, parent=None, f=Qt.Window):
        super(TVLinker, self).__init__(parent, f)
        self.rows, self.cols = 0, 0
        self.init_stylesheet()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 5)
        self.init_settings()
        layout.addLayout(self.init_form())
        layout.addWidget(self.init_table())
        layout.addLayout(self.init_metabar())
        self.setLayout(layout)
        self.setWindowTitle(qApp.applicationName())
        self.setWindowIcon(QIcon(self.get_path('teevee-app-icon.png')))
        self.resize(1000, 800)
        self.show()
        self.start_scraping()
        self.hosters_win = HosterLinks(parent=self)

    def init_stylesheet(self) -> None:
        qApp.setStyle('Fusion')
        QFontDatabase.addApplicationFont(self.get_path('OpenSans.ttf'))
        qss = QFile(self.get_path('%s.qss' % qApp.applicationName().lower()))
        qss.open(QFile.ReadOnly | QFile.Text)
        stream = QTextStream(qss)
        qApp.setStyleSheet(stream.readAll())

    def init_settings(self) -> None:
        self.settings = QSettings(self.get_path('%s.ini' % qApp.applicationName().lower()), QSettings.IniFormat)
        self.source_url = self.settings.value('source_url')
        self.user_agent = self.settings.value('user_agent')
        self.dl_pagecount = int(self.settings.value('dl_pagecount'))
        self.dl_pagelinks = int(self.settings.value('dl_pagelinks'))
        self.meta_template = self.settings.value('meta_template')
        self.realdebrid_api_token = self.settings.value('realdebrid_api_token')

    def init_form(self) -> QHBoxLayout:
        self.search_field = QLineEdit(self, clearButtonEnabled=True,
                                      placeholderText='Enter search criteria')
        self.search_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.search_field.textChanged.connect(self.filter_table)
        self.refresh_button = QPushButton(QIcon.fromTheme('view-refresh'), ' Refresh', cursor=Qt.PointingHandCursor,
                                          iconSize=QSize(12, 12), clicked=self.refresh_links)
        self.dlpages_field = QComboBox(self, editable=False, cursor=Qt.PointingHandCursor)
        self.dlpages_field.addItems(('10', '20', '30', '40'))
        self.dlpages_field.setCurrentIndex(self.dlpages_field.findText(str(self.dl_pagecount), Qt.MatchFixedString))
        self.dlpages_field.currentIndexChanged.connect(self.update_pagecount)
        layout = QHBoxLayout()
        layout.addWidget(QLabel('Search:'))
        layout.addWidget(self.search_field)
        layout.addWidget(QLabel('Pages:'))
        layout.addWidget(self.dlpages_field)
        layout.addWidget(self.refresh_button)
        return layout

    def init_table(self) -> QTableWidget:
        self.table = QTableWidget(0, 4, self)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.hideColumn(1)
        self.table.setCursor(Qt.PointingHandCursor)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setHorizontalHeaderLabels(('Date', 'URL', 'Description', 'Format'))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(100)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.sortByColumn(0, Qt.DescendingOrder)
        self.table.doubleClicked.connect(self.show_hosters)
        return self.table

    def init_metabar(self) -> QHBoxLayout:
        palette = QPalette()
        palette.setColor(QPalette.Base, Qt.lightGray)
        self.setPalette(palette)
        self.progress = QProgressBar(parent=self, minimum=0, maximum=(self.dl_pagecount * self.dl_pagelinks), visible=False)
        self.meta_label = QLabel(textFormat=Qt.RichText, alignment=Qt.AlignRight, objectName='totals')
        self.meta_label.setFixedHeight(30)
        self.meta_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update_metabar()
        layout = QHBoxLayout()
        layout.addWidget(self.progress, Qt.AlignLeft)
        layout.addWidget(self.meta_label, Qt.AlignRight)
        return layout

    def update_metabar(self) -> bool:
        rowcount = self.table.rowCount()
        self.meta_label.setText(self.meta_template.replace('%s', str(rowcount)))
        self.progress.setValue(rowcount)
        return True

    def start_scraping(self, maxpages: int = 10) -> None:
        self.rows = 0
        self.setCursor(Qt.BusyCursor)
        if self.table.rowCount() > 0:
            self.table.clearContents()
            self.table.setRowCount(0)
        self.table.setSortingEnabled(False)
        self.scrape = ScrapeThread(settings=self.settings, maxpages=maxpages)
        self.scrape.addRow.connect(self.add_row)
        self.scrape.started.connect(self.progress.show)
        self.scrape.finished.connect(self.scrape_finished)
        self.progress.setValue(0)
        self.scrape.start()

    @pyqtSlot(bool)
    def refresh_links(self) -> None:
        self.start_scraping(int(self.dlpages_field.currentText()))

    @pyqtSlot(int)
    def update_pagecount(self, index: int) -> None:
        pagecount = int(self.dlpages_field.itemText(index))
        self.progress.setMaximum(pagecount * self.dl_pagelinks)
        self.start_scraping(pagecount)

    @pyqtSlot()
    def scrape_finished(self) -> None:
        self.progress.hide()
        self.table.setSortingEnabled(True)
        self.unsetCursor()

    @pyqtSlot(list)
    def add_row(self, row: list) -> None:
        self.cols = 0
        self.table.setRowCount(self.rows + 1)
        for item in row:
            table_item = QTableWidgetItem(item)
            table_item.setToolTip(row[1])
            table_item.setFont(QFont('Open Sans', weight=QFont.Normal))
            if self.cols == 2:
                table_item.setFont(QFont('Open Sans', weight=QFont.DemiBold))
                table_item.setText('  ' + table_item.text())
            elif self.cols == 3:
                table_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(self.rows, self.cols, table_item)
            self.update_metabar()
            self.cols += 1
        self.rows += 1

    @pyqtSlot(list)
    def add_hosters(self, hosters: list) -> None:
        self.hosters_win.show_hosters(hosters)

    @pyqtSlot(QModelIndex)
    def show_hosters(self, index: QModelIndex) -> bool:
        self.hosters_win.show()
        self.links = HostersThread(settings=self.settings, link_url=self.table.item(self.table.currentRow(), 1).text())
        self.links.setHosters.connect(self.add_hosters)
        self.links.start()

    @pyqtSlot(str)
    def filter_table(self, text: str) -> None:
        valid_rows = []
        if len(text) > 0:
            for item in self.table.findItems(text, Qt.MatchContains):
                valid_rows.append(item.row())
        for row in range(0, self.table.rowCount()):
            if len(text) > 0 and row not in valid_rows:
                self.table.hideRow(row)
            else:
                self.table.showRow(row)

    @staticmethod
    def unrestrict_link(api_token: str, link: str) -> str:
        dl_link = ''
        conn = http.client.HTTPSConnection('api.real-debrid.com')
        payload = 'link=%s' % quote_plus(link)
        headers = {
            'Authorization': 'Bearer %s' % api_token, 
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cache-Control': 'no-cache'
        }
        conn.request('POST', '/rest/1.0/unrestrict/link', payload, headers)
        res = conn.getresponse()
        data = res.read()
        jsondoc = QJsonDocument.fromJson(data)
        if jsondoc.isObject():
            api_result = jsondoc.object()
            dl_link = api_result['download'].toString()
        return dl_link

    @staticmethod
    def get_path(path: str = None) -> str:
        return ':assets/%s' % path

    def closeEvent(self, event: QCloseEvent) -> None:
        self.table.deleteLater()
        self.deleteLater()
        qApp.quit()


def main():
    import sys
    app = QApplication(sys.argv)
    app.setOrganizationName('ozmartians.com')
    app.setApplicationName('TVLinker')
    app.setQuitOnLastWindowClosed(True)
    tv = TVLinker()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
