import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: root
    visible: true
    visibility: Window.Maximized
    minimumWidth: 900
    minimumHeight: 640
    title: "Manager Helper 1.1"
    color: appBg
    property color appBg: "#101720"
    property color surface: "#192431"
    property color elevated: "#233345"
    property color foreground: "#eaf1f8"
    property color secondary: "#98aabd"
    property color accent: "#79c7ff"
    property int page: 0
    property int boardId: 0
    property int folderId: 0
    property int selectedNote: 0
    property bool noteDirty: false
    property bool loadingNote: false
    function saveActiveNote() {
        if (selectedNote > 0 && noteDirty) {
            noteDirty = false
            workspace.saveNote(selectedNote, noteTitle.text, noteBody.text)
        }
    }
    function selectNote(note) {
        saveActiveNote()
        loadingNote = true
        selectedNote = note.id
        noteTitle.text = note.title
        noteBody.text = note.body
        noteDirty = false
        loadingNote = false
    }
    onClosing: saveActiveNote()
    Timer {
        id: noteSaveTimer
        interval: 750
        repeat: false
        onTriggered: root.saveActiveNote()
    }
    property int editTaskId: 0
    property int editLaneId: 0
    property int alarmTaskId: 0
    property var boardData: []
    property var laneData: []
    property var folderData: []
    property var noteData: []
    property var scheduleData: []

    function refresh() {
        boardData = workspace.boards()
        if (!boardId && boardData.length) boardId=boardData[0].id
        laneData=workspace.lanes(boardId)
        folderData=workspace.folders()
        if (!folderId && folderData.length) folderId=folderData[0].id
        noteData=workspace.notes(folderId)
        scheduleData=workspace.schedule()
    }
    function smokeCrud() {
        var b = root.boardData[0].id
        var before = workspace.lanes(b).length
        root.boardId = b
        root.promptMode = "lane"
        promptTitle.text = "SMOKE_TEST_LANE"
        promptDialog.open()
        promptDialog.accept()
        var after = workspace.lanes(b)
        if (after.length !== before + 1) throw new Error("Column dialog must create exactly one lane")
        var lane = after[after.length - 1]
        root.taskEditor(null, lane.id)
        taskTitle.text = "SMOKE_TEST_TASK"
        taskBody.text = "Smoke test"
        taskDue.text = ""
        taskDialog.accept()
        if (workspace.tasks(lane.id).length !== 1) throw new Error("Task dialog did not create exactly one task")
    }
    function deadlineText(raw) {
        if (!raw) return ""
        return raw.replace("T"," ").slice(5,16)
    }
    function taskEditor(task, lane) {
        editTaskId=task ? task.id : 0
        editLaneId=lane
        taskTitle.text=task ? task.title : ""
        taskBody.text=task ? task.body : ""
        taskTimer.checked=Boolean(task && task.due)
        taskDue.text=task && task.due ? task.due.replace("T"," ") : ""
        taskTelegram.text=task ? (task.telegram_url || "") : ""
        taskAccent.text=task ? (task.color || "") : ""
        taskDialog.open()
    }
    Component.onCompleted: {
        var settings=workspace.appearance()
        if (settings.background) appBg=settings.background
        if (settings.accent && settings.accent[0]==="#") accent=settings.accent
        bgInput.text=settings.background || "#0b111d"
        accentInput.text=settings.accent || "#6fc4ff"
        var d=settings.lane_defaults || {}
        defaultLaneBg.text=d.background || "#192535"
        defaultLaneFg.text=d.foreground || "#ecf2fb"
        defaultLaneAccent.text=d.accent || "#79b7e8"
        defaultLaneWidth.value=d.width || 320
        defaultLaneTimer.checked=d.timer === undefined ? true : d.timer
        refresh()
    }
    Connections {
        target: workspace
        function onChanged() { root.refresh() }
        function onAlarmRaised(taskId,title,due) {
            root.alarmTaskId=taskId
            alarmTitle.text=title
            alarmDue.text="Срок: "+due.replace("T"," ")
            alarmDialog.open()
            root.raise()
            root.requestActivate()
        }
    }

    component Panel: Rectangle {
        color: root.surface
        radius: 14
        border.color: "#304153"
        border.width: 1
    }
    component ActionButton: Button {
        id: button
        font.pixelSize: 13
        font.weight: Font.DemiBold
        palette.buttonText: root.foreground
        background: Rectangle {
            radius: 9
            color: button.down ? "#29465f" : button.hovered ? "#2a4157" : button.highlighted ? "#254158" : root.elevated
            border.color: button.hovered || button.highlighted ? root.accent : "#334b65"
        }
    }
    component TextField2: TextField {
        color: root.foreground
        placeholderTextColor: "#9bb0ca"
        selectionColor: root.accent
        font.pixelSize: 14
        background: Rectangle {
            color: "#223146"
            border.color: parent.activeFocus ? root.accent : "#3a4d63"
            radius: 9
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.preferredWidth: 220
            Layout.fillHeight: true
            color: "#131d28"
            border.color: "#2a3b4f"
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 13
                Label { text: "Manager Helper"; color: root.foreground; font.pixelSize: 21; font.bold: true }
                Label { text: "1.1"; color: root.secondary; font.pixelSize: 12 }
                Item { Layout.preferredHeight: 14 }
                Repeater {
                    model: ["Доски","Расписание","Блокнот","Оформление"]
                    delegate: ActionButton {
                        required property int index
                        required property string modelData
                        Layout.fillWidth: true
                        text: ["▦  ", "◷  ", "▤  ", "⚙  "][index] + modelData
                        highlighted: root.page===index
                        onClicked: root.page=index
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 24
            spacing: 16
            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: ["Рабочие доски","Расписание","Блокнот","Оформление"][root.page]
                    color: root.foreground; font.pixelSize: 27; font.weight: Font.DemiBold
                }
                Item { Layout.fillWidth: true }
                Label { text: Qt.formatDateTime(new Date(),"dd.MM.yyyy"); color: root.secondary; font.pixelSize: 13 }
            }
            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: root.page
                ColumnLayout {
                    spacing: 15
                    RowLayout {
                        spacing: 10
                        ComboBox {
                            id: boardPicker
                            Layout.preferredWidth: 300
                            model: root.boardData.map(function(b) { return b.name; })
                            currentIndex: root.boardData.findIndex(function(b){return b.id===root.boardId})
                            onActivated: function(i) { root.boardId=root.boardData[i].id; root.refresh() }
                        }
                        ActionButton { text: "+ Доска"; onClicked: { promptMode="board"; promptTitle.text=""; promptDialog.open() } }
                        ActionButton { text: "+ Колонка"; onClicked: { promptMode="lane"; promptTitle.text=""; promptDialog.open() } }
                        ActionButton {
                            text: "Удалить доску"
                            enabled: root.boardId > 0
                            onClicked: {
                                root.deleteBoardId = root.boardId
                                confirmDeleteBoard.open()
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Label { text: root.laneData.length+" колонок"; color: root.secondary }
                    }
                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        id: boardScroll
                        contentWidth: laneRow.implicitWidth
                        contentHeight: height
                        clip: true
                        Row {
                            id: laneRow
                            height: boardScroll.height
                            spacing: 14
                            Repeater {
                                model: root.laneData
                                delegate: Panel {
                                    id: lanePanel
                                    required property var modelData
                                    property var tasksData: []
                                    function loadTasks() {
                                        if (modelData && modelData.id) tasksData = workspace.tasks(modelData.id)
                                    }
                                    Component.onCompleted: loadTasks()
                                    onModelDataChanged: loadTasks()
                                    Connections {
                                        target: workspace
                                        function onChanged() { lanePanel.loadTasks() }
                                    }
                                    property real previewWidth: -1
                                     width: previewWidth >= 0 ? previewWidth : Math.max(250, Math.min(720, Number(modelData.width || 320)))
                                    height: Math.max(190, Math.min(boardScroll.height - 8, laneColumn.implicitHeight+24))
                                    color: modelData.bg_color || root.surface
                                    DropArea {
                                        anchors.fill: parent
                                        keys: ["manager-lane", "manager-task"]
                                        onDropped: function(drop) {
                                            if (!drop.source) return
                                            if (drop.source.laneId !== undefined)
                                                workspace.reorderLane(drop.source.laneId, lanePanel.modelData.id)
                                            else if (drop.source.taskId !== undefined)
                                                workspace.dropTask(drop.source.taskId, lanePanel.modelData.id, 0)
                                        }
                                    }
                                    Rectangle {
                                        id: resizeGrip
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.bottom: parent.bottom
                                        width: 9
                                        z: 20
                                        color: resizeMouse.pressed ? root.accent : "transparent"
                                        MouseArea {
                                            id: resizeMouse
                                            anchors.fill: parent
                                            cursorShape: Qt.SizeHorCursor
                                            property real startingWidth: 0
                                            property real startingX: 0
                                            onPressed: function(mouse) {
                                                startingWidth=lanePanel.width
                                                startingX=mapToItem(root.contentItem, mouse.x, mouse.y).x
                                            }
                                            onPositionChanged: function(mouse) {
                                                if (!pressed) return
                                                var x=mapToItem(root.contentItem, mouse.x, mouse.y).x
                                                lanePanel.previewWidth=Math.max(250,Math.min(720,startingWidth+x-startingX))
                                            }
                                            onReleased: {
                                                 var finalWidth = Math.round(lanePanel.width)
                                                 workspace.resizeLane(lanePanel.modelData.id, finalWidth)
                                                 lanePanel.previewWidth = -1
                                             }
                                             onCanceled: lanePanel.previewWidth = -1
                                        }
                                    }
                                    Column {
                                        id: laneColumn
                                        x: 12; y: 12; width: parent.width-24
                                        spacing: 9
                                        RowLayout {
                                            width: parent.width
                                            Rectangle {
                                                id: laneGrip
                                                width: 28; height: 28; radius: 7
                                                color: laneDrag.active ? "#416889" : "#293c54"
                                                property int laneId: lanePanel.modelData.id
                                                Drag.active: laneDrag.active
                                                Drag.source: laneGrip
                                                Drag.keys: ["manager-lane"]
                                                Drag.hotSpot.x: width / 2
                                                Drag.hotSpot.y: height / 2
                                                Label { anchors.centerIn: parent; text: "⠿"; color: root.foreground; font.pixelSize: 18 }
                                                DragHandler {
                                                    id: laneDrag
                                                    target: laneGrip
                                                    cursorShape: Qt.OpenHandCursor
                                                    onActiveChanged: {
                                                        if (!active) {
                                                            laneGrip.Drag.drop()
                                                            laneGrip.x = 0
                                                            laneGrip.y = 0
                                                        }
                                                    }
                                                }
                                            }
                                            Label {
                                                text: lanePanel.modelData.name
                                                color: lanePanel.modelData.text_color || root.foreground
                                                font.pixelSize: 15; font.bold: true
                                                Layout.fillWidth: true
                                                elide: Text.ElideRight
                                            }
                                            ActionButton {
                                                text: "···"
                                                onClicked: {
                                                    laneSettingsId=lanePanel.modelData.id
                                                    laneName.text=lanePanel.modelData.name
                                                    laneBackground.text=lanePanel.modelData.bg_color || ""
                                                    laneForeground.text=lanePanel.modelData.text_color || ""
                                                    laneAccent.text=lanePanel.modelData.color || ""
                                                    laneWidth.value=lanePanel.modelData.width || 320
                                                    laneTimer.checked=Boolean(lanePanel.modelData.timer_enabled)
                                                    laneSettings.open()
                                                }
                                            }
                                        }
                                        Repeater {
                                            model: lanePanel.tasksData
                                            delegate: Rectangle {
                                                id: taskCard
                                                required property var modelData
                                                property int taskId: modelData.id
                                                property bool overdue: workspace.isOverdue(modelData.due || "")
                                                 property bool wasDragged: false
                                                Drag.active: taskDrag.active
                                                Drag.source: taskCard
                                                Drag.keys: ["manager-task"]
                                                Drag.hotSpot.x: width / 2
                                                Drag.hotSpot.y: height / 2
                                                DragHandler {
                                                    id: taskDrag
                                                    target: taskCard
                                                    onActiveChanged: {
                                                        if (active) taskCard.wasDragged = true
                                                        else {
                                                            taskCard.Drag.drop()
                                                            taskCard.x = 0
                                                        }
                                                    }
                                                    acceptedButtons: Qt.LeftButton
                                                    grabPermissions: PointerHandler.CanTakeOverFromAnything
                                                }
                                                z: taskDrag.active ? 30 : 0
                                                DropArea {
                                                    anchors.fill: parent
                                                    keys: ["manager-task"]
                                                    onDropped: function(drop) {
                                                        if (drop.source && drop.source.taskId !== undefined)
                                                            workspace.dropTask(drop.source.taskId, lanePanel.modelData.id, taskCard.modelData.id)
                                                    }
                                                }
                                                width: laneColumn.width
                                                height: 64
                                                radius: 12
                                                color: modelData.bg_color || "#1e3046"
                                                border.color: taskCard.overdue ? "#d45b68" : "#34506d"
                                                Rectangle {
                                                    x: 0; y: 7; width: 4; height: parent.height-14
                                                    radius: 2
                                                    color: taskCard.overdue ? "#f17886" : (taskCard.modelData.color || root.accent)
                                                }
                                                RowLayout {
                                                    anchors.fill: parent
                                                    anchors.leftMargin: 15
                                                    anchors.rightMargin: taskCard.modelData.telegram_url ? 113 : 10
                                                    spacing: 8
                                                    Label {
                                                        Layout.fillWidth: true
                                                        text: taskCard.modelData.title
                                                        color: taskCard.modelData.text_color || root.foreground
                                                        font.pixelSize: 14
                                                        font.weight: Font.DemiBold
                                                        elide: Text.ElideRight
                                                    }
                                                    Label {
                                                        visible: Boolean(taskCard.modelData.due)
                                                        text: taskCard.overdue ? "⚠ Просрочено · " + root.deadlineText(taskCard.modelData.due) : root.deadlineText(taskCard.modelData.due)
                                                        color: taskCard.overdue ? "#ff9ca5" : (taskCard.modelData.text_color || root.secondary)
                                                        font.pixelSize: 11
                                                    }
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    anchors.rightMargin: taskCard.modelData.telegram_url ? 108 : 0
                                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                                    onPressed: taskCard.wasDragged = false
                                                    onClicked: function(mouse) {
                                                        if (taskCard.wasDragged) return
                                                        if (mouse.button===Qt.RightButton) {
                                                            root.editTaskId=taskCard.modelData.id
                                                            taskStyleBackground.text=taskCard.modelData.bg_color || ""
                                                            taskStyleForeground.text=taskCard.modelData.text_color || ""
                                                            taskStyleAccent.text=taskCard.modelData.color || ""
                                                            taskStyleTelegram.text=taskCard.modelData.telegram_url || ""
                                                            root.moveTaskBoardId = 0
                                                            root.moveTaskBoardId = root.boardId
                                                            root.moveTaskLaneId = taskCard.modelData.lane_id
                                                            taskStyle.open()
                                                        } else root.taskEditor(taskCard.modelData,lanePanel.modelData.id)
                                                    }
                                                }
                                                ActionButton {
                                                    visible: Boolean(taskCard.modelData.telegram_url)
                                                    text: "К задаче ↗"
                                                    width: 101
                                                    height: 34
                                                    anchors.right: parent.right
                                                    anchors.rightMargin: 9
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    onClicked: workspace.openTelegram(taskCard.modelData.telegram_url)
                                                }
                                            }
                                        }
                                        ActionButton {
                                            width: parent.width
                                            text: "+ Новая задача"
                                            onClicked: root.taskEditor(null,lanePanel.modelData.id)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                ColumnLayout {
                    spacing: 12
                    Label { text: "Все доски · просроченные, сегодня и два следующих дня"; color: root.secondary; font.pixelSize: 13 }
                    ListView {
                        Layout.fillWidth: true; Layout.fillHeight: true
                        clip: true; spacing: 9
                        model: root.scheduleData
                        delegate: Panel {
                            required property var modelData
                            width: ListView.view.width
                            height: 65
                            RowLayout {
                                anchors.fill: parent; anchors.margins: 14; spacing: 16
                                Label { text: root.deadlineText(modelData.due); color: root.accent; font.bold: true; Layout.preferredWidth: 105 }
                                Label { text: modelData.title; color: root.foreground; Layout.fillWidth: true; elide: Text.ElideRight }
                                Label { text: modelData.board_name+" / "+modelData.lane_name; color: root.secondary; font.pixelSize: 12 }
                            }
                            MouseArea { anchors.fill: parent; onClicked: root.taskEditor(modelData,modelData.lane_id) }
                        }
                    }
                }
                RowLayout {
                    spacing: 14
                    Panel {
                        Layout.preferredWidth: 245
                        Layout.fillHeight: true
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 12
                            Label { text: "ПАПКИ"; color: root.secondary; font.bold: true }
                            ListView {
                                Layout.fillWidth: true; Layout.fillHeight: true
                                model: root.folderData
                                delegate: ActionButton {
                                    required property var modelData
                                    width: ListView.view.width
                                    text: modelData.name
                                    onClicked: {
                                        root.saveActiveNote()
                                        noteSaveTimer.stop()
                                        root.loadingNote = true
                                        root.selectedNote = 0
                                        root.noteDirty = false
                                        noteTitle.text = ""
                                        noteBody.text = ""
                                        root.folderId = modelData.id
                                        root.noteData = workspace.notes(root.folderId)
                                        root.loadingNote = false
                                    }
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                ActionButton {
                                    text: "+ Папка"
                                    Layout.fillWidth: true
                                    onClicked: { promptMode="folder"; promptTitle.text=""; promptDialog.open() }
                                }
                                ActionButton {
                                    text: "Удалить папку"
                                    enabled: root.folderId > 0
                                    onClicked: {
                                        root.deleteFolderId = root.folderId
                                        confirmDeleteFolder.open()
                                    }
                                }
                            }
                        }
                    }
                    Panel {
                        Layout.preferredWidth: 260
                        Layout.fillHeight: true
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 12
                            Label { text: "ЗАПИСИ"; color: root.secondary; font.bold: true }
                            ListView {
                                Layout.fillWidth: true; Layout.fillHeight: true
                                model: root.noteData
                                delegate: ActionButton {
                                    required property var modelData
                                    width: ListView.view.width
                                    text: modelData.title
                                    onClicked: {
                                        root.selectNote(modelData)
                                    }
                                }
                            }
                            ActionButton {
                                text: "+ Запись"
                                enabled: root.folderId > 0
                                onClicked: {
                                    root.saveActiveNote()
                                    var newId = workspace.addNote(root.folderId,"Новая запись","")
                                    root.selectNote(workspace.note(newId))
                                }
                            }
                        }
                    }
                    Panel {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 16; spacing: 12
                            TextField2 {
                                id: noteTitle
                                Layout.fillWidth: true
                                placeholderText: "Название записи"
                                onTextEdited: {
                                    if (!root.loadingNote && root.selectedNote > 0) {
                                        root.noteDirty = true
                                        noteSaveTimer.restart()
                                    }
                                }
                            }
                            TextArea {
                                id: noteBody
                                onTextChanged: {
                                    if (!root.loadingNote && root.selectedNote > 0) {
                                        root.noteDirty = true
                                        noteSaveTimer.restart()
                                    }
                                }
                                Layout.fillWidth: true; Layout.fillHeight: true
                                wrapMode: TextEdit.Wrap
                                color: root.foreground
                                font.pixelSize: 14
                                background: Rectangle { color: "#223146"; radius: 10 }
                            }
                            RowLayout {
                                ActionButton { text: "Сохранить"; enabled: root.selectedNote>0; onClicked: { root.noteDirty = true; root.saveActiveNote() } }
                                ActionButton { text: "Удалить"; enabled: root.selectedNote>0; onClicked: {
                                    noteSaveTimer.stop()
                                    root.noteDirty = false
                                    root.loadingNote = true
                                    workspace.deleteNote(root.selectedNote)
                                    root.selectedNote = 0
                                    noteTitle.text = ""
                                    noteBody.text = ""
                                    root.loadingNote = false
                                } }
                            }
                        }
                    }
                }
                Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 24
                        clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        ColumnLayout {
                            width: Math.min(760, Math.max(580, parent.width - 18))
                            spacing: 18
                            Label { text: "Персонализация"; color: root.foreground; font.pixelSize: 22; font.bold: true }
                            Label {
                                text: "Выбирай цвета нажатием на образцы — коды вводить необязательно."
                                color: root.secondary; Layout.fillWidth: true; wrapMode: Text.WordWrap
                            }
                            Rectangle { Layout.fillWidth: true; height: 1; color: "#30435d" }
                            Label { text: "Цветовая тема"; color: root.foreground; font.pixelSize: 18; font.bold: true }
                            RowLayout {
                                spacing: 10
                                ActionButton { text: "Ночной синий"; onClicked: { bgInput.text="#0b111d"; accentInput.text="#6fc4ff" } }
                                ActionButton { text: "Графит"; onClicked: { bgInput.text="#161a21"; accentInput.text="#9bafff" } }
                                ActionButton { text: "Изумруд"; onClicked: { bgInput.text="#0e1b1b"; accentInput.text="#55c5ad" } }
                            }
                            Label { text: "Фон приложения"; color: root.secondary }
                            ColorPicker { id: bgInput; Layout.fillWidth: true; placeholderText: "#0b111d" }
                            Label { text: "Основной акцент"; color: root.secondary }
                            ColorPicker { id: accentInput; Layout.fillWidth: true; placeholderText: "#6fc4ff" }
                            Rectangle { Layout.fillWidth: true; height: 1; color: "#30435d"; Layout.topMargin: 12 }
                            Label { text: "Новые колонки"; color: root.foreground; font.pixelSize: 18; font.bold: true }
                            Label {
                                text: "Настройки применятся только к новым колонкам. Существующие останутся без изменений."
                                color: root.secondary; Layout.fillWidth: true; wrapMode: Text.WordWrap
                            }
                            Label { text: "Фон колонки"; color: root.secondary }
                            ColorPicker { id: defaultLaneBg; Layout.fillWidth: true; placeholderText: "#192535" }
                            Label { text: "Цвет текста"; color: root.secondary }
                            ColorPicker { id: defaultLaneFg; Layout.fillWidth: true; placeholderText: "#ecf2fb" }
                            Label { text: "Цветовой маркер"; color: root.secondary }
                            ColorPicker { id: defaultLaneAccent; Layout.fillWidth: true; placeholderText: "#79b7e8" }
                            Label { text: "Ширина новой колонки"; color: root.secondary }
                            RowLayout {
                                Layout.fillWidth: true
                                Slider { id: defaultLaneWidth; from: 250; to: 720; stepSize: 10; Layout.fillWidth: true }
                                Label { text: Math.round(defaultLaneWidth.value) + " px"; color: root.foreground; Layout.preferredWidth: 72 }
                            }
                            CheckBox { id: defaultLaneTimer; text: "Включать контроль сроков"; checked: true; palette.text: root.foreground }
                            Rectangle { Layout.fillWidth: true; height: 1; color: "#30435d"; Layout.topMargin: 12 }
                            Label { id: appearanceError; visible: text.length > 0; color: "#ff9b9b"; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                            RowLayout {
                                Layout.fillWidth: true
                                ActionButton {
                                    text: "Сбросить"
                                    onClicked: {
                                        bgInput.text="#0b111d"; accentInput.text="#6fc4ff"
                                        defaultLaneBg.text="#192535"; defaultLaneFg.text="#ecf2fb"
                                        defaultLaneAccent.text="#79b7e8"; defaultLaneWidth.value=320
                                        defaultLaneTimer.checked=true
                                    }
                                }
                                Item { Layout.fillWidth: true }
                                ActionButton {
                                    text: "Сохранить настройки"
                                    highlighted: true
                                    onClicked: {
                                        var colors=[bgInput.text,accentInput.text,defaultLaneBg.text,defaultLaneFg.text,defaultLaneAccent.text]
                                        if (!colors.every(function(c){ return /^#[0-9a-fA-F]{6}$/.test(c) })) {
                                            appearanceError.text="Проверь цвета: выбери образец или введи код #RRGGBB."
                                            return
                                        }
                                        appearanceError.text=""
                                        root.appBg=bgInput.text; root.accent=accentInput.text
                                        workspace.saveAppearance(bgInput.text,accentInput.text)
                                        workspace.saveLaneDefaults(defaultLaneBg.text,defaultLaneFg.text,defaultLaneAccent.text,
                                                                   Math.round(defaultLaneWidth.value),defaultLaneTimer.checked)
                                    }
                                }
                            }
                            Item { Layout.preferredHeight: 24 }
                        }
                    }
                }
            }
        }
    }

    property string promptMode: "board"
    property int laneSettingsId: 0
    property int deleteLaneId: 0
    property int deleteBoardId: 0
    property int deleteTaskId: 0
    property int moveTaskBoardId: 0
    property int moveTaskLaneId: 0
    property int deleteFolderId: 0
    StyledDialog {
        id: promptDialog; title: "Создать"; modal: true; anchors.centerIn: parent
        canSubmit: promptTitle.text.trim().length > 0
        width: 400; standardButtons: Dialog.Ok | Dialog.Cancel
        ColumnLayout { anchors.fill: parent; TextField2 { id: promptTitle; Layout.fillWidth: true; placeholderText: "Название" } }
        onAccepted: {
            if (root.promptMode==="board") workspace.addBoard(promptTitle.text)
            else if (root.promptMode==="lane") workspace.addLane(root.boardId,promptTitle.text)
            else if (root.promptMode==="folder") workspace.addFolder(promptTitle.text)
        }
    }
    StyledDialog {
        id: confirmDeleteFolder
        title: "Удалить папку?"
        modal: true
        anchors.centerIn: parent
        width: 430
        standardButtons: Dialog.Ok | Dialog.Cancel
        confirmLabel: "Удалить"
        Label {
            width: 370
            wrapMode: Text.WordWrap
            color: root.foreground
            text: "Папка и все записи в ней будут удалены без возможности отмены. Продолжить?"
        }
        onAccepted: {
            if (root.deleteFolderId <= 0) return
            root.saveActiveNote()
            noteSaveTimer.stop()
            root.loadingNote = true
            root.noteDirty = false
            root.selectedNote = 0
            noteTitle.text = ""
            noteBody.text = ""
            workspace.deleteFolder(root.deleteFolderId)
            root.folderId = 0
            root.refresh()
            root.loadingNote = false
            root.deleteFolderId = 0
        }
    }
    StyledDialog {
        id: taskDialog
        title: root.editTaskId ? "Редактировать задачу" : "Новая задача"
        canSubmit: taskTitle.text.trim().length > 0
                   && (!taskTimer.checked || workspace.validDue(taskDue.text) && taskDue.text.trim().length > 0)
                   && workspace.validTelegram(taskTelegram.text)
        modal: true
        anchors.centerIn: parent
        width: 550
        standardButtons: Dialog.Save | Dialog.Cancel
        ColumnLayout {
            anchors.fill: parent
            spacing: 11
            Label { text: "Название задачи"; color: root.secondary }
            TextField2 { id: taskTitle; Layout.fillWidth: true; placeholderText: "Что нужно сделать?" }
            Label { text: "Описание"; color: root.secondary }
            TextArea {
                id: taskBody
                Layout.fillWidth: true
                Layout.preferredHeight: 190
                color: root.foreground
                wrapMode: TextEdit.Wrap
                placeholderTextColor: "#9bb0ca"
                font.pixelSize: 14
                placeholderText: "Детали задачи (необязательно)"
                background: Rectangle { color: "#223146"; radius: 9 }
            }
            Label { text: "Ссылка на Telegram"; color: root.secondary }
            TextField2 {
                id: taskTelegram
                Layout.fillWidth: true
                placeholderText: "https://t.me/username/123"
            }
            Label {
                visible: !workspace.validTelegram(taskTelegram.text)
                text: "Укажи ссылку t.me или tg://"
                color: "#ff8999"
            }
            CheckBox {
                id: taskTimer
                text: "Поставить таймер"
                checked: false
                onToggled: {
                    if (checked && !taskDue.text.trim())
                        taskDue.text = workspace.defaultTaskDue()
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                visible: taskTimer.checked
                spacing: 5
                Label { text: "Срок выполнения · по умолчанию через 2 часа"; color: root.secondary }
                TextField2 {
                    id: taskDue
                    Layout.fillWidth: true
                    placeholderText: "ГГГГ-ММ-ДД ЧЧ:ММ"
                }
                Label {
                    visible: !workspace.validDue(taskDue.text) || !taskDue.text.trim()
                    text: "Укажи дату и время: ГГГГ-ММ-ДД ЧЧ:ММ"
                    color: "#ff8999"
                }
            }
            Label { text: "Цветовой маркер"; color: root.secondary }
            ColorPicker { id: taskAccent; Layout.fillWidth: true; placeholderText: "#79b7e8" }
            ActionButton {
                text: "Удалить задачу навсегда"
                visible: root.editTaskId > 0
                Layout.fillWidth: true
                onClicked: {
                    root.deleteTaskId = root.editTaskId
                    taskDialog.close()
                    confirmDeleteTask.open()
                }
            }
        }
        onAccepted: {
            var due = taskTimer.checked ? taskDue.text.trim().replace(" ","T") : ""
            if (root.editTaskId)
                workspace.saveTaskDetails(root.editTaskId,taskTitle.text,taskBody.text,due,taskAccent.text,taskTelegram.text)
            else
                workspace.addTaskDetails(root.editLaneId,taskTitle.text,taskBody.text,due,taskAccent.text,taskTelegram.text)
        }
    }
    StyledDialog {
        id: laneSettings; title: "Настройки колонки"; modal: true; anchors.centerIn: parent; width: 440
        canSubmit: laneName.text.trim().length > 0
        standardButtons: Dialog.Save | Dialog.Cancel
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            Label { text: "Название колонки"; color: root.secondary }
            TextField2 { id: laneName; Layout.fillWidth: true; placeholderText: "Название колонки" }
            Label { text: "Фон колонки — нажми на цвет"; color: root.secondary }
            ColorPicker { id: laneBackground; Layout.fillWidth: true; placeholderText: "#192535" }
            Label { text: "Цвет текста"; color: root.secondary }
            ColorPicker { id: laneForeground; Layout.fillWidth: true; placeholderText: "#ecf2fb" }
            Label { text: "Цветовой маркер"; color: root.secondary }
            ColorPicker { id: laneAccent; Layout.fillWidth: true; placeholderText: "#79b7e8" }
            Label { text: "Ширина колонки"; color: root.secondary }
            Slider { id: laneWidth; from: 250; to: 720; stepSize: 10; Layout.fillWidth: true }
            Label { text: Math.round(laneWidth.value)+" px"; color: root.foreground }
            CheckBox { id: laneTimer; text: "Контролировать таймеры этой колонки"; checked: true }
            ActionButton {
                text: "Удалить колонку и задачи"
                onClicked: {
                    root.deleteLaneId = root.laneSettingsId
                    laneSettings.close()
                    confirmDeleteLane.open()
                }
            }
        }
        onAccepted: {
            workspace.renameLane(root.laneSettingsId, laneName.text)
            workspace.styleLane(root.laneSettingsId,laneBackground.text,laneForeground.text,laneAccent.text,Math.round(laneWidth.value))
            workspace.timerLane(root.laneSettingsId,laneTimer.checked)
        }
    }
    StyledDialog {
        id: confirmDeleteBoard
        confirmLabel: "Удалить"
        title: "Удалить доску со всеми колонками?"
        modal: true
        anchors.centerIn: parent
        width: 440
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label {
            width: 370
            color: root.foreground
            wrapMode: Text.WordWrap
            text: "Будут удалены все колонки и задачи этой доски (" +
                  workspace.boardTaskCount(root.deleteBoardId) +
                  " задач). Отменить удаление нельзя."
        }
        onAccepted: {
            if (workspace.deleteBoard(root.deleteBoardId)) {
                root.boardId = 0
                root.refresh()
            }
            root.deleteBoardId = 0
        }
    }
    StyledDialog {
        id: confirmDeleteLane
        confirmLabel: "Удалить"
        title: "Удалить колонку со всеми задачами?"
        modal: true
        anchors.centerIn: parent
        width: 420
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label {
            text: "В колонке задач: " + workspace.laneTaskCount(root.deleteLaneId) + ". Колонка и все её задачи будут удалены без возможности отмены."
            width: 350
            color: root.foreground
            wrapMode: Text.WordWrap
        }
        onAccepted: workspace.deleteLane(root.deleteLaneId)
    }
    StyledDialog {
        id: taskStyle; title: "Настройки карточки"; modal: true; anchors.centerIn: parent; width: 430
        standardButtons: Dialog.Save | Dialog.Cancel
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            Label { text: "Фон карточки"; color: root.secondary }
            ColorPicker { id: taskStyleBackground; Layout.fillWidth: true; placeholderText: "#25364a" }
            Label { text: "Цвет текста"; color: root.secondary }
            ColorPicker { id: taskStyleForeground; Layout.fillWidth: true; placeholderText: "#ecf2fb" }
            Label { text: "Цветовой маркер"; color: root.secondary }
            ColorPicker { id: taskStyleAccent; Layout.fillWidth: true; placeholderText: "#79b7e8" }
            Label { text: "Ссылка Telegram на сообщение или чат"; color: root.secondary }
            TextField2 { id: taskStyleTelegram; Layout.fillWidth: true; placeholderText: "https://t.me/c/123456789/42" }
            Label { text: "На карточке появится кнопка «К задаче». Пустое поле убирает кнопку."; color: root.secondary; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Label { text: "Переместить задачу"; color: root.secondary }
            Label { text: "Доска"; color: root.secondary }
            ComboBox {
                id: moveTaskBoard
                Layout.fillWidth: true
                model: root.boardData.map(function(b) { return b.name })
                currentIndex: root.boardData.findIndex(function(b) { return b.id === root.moveTaskBoardId })
                onActivated: function(i) {
                    root.moveTaskBoardId = root.boardData[i].id
                    root.moveTaskLaneId = 0
                }
            }
            Label { text: "Колонка"; color: root.secondary }
            ComboBox {
                id: moveTaskLane
                Layout.fillWidth: true
                property var destinationLanes: workspace.lanes(root.moveTaskBoardId)
                model: destinationLanes.map(function(l) { return l.name })
                currentIndex: destinationLanes.findIndex(function(l) { return l.id === root.moveTaskLaneId })
                onActivated: function(i) { root.moveTaskLaneId = destinationLanes[i].id }
            }
            Label {
                visible: moveTaskLane.destinationLanes.length === 0
                text: "На выбранной доске нет колонок."
                color: "#ff9ca5"
            }
            RowLayout {
                Layout.fillWidth: true
                ActionButton {
                    text: "Изменить текст задачи"
                    Layout.fillWidth: true
                    onClicked: {
                        var task = workspace.task(root.editTaskId)
                        taskStyle.close()
                        root.taskEditor(task, task.lane_id)
                    }
                }
                ActionButton {
                    text: "Удалить задачу навсегда"
                    Layout.fillWidth: true
                    onClicked: {
                        root.deleteTaskId = root.editTaskId
                        taskStyle.close()
                        confirmDeleteTask.open()
                    }
                }
            }
        }
        onAccepted: {
            workspace.configureTask(root.editTaskId,taskStyleBackground.text,taskStyleForeground.text,taskStyleAccent.text,taskStyleTelegram.text)
            if (root.moveTaskLaneId > 0)
                workspace.moveTaskToLane(root.editTaskId, root.moveTaskLaneId)
        }
    }
    StyledDialog {
        id: confirmDeleteTask
        confirmLabel: "Удалить"
        title: "Удалить задачу?"
        modal: true
        anchors.centerIn: parent
        width: 430
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label {
            text: "Задача будет удалена из колонки. Отменить это действие нельзя."
            width: 360
            color: root.foreground
            wrapMode: Text.WordWrap
        }
        onAccepted: workspace.deleteTask(root.deleteTaskId)
    }
    StyledDialog {
        id: alarmDialog; title: "MANAGER HELPER / ТАЙМ-ЛИМИТ"; modal: true
        closePolicy: Popup.NoAutoClose
        anchors.centerIn: parent; width: 490
        ColumnLayout {
            anchors.fill: parent; spacing: 18
            Label { text: "ВРЕМЯ ЗАДАЧИ ИСТЕКЛО"; color: "#e8a07c"; font.pixelSize: 19; font.bold: true }
            Label { id: alarmTitle; color: root.foreground; font.pixelSize: 18; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Label { id: alarmDue; color: root.secondary }
            RowLayout {
                ActionButton { text: "Выполнено"; onClicked: { workspace.resolveAlarm(root.alarmTaskId,"done");alarmDialog.close() } }
                ActionButton { text: "Отложить 15 мин"; onClicked: { workspace.resolveAlarm(root.alarmTaskId,"snooze");alarmDialog.close() } }
                ActionButton { text: "Открыть"; onClicked: { workspace.resolveAlarm(root.alarmTaskId,"open");alarmDialog.close();root.taskEditor(workspace.task(root.alarmTaskId),0) } }
            }
        }
    }
}
