from Qt import QtCore, QtGui, QtWidgets

from bigglesworth.utils import loadUi, localPath, setBold
from bigglesworth.widgets.delegates import CheckBoxDelegate

PortRole = QtCore.Qt.UserRole + 1

class CheckableDelegate(CheckBoxDelegate):
    def sizeHint(self, option, index):
        hint = CheckBoxDelegate.sizeHint(self, option, index)
        self.initStyleOption(option, index)
        hint.setHeight(option.fontMetrics.height() * 1.5)
        return hint

    def paint(self, painter, option, index):
        if not index.flags() & QtCore.Qt.ItemIsEnabled:
            return QtWidgets.QStyledItemDelegate.paint(self, painter, option, index)
        QtWidgets.QStyledItemDelegate.paint(self, painter, option, QtCore.QModelIndex())
        self.square_pen = self.square_pen_enabled
        self.select_pen = self.select_pen_enabled
        self.select_brush = self.select_brush_enabled
#            self.square_pen = self.square_pen_disabled
#            self.select_pen = self.select_pen_disabled
#            self.select_brush = self.select_brush_disabled
#        option = QtWidgets.QStyleOptionViewItem()
#        option.__init__(style)
        self.initStyleOption(option, index)
        painter.setRenderHints(QtGui.QPainter.Antialiasing)
        painter.save()
        painter.translate(option.rect.left() + 4, option.rect.y() + option.rect.height() / 2 - 5)
        painter.setPen(self.square_pen)
        painter.drawRect(0, 0, 10, 10)
        if index.data(QtCore.Qt.CheckStateRole):
            painter.setPen(self.select_pen)
            painter.setBrush(self.select_brush)
#            painter.translate(self.square.left(), self.square.top())
            painter.drawPath(self.path)
        painter.restore()
        painter.setFont(option.font)
        rect = option.rect.adjusted(18, 0, 0, 0)
        painter.setPen(option.palette.color(option.palette.Text))
        painter.drawText(rect, option.displayAlignment, 
            option.fontMetrics.elidedText(option.text, option.textElideMode, rect.width()))

    def editorEvent(self, event, model, option, index):
        self.initStyleOption(option, index)
        if event.type() == QtCore.QEvent.MouseButtonPress and option.rect.left() <= event.pos().x() <= option.rect.left() + 18:
            return CheckBoxDelegate.editorEvent(self, event, model, option, index)
        return QtWidgets.QStyledItemDelegate.editorEvent(self, event, model, option, index)


class MidiConnectionsDialog(QtWidgets.QDialog):
    def __init__(self, main, parent=None):
        QtWidgets.QDialog.__init__(self, parent)
        self.setWindowTitle('MIDI connections')
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        self.midiConnectionWidget = MidiConnectionsWidget()
        layout.addWidget(self.midiConnectionWidget)
#        self.midiConnectionWidget.setMain(main)
#        self.midiConnectionWidget.midiConnect.connect(main.editorWindow.midiConnect)
        self.midiConnectionWidget.midiConnect.connect(main.midiConnect)


class MidiConnectionsWidget(QtWidgets.QWidget):
    midiConnect = QtCore.pyqtSignal(object, int, bool)
    shown = False
    _hideAlert = False

    def __init__(self, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, *args, **kwargs)
        loadUi(localPath('ui/midiconnections.ui'), self)
        if self.property('hideOutput') or kwargs.get('hideOutput'):
            self.hideOutput = True
        if self.property('hideAlert') or kwargs.get('hideAlert'):
            self.hideAlert = True
        self.refreshBtn.clicked.connect(self.refresh)

        self.inputModel = QtGui.QStandardItemModel()
        self.inputTreeView.setModel(self.inputModel)
        self.inputTreeView.doubleClicked.connect(self.toggleConnection)
        self.inputTreeView.customContextMenuRequested.connect(self.contextMenu)
        self.inputDelegate = CheckableDelegate()
        self.inputTreeView.setItemDelegate(self.inputDelegate)
#        self.inputTreeView.setUniformRowHeights(True)

        self.outputModel = QtGui.QStandardItemModel()
        self.outputTreeView.setModel(self.outputModel)
        self.outputTreeView.doubleClicked.connect(self.toggleConnection)
        self.outputTreeView.customContextMenuRequested.connect(self.contextMenu)
        self.outputDelegate = CheckableDelegate()
        self.outputTreeView.setItemDelegate(self.outputDelegate)
#        self.outputTreeView.setUniformRowHeights(True)

        self.main = QtWidgets.QApplication.instance()
        self.midiDevice = self.main.midiDevice
        self.rtmidi = self.midiDevice.mode
        self.input = self.midiDevice.input
        self.output = self.midiDevice.output
        self.graph = self.main.graph
        self.graph.graph_changed.connect(self.refresh)

        self.duplicates = set()

    @QtCore.pyqtProperty(bool)
    def hideAlert(self):
        return self._hideAlert

    @hideAlert.setter
    def hideAlert(self, hide):
        try:
            self.infoLbl.setText('')
            self.infoIcon.setVisible(not hide)
            self._hideAlert = hide
        except:
            pass

    @QtCore.pyqtProperty(bool)
    def hideOutput(self):
        return self.outputTreeView.isVisible()

    @hideOutput.setter
    def hideOutput(self, hide):
        try:
            self.outputTreeView.setVisible(not hide)
            self.vLine.setVisible(not hide)
        except:
            pass


    def setPossibleDuplicates(self, ports):
        self.duplicates |= ports
        indexes = []
        for row in range(self.inputModel.rowCount()):
            index = self.inputModel.index(row, 0)
            if not index.flags() & QtCore.Qt.ItemIsEnabled:
                for row in range(self.inputModel.rowCount(index)):
                    child = index.child(row, 0)
                    if child.data(PortRole).addr in self.duplicates:
                        indexes.append(child)
            else:
                if index.data(PortRole).addr in self.duplicates:
                    indexes.append(index)
        self.inputModel.dataChanged.disconnect(self.toggleConnection)
        for index in indexes:
            self.inputModel.setData(index, QtGui.QColor(QtCore.Qt.red), QtCore.Qt.ForegroundRole)
        self.inputModel.dataChanged.connect(self.toggleConnection)
        self.inputTreeView.scrollTo(indexes[0], self.inputTreeView.PositionAtCenter)

    def focusInEvent(self, event):
        #TODO: fix next widget focus
        QtWidgets.QWidget.focusInEvent(self, event)
        self.inputTreeView.setFocus()

    def toggleConnection(self, index):
        if not index.isValid():
            return
        if not index.flags() & QtCore.Qt.ItemIsEnabled:
            return
        direction = index.model() == self.outputModel
        port = index.data(PortRole)
        if direction:
            connected = any([True for conn in port.connections.input if conn.src == self.main.midiDevice.output])
        else:
            connected = any([True for conn in port.connections.output if conn.dest == self.main.midiDevice.input])
        self.midiConnect.emit(port, direction, not connected)

    def contextMenu(self, pos):
        view = self.sender()
        direction = True if view == self.outputTreeView else False
        index = view.indexAt(pos)
        if not index.isValid():
            return

        item = view.model().itemFromIndex(index)
        menu = QtWidgets.QMenu()

        if item.isEnabled():
            connected = index.data(QtCore.Qt.FontRole).bold()
            portAction = menu.addAction('Disconnect' if connected else 'Connect')
            port = item.data()
        else:
            portAction = None

        disconnectAllAction = menu.addAction('Disconnect all')
        if view == self.inputTreeView:
            if not any(conn for conn in self.main.midiDevice.input.connections.input if not conn.hidden):
                disconnectAllAction.setEnabled(False)
        elif not any(conn for conn in self.main.midiDevice.output.connections.output if not conn.hidden):
            disconnectAllAction.setEnabled(False)

        res = menu.exec_(view.viewport().mapToGlobal(pos))
        if not res:
            return
        elif res == portAction:
            self.midiConnect.emit(port, direction, not connected)
        elif res == disconnectAllAction:
            if direction:
                ports = [conn.dest for conn in self.main.midiDevice.output.connections.output if not conn.hidden]
            else:
                ports = [conn.src for conn in self.main.midiDevice.input.connections.input if not conn.hidden]
            for port in ports:
#                print(port)
                self.midiConnect.emit(port, direction, False)

#    def setMain(self, main):
#        self.main = main
#        self.backend = self.main.midiDevice.mode
#        self.input = self.main.midiDevice.input
#        self.output = self.main.midiDevice.output
#        self.graph = self.main.graph
#        self.graph.graph_changed.connect(self.refresh)
#        self.refresh()
#
#    def unsetMain(self):
#        self.graph.graph_changed.disconnect(self.refresh)

    def refresh(self):
        self.duplicates = set()
        inPos = self.inputTreeView.verticalScrollBar().value()
        outPos = self.outputTreeView.verticalScrollBar().value()
        try:
            self.inputModel.dataChanged.disconnect(self.toggleConnection)
            self.outputModel.dataChanged.disconnect(self.toggleConnection)
        except:
            pass
        self.inputModel.clear()
        self.outputModel.clear()
        inConn = 0
        outConn = 0
        portFlags = QtCore.Qt.ItemIsEnabled|QtCore.Qt.ItemIsEditable
        for client in [self.main.graph.client_id_dict[cid] for cid in sorted(self.main.graph.client_id_dict.keys())]:
            if client in (self.main.midiDevice.input.client, self.main.midiDevice.output.client):
                continue
            in_ports = []
            out_ports = []
            for port in client.ports:
                if port.hidden:
                    continue
                if port.is_input:
                    in_ports.append(port)
                if port.is_output:
                    out_ports.append(port)
            if in_ports:
                if not self.rtmidi:
                    clientItem = QtGui.QStandardItem(client.name)
                    clientItem.setData(u'<b>Client:</b> {c}<br/><b>Address:</b> {cid}'.format(c=client.name, cid=client.id), QtCore.Qt.ToolTipRole)
                    clientItem.setEnabled(False)
                for port in in_ports:
                    portItem = QtGui.QStandardItem(port.name)
                    portItem.setFlags(portFlags)
                    connected = any([True for conn in port.connections.input if conn.src == self.main.midiDevice.output])
                    setBold(portItem, connected)
                    if connected:
                        outConn += 1
                        portItem.setData(QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)
                    portItem.setData(u'<b>Client:</b> {c}<br/><b>Port:</b> {p}<br/><b>Address:</b> {cid}:{pid}'.format(
                        c=client.name, p=port.name, cid=client.id, pid=port.id), QtCore.Qt.ToolTipRole)
                    portItem.setData(port, PortRole)
                    if self.rtmidi:
                        self.outputModel.appendRow(portItem)
                    else:
                        clientItem.appendRow(portItem)
                if not self.rtmidi:
                    self.outputModel.appendRow(clientItem)
            if out_ports:
                if not self.rtmidi:
                    clientItem = QtGui.QStandardItem(client.name)
                    clientItem.setData(u'<b>Client:</b> {name}<br/><b>Address:</b> {id}'.format(name=client.name, id=client.id), QtCore.Qt.ToolTipRole)
                    clientItem.setEnabled(False)
                for port in out_ports:
                    portItem = QtGui.QStandardItem(port.name)
                    portItem.setFlags(portFlags)
                    connected = any([True for conn in port.connections.output if conn.dest == self.main.midiDevice.input])
                    setBold(portItem, connected)
                    if connected:
                        inConn += 1
                        portItem.setData(QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)
                    portItem.setData(u'<b>Client:</b> {c}<br/><b>Port:</b> {p}<br/><b>Address:</b> {cid}:{pid}'.format(
                        c=client.name, p=port.name, cid=client.id, pid=port.id), QtCore.Qt.ToolTipRole)
                    portItem.setData(port, PortRole)
                    if self.rtmidi:
                        self.inputModel.appendRow(portItem)
                    else:
                        clientItem.appendRow(portItem)
                if not self.rtmidi:
                    self.inputModel.appendRow(clientItem)
        self.inputTreeView.expandAll()
        self.outputTreeView.expandAll()

        self.inputModel.setHeaderData(0, QtCore.Qt.Horizontal, 'Input ({})'.format(inConn if inConn else 'not connected'))
        self.inputModel.setHeaderData(0, QtCore.Qt.Horizontal, QtCore.Qt.AlignCenter, QtCore.Qt.TextAlignmentRole)
        self.outputModel.setHeaderData(0, QtCore.Qt.Horizontal, 'Output ({})'.format(outConn if outConn else 'not connected'))
        self.outputModel.setHeaderData(0, QtCore.Qt.Horizontal, QtCore.Qt.AlignCenter, QtCore.Qt.TextAlignmentRole)

        self.inputTreeView.verticalScrollBar().setValue(inPos)
        self.outputTreeView.verticalScrollBar().setValue(outPos)

        self.inputModel.dataChanged.connect(self.toggleConnection)
        self.outputModel.dataChanged.connect(self.toggleConnection)
        if inConn <= 1 or self.hideAlert:
            self.infoLbl.setText('')
            self.infoIcon.setVisible(False)
        elif not self.infoLbl.text():
            self.infoLbl.setText('Be careful when connecting to more than one MIDI input, as some devices, programs or ' \
                'system utilities might duplicate events incoming from your Blofeld.')
            self.infoIcon.setVisible(True)
            if not self.infoIcon.pixmap():
                self.infoIcon.setPixmap(QtGui.QIcon.fromTheme('emblem-warning').pixmap(self.fontMetrics().height() * .8))

    def showEvent(self, event):
        if not self.shown:
            self.shown = True
            self.refresh()

