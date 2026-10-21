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
    title: "MANAGER HELPER // 1.1"
    color: appBg
    property color appBg: "#0b111d"
    property color surface: "#141f30"
    property color elevated: "#1e3048"
    property color foreground: "#f0f5ff"
    property color secondary: "#899db9"
    property color accent: "#6fc4ff"
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
        taskDue.text=task && task.due ? task.due.replace("T"," ") : ""
        taskAccent.text=task ? (task.color || "") : ""
        taskDialog.open()
    }
    Component.onCompleted: {
        var settings=workspace.appearance()
        if (settings.background) appBg=settings.background
        if (settings.accent && settings.accent[0]==="#") accent=settings.accent
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
        radius: 18
        border.color: "#293a53"
        border.width: 1
    }
    component ActionButton: Button {
        id: button
        font.pixelSize: 13
        font.weight: Font.DemiBold
        palette.buttonText: root.foreground
        background: Rectangle {
            radius: 11
            color: button.down ? "#2c5675" : button.hovered ? "#29435f" : button.highlighted ? "#234764" : root.elevated
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
            Layout.preferredWidth: 238
            Layout.fillHeight: true
            color: "#0f1929"
            border.color: "#2a3b4f"
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 13
                Label { text: "MANAGER"; color: root.foreground; font.pixelSize: 24; font.bold: true }
                Label { text: "HELPER  /  v1.1"; color: root.accent; font.pixelSize: 13; font.bold: true }
                Label { text: "PERSONAL WORKSPACE"; color: root.secondary; font.pixelSize: 10; font.letterSpacing: 1 }
                Item { Layout.preferredHeight: 14 }
                Repeater {
                    model: ["Доски","Расписание","Блокнот","Оформление"]
                    delegate: ActionButton {
                        required property int index
                        required property string modelData
                        Layout.fillWidth: true
                        text: modelData
                        highlighted: root.page===index
                        onClicked: root.page=index
                    }
                }
                Item { Layout.fillHeight: true }
                Label { text: "ЛОКАЛЬНЫЕ ДАННЫЕ"; color: root.secondary; font.pixelSize: 10 }
                Label { text: "SQLite · без облака"; color: root.secondary; font.pixelSize: 12 }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 28
            spacing: 16
            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: ["Рабочие доски","Расписание","Блокнот","Оформление"][root.page]
                    color: root.foreground; font.pixelSize: 30; font.weight: Font.DemiBold
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
                            spacing: 18
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
                                    width: Math.max(270,Math.min(600,Math.max(modelData.width || 320, (boardScroll.width - 18 * Math.max(0,root.laneData.length-1)) / Math.max(1,root.laneData.length))))
                                    height: Math.max(190, Math.min(boardScroll.height - 8, laneColumn.implicitHeight+24))
                                    color: modelData.bg_color || root.surface
                                    Column {
                                        id: laneColumn
                                        x: 12; y: 12; width: parent.width-24
                                        spacing: 9
                                        RowLayout {
                                            width: parent.width
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
                                                width: laneColumn.width
                                                height: 72
                                                radius: 12
                                                color: modelData.bg_color || "#1e3046"
                                                border.color: "#34506d"
                                                Rectangle {
                                                    x: 0; y: 7; width: 4; height: parent.height-14
                                                    radius: 2
                                                    color: taskCard.modelData.color || root.accent
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
                                                        text: root.deadlineText(taskCard.modelData.due)
                                                        color: taskCard.modelData.text_color || root.secondary
                                                        font.pixelSize: 11
                                                    }
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    anchors.rightMargin: taskCard.modelData.telegram_url ? 108 : 0
                                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                                    onClicked: function(mouse) {
                                                        if (mouse.button===Qt.RightButton) {
                                                            root.editTaskId=taskCard.modelData.id
                                                            taskStyleBackground.text=taskCard.modelData.bg_color || ""
                                                            taskStyleForeground.text=taskCard.modelData.text_color || ""
                                                            taskStyleAccent.text=taskCard.modelData.color || ""
                                                            taskStyleTelegram.text=taskCard.modelData.telegram_url || ""
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
                                    onClicked: { root.folderId=modelData.id; root.noteData=workspace.notes(root.folderId) }
                                }
                            }
                            ActionButton { text: "+ Папка"; onClicked: { promptMode="folder";promptTitle.text="";promptDialog.open() } }
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
                                ActionButton { text: "Удалить"; enabled: root.selectedNote>0; onClicked: { workspace.deleteNote(root.selectedNote);root.selectedNote=0;noteTitle.text="";noteBody.text="" } }
                            }
                        }
                    }
                }
                Panel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    ColumnLayout {
                        anchors.margins: 24; anchors.fill: parent; spacing: 16
                        Label { text: "Внешний вид рабочего пространства"; color: root.foreground; font.pixelSize: 20 }
                        Label { text: "Цвета вводятся в формате #RRGGBB. Отдельные цвета колонок и задач задаются в их меню."; color: root.secondary; wrapMode: Text.WordWrap }
                        Label { text: "Фон приложения"; color: root.secondary }
                        TextField2 { id: bgInput; text: root.appBg.toString(); Layout.preferredWidth: 240 }
                        Label { text: "Основной акцент"; color: root.secondary }
                        TextField2 { id: accentInput; text: root.accent.toString(); Layout.preferredWidth: 240 }
                        ActionButton {
                            text: "Применить"
                            onClicked: {
                                if (/^#[0-9a-fA-F]{6}$/.test(bgInput.text) && /^#[0-9a-fA-F]{6}$/.test(accentInput.text)) {
                                    root.appBg=bgInput.text;root.accent=accentInput.text
                                    workspace.saveAppearance(bgInput.text,accentInput.text)
                                }
                            }
                        }
                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }

    property string promptMode: "board"
    property int laneSettingsId: 0
    property int deleteLaneId: 0
    property int deleteTaskId: 0
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
        id: taskDialog; title: root.editTaskId ? "Редактировать задачу" : "Новая задача"
        canSubmit: taskTitle.text.trim().length > 0 && workspace.validDue(taskDue.text)
        modal: true; anchors.centerIn: parent; width: 550
        standardButtons: Dialog.Save | Dialog.Cancel
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            TextField2 { id: taskTitle; Layout.fillWidth: true; placeholderText: "Название" }
            TextArea {
                id: taskBody; Layout.fillWidth: true; Layout.preferredHeight: 110
                color: root.foreground; wrapMode: TextEdit.Wrap
                placeholderTextColor: "#9bb0ca"
                font.pixelSize: 14
                placeholderText: "Описание"
                background: Rectangle { color: "#223146"; radius: 9 }
            }
            Label { text: "Дедлайн: ГГГГ-ММ-ДД ЧЧ:ММ (пусто — без срока)"; color: root.secondary }
            TextField2 { id: taskDue; Layout.fillWidth: true; placeholderText: "2026-10-20 14:00" }
            Label { visible: !workspace.validDue(taskDue.text); text: "Проверь дату: ГГГГ-ММ-ДД ЧЧ:ММ"; color: "#ff8999" }
            Label { text: "Цветовой маркер (#RRGGBB)"; color: root.secondary }
            ColorPicker { id: taskAccent; Layout.fillWidth: true; placeholderText: "#79b7e8" }
            ActionButton {
                text: "Удалить эту задачу"
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
            var due=taskDue.text.trim().replace(" ","T")
            if (root.editTaskId) workspace.saveTask(root.editTaskId,taskTitle.text,taskBody.text,due,taskAccent.text)
            else workspace.addTask(root.editLaneId,taskTitle.text,taskBody.text,due,taskAccent.text)
        }
    }
    StyledDialog {
        id: laneSettings; title: "Оформление колонки"; modal: true; anchors.centerIn: parent; width: 440
        standardButtons: Dialog.Save | Dialog.Cancel
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            Label { text: "Фон колонки"; color: root.secondary }
            ColorPicker { id: laneBackground; Layout.fillWidth: true; placeholderText: "#192535" }
            Label { text: "Цвет текста"; color: root.secondary }
            ColorPicker { id: laneForeground; Layout.fillWidth: true; placeholderText: "#ecf2fb" }
            Label { text: "Цветовой маркер"; color: root.secondary }
            ColorPicker { id: laneAccent; Layout.fillWidth: true; placeholderText: "#79b7e8" }
            Label { text: "Ширина колонки"; color: root.secondary }
            Slider { id: laneWidth; from: 250; to: 600; stepSize: 10; Layout.fillWidth: true }
            Label { text: Math.round(laneWidth.value)+" px"; color: root.foreground }
            CheckBox { id: laneTimer; text: "Контролировать таймеры этой колонки"; checked: true }
            ActionButton {
                text: "Удалить пустую колонку"
                onClicked: {
                    root.deleteLaneId = root.laneSettingsId
                    laneSettings.close()
                    confirmDeleteLane.open()
                }
            }
        }
        onAccepted: {
            workspace.styleLane(root.laneSettingsId,laneBackground.text,laneForeground.text,laneAccent.text,Math.round(laneWidth.value))
            workspace.timerLane(root.laneSettingsId,laneTimer.checked)
        }
    }
    StyledDialog {
        id: confirmDeleteLane
        title: "Удалить колонку?"
        modal: true
        anchors.centerIn: parent
        width: 420
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label {
            text: "Удаляются только пустые колонки. Если внутри есть задачи, удаление будет отклонено."
            width: 350
            color: root.foreground
            wrapMode: Text.WordWrap
        }
        onAccepted: workspace.deleteEmptyLane(root.deleteLaneId)
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
            RowLayout {
                Layout.fillWidth: true
                ActionButton {
                    text: "Переименовать / изменить"
                    Layout.fillWidth: true
                    onClicked: {
                        var task = workspace.task(root.editTaskId)
                        taskStyle.close()
                        root.taskEditor(task, task.lane_id)
                    }
                }
                ActionButton {
                    text: "Удалить задачу"
                    Layout.fillWidth: true
                    onClicked: {
                        root.deleteTaskId = root.editTaskId
                        taskStyle.close()
                        confirmDeleteTask.open()
                    }
                }
            }
        }
        onAccepted: workspace.configureTask(root.editTaskId,taskStyleBackground.text,taskStyleForeground.text,taskStyleAccent.text,taskStyleTelegram.text)
    }
    StyledDialog {
        id: confirmDeleteTask
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
