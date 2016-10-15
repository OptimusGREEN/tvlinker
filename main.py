#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from urllib.request import Request, urlopen

from PyQt5.QtCore import QFile, QModelIndex, QSettings, QSize, QTextStream, QThread, QUrl, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QCloseEvent, QDesktopServices, QFont, QFontDatabase, QIcon
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog, QHeaderView, QHBoxLayout, QLabel,
                             QLineEdit, QProgressBar, QPushButton, QSizePolicy, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, qApp)
from bs4 import BeautifulSoup

import assets


class ScrapeThread(QThread):

    addRow = pyqtSignal(list)

    def __init__(self, maxpages:int):
        QThread.__init__(self)
        self.maxpages = maxpages

    def __del__(self):
        self.wait()

    def init_settings(self) -> None:
        self.settings = QSettings(TVLinker.get_path('%s.ini' % qApp.applicationName().lower()), QSettings.IniFormat)
        self.source_url = self.settings.value('source_url')
        self.user_agent = self.settings.value('user_agent')

    def scrape_links(self) -> None:
        row = 0
        for page in range(1, self.maxpages):
            url = self.source_url % page
            req = Request(url, headers={'User-agent': self.user_agent})
            res = urlopen(req)
            try:
                bs = BeautifulSoup(res.read(), 'lxml')
            except:
                bs = BeautifulSoup(res.read(), 'html.parser')
            links = bs.find_all('table', class_='posts_table')
            for link_table in links:
                cols = link_table.tr.find_all('td')
                table_row = [
                    cols[2].get_text(),
                    cols[1].find('a').get('href'),
                    cols[1].find('a').get_text(),
                    cols[0].find('a').get_text().replace('TV-', '')
                ]
                # qApp.processEvents()
                self.addRow.emit(table_row)
                row += 1

    def run(self):
        self.init_settings()
        self.scrape_links()


class TVLinker(QDialog):
    def __init__(self, parent=None, f=Qt.Window):
        super(TVLinker, self).__init__(parent, f)
        self.rows, self.cols = 0, 0
        self.init_stylesheet()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 0)
        self.settings = QSettings(self.get_path('%s.ini' % qApp.applicationName().lower()), QSettings.IniFormat)
        self.dl_pagecount = int(self.settings.value('dl_pagecount'))
        self.meta_template = self.settings.value('meta_template')
        layout.addLayout(self.init_form())
        layout.addWidget(self.init_table())
        layout.addWidget(self.init_metabar())
        self.setLayout(layout)
        self.setWindowTitle(qApp.applicationName())
        self.setWindowIcon(QIcon(self.get_path('%s.png' % qApp.applicationName().lower())))
        self.resize(1000, 800)
        self.show()
        self.start_scraping()

    def init_stylesheet(self) -> None:
        qApp.setStyle('Fusion')
        QFontDatabase.addApplicationFont(self.get_path('OpenSans.ttf'))
        qss = QFile(self.get_path('%s.qss' % qApp.applicationName().lower()))
        qss.open(QFile.ReadOnly | QFile.Text)
        stream = QTextStream(qss)
        qApp.setStyleSheet(stream.readAll())

    def init_form(self) -> QHBoxLayout:
        self.search_field = QLineEdit(self, clearButtonEnabled=True,
                                      placeholderText='Enter search criteria')
        self.search_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.search_field.textChanged.connect(self.filter_table)
        self.refresh_button = QPushButton(QIcon.fromTheme('view-refresh'), ' Refresh', cursor=Qt.PointingHandCursor,
                                          iconSize=QSize(12, 12), clicked=self.start_scraping)
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
        self.table.setSortingEnabled(True)
        self.table.hideColumn(1)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.viewport().setAttribute(Qt.WA_Hover)
        self.table.setHorizontalHeaderLabels(('Date', 'URL', 'Description', 'Media'))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.sortByColumn(0, Qt.DescendingOrder)
        self.table.doubleClicked.connect(self.open_link)
        return self.table

    def init_metabar(self) -> QLabel:
        self.meta_label = QLabel(textFormat=Qt.RichText, alignment=Qt.AlignRight, objectName='totals')
        self.meta_label.setAutoFillBackground(True)
        self.meta_label.setFixedHeight(30)
        self.meta_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.update_metabar()
        self.meta_label.setContentsMargins(0, 0, 0, 0)
        return self.meta_label

    def update_metabar(self) -> bool:
        self.meta_label.setText(self.meta_template.replace('%s', str(self.table.rowCount())))
        return True

    def start_scraping(self, maxpages: int = 20) -> str:
        self.rows = 0
        self.setCursor(Qt.BusyCursor)
        if self.table.rowCount() > 0:
            self.table.clearContents()
            self.table.setRowCount(0)
        qApp.processEvents()
        self.table.setSortingEnabled(False)
        self.scrape = ScrapeThread(maxpages)
        self.scrape.start()
        self.scrape.addRow.connect(self.add_row)
        self.table.setSortingEnabled(True)
        self.update_metabar()
        self.setCursor(Qt.PointingHandCursor)

    @pyqtSlot(int)
    def update_pagecount(self, index: int) -> str:
        return self.start_scraping(int(self.dlpages_field.itemText(index)))

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
            # qApp.processEvents()
            self.cols += 1
        self.rows += 1

    @pyqtSlot(QModelIndex)
    def open_link(self, index: QModelIndex) -> bool:
        return QDesktopServices.openUrl(QUrl(self.table.item(self.table.currentRow(), 1).text()))

    @pyqtSlot(str)
    def filter_table(self, text: str) -> None:
        valid_rows = []
        for item in self.table.findItems(text, Qt.MatchContains):
            valid_rows.append(item.row())
        for row in range(0, self.table.rowCount()):
            if row not in valid_rows:
                self.table.hideRow(row)
            else:
                self.table.showRow(row)
        self.update_metabar()

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
