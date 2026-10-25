# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5 import QtWidgets
from pyqtgraph.Qt import QtCore, QtGui

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *


def is_class(o):
    return hasattr(o, '__dict__')

class ClassVariablesGuiEditor():
    class DynamicItem():
        def __init__(self, name, label, convertFunc, varStoragePtr):
            self._name = name
            self._label = label
            self._layout = None
            self._convertFunc = convertFunc

            self._editWg = None

            self._varStoragePtr = varStoragePtr

            self._createLayout()

        def _createLayout(self):
            self._layout = QHBoxLayout()
            label = QLabel(self._label)
            self._editWg = QLineEdit()
            self._layout.addWidget(label)
            self._layout.addWidget(self._editWg)
            val = getattr(self._varStoragePtr, self._name)
            self._editWg.setText(str(val))

            def onTextChanged(txt):
                try:
                    value = self._convertFunc(txt)
                    setattr(self._varStoragePtr, self._name, value)
                except:
                    pass

            self._editWg.textChanged.connect(onTextChanged)

        def getLayout(self):
            return self._layout

    # NOTE: we do not store anything iside the class, but let it be
    # the class method insted of just functin (perhaps we will need it in the future)

    def createControls(self, cls, title, layout):
        box = QGroupBox(title)
        layout.addWidget(box)
        
        insideLayout = QHBoxLayout()
        box.setLayout(insideLayout)

        varsLayout = QVBoxLayout()
        insideLayout.addLayout(varsLayout)
        

        objsLayout = QHBoxLayout()
        insideLayout.addLayout(objsLayout)
       
                
        for attr in dir(cls):
            if attr.startswith("__"):
                continue
            if attr.startswith("_"):
                continue

            val = getattr(cls, attr)
            if callable(val):
                continue

            if isinstance(val, list):
                listItemsLayout = QVBoxLayout()
                itemBox = QGroupBox(attr)
                itemBox.setLayout(listItemsLayout)
                objsLayout.addWidget(itemBox)
                for itemId in range(len(val)):
                    item = val[itemId]
                    title = str(itemId+1)
                    self.createControls(item, title, listItemsLayout)

                continue

            if is_class(val):
                self.createControls(val, attr, objsLayout)
                continue

            #print(attr + "->" + str(val))
            item = self.DynamicItem(attr, attr, type(val), cls)
            varsLayout.addLayout(item.getLayout())
